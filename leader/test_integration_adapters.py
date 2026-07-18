import time
from threading import Thread

import pytest
import requests
import uvicorn

from bridges.agent_bridge import app
from leader.executor import Executor
from leader.models import Task, TaskCategory
from leader.registry import Registry
from leader.router import Router

# Spin up uvicorn server in a background thread
PORT = 8989
SERVER_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="module", autouse=True)
def run_mock_server():
    """Start uvicorn server in background thread for real HTTP integration tests."""
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to become healthy
    t0 = time.time()
    while time.time() - t0 < 5.0:
        try:
            resp = requests.get(f"{SERVER_URL}/health", timeout=1.0)
            if resp.status_code == 200:
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.1)
    else:
        pytest.fail("Mock bridge server failed to start.")

    yield

    # Server will stop when the daemon thread exits at test teardown


@pytest.mark.asyncio
async def test_hermes_adapter_integration():
    """Test HermesAdapter against a real running HTTP endpoint."""
    registry = Registry()
    hermes_spec = registry.get("hermes")
    assert hermes_spec is not None

    # Connect Hermes adapter to the real running server
    hermes_spec.connected = True
    hermes_spec.config = {
        "base_url": SERVER_URL,
        "api_key": "test-key-123",
    }

    # Load adapter dynamically
    from leader.executor import _load_adapter

    adapter = _load_adapter("hermes", registry)
    assert adapter is not None
    assert adapter.is_available()

    task = Task(prompt="Audit database schema", category=TaskCategory.CODING)
    result = await adapter.run(task)

    assert result.success
    assert result.backend_id == "hermes"
    assert "Completed execution: 'Audit database schema'" in result.output
    assert result.latency_ms > 0
    assert not result.error


@pytest.mark.asyncio
async def test_babyagi_adapter_integration():
    """Test BabyAGIAdapter against a real running HTTP endpoint."""
    registry = Registry()
    babyagi_spec = registry.get("babyagi")
    assert babyagi_spec is not None

    babyagi_spec.connected = True
    babyagi_spec.config = {
        "base_url": SERVER_URL,
        "api_key": "test-key-123",
    }

    from leader.executor import _load_adapter

    adapter = _load_adapter("babyagi", registry)
    assert adapter is not None
    assert adapter.is_available()

    task = Task(prompt="Find user profile trends", category=TaskCategory.RESEARCH)
    result = await adapter.run(task)

    assert result.success
    assert result.backend_id == "babyagi"
    assert "Successfully executed objective/task: 'Find user profile trends'" in result.output
    assert not result.error


@pytest.mark.asyncio
async def test_agentgpt_adapter_integration():
    """Test AgentGPTAdapter against a real running HTTP endpoint."""
    registry = Registry()
    agentgpt_spec = registry.get("agentgpt")
    assert agentgpt_spec is not None

    agentgpt_spec.connected = True
    agentgpt_spec.config = {
        "base_url": SERVER_URL,
    }

    from leader.executor import _load_adapter

    adapter = _load_adapter("agentgpt", registry)
    assert adapter is not None
    assert adapter.is_available()

    task = Task(prompt="Plan marketing launch", category=TaskCategory.CREATIVE)
    result = await adapter.run(task)

    assert result.success
    assert result.backend_id == "agentgpt"
    assert "AgentGPT completed goal: 'Plan marketing launch'" in result.output
    assert not result.error


@pytest.mark.asyncio
async def test_end_to_end_routed_rest_execution():
    """Test the full router-executor pipeline with connected REST backends."""
    registry = Registry()

    # Disable default built-in direct_llm to force routing to specialist
    direct_llm_spec = registry.get("direct_llm")
    if direct_llm_spec:
        direct_llm_spec.connected = False

    # Connect hermes to the server
    hermes_spec = registry.get("hermes")
    if hermes_spec:
        hermes_spec.connected = True
        hermes_spec.config = {"base_url": SERVER_URL}

    # Route a research task - hermes is a specialist for RESEARCH
    task = Task(prompt="Research market competitors", category=TaskCategory.RESEARCH)

    from leader.logger import TaskLogger

    # Create dummy in-memory db logger
    logger = TaskLogger(db_path=None)
    router = Router(registry, logger)
    executor = Executor(registry)

    decision = router.decide(task)
    assert decision.primary == "hermes"

    result = await executor.run(task, decision)
    assert result.success
    assert result.backend_id == "hermes"
    assert "Completed execution: 'Research market competitors'" in result.output
