#!/usr/bin/env bash
# Run PromptCraft locally on port 5055 (override with PORT=... if needed).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing ${PY}. Create it with:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi
export PORT="${PORT:-5055}"
exec "$PY" "$ROOT/app.py"
