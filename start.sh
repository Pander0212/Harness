#!/usr/bin/env bash
# Startet den Harness (Linux/Mac). Legt beim ersten Start ein venv an.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/python main.py "$@"
