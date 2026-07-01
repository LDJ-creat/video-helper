#!/usr/bin/env bash
# Start Video Helper backend (services/core) for local development.
#
# Usage:
#   ./scripts/core-dev.sh
#   make core-dev
#
# Equivalent to:
#   cd services/core && uv run python main.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CORE_DIR="$REPO_ROOT/services/core"
ENV_FILE="$CORE_DIR/.env"
ENV_EXAMPLE="$CORE_DIR/.env.example"

info() { printf '[core-dev] %s\n' "$*"; }

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

if [[ ! -d "$CORE_DIR" ]]; then
  echo "Core directory not found: $CORE_DIR" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$ENV_EXAMPLE" ]]; then
    info "No .env found; copy from .env.example first:"
    printf '  cp "%s" "%s"\n' "$ENV_EXAMPLE" "$ENV_FILE"
  else
    info "No .env found in services/core (optional; settings can come from the UI)."
  fi
fi

info "Starting backend at http://127.0.0.1:8000"
info "Working directory: $CORE_DIR"
printf '\n'

cd "$CORE_DIR"
exec uv run python main.py
