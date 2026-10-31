#!/usr/bin/env bash
# Starts the MCP server (:8001) and the agent (:8000) locally.
# Requires scripts/1_tunnels.sh to be running (reads the agent tunnel URL).
# Safe to Ctrl+C and re-run anytime (e.g. after adding AGENT_TOKEN) —
# tunnel URLs are unaffected because tunnels run in the other terminal.
set -euo pipefail
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python) || { echo "python3 not found"; exit 1; }

[ -f demo.env ] || { echo "Copy demo.env.template to demo.env and fill it in."; exit 1; }
set -a; source demo.env; set +a

[ -f .tunnel_agent_url ] || { echo "Run ./1_tunnels.sh first (in another terminal)."; exit 1; }
export PUBLIC_URL="$(cat .tunnel_agent_url)/"
[ -n "${AGENT_TOKEN:-}" ] || echo "WARN: AGENT_TOKEN empty — fine for first run (registration only)."
export AGENT_TOKEN="${AGENT_TOKEN:-placeholder-fill-after-registration}"

PORT=8001 "$PY" ../mcp-server/server.py & P1=$!
PORT=8000 "$PY" ../agent/agent.py      & P2=$!
trap 'kill $P1 $P2 2>/dev/null' EXIT
echo "MCP server on :8001, agent on :8000 (public: $PUBLIC_URL)"
wait
