#!/usr/bin/env bash
# Benchmark closed loop: optional backend start + run_benchmark.py

set -euo pipefail

API_BASE_URL="http://127.0.0.1:8000"
PROFILE="short-local"
SKIP_START_BACKEND=0
DATA_DIR=""
TIMEOUT_SEC=1200

usage() {
  cat <<EOF
Usage: $0 [options]
  --api-base-url URL
  --profile NAME           Default: short-local
  --skip-start-backend
  --data-dir DIR
  --timeout-sec N
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --skip-start-backend) SKIP_START_BACKEND=1; shift 1 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --timeout-sec) TIMEOUT_SEC="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_DIR="$REPO_ROOT/services/core"
command -v uv >/dev/null || { echo "uv required" >&2; exit 1; }

if [[ -z "$DATA_DIR" ]]; then
  DATA_DIR="${TMPDIR:-/tmp}/vh-benchmark-data-$(date +%s)"
fi
mkdir -p "$DATA_DIR"

backend_pid=""
cleanup() {
  if [[ -n "$backend_pid" ]]; then
    kill "$backend_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

wait_for_health() {
  local url="$1"
  local deadline=$(( $(date +%s) + 60 ))
  while [[ $(date +%s) -lt $deadline ]]; do
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo "health timeout: $url" >&2
  exit 1
}

if [[ $SKIP_START_BACKEND -eq 0 ]]; then
  export DATA_DIR="$DATA_DIR"
  export WORKER_ENABLE=1
  export MAX_CONCURRENT_JOBS=1
  export TRANSCRIBE_MODEL_SIZE="${TRANSCRIBE_MODEL_SIZE:-tiny}"
  export TRANSCRIBE_DEVICE="${TRANSCRIBE_DEVICE:-cpu}"
  export TRANSCRIBE_COMPUTE_TYPE="${TRANSCRIBE_COMPUTE_TYPE:-int8}"
  profile_env_json="$(cd "$CORE_DIR" && uv run python scripts/apply_profile_env.py --profile "$PROFILE" --profiles-file "$REPO_ROOT/benchmarks/profiles.yaml")"
  if [[ -n "$profile_env_json" && "$profile_env_json" != "{}" ]]; then
    while IFS='=' read -r key value; do
      if [[ -n "$key" ]]; then
        export "$key=$value"
      fi
    done < <(PROFILE_ENV_JSON="$profile_env_json" python3 -c "import json,os; d=json.loads(os.environ['PROFILE_ENV_JSON']);
for k,v in d.items(): print(f'{k}={v}')")
  fi
  ( cd "$CORE_DIR" && uv run python main.py ) &
  backend_pid=$!
  wait_for_health "$API_BASE_URL/api/v1/health"
fi

(
  cd "$CORE_DIR"
  uv run python scripts/run_benchmark.py \
    --mode benchmark \
    --profile "$PROFILE" \
    --api-base "$API_BASE_URL" \
    --data-dir "$DATA_DIR" \
    --profiles-file "$REPO_ROOT/benchmarks/profiles.yaml" \
    --out-dir "$REPO_ROOT/benchmarks/results"
)

echo "[ok] benchmark finished profile=$PROFILE"
