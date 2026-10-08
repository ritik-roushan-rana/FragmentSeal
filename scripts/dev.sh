#!/usr/bin/env bash
# Run the API and the web app together. Ctrl-C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$ROOT/backend/.venv/bin/python" ]; then
  echo "backend/.venv is missing — run ./scripts/setup.sh first" >&2
  exit 1
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "frontend/node_modules is missing — run ./scripts/setup.sh first" >&2
  exit 1
fi

cleanup() {
  echo
  echo "stopping…"
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "api  → http://127.0.0.1:8000  (docs at /docs)"
(cd "$ROOT/backend" && .venv/bin/python -m uvicorn app.main:app --reload --port 8000) &

echo "web  → http://localhost:3000"
(cd "$ROOT/frontend" && npm run dev) &

wait
