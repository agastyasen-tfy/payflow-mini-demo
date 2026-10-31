# PayFlow Mini — Agent Identity & Registry Demo

A deliberately tiny demo of TrueFoundry **Agent Identity**, **Agent Registry**,
**MCP Gateway**, **access control**, and **tracing** — one agent, one MCP server,
one model, one login.

```
┌─────────────┐   A2A (JSON-RPC)   ┌──────────────────────┐   proxy    ┌──────────────────┐
│  Chat UI    │ ─────────────────▶ │  TrueFoundry Gateway │ ─────────▶ │ Refunds Agent    │
│ (demo user) │   user token       │  /api/llm/agent/...  │            │ (A2A, Starlette) │
└─────────────┘                    └──────────────────────┘            └────────┬─────────┘
                                                                                │ user token +
                                                                                │ x-tfy-agent-authorization
                                                             ┌──────────────────┴──────────────┐
                                                             ▼                                 ▼
                                                   LLM Gateway (chat/completions)   MCP Gateway (/mcp/.../server)
                                                             │                                 │
                                                             ▼                                 ▼
                                                     openai-main/gpt-4o-mini         payflow-transactions MCP
```

## Components

| Dir | What | Port |
|---|---|---|
| `mcp-server/` | FastMCP server: `list_transactions`, `get_transaction`, `issue_refund` | 8001 |
| `agent/` | Remote A2A agent (`payflow-refunds-agent`): agent card + LLM tool-calling loop, all calls via the gateway with agent identity | 8000 |
| `ui/` | Single-page chat UI with one fake login; forwards to the agent **through the Agent Gateway** | 8080 |

## Setup

### 1. Deploy the MCP server and the agent
Deploy `mcp-server/` and `agent/` anywhere reachable by the gateway (e.g. two small
TrueFoundry Services). `pip install -r requirements.txt && python server.py / agent.py`.

### 2. Register the MCP server (MCP Gateway → Add Server)
- Type: any remote server · URL: `https://<mcp-host>/mcp` · Transport: streamable HTTP
- Auth: No auth (demo) or API key. Name it `payflow-transactions`.

### 3. Register the agent (Agent Registry → Register Agent)
- Name: `payflow-refunds-agent` · Config: **Proxy via Gateway**, Framework **A2A**,
  URL: `https://<agent-host>`, Agent Card Endpoint: `/.well-known/agent-card.json`
- An **Agent Identity** is created automatically. Fetch its token: agent row → ⋮ → **Get Token**.

### 4. Grant least-privilege access (the access-control story)
- On `payflow-transactions` MCP server: add collaborator `agent:payflow-refunds-agent`
  with role **MCP Server User**.
- On the model provider account (e.g. `openai-main`): add the same agent as collaborator.
- On the agent: give the demo user **Agent Access** (so they may invoke it).

### 5. Configure env vars

Agent (`agent/agent.py`):
```
GATEWAY_BASE_URL=https://your-company.truefoundry.cloud
MODEL=openai-main/gpt-4o-mini
MCP_SERVER_NAME=payflow-transactions
AGENT_TOKEN=<from Registry ⋮ → Get Token>
USER_TOKEN=<demo user PAT — fallback if gateway doesn't pass the user token through>
PUBLIC_URL=https://<agent-host>/
```

UI (`ui/app.py`):
```
GATEWAY_BASE_URL=https://your-company.truefoundry.cloud
AGENT_NAME=payflow-refunds-agent
USER_TOKEN=<demo user personal access token>
DEMO_PASSWORD=payflow
```

## Demo runbook (~8 minutes)

1. **Registry** — show `payflow-refunds-agent` in the Agent Registry: metadata,
   its 1:1 **Agent Identity**, A2A config. *"Nothing acts anonymously."*
2. **Chat** — log in to the UI, ask: *"Show transactions for cust_42"*, then
   *"Refund txn_1002, reason: duplicate charge"*. The agent calls the LLM and
   MCP tools through the gateway with its identity attached.
3. **Traces** — AI Monitoring → Request Traces: show the same request end-to-end —
   agent invocation (A2A), the LLM call, and each MCP `tools/call` — all attributed
   to `payflow-refunds-agent` acting for the demo user.
4. **Access control (live revoke)** — remove `agent:payflow-refunds-agent` from the
   MCP server's collaborators. Ask for a refund again → the UI shows a red
   **⛔ 403** bubble. Re-add the grant → it works again. No code changes, no redeploys.
5. **(Optional)** Call the gateway agent endpoint with no/invalid token via curl → 401,
   showing the registry as an enforcement point.

## Smoke-test locally (no gateway)
`python mcp-server/server.py` then point the agent's `MCP_URL` logic at it directly
to validate tools before wiring the gateway.
