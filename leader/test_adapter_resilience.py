"""
Tests for Adapter Maturity Tiers, TCP Connection Pooling, Exponential Backoff, and Health Probes.
"""

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from leader.adapters.base import BaseAdapter
from leader.adapters.direct_llm import DirectLLMAdapter
from leader.models import Task, TaskCategory, TaskResult
from leader.registry import AdapterTier, Registry


class SampleTestAdapter(BaseAdapter):
    def __init__(self, endpoint: str = "http://127.0.0.1:8080", is_avail: bool = True):
        super().__init__(
            config={
                "base_url": endpoint,
                "id": "sample_test",
                "max_retries": 2,
                "base_backoff_s": 0.01,
            }
        )
        self.endpoint = endpoint
        self._avail = is_avail
        self.attempts = 0

    def is_available(self) -> bool:
        return self._avail

    async def run(self, task: Task) -> TaskResult:
        self.attempts += 1
        if self.attempts < 3:
            return TaskResult(
                task_id=task.task_id,
                backend_id=self.id,
                output="",
                success=False,
                latency_ms=5.0,
                error="HTTP 429 RateLimit: Too Many Requests",
            )
        return TaskResult(
            task_id=task.task_id,
            backend_id=self.id,
            output="Successful task output",
            success=True,
            latency_ms=10.0,
        )


class FailingTestAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(config={"id": "failing_test", "max_retries": 1, "base_backoff_s": 0.01})

    def is_available(self) -> bool:
        return True

    async def run(self, task: Task) -> TaskResult:
        return TaskResult(
            task_id=task.task_id,
            backend_id=self.id,
            output="",
            success=False,
            latency_ms=5.0,
            error="HTTP 503 Overloaded",
        )


def test_catalogue_adapter_tiers():
    """Verify all catalogue backends have an explicit AdapterTier defined."""
    reg = Registry()
    all_specs = reg.all()
    assert len(all_specs) >= 30

    tier_counts = {
        AdapterTier.TIER_1_NATIVE: 0,
        AdapterTier.TIER_2_PROTOCOL: 0,
        AdapterTier.TIER_3_WEBHOOK: 0,
    }
    for spec in all_specs:
        assert isinstance(spec.tier, AdapterTier)
        tier_counts[spec.tier] += 1

    # Tier 1 Native backends (direct_llm, autogen, crewai, litellm, azureopenai, vertexai, bedrock)
    assert tier_counts[AdapterTier.TIER_1_NATIVE] >= 7
    # Tier 2 Protocol backends
    assert tier_counts[AdapterTier.TIER_2_PROTOCOL] >= 15
    # Tier 3 Webhook backends
    assert tier_counts[AdapterTier.TIER_3_WEBHOOK] >= 3


@pytest.mark.asyncio
async def test_base_adapter_connection_pooling():
    adapter = SampleTestAdapter()
    try:
        session1 = await adapter.get_session()
        session2 = await adapter.get_session()
        assert session1 is session2
        assert isinstance(session1.connector, aiohttp.TCPConnector)
        assert not session1.closed
    finally:
        await adapter.close()
        assert session1.closed


@pytest.mark.asyncio
async def test_exponential_backoff_retry_success():
    adapter = SampleTestAdapter()
    task = Task(prompt="Test task payload", category=TaskCategory.CODING)

    try:
        res = await adapter.run_with_retry(task)
        assert res.success is True
        assert res.output == "Successful task output"
        assert adapter.attempts == 3
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_exponential_backoff_retry_exhausted():
    adapter = FailingTestAdapter()
    task = Task(prompt="Test permanent failing task", category=TaskCategory.CODING)

    try:
        res = await adapter.run_with_retry(task)
        assert res.success is False
        assert "503 Overloaded" in res.error
    finally:
        await adapter.close()


@pytest.mark.asyncio
async def test_health_check_async():
    # Setup a mock server
    app = web.Application()

    async def health_handler(request):
        return web.Response(text="healthy", status=200)

    app.router.add_get("/health", health_handler)
    server = TestServer(app)
    await server.start_server()

    adapter_healthy = SampleTestAdapter(endpoint=f"http://127.0.0.1:{server.port}/health")
    adapter_dead = SampleTestAdapter(endpoint="http://127.0.0.1:1")  # unreachable port

    try:
        assert await adapter_healthy.health_check_async() is True
        assert await adapter_dead.health_check_async() is False
    finally:
        await adapter_healthy.close()
        await adapter_dead.close()
        await server.close()


@pytest.mark.asyncio
async def test_direct_llm_adapter_session_reuse():
    # Use valid CI test key conforming to regex
    adapter = DirectLLMAdapter(config={"api_key": "sk-ant-testkey-12345", "provider": "anthropic"})
    try:
        s1 = await adapter.get_session()
        s2 = await adapter.get_session()
        assert s1 is s2
        assert not s1.closed
    finally:
        await adapter.close()
        assert s1.closed
