#!/usr/bin/env bash
# Start Jeevandhara with one command (Linux / macOS):   ./run.sh
# Creates backend/.venv and installs dependencies the first time.
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV="backend/.venv"

if [ ! -x "$VENV/bin/python" ]; then
    echo "Creating virtual environment in $VENV ..."
    "$PYTHON" -m venv "$VENV"
fi

# Install / update dependencies only when requirements.txt changed.
STAMP="$VENV/.requirements-installed"
if [ ! -f "$STAMP" ] || [ backend/requirements.txt -nt "$STAMP" ]; then
    echo "Installing dependencies ..."
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet -r backend/requirements.txt
    touch "$STAMP"
fi

PORT="${PORT:-8000}"
URL="http://127.0.0.1:${PORT}/"

# Open the browser once the server is up (best effort).
(
    for _ in $(seq 1 40); do
        if "$VENV/bin/python" -c "import urllib.request; urllib.request.urlopen('${URL}health', timeout=1)" 2>/dev/null; then
            if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true
            elif command -v open >/dev/null 2>&1; then open "$URL" || true
            fi
            break
        fi
        sleep 0.5
    done
) &

PORT="$PORT" exec "$VENV/bin/python" backend/main.py
