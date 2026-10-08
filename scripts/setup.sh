#!/usr/bin/env bash
# One-time setup: Python venv + dependencies, Node modules, env files, demo data.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3.12}"

echo "==> Backend: virtual environment"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  "$PYTHON" -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "    created backend/.env from the example"
fi

echo "==> Backend: database schema, demo accounts and sample documents"
.venv/bin/python -m app.seed --documents

echo "==> Frontend: node modules"
cd "$ROOT/frontend"
npm install --silent
if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "    created frontend/.env.local from the example"
fi

cat <<'DONE'

Setup complete.

  Start both servers:   ./scripts/dev.sh
  Web app:              http://localhost:3000
  API docs:             http://127.0.0.1:8000/docs

  Admin    admin@docauth.dev    / Admin@12345
  Verifier verifier@docauth.dev / Verify@12345
DONE
