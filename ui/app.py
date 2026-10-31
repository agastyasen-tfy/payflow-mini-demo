"""PayFlow mini demo — single-page chat UI.

One login (a demo user), one chat box. Every message is sent to the registered
agent THROUGH the TrueFoundry Agent Gateway:

    POST {GATEWAY_BASE_URL}/api/llm/remote-agent/{AGENT_NAME}
    Authorization: Bearer <user token>

so the Registry's access control is enforced and every hop shows up in traces.

Env vars:
  GATEWAY_BASE_URL  e.g. https://your-company.truefoundry.cloud
  AGENT_NAME        name of the agent in the Agent Registry, e.g. payflow-refunds-agent
  USER_TOKEN        the demo user's TrueFoundry token (personal access token)
  DEMO_PASSWORD     password for the fake login page (default: payflow)
  PORT              default 8080
"""
import os
import uuid

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

GATEWAY_BASE_URL = os.environ["GATEWAY_BASE_URL"].rstrip("/")
AGENT_NAME = os.environ.get("AGENT_NAME", "payflow-refunds-agent")
USER_TOKEN = os.environ["USER_TOKEN"]
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "payflow")
AGENT_URL = f"{GATEWAY_BASE_URL}/api/llm/remote-agent/{AGENT_NAME}"

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


async def index(_: Request):
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def login(request: Request):
    body = await request.json()
    ok = body.get("password") == DEMO_PASSWORD
    return JSONResponse({"ok": ok}, status_code=200 if ok else 401)


async def chat(request: Request):
    body = await request.json()
    text = (body.get("message") or "").strip()
    if not text:
        return JSONResponse({"error": "empty message"}, status_code=400)

    rpc = {
        "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "message/send",
        "params": {"message": {"kind": "message", "role": "user",
                               "messageId": str(uuid.uuid4()),
                               "parts": [{"kind": "text", "text": text}]}},
    }
    try:
        async with httpx.AsyncClient(timeout=90) as http:
            resp = await http.post(
                AGENT_URL, json=rpc,
                headers={"Authorization": f"Bearer {USER_TOKEN}"})
    except httpx.HTTPError as e:
        return JSONResponse({"reply": f"Network error reaching gateway: {e}",
                             "denied": True})

    if resp.status_code in (401, 403):
        return JSONResponse({"denied": True, "status": resp.status_code,
                             "reply": f"⛔ Gateway denied the call ({resp.status_code}): "
                                      f"{resp.text[:400]}"})
    if resp.status_code >= 400:
        return JSONResponse({"denied": True, "status": resp.status_code,
                             "reply": f"Gateway error {resp.status_code}: {resp.text[:400]}"})

    data = resp.json()
    try:
        parts = data["result"]["status"]["message"]["parts"]
        reply = " ".join(p.get("text", "") for p in parts)
        state = data["result"]["status"].get("state", "completed")
    except (KeyError, TypeError):
        reply, state = str(data)[:800], "unknown"
    return JSONResponse({"reply": reply, "state": state})


app = Starlette(routes=[
    Route("/", index),
    Route("/api/login", login, methods=["POST"]),
    Route("/api/chat", chat, methods=["POST"]),
])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
