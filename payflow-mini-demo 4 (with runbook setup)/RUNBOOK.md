# PayFlow Mini Demo — Full Runbook (from scratch → demo → teardown)

Setup for a recurring demo on a shared/public control plane (platform-admin).
Everything runs on YOUR LAPTOP behind one ngrok tunnel. Expect ~15 min for a
from-scratch setup once prerequisites are done.

─────────────────────────────────────────────────────────────────────
ARCHITECTURE
─────────────────────────────────────────────────────────────────────
  laptop:8000  combined.py          ONE ngrok tunnel (reserved domain,
    ├─ /                A2A agent    URL NEVER CHANGES):
    ├─ /.well-known/... agent card   https://detective-sublime-cytoplasm.ngrok-free.dev
    └─ /mcp/            MCP server
  laptop:8080  ui/app.py  → platform-admin gateway → (back through tunnel)

  Identity flow: UI sends USER PAT → gateway → agent. Agent calls LLM + MCP
  through the gateway AS ITSELF (agent token in Authorization).

─────────────────────────────────────────────────────────────────────
0. ONE-TIME PREREQUISITES (already done; only for a new laptop)
─────────────────────────────────────────────────────────────────────
  pip3 install -r mcp-server/requirements.txt -r agent/requirements.txt -r ui/requirements.txt
  brew install ngrok
  ngrok config add-authtoken <token>          # dashboard.ngrok.com
  # ngrok.yml needs no tunnels section — we use `ngrok http` directly.
  # NOTE: agent/agent.py line ~128 is patched to run_agent(user_text, None)
  #       (agent acts as itself downstream). Keep that patch.
  # NOTE: ui/app.py uses /api/llm/remote-agent/<name> (correct invoke path).

  Cheat-sheet of fixed values used throughout:
    DOMAIN        https://detective-sublime-cytoplasm.ngrok-free.dev
    GATEWAY       https://platform-admin.live-demo.truefoundry.cloud   (NO /api/llm suffix!)
    MCP NAME      payflow-transactions
    AGENT NAME    payflow-refunds-agent
    MODEL         anthropic/claude-opus-4-8   (verify id in AI Gateway → Models)

─────────────────────────────────────────────────────────────────────
1. START LOCAL STACK (3 terminals)
─────────────────────────────────────────────────────────────────────
  T1 (tunnel — never touch again):
      ngrok http 8000 --domain detective-sublime-cytoplasm.ngrok-free.dev
  T1b (optional, prevents sleep): caffeinate -dis

  Prepare scripts/demo.env (if missing, copy from demo.env.template):
      GATEWAY_BASE_URL=https://platform-admin.live-demo.truefoundry.cloud
      MODEL=anthropic/claude-opus-4-8
      MCP_SERVER_NAME=payflow-transactions
      AGENT_NAME=payflow-refunds-agent
      AGENT_TOKEN=                 ← empty for now; filled in step 3
      USER_TOKEN=<your platform-admin PAT>    (Settings → Personal Access Tokens)
      # No quotes needed. NO spaces around '='. Tokens on ONE line.

  T2 (services):   ./run.sh        # or the 4 lines it wraps:
      # set -a; source scripts/demo.env; set +a
      # export PUBLIC_URL=https://detective-sublime-cytoplasm.ngrok-free.dev/
      # export AGENT_TOKEN="${AGENT_TOKEN:-placeholder}"
      # python3 combined.py

  VERIFY:
      curl https://detective-sublime-cytoplasm.ngrok-free.dev/.well-known/agent-card.json
      → JSON with "payflow-refunds-agent". If Cloudflare/ngrok error page: tunnel issue.

─────────────────────────────────────────────────────────────────────
2. REGISTER ON PLATFORM-ADMIN
─────────────────────────────────────────────────────────────────────
  a) MCP Gateway → Add Server (remote):
       Name: payflow-transactions
       URL : https://detective-sublime-cytoplasm.ngrok-free.dev/mcp/   ← TRAILING SLASH
       Auth: none
  b) Agent Registry → Register Agent:
       Name: payflow-refunds-agent
       Config: Proxy via Gateway · Framework: A2A
       URL : https://detective-sublime-cytoplasm.ngrok-free.dev
       Agent Card Endpoint: /.well-known/agent-card.json
       "How the Gateway calls this agent": leave empty
  (Both URLs are permanent thanks to the reserved domain — reused every time.)

─────────────────────────────────────────────────────────────────────
3. AGENT TOKEN
─────────────────────────────────────────────────────────────────────
  Agent row → ⋮ → Get Token → paste into scripts/demo.env as AGENT_TOKEN=...
  Restart T2:  Ctrl+C → ./run.sh

─────────────────────────────────────────────────────────────────────
4. GRANTS (3 of them — all on platform-admin)
─────────────────────────────────────────────────────────────────────
  1. MCP server payflow-transactions → collaborators →
       agent:payflow-refunds-agent → MCP Server User
  2. Anthropic provider account → collaborators → agent:payflow-refunds-agent
  3. Agent payflow-refunds-agent → collaborators → your user → Agent Access

