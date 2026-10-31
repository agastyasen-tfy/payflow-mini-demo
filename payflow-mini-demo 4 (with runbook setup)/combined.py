"""Single-port runner: agent (/) + MCP server (/mcp) on one port.

Lets everything sit behind ONE tunnel:
  https://<tunnel>/                      -> A2A agent
  https://<tunnel>/.well-known/...      -> agent card
  https://<tunnel>/mcp                   -> MCP server (register this + /mcp on MCP Gateway)

Env: same as agent.py (GATEWAY_BASE_URL, AGENT_TOKEN, MODEL, MCP_SERVER_NAME,
PUBLIC_URL, USER_TOKEN). PORT defaults to 8000.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp-server"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent"))

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from server import mcp              # mcp-server/server.py  (FastMCP instance)
import agent as agent_module        # agent/agent.py        (Starlette app)

mcp_app = mcp.http_app(path="/")    # serves MCP at mount point

app = Starlette(
    routes=[Mount("/mcp", app=mcp_app)] + list(agent_module.app.routes),
    lifespan=mcp_app.lifespan,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
