# PayFlow Mini Demo — Runbook

A minimal demo of TrueFoundry **Agent Registry, Agent Identity, MCP Gateway,
access control, and tracing**: one A2A agent + one MCP server + one chat UI,
all deployed as TrueFoundry Services on the demo control plane.

## Architecture

```
┌──────────┐  A2A (user PAT)  ┌─────────────────────┐  proxy   ┌───────────────┐
│ Chat UI  │ ───────────────▶ │ Gateway             │ ───────▶ │ Refunds Agent │
│ (Service)│                  │ /api/llm/remote-    │          │ (Service)     │
└──────────┘                  │  agent/<name>       │          └───────┬───────┘
                              └─────────────────────┘                  │ agent token
                                             ┌─────────────────────────┴──────────┐
                                             ▼                                    ▼
                                   LLM Gateway → Claude              MCP Gateway → payflow-
                                                                     transactions (Service)
```

- **Identity model:** user invokes the agent with their PAT; the agent calls the
  LLM + MCP **as itself** (agent token) → downstream traces attribute to the agent.
- All three components are Dockerfile-based TrueFoundry Services (port 8000).

## Components

| Dir | Service name | What |
|---|---|---|
| `mcp-server/` | `payflow-mcp` | FastMCP: `list_transactions`, `get_transaction`, `issue_refund` (in-memory demo data) |
| `agent/` | `payflow-agent` | A2A agent: card at `/.well-known/agent-card.json`, LLM tool-calling loop via gateway |
| `ui/` | `payflow-ui` | Single-page chat, fake login, forwards to agent via Agent Gateway |

Fixed names used throughout (must match exactly everywhere):
- MCP server registration: **`payflow-transactions`**
- Agent registration: **`payflow-refunds-agent`**
- Gateway base URL: **`https://platform-admin.live-demo.truefoundry.cloud`** (never append `/api/llm`)
- Model: **`anthropic/claude-opus-4-8`** (verify exact id in AI Gateway → Models)

---

## Part A — Deploy the three Services (one-time per setup)

Prereq: this repo pushed to GitHub (or use "Code from Laptop" equivalently).
UI path for each: **Deployments → New Deployment → Service** → pick workspace →
source = Git repo → set build context to the component dir → Dockerfile build.

### A1. payflow-mcp
- Build context: `mcp-server/` · Dockerfile: `mcp-server/Dockerfile`
- Port: **8000**, expose: yes, no endpoint auth (gateway must reach it)
- Env: *(none needed)*
- After deploy, note endpoint → `MCP_ENDPOINT` (e.g. `https://payflow-mcp-<ws>.<domain>`)

