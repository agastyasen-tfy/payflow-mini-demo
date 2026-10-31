"""PayFlow Refunds Agent — a minimal remote A2A agent.

- Exposes an A2A agent card at /.well-known/agent-card.json (register this URL
  in the TrueFoundry Agent Registry: Proxy via Gateway, Framework = A2A).
- On each message: runs an LLM tool-calling loop. The LLM is called via the
  TrueFoundry LLM Gateway and tools via the MCP Gateway — both calls carry the
  agent's identity in `x-tfy-agent-authorization` and the end user's token in
  `Authorization` (delegation / on-behalf-of pattern).

Env vars:
  GATEWAY_BASE_URL   e.g. https://your-company.truefoundry.cloud
  MODEL              e.g. openai-main/gpt-4o-mini
  MCP_SERVER_NAME    name of the MCP server on the gateway, e.g. payflow-transactions
  AGENT_TOKEN        TrueFoundry-backed agent identity token (Registry ⋮ → Get Token)
  USER_TOKEN         fallback user token if gateway doesn't pass one through
  PORT               default 8000
"""
import json
import os

import httpx
import uvicorn
from fastmcp import Client as MCPClient
from fastmcp.client.transports import StreamableHttpTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

GATEWAY_BASE_URL = os.environ["GATEWAY_BASE_URL"].rstrip("/")
MODEL = os.environ.get("MODEL", "openai-main/gpt-4o-mini")
MCP_SERVER_NAME = os.environ.get("MCP_SERVER_NAME", "payflow-transactions")
AGENT_TOKEN = os.environ["AGENT_TOKEN"]
PORT = int(os.environ.get("PORT", "8000"))

MCP_URL = f"{GATEWAY_BASE_URL}/api/llm/mcp/{MCP_SERVER_NAME}/server"
LLM_URL = f"{GATEWAY_BASE_URL}/api/llm/chat/completions"

SYSTEM_PROMPT = (
    "You are the PayFlow Refunds Agent. You help users look up transactions and "
    "issue refunds using the available tools. Be concise. Always confirm what you "
    "did, including transaction ids and amounts."
)

AGENT_CARD = {
    "protocolVersion": "0.2.6",
    "name": "payflow-refunds-agent",
    "description": "Looks up PayFlow transactions and issues refunds on behalf of the user.",
    "url": f"http://0.0.0.0:{PORT}/",  # overridden by PUBLIC_URL if set
    "version": "1.0.0",
    "capabilities": {"streaming": False},
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [{
        "id": "refunds",
        "name": "Transaction lookup & refunds",
        "description": "List/get transactions and issue refunds via the PayFlow MCP server.",
        "tags": ["payments", "refunds"],
    }],
}
if os.environ.get("PUBLIC_URL"):
    AGENT_CARD["url"] = os.environ["PUBLIC_URL"]


def _headers(user_token: str | None) -> dict:
    """Two-token pattern: user in Authorization, agent in x-tfy-agent-authorization.
    If there is no user token, the agent acts as itself."""
    if user_token:
        return {"Authorization": f"Bearer {user_token}",
                "x-tfy-agent-authorization": f"Bearer {AGENT_TOKEN}"}
    return {"Authorization": f"Bearer {AGENT_TOKEN}"}


async def run_agent(user_text: str, user_token: str | None) -> str:
    headers = _headers(user_token)
    transport = StreamableHttpTransport(url=MCP_URL, headers=headers)
    async with MCPClient(transport) as mcp:
        tools = await mcp.list_tools()
        openai_tools = [{
            "type": "function",
            "function": {"name": t.name, "description": t.description or "",
                         "parameters": t.inputSchema},
        } for t in tools]

        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text}]

        async with httpx.AsyncClient(timeout=60) as http:
            for _ in range(6):  # max tool-call rounds
                resp = await http.post(LLM_URL, headers=headers, json={
                    "model": MODEL, "messages": messages, "tools": openai_tools})
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]
                messages.append(msg)
                if not msg.get("tool_calls"):
                    return msg.get("content") or ""
                for tc in msg["tool_calls"]:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                    result = await mcp.call_tool(tc["function"]["name"], args)
                    content = "\n".join(
                        b.text for b in result.content if getattr(b, "text", None))
                    messages.append({"role": "tool", "tool_call_id": tc["id"],
                                     "content": content or "(empty)"})
        return "I hit the maximum number of tool-call rounds. Partial progress logged."


# ---- A2A protocol (JSON-RPC message/send) ----------------------------------

def _extract_text(a2a_message: dict) -> str:
    return " ".join(p.get("text", "") for p in a2a_message.get("parts", [])
                    if p.get("kind") == "text" or "text" in p).strip()


async def a2a_endpoint(request: Request) -> JSONResponse:
    body = await request.json()
    rpc_id = body.get("id")
    if body.get("method") not in ("message/send", "message/stream"):
        return JSONResponse({"jsonrpc": "2.0", "id": rpc_id,
                             "error": {"code": -32601, "message": "method not found"}},
                            status_code=200)
    user_text = _extract_text(body.get("params", {}).get("message", {}))

    # User token: passed through by the gateway (Token Passthrough) or env fallback.
    auth = request.headers.get("authorization", "")
    user_token = auth.removeprefix("Bearer ").strip() or os.environ.get("USER_TOKEN")

    try:
        answer = await run_agent(user_text, None)  # act as agent itself
        status, text = "completed", answer
    except httpx.HTTPStatusError as e:
        status = "failed"
        text = f"Gateway denied a call ({e.response.status_code}): {e.response.text[:500]}"
    except Exception as e:  # surface MCP 403s etc. in the demo
        status, text = "failed", f"Error: {e}"

    import uuid
    return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": {
        "id": str(uuid.uuid4()), "contextId": str(uuid.uuid4()), "kind": "task",
        "status": {"state": status,
                   "message": {"kind": "message", "role": "agent",
                               "messageId": str(uuid.uuid4()),
                               "parts": [{"kind": "text", "text": text}]}},
    }})


async def agent_card(_: Request) -> JSONResponse:
    return JSONResponse(AGENT_CARD)


app = Starlette(routes=[
    Route("/.well-known/agent-card.json", agent_card, methods=["GET"]),
    Route("/.well-known/agent.json", agent_card, methods=["GET"]),  # legacy path
    Route("/", a2a_endpoint, methods=["POST"]),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
