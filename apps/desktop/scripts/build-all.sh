#!/usr/bin/env bash
# Video Helper Desktop — Full release build (macOS/Linux)
#
# Rough equivalents of apps/desktop/scripts/build-all.ps1 (Windows).
# Steps:
#   1) Compile Electron main process (TypeScript)
#   2) Build Next.js frontend (standalone) + hydrate node_modules
#   3) Package FastAPI backend (PyInstaller)
#   4) Build Electron installer (electron-builder)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
DESKTOP_DIR="$ROOT_DIR/apps/desktop"
WEB_DIR="$ROOT_DIR/apps/web"
CORE_DIR="$ROOT_DIR/services/core"

API_BASE_URL_DEFAULT="http://127.0.0.1:8000"
API_BASE_URL="${API_BASE_URL:-$API_BASE_URL_DEFAULT}"
NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-$API_BASE_URL}"

step() {
  echo
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Step $1: $2"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: '$1' not found. $2" >&2
    exit 1
  }
}

now_ts() {
  date +%Y%m%d-%H%M%S
}

list_procs_by_cmd_substr() {
  # Print pids whose command line contains the given substring (best-effort).
  # Works on macOS/Linux.
  local needle="$1"
  ps -ax -o pid= -o command= 2>/dev/null | awk -v n="$needle" 'index($0, n) > 0 { print $1 }' | tr -d ' '
}

