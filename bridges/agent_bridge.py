from fastapi import FastAPI, Request
import uvicorn

app = FastAPI(title="Leader Mock Agent Bridge")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/execute")
async def execute_v1(request: Request):
    # Handles BabyAGI, TaskWeaver REST signatures
    data = await request.json()
    prompt = data.get("objective") or data.get("task") or "task"
    return {"result": f"[Mock Agent Bridge] Successfully executed objective/task: '{prompt}'"}


@app.post("/api/agent/execute")
async def execute_agentgpt(request: Request):
    # Handles AgentGPT REST signatures
    data = await request.json()
    prompt = data.get("goal") or "goal"
    return {"result": f"[Mock Agent Bridge] AgentGPT completed goal: '{prompt}'"}


@app.post("/api/run")
async def run_api(request: Request):
    # Handles MetaGPT, Hermes, Generic REST signatures
    data = await request.json()
    prompt = data.get("requirement") or data.get("task") or "task"
    return {"result": f"[Mock Agent Bridge] Completed execution: '{prompt}'"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
