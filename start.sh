#!/usr/bin/env bash
# One-click start for macOS / Linux
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "First run: creating virtual environment…"
  python3 -m venv .venv
fi
echo "Checking packages…"
./.venv/bin/pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
( sleep 2; open "http://localhost:${PORT:-8000}" 2>/dev/null || xdg-open "http://localhost:${PORT:-8000}" 2>/dev/null ) &
./.venv/bin/python backend/main.py