kill_pids() {
  # Kill pids passed on stdin or as args.
  local pids=("$@")
  if [[ ${#pids[@]} -eq 0 ]]; then
    return 0
  fi

  # Try TERM then KILL.
  for pid in "${pids[@]}"; do
    [[ -n "$pid" ]] || continue
    kill "$pid" >/dev/null 2>&1 || true
  done
  sleep 0.6
  for pid in "${pids[@]}"; do
    [[ -n "$pid" ]] || continue
    kill -9 "$pid" >/dev/null 2>&1 || true
  done
}

stop_processes_that_may_lock_paths() {
  # Be conservative: only kill processes whose command line contains our repo paths.
  # This avoids killing unrelated node/electron processes.
  local patterns=(
    "$DESKTOP_DIR/release"
    "$DESKTOP_DIR/release-temp"
    "$WEB_DIR/.next/standalone"
    "$WEB_DIR/.next"
  )

  local all_pids=()
  for pat in "${patterns[@]}"; do
    while IFS= read -r pid; do
      [[ -n "$pid" ]] || continue
      all_pids+=("$pid")
    done < <(list_procs_by_cmd_substr "$pat")
  done

  # De-dup
  if [[ ${#all_pids[@]} -eq 0 ]]; then
    return 0
  fi

  local uniq=()
  local seen=""
  for pid in "${all_pids[@]}"; do
    if [[ ",${seen}," != *",${pid},"* ]]; then
      uniq+=("$pid")
      seen="${seen},${pid}"
    fi
  done

  echo "Stopping processes that may lock build outputs..."
  echo "PIDs: ${uniq[*]}"
  kill_pids "${uniq[@]}"
}

try_remove_dir_with_retries() {
  local dir="$1"
  local max_retries="${2:-10}"
  [[ -d "$dir" ]] || return 0

  local i
  for i in $(seq 1 "$max_retries"); do
    rm -rf "$dir" >/dev/null 2>&1 || true
    [[ ! -e "$dir" ]] && return 0

    if [[ $i -eq 3 ]]; then
      stop_processes_that_may_lock_paths || true
    fi
    sleep 0.9
  done

  if [[ -e "$dir" ]]; then
    echo "WARN: Failed to remove dir after retries: $dir" >&2
    if command -v lsof >/dev/null 2>&1; then
      echo "Tip: check open handles with: lsof +D \"$dir\"" >&2
    fi
    return 1
  fi
  return 0
}

clear_stale_next_standalone() {
  local target="$WEB_DIR/.next/standalone"
  [[ -d "$target" ]] || return 0

  echo "Cleaning stale Next standalone output: $target"
  try_remove_dir_with_retries "$target" 10
}

clear_stale_desktop_unpacked() {
  # Similar to Windows' win-unpacked cleanup; for macOS/Linux we remove
  # platform-specific unpacked outputs under apps/desktop/release.
  local release_dir="$DESKTOP_DIR/release"
  [[ -d "$release_dir" ]] || return 0

  local targets=(
    "$release_dir/linux-unpacked"
    "$release_dir/win-unpacked"
    "$release_dir/mac"
    "$release_dir/mac-arm64"
    "$release_dir/mac-x64"
    "$release_dir/mac-universal"
  )

  local t
  for t in "${targets[@]}"; do
    [[ -d "$t" ]] || continue
    echo "Cleaning stale output: $t"
    if ! try_remove_dir_with_retries "$t" 10; then
      return 1
    fi
  done

  # Also clean any previous temp outputs (release-temp*) unpacked directories.
  local temp
  for temp in "$DESKTOP_DIR"/release-temp*; do
    [[ -d "$temp" ]] || continue
    for t in "$temp"/linux-unpacked "$temp"/win-unpacked "$temp"/mac*; do
      [[ -d "$t" ]] || continue
      echo "Cleaning stale output: $t"
      try_remove_dir_with_retries "$t" 10 || true
    done
  done

  return 0
}

get_latest_artifact_file() {
  # Return the newest artifact file under a directory (excluding blockmaps/yml).
  # Handles spaces in filenames.
  local out_dir="$1"
  [[ -d "$out_dir" ]] || return 1

  _mtime() {
    local f="$1"
    if stat -c "%Y" "$f" >/dev/null 2>&1; then
      stat -c "%Y" "$f"
      return 0
    fi
    if stat -f "%m" "$f" >/dev/null 2>&1; then
      stat -f "%m" "$f"
      return 0
    fi
    echo 0
  }

  local best_ts=0
  local best_file=""

  while IFS= read -r -d '' f; do
    local ts
    ts="$(_mtime "$f")"
    if [[ -z "$best_file" || "$ts" -gt "$best_ts" ]]; then
      best_ts="$ts"
      best_file="$f"
    fi
  done < <(
    find "$out_dir" -maxdepth 1 -type f \
      ! -name "*.blockmap" \
      ! -name "latest*.yml" \
      ! -name "builder-debug*.yml" \
      ! -name "builder-effective-config*.yaml" \
      \( -name "*.dmg" -o -name "*.AppImage" -o -name "*.zip" -o -name "*.tar.gz" -o -name "*.exe" -o -name "*.deb" -o -name "*.rpm" \) \
      -print0 2>/dev/null
  )

  [[ -n "$best_file" ]] || return 1
  echo "$best_file"
}

step 1 "Compiling Electron main process (TypeScript)"
require_cmd pnpm "Install pnpm (Node.js package manager)."
( cd "$DESKTOP_DIR" && pnpm compile )

step 2 "Building Next.js frontend (standalone)"
require_cmd npm "Install Node.js (npm is bundled)."
stop_processes_that_may_lock_paths || true
clear_stale_next_standalone
export BUILD_STANDALONE=1
export API_BASE_URL
export NEXT_PUBLIC_API_BASE_URL
( cd "$WEB_DIR" && pnpm build )
unset BUILD_STANDALONE || true
unset API_BASE_URL || true
unset NEXT_PUBLIC_API_BASE_URL || true

echo "Hydrating Next standalone node_modules (npm)"
STANDALONE_WEB_DIR="$WEB_DIR/.next/standalone/apps/web"
if [[ ! -d "$STANDALONE_WEB_DIR" ]]; then
  echo "ERROR: Next standalone output not found at: $STANDALONE_WEB_DIR" >&2
  echo "       Did Step 2 (pnpm build) succeed?" >&2
  exit 1
fi

(
  cd "$STANDALONE_WEB_DIR"
  rm -rf node_modules
  npm install --omit=dev --no-package-lock --loglevel=error
)

CHECK_SCRIPT="$ROOT_DIR/scripts/ci/check-next-standalone-deps.mjs"
if [[ -f "$CHECK_SCRIPT" ]]; then
  node "$CHECK_SCRIPT" "$STANDALONE_WEB_DIR"
fi

ROOT_STANDALONE_NODE_MODULES="$WEB_DIR/.next/standalone/node_modules"
rm -rf "$ROOT_STANDALONE_NODE_MODULES" || true

step 3 "Packaging FastAPI backend (PyInstaller)"
require_cmd uv "Install uv: pip install uv (or use your package manager)."
( cd "$CORE_DIR" && uv run python scripts/build_backend.py )

step 4 "Building Electron installer (electron-builder)"

stop_processes_that_may_lock_paths || true

clean_ok=1
if ! clear_stale_desktop_unpacked; then
  clean_ok=0
fi

output_dir="$DESKTOP_DIR/release"
if [[ $clean_ok -eq 1 ]]; then
  ( cd "$DESKTOP_DIR" && pnpm build )
else
  alt_out="release-temp-$(now_ts)"
  echo
  echo "release output seems locked; building with a fresh output directory: $alt_out"
  echo "(This avoids file-handle locks from previous runs. You can delete old release-temp* later.)"
  output_dir="$DESKTOP_DIR/$alt_out"
  ( cd "$DESKTOP_DIR" && pnpm exec electron-builder --config.directories.output="$alt_out" )

  # Normalize: copy latest installer artifact back into release/ for easy discovery.
  mkdir -p "$DESKTOP_DIR/release"
  if latest_file="$(get_latest_artifact_file "$output_dir" 2>/dev/null)"; then
    cp -f "$latest_file" "$DESKTOP_DIR/release/" || true
    echo "Artifact written: $latest_file"
    echo "Artifact copied to: $DESKTOP_DIR/release/$(basename "$latest_file")"
  else
    echo "WARN: Could not locate installer artifact under: $output_dir" >&2
  fi
fi

echo
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅  Build complete!                             ║"
echo "║                                                  ║"
echo "║  Output: apps/desktop/release/                    ║"
echo "╚══════════════════════════════════════════════════╝"
