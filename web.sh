#!/usr/bin/env bash
# Start the QLFW demo website and open it in the browser.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PY:-.venv/bin/python}
if [ ! -x "$PY" ]; then
    echo "No virtual environment found. Run this first:"
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt flask"
    exit 1
fi

[ -f samples/certificate.png ] || $PY make_sample.py

echo
echo "  QLFW demo website starting..."
echo "  Open this in your browser:   http://127.0.0.1:5005"
echo "  Press Control-C here to stop it."
echo

( sleep 2; command -v open >/dev/null && open http://127.0.0.1:5005 ) &
exec $PY webapp/app.py
