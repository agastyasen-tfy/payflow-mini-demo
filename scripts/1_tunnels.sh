#!/usr/bin/env bash
# Starts two cloudflared Quick Tunnels (no account needed):
#   localhost:8001 -> MCP server tunnel
#   localhost:8000 -> agent tunnel
# Writes the public URLs to scripts/.tunnel_mcp_url and scripts/.tunnel_agent_url
# KEEP THIS RUNNING for the whole demo — URLs change if you restart it.
set -euo pipefail
cd "$(dirname "$0")"

command -v cloudflared >/dev/null || {
  echo "cloudflared not found. Install it first:"
  echo "  macOS : brew install cloudflared"
  echo "  Linux : curl -L -o /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x /usr/local/bin/cloudflared"
  exit 1
}

start_tunnel () { # $1=local port  $2=url output file  $3=log file
  cloudflared tunnel --url "http://localhost:$1" --protocol http2 --no-autoupdate > "$3" 2>&1 &
  echo $!
}

LOG_MCP=.cf_mcp.log; LOG_AGENT=.cf_agent.log
rm -f .tunnel_mcp_url .tunnel_agent_url "$LOG_MCP" "$LOG_AGENT"
PID1=$(start_tunnel 8001 .tunnel_mcp_url "$LOG_MCP")
PID2=$(start_tunnel 8000 .tunnel_agent_url "$LOG_AGENT")
trap 'kill $PID1 $PID2 2>/dev/null' EXIT

grab_url () { # $1=log file  $2=out file
  for _ in $(seq 1 30); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$1" | head -1 || true)
    [ -n "${URL:-}" ] && { echo "$URL" > "$2"; echo "$URL"; return 0; }
    sleep 1
  done
  echo "ERROR: tunnel URL not found; see $1" >&2; return 1
}

echo "── Tunnel URLs ─────────────────────────────────────────────"
echo "MCP server : $(grab_url "$LOG_MCP" .tunnel_mcp_url)"
echo "Agent      : $(grab_url "$LOG_AGENT" .tunnel_agent_url)"
echo "────────────────────────────────────────────────────────────"
echo "Register on PLATFORM-ADMIN with:"
echo "  MCP Gateway URL   : $(cat .tunnel_mcp_url)/mcp"
echo "  Agent Registry URL: $(cat .tunnel_agent_url)"
echo "  Agent card path   : /.well-known/agent-card.json"
echo
echo "Tunnels running. Press Ctrl+C to stop (URLs will change on restart)."
wait
