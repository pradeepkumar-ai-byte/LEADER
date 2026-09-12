"""
Leader – CrewAI Framework Bridge Entrypoint

Provides both direct Python import interfaces and a REST server wrapper
for integrating CrewAI task pipelines with LEADER safety middleware.
"""

import uvicorn
from fastapi import FastAPI, Request

from leader.bridges.crewai import (
    CREWAI_AVAILABLE,
    LeaderStepCallback,
    LeaderTaskCallback,
)

app = FastAPI(title="Leader CrewAI Bridge")
step_cb = LeaderStepCallback()
task_cb = LeaderTaskCallback()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "crewai_available": CREWAI_AVAILABLE,
        "bridge": "crewai",
    }


@app.post("/v1/crewai/step")
async def evaluate_step(request: Request):
    """REST endpoint to evaluate intermediate CrewAI agent step outputs."""
    data = await request.json()
    step_output = data.get("step_output", "")
    try:
        step_cb(step_output)
        return {
            "status": "ok",
            "interrupted": step_cb.is_interrupted,
            "session_id": step_cb.chain_id,
        }
    except Exception as exc:
        return {
            "status": "error",
            "interrupted": True,
            "error": str(exc),
            "session_id": step_cb.chain_id,
        }


@app.post("/v1/crewai/task")
async def evaluate_task(request: Request):
    """REST endpoint to validate finished CrewAI task outputs against exploit signatures."""
    data = await request.json()
    task_output = data.get("task_output", "")
    task_cb(task_output)
    return {
        "status": "ok",
        "violations": task_cb.violations_found,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