### A2. payflow-agent
- Build context: `agent/` · Dockerfile: `agent/Dockerfile`
- Port: **8000**, expose: yes, no endpoint auth
- Env:
  | key | value |
  |---|---|
  | GATEWAY_BASE_URL | `https://platform-admin.live-demo.truefoundry.cloud` |
  | MODEL | `anthropic/claude-opus-4-8` |
  | MCP_SERVER_NAME | `payflow-transactions` |
  | PUBLIC_URL | `https://payflow-agent-<ws>.<domain>/` (the service's own endpoint) |
  | AGENT_TOKEN | *(leave blank/placeholder on first deploy — set in Part C)* |
- Verify: `curl <AGENT_ENDPOINT>/.well-known/agent-card.json` → JSON

### A3. payflow-ui
- Build context: `ui/` · Dockerfile: `ui/Dockerfile`
- Port: **8000**, expose: yes (endpoint auth optional — it has its own fake login)
- Env:
  | key | value |
  |---|---|
  | GATEWAY_BASE_URL | `https://platform-admin.live-demo.truefoundry.cloud` |
  | AGENT_NAME | `payflow-refunds-agent` |
  | USER_TOKEN | your PAT (Settings → Personal Access Tokens) |
  | DEMO_PASSWORD | `payflow` (or anything) |

## Part B — Register on the gateway

1. **MCP Gateway → Add Server** (remote):
   - Name `payflow-transactions` · URL `<MCP_ENDPOINT>/mcp/` ← **trailing slash**
   - Auth: none
2. **Agent Registry → Register Agent**:
   - Name `payflow-refunds-agent` · Proxy via Gateway · Framework **A2A**
   - URL `<AGENT_ENDPOINT>` · Agent Card Endpoint `/.well-known/agent-card.json`
   - "How the Gateway calls this agent": leave empty

## Part C — Agent token

1. Agent row → **⋮ → Get Token** → copy
2. `payflow-agent` service → Edit → env `AGENT_TOKEN` = token → redeploy
   (env-only change; no rebuild)

## Part D — Grants (3)

1. MCP server `payflow-transactions` → collaborators →
   `agent:payflow-refunds-agent` → **MCP Server User**
2. Anthropic provider account → collaborators → same agent
3. Agent → collaborators → your user → **Agent Access**

## Part E — Verify end-to-end

Open `<UI_ENDPOINT>` → password → send:
1. `Show transactions for cust_42` → txn_1001 ($129.99) + txn_1002 ($24.50)
2. `Refund txn_1002, reason: test` → confirmation
3. AI Monitoring → Request Traces → hops attributed to `payflow-refunds-agent`

**Before the real demo: restart `payflow-mcp`** (resets in-memory refund state).

---

## Demo script (~10 min)

- **Act 1 — Registry (2 min):** show agent + its auto-created Identity + Get Token;
  show the MCP server. *"This agent holds no API keys — only an identity.
  Nothing acts anonymously."*
- **Act 2 — It works (3 min):** chat → list cust_42 → refund txn_1002.
  *"The agent autonomously picks the model calls and payment tools."*
- **Act 3 — Traces (3 min):** walk one request: user→agent (A2A), agent→Claude,
  agent→`list_transactions`, agent→`issue_refund`. *"Every hop attributed.
  'Who issued this refund?' — answered."*
- **Act 4 — Control (2.5 min):**
  - Lever 1: remove the MCP grant → chat ⛔. *"Blocked at the front door —
    the session is never even established."*
  - Lever 2: remove the Anthropic grant → chat ⛔ → **show the 403 in traces**,
    attributed to the agent. Re-grant both → works. *"No code change, no
    redeploy, no key rotation."*
- **Close:** *"Registered, identified, least-privileged, traced, instantly
  controllable — any framework, running anywhere."*

Demo data: `cust_42` → txn_1001 $129.99, txn_1002 $24.50 · `cust_7` → txn_1003 (disputed)
Known quirk: denied MCP session-init emits no trace span (flagged) — hence
Lever 2 uses the model grant for the traced 403.

## Teardown (public platform)

1. Agent Registry → delete `payflow-refunds-agent` (removes identity + token)
2. MCP Gateway → delete `payflow-transactions`
3. Anthropic provider account → remove lingering agent collaborator (check)
4. Delete the three Services (or just scale to 0 / pause if you'll re-demo soon —
   then next setup is only Parts B–D, ~5 min, since endpoints are stable)
5. Demo-request traces may persist per platform retention

## Re-setup from scratch

- Services deleted: Parts A–E (~20 min, mostly build time)
- Services kept: Parts B–E (~5 min). Endpoints are stable, so registration
  values are identical every time; only AGENT_TOKEN is new.

## Troubleshooting

| Symptom | Fix |
|---|---|
| UI: 404 `invalid_request_error` | `GATEWAY_BASE_URL` must not end in `/api/llm`; invoke path is `/api/llm/remote-agent/<name>` |
| Registration can't fetch agent card | agent service down, or endpoint auth enabled on it |
| `/mcp` returns 307 | normal — register with trailing slash `/mcp/` |
| Chat 401 | AGENT_TOKEN/USER_TOKEN wrong, expired, or stale after re-registering |
| Chat 403 | one of the 3 grants missing (or Act 4 revoke left in place!) |
| Agent 404 on MCP | `MCP_SERVER_NAME` ≠ registered name |
| Traces show user, not agent, downstream | `agent.py` must call `run_agent(user_text, None)` (agent-as-itself) — already in repo |
| Refunds "already refunded" | restart `payflow-mcp` to reset in-memory data |
