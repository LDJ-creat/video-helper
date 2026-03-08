#!/usr/bin/env bash
# Phase 6 Smoke Test (macOS/Linux): Closed Loop
# Equivalent of scripts/smoke-phase6-closed-loop.ps1
#
# What this checks:
# - Start backend with worker enabled (unless --skip-start-backend)
# - Wait for /api/v1/health
# - Run python closed-loop validation script (services/core/scripts/smoke_closed_loop.py)
#
# Notes:
# - Requires: uv, curl, (lsof recommended), python (via uv).
# - Relies on services/core/.env for LLM settings.

set -euo pipefail

API_BASE_URL="http://127.0.0.1:8000"
TIMEOUT_SEC=1200
SKIP_START_BACKEND=0
DATA_DIR=""
LOG_CURSOR_SECRET="dev-log-cursor-secret"
PROFILE="bilibili"
TRANSCRIBE_PROVIDER="faster-whisper"
TRANSCRIBE_MODEL_SIZE="tiny"
TRANSCRIBE_DEVICE="cpu"
TRANSCRIBE_COMPUTE_TYPE="int8"
URL="https://www.bilibili.com/video/BV1jgifB7EAp/?spm_id_from=333.337.search-card.all.click&vd_source=8e03b1a6cd89d2b50af0c43b7de269ff"
NO_EVIDENCE=0
YTDLP_COOKIES_FROM_BROWSER=""
YTDLP_COOKIES_FILE=""
YTDLP_FORMAT_OVERRIDE=""

usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --api-base-url URL          Default: $API_BASE_URL
  --timeout-sec N             Default: $TIMEOUT_SEC
  --skip-start-backend        Do not start backend automatically
  --data-dir DIR              Use DIR as DATA_DIR
  --log-cursor-secret STR      Default: $LOG_CURSOR_SECRET
  --profile NAME               Default: $PROFILE (supported: bilibili)
  --transcribe-provider NAME    Default: $TRANSCRIBE_PROVIDER
  --transcribe-model-size SIZE  Default: $TRANSCRIBE_MODEL_SIZE
  --transcribe-device DEV       Default: $TRANSCRIBE_DEVICE
  --transcribe-compute-type T   Default: $TRANSCRIBE_COMPUTE_TYPE
  --url URL                   Video URL (default is a bilibili BV)
  --no-evidence               Skip evidence generation
  --ytdlp-cookies-from-browser STR
  --ytdlp-cookies-file PATH
  --ytdlp-format STR           Override YTDLP_FORMAT (optional)
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
    --timeout-sec) TIMEOUT_SEC="$2"; shift 2 ;;
    --skip-start-backend) SKIP_START_BACKEND=1; shift 1 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --log-cursor-secret) LOG_CURSOR_SECRET="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --transcribe-provider) TRANSCRIBE_PROVIDER="$2"; shift 2 ;;
    --transcribe-model-size) TRANSCRIBE_MODEL_SIZE="$2"; shift 2 ;;
    --transcribe-device) TRANSCRIBE_DEVICE="$2"; shift 2 ;;
    --transcribe-compute-type) TRANSCRIBE_COMPUTE_TYPE="$2"; shift 2 ;;
    --url) URL="$2"; shift 2 ;;
    --no-evidence) NO_EVIDENCE=1; shift 1 ;;
    --ytdlp-cookies-from-browser) YTDLP_COOKIES_FROM_BROWSER="$2"; shift 2 ;;
    --ytdlp-cookies-file) YTDLP_COOKIES_FILE="$2"; shift 2 ;;
    --ytdlp-format) YTDLP_FORMAT_OVERRIDE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

info() { echo "[smoke] $*"; }
ok() { echo "[ok] $*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: '$1' not found. $2" >&2
    exit 1
  }
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="$REPO_ROOT/services/core"

require_cmd uv "Install uv first."
require_cmd curl "Install curl first."

if [[ -z "$DATA_DIR" ]]; then
  DATA_DIR="${TMPDIR:-/tmp}/vh-smoke-data-$(date +%s)"
fi
mkdir -p "$DATA_DIR"

# Defaults for bilibili profile
if [[ "$PROFILE" == "bilibili" ]]; then
  if [[ -n "$YTDLP_FORMAT_OVERRIDE" ]]; then
    export YTDLP_FORMAT="$YTDLP_FORMAT_OVERRIDE"
  elif [[ -z "${YTDLP_FORMAT:-}" ]]; then
    export YTDLP_FORMAT="bestvideo+bestaudio/best"
  fi

  if [[ -z "$YTDLP_COOKIES_FROM_BROWSER" && -z "$YTDLP_COOKIES_FILE" ]]; then
    default_cookie="$REPO_ROOT/www.bilibili.com_cookies.txt"
    if [[ -f "$default_cookie" ]]; then
      YTDLP_COOKIES_FILE="$default_cookie"
    fi
  fi
fi

backend_pid=""

