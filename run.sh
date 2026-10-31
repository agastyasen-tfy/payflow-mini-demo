#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
set -a; source scripts/demo.env; set +a
export PUBLIC_URL=https://detective-sublime-cytoplasm.ngrok-free.dev/
export AGENT_TOKEN="${AGENT_TOKEN:-placeholder}"
exec python3 combined.py
