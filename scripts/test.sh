#!/usr/bin/env bash
# Full check: backend test suite, frontend types, lint and production build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Backend tests"
cd "$ROOT/backend"
.venv/bin/python -m pytest tests -q

echo
echo "==> Frontend types"
cd "$ROOT/frontend"
npx tsc --noEmit

echo "==> Frontend lint"
npx eslint .

echo "==> Frontend build"
npx next build

echo
echo "All checks passed."