cleanup() {
  if [[ -n "$backend_pid" ]]; then
    info "Stopping backend (pid=$backend_pid)"
    # Try to stop children first (best-effort)
    if command -v pkill >/dev/null 2>&1; then
      pkill -P "$backend_pid" >/dev/null 2>&1 || true
    fi
    kill "$backend_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

ensure_port_free() {
  local port="$1"

  if command -v lsof >/dev/null 2>&1; then
    local pid
    pid="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true)"
    if [[ -z "$pid" ]]; then
      return 0
    fi

    local cmd
    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    info "Port $port is in use by pid=$pid cmd=$cmd"

    if echo "$cmd" | grep -Eqi "services/core|main\.py|uv run"; then
      info "Stopping stale backend on port $port (pid=$pid)..."
      kill "$pid" 2>/dev/null || true
      sleep 0.6
      local pid2
      pid2="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true)"
      [[ -z "$pid2" ]] || {
        echo "ERROR: failed to free port $port (still in use by pid=$pid2)" >&2
        exit 1
      }
      return 0
    fi

    echo "ERROR: port $port already in use (pid=$pid). Stop it or use --skip-start-backend" >&2
    exit 1
  else
    if command -v ss >/dev/null 2>&1; then
      # Linux fallback
      if ss -ltnp 2>/dev/null | grep -q ":${port} "; then
        echo "ERROR: port $port appears to be in use (detected by ss). Stop it or use --skip-start-backend" >&2
        exit 1
      fi
      return 0
    fi
    info "WARN: lsof/ss not found; skipping port check for $port"
  fi
}

wait_for_health() {
  local health_url="$1"
  local timeout_s="$2"
  local deadline
  deadline=$(( $(date +%s) + timeout_s ))

  while [[ $(date +%s) -lt $deadline ]]; do
    if resp="$(curl -fsS --max-time 60 "$health_url" 2>/dev/null)"; then
      if uv run python -c 'import json,sys; o=json.loads(sys.argv[1]); assert o.get("status"); assert "ready" in o' "$resp" >/dev/null 2>&1; then
        return 0
      fi
    fi
    sleep 0.5
  done

  echo "ERROR: timed out waiting for health: $health_url" >&2
  exit 1
}

if [[ $SKIP_START_BACKEND -eq 0 ]]; then
  ensure_port_free 8000
  info "Starting backend (worker enabled)..."

  export DATA_DIR="$DATA_DIR"
  export LOG_CURSOR_SECRET="$LOG_CURSOR_SECRET"
  export WORKER_ENABLE="1"
  export MAX_CONCURRENT_JOBS="1"

  export TRANSCRIBE_PROVIDER="$TRANSCRIBE_PROVIDER"
  export TRANSCRIBE_MODEL_SIZE="$TRANSCRIBE_MODEL_SIZE"
  export TRANSCRIBE_DEVICE="$TRANSCRIBE_DEVICE"
  export TRANSCRIBE_COMPUTE_TYPE="$TRANSCRIBE_COMPUTE_TYPE"

  # Conservative timeouts for slow LLM first-byte
  export LLM_TIMEOUT_S="${LLM_TIMEOUT_S:-180}"
  export LLM_PREFLIGHT_TIMEOUT_S="${LLM_PREFLIGHT_TIMEOUT_S:-60}"
  export LLM_MAX_ATTEMPTS="${LLM_MAX_ATTEMPTS:-3}"
  export LLM_PLAN_MAX_SEGMENTS="${LLM_PLAN_MAX_SEGMENTS:-40}"
  export LLM_PLAN_MAX_CHARS="${LLM_PLAN_MAX_CHARS:-8000}"

  if [[ -n "$YTDLP_COOKIES_FROM_BROWSER" ]]; then
    export YTDLP_COOKIES_FROM_BROWSER="$YTDLP_COOKIES_FROM_BROWSER"
  fi
  if [[ -n "$YTDLP_COOKIES_FILE" ]]; then
    export YTDLP_COOKIES_FILE="$YTDLP_COOKIES_FILE"
  fi

  (
    cd "$CORE_DIR"
    uv run python main.py
  ) &
  backend_pid=$!
fi

wait_for_health "$API_BASE_URL/api/v1/health" 60
ok "Health ready"

summary_path="$DATA_DIR/smoke_closed_loop_summary_$(date +%s).json"

info "Running closed-loop validation (python)..."
(
  cd "$CORE_DIR"
  uv run python scripts/smoke_closed_loop.py \
    --api-base "$API_BASE_URL" \
    --timeout-sec "$TIMEOUT_SEC" \
    --source-type "bilibili" \
    --url "$URL" \
    --summary-out "$summary_path"
)

if [[ $NO_EVIDENCE -eq 0 && -f "$summary_path" ]]; then
  report_script="$CORE_DIR/scripts/report_smoke_evidence.py"
  if [[ -f "$report_script" ]]; then
    job_id="$(uv run python -c 'import json,sys; p=sys.argv[1]; obj=json.load(open(p,"r",encoding="utf-8")); print(obj.get("jobId") or "")' "$summary_path" 2>/dev/null || true)"

    if [[ -n "$job_id" ]]; then
      out_dir="$REPO_ROOT/_bmad-output/implementation-artifacts"
      mkdir -p "$out_dir"
      out_path="$out_dir/smoke-evidence-closed-loop-$job_id.json"
      info "Collecting evidence..."
      ( cd "$CORE_DIR" && uv run python scripts/report_smoke_evidence.py --data-dir "$DATA_DIR" --job-id "$job_id" --max-files 20 --out "$out_path" ) || true
      ok "Evidence written: $out_path"
    fi
  fi
fi

ok "Closed-loop smoke succeeded"
