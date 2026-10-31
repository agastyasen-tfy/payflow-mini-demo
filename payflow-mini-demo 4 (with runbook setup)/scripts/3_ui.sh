#!/usr/bin/env bash
# Starts the chat UI on http://localhost:8080 (login password: payflow)
set -euo pipefail
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python) || { echo "python3 not found"; exit 1; }
set -a; source demo.env; set +a
[ -n "${USER_TOKEN:-}" ] || { echo "Set USER_TOKEN in demo.env"; exit 1; }
PORT=8080 "$PY" ../ui/app.py