─────────────────────────────────────────────────────────────────────
5. UI + END-TO-END TEST
─────────────────────────────────────────────────────────────────────
  T3:  ./scripts/3_ui.sh          # http://localhost:8080, password: payflow
  Test: "Show transactions for cust_42"  → expect txn_1001 ($129.99) + txn_1002 ($24.50)
  Test: "Refund txn_1002, reason: test"  → expect refund confirmation
  Check Request Traces: hops attributed to payflow-refunds-agent.
  RESTART T2 before the real demo (resets in-memory refunds).

─────────────────────────────────────────────────────────────────────
6. DEMO SCRIPT (short form — see full arc in chat/notes)
─────────────────────────────────────────────────────────────────────
  Act 1  Registry: show agent + identity + Get Token + MCP server. 
         "No API keys given to this agent — only an identity."
  Act 2  Chat: list cust_42 → refund txn_1002.
  Act 3  Traces: walk hops — A2A in, agent→Claude, agent→tools. All attributed.
  Act 4  Control:
         Lever 1: remove MCP grant → chat ⛔ ("blocked at the front door,
                  session never established").
         Lever 2: remove Anthropic grant → chat ⛔ → show the 403 IN TRACES
                  attributed to the agent. Re-grant both → works again.
  Close: "Registered, identified, least-privileged, traced, instantly
         controllable — any framework, running anywhere (this is my laptop)."

  Data: cust_42 → txn_1001 $129.99, txn_1002 $24.50 · cust_7 → txn_1003 (disputed)
  Known quirk: denied MCP session-init does NOT appear in traces (flagged to
  gateway team) — hence lever 2 uses the model grant for the traced 403.

─────────────────────────────────────────────────────────────────────
7. TEARDOWN (public platform — leave nothing behind)
─────────────────────────────────────────────────────────────────────
  On platform-admin (order matters-ish; deleting agent kills its identity+token):
    1. Agent Registry → payflow-refunds-agent → ⋮ → Delete
       (removes the agent, its identity, its token, and its grants)
    2. MCP Gateway → payflow-transactions → Delete
    3. Anthropic provider account → collaborators → remove the agent entry
       if it lingers after agent deletion (check!)
    4. AI Monitoring: traces of demo requests may persist — if the platform is
       truly public and that matters, check retention/deletion options.
  On laptop:
    5. Ctrl+C T2/T3; Ctrl+C T1 (ngrok) — domain stays reserved to your account.
    6. AGENT_TOKEN in demo.env is now dead (deleted with agent) — blank it:
         sed -i '' 's|^AGENT_TOKEN=.*|AGENT_TOKEN=|' scripts/demo.env
    7. Your USER_TOKEN PAT survives — keep it (reused next time) or revoke it
       in Settings if you prefer per-demo PATs.

─────────────────────────────────────────────────────────────────────
8. NEXT TIME FROM SCRATCH = steps 1→5 (~15 min)
─────────────────────────────────────────────────────────────────────
  Same URLs every time (reserved domain) → registration values identical.
  Only NEW values each time: AGENT_TOKEN (new identity on re-register).
  USER_TOKEN only if you revoked it.

─────────────────────────────────────────────────────────────────────
TROUBLESHOOTING (everything we actually hit)
─────────────────────────────────────────────────────────────────────
  404 {"invalid_request_error"} from UI
      → GATEWAY_BASE_URL must NOT end with /api/llm (double-path bug), and
        invoke path is /api/llm/remote-agent/<name>. Restart UI after fixing.
  Port 8000 in use → lsof -nP -iTCP:8000 -sTCP:LISTEN → kill <PID>
  python not found → scripts use python3 (patched); new scripts: use python3
  Tunnel dead / CF error 1033 → that was cloudflared+VPN; we use ngrok now.
        If ngrok dies: restart T1 — domain is reserved, URL unchanged, no
        re-registration needed. (This is why we pay the ngrok-account tax.)
  ngrok both tunnels same URL → not applicable anymore (single tunnel), but
        if you ever need two: pin `domain:` on ONE tunnel only in ngrok.yml.
  /mcp returns 307 → normal (redirect to /mcp/); register WITH trailing slash.
  Chat 401 → AGENT_TOKEN or USER_TOKEN wrong/expired/stale. Re-fetch, no
        spaces around '=', single line, restart T2 (and T3 if USER_TOKEN).
  Chat 403 → one of the 3 grants in step 4 missing (or you left a revoke
        from Act 4 in place — re-grant!).
  Agent 404 on MCP calls → MCP_SERVER_NAME ≠ registered name.
  Traces show YOU not the agent on downstream calls → agent.py line ~128
        must pass None (agent-as-itself). Already patched; survives restarts.
  Everything up but chat hangs → check T2 terminal for a traceback.
  One-liner to kill all demo leftovers:
        pkill -f ngrok; pkill -f combined.py; pkill -f app.py
