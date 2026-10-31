# SETUP — tunnel-based (laptop + cloudflared), no devtest deploy needed

Everything RUNS on your laptop; two cloudflared Quick Tunnels make the MCP server
and agent publicly reachable so the PLATFORM-ADMIN gateway can call them.
All governance (registry, identity, grants, traces) is on PLATFORM-ADMIN.

```
laptop:8001 (MCP server) ──cloudflared──▶ https://xxxx.trycloudflare.com ─┐
laptop:8000 (agent)      ──cloudflared──▶ https://yyyy.trycloudflare.com ─┤
laptop:8080 (chat UI) ──▶ PLATFORM-ADMIN gateway ─────────────────────────┘
```

Values needed (ALL from PLATFORM-ADMIN):

| Value | Where |
|---|---|
| GATEWAY_BASE_URL | the platform-admin URL you log in to |
| MODEL | AI Gateway → Models, e.g. `openai-main/gpt-4o-mini` |
| USER_TOKEN | Settings → Personal Access Tokens → New |
| AGENT_TOKEN | Agent Registry → agent ⋮ → Get Token (exists after Phase 2) |

## Phase 0 — one-time install
```bash
pip install -r mcp-server/requirements.txt -r agent/requirements.txt -r ui/requirements.txt
brew install cloudflared        # macOS
# Linux: curl -L -o /usr/local/bin/cloudflared \
#   https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
#   && chmod +x /usr/local/bin/cloudflared
cp scripts/demo.env.template scripts/demo.env   # fill GATEWAY_BASE_URL, MODEL, USER_TOKEN
```

## Phase 1 — tunnels + services (two terminals)
```bash
# Terminal 1 — KEEP RUNNING ALL DAY (URLs change on restart!)
./scripts/1_tunnels.sh          # prints the two public URLs to register

# Terminal 2
./scripts/2_services.sh         # starts MCP server :8001 and agent :8000
```
Sanity check: `curl <agent-tunnel-url>/.well-known/agent-card.json` → JSON.

## Phase 2 — register on PLATFORM-ADMIN
1. MCP Gateway → Add Server: name `payflow-transactions`,
   URL = `<mcp-tunnel-url>/mcp` (printed by script 1), auth: none
2. Agent Registry → Register: name `payflow-refunds-agent`, Proxy via Gateway,
   Framework A2A, URL = `<agent-tunnel-url>`, card path `/.well-known/agent-card.json`
3. Agent ⋮ → Get Token → paste into `scripts/demo.env` as AGENT_TOKEN
4. Ctrl+C **Terminal 2 only** and re-run `./scripts/2_services.sh`
   (tunnels in Terminal 1 untouched → URLs stay valid)

## Phase 3 — grants on PLATFORM-ADMIN
- MCP server → collaborators → `agent:payflow-refunds-agent` → MCP Server User
- Model provider account → collaborators → same agent
- Agent → collaborators → your demo user → Agent Access

## Phase 4 — demo
```bash
# Terminal 3
./scripts/3_ui.sh               # http://localhost:8080, password: payflow
```
Try: "Show transactions for cust_42" → "Refund txn_1002, duplicate charge" →
show Request Traces on platform-admin → revoke the MCP grant → re-ask → ⛔ 403.

## Tunnel gotchas (important)
- Quick Tunnel URLs are RANDOM and change every restart of script 1. If it dies,
  you must update the URLs in the MCP server + agent registrations on platform-admin.
  Start it ~30 min before the demo and leave it alone.
- The script forces `--protocol http2` (QUIC/UDP is blocked on many corp networks
  and causes HTTP 530 errors).
- Quick Tunnels need no Cloudflare account but have no SLA — fine for a demo.
  For something stable, use a named tunnel (Cloudflare account + fixed hostname)
  or `ngrok http 8000 --domain <reserved-domain>` (paid) for permanent URLs.
- If your laptop sits behind a VPN that blocks cloudflared's outbound connection
  entirely, try ngrok: `ngrok http 8000` / `ngrok http 8001` and use those URLs
  (same registration steps; free tier URLs also rotate per restart).

## Troubleshooting
| Symptom | Cause |
|---|---|
| HTTP 530 via tunnel | QUIC blocked → script already forces http2; check Terminal 1 logs |
| Registration can't fetch agent card | script 2 not running, or stale tunnel URL |
| Chat 403 | missing Phase 3 grant (also your demo moment!) |
| Chat 401 | wrong/expired USER_TOKEN or AGENT_TOKEN |
| Agent error 404 on MCP | MCP_SERVER_NAME in demo.env ≠ registered name |
