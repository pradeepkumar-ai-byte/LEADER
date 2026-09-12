"""
Leader – Microsoft AutoGen Framework Bridge Entrypoint

Provides both direct Python import interfaces and a REST server wrapper
for integrating AutoGen groupchats with LEADER safety middleware.
"""

import uvicorn
from fastapi import FastAPI, Request

from leader.bridges.autogen import (
    AUTOGEN_AVAILABLE,
    LeaderGroupChatManager,
)

app = FastAPI(title="Leader Microsoft AutoGen Bridge")
manager = LeaderGroupChatManager(groupchat=None)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "autogen_available": AUTOGEN_AVAILABLE,
        "bridge": "autogen",
    }


@app.post("/v1/autogen/intercept")
async def intercept(request: Request):
    """REST endpoint for AutoGen agents to validate messages."""
    data = await request.json()
    message = data.get("message", "")
    sender = data.get("sender", "agent")
    recipient = data.get("recipient", "group")
    allowed, response = manager.intercept_message(message, sender, recipient)
    return {
        "allowed": allowed,
        "response": response,
        "session_id": manager.chain_id,
        "terminated": manager.is_terminated,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
