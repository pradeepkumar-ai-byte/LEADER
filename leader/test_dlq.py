"""
Tests for Leader Dead-Letter Queue (DLQ), failure isolation, and replay workflows.
"""

import pytest
from aiohttp.test_utils import TestClient, TestServer

from leader.logger import SCHEMA_VERSION, TaskLogger
from leader.models import TaskResult
from leader.sdk import Leader
from leader.server import create_app


def test_schema_version_and_migration(tmp_path):
    db_file = tmp_path / "test_migration.db"

    # Initialize logger which runs migrations up to SCHEMA_VERSION 4
    logger = TaskLogger(db_path=db_file)
    assert logger._get_version() == 4
    assert SCHEMA_VERSION == 4

    # Verify dead_letters table structure
    cur = logger.conn.execute("PRAGMA table_info(dead_letters)")
    cols = {row[1]: row[2] for row in cur.fetchall()}
    assert "dead_letter_id" in cols
    assert "task_id" in cols
    assert "prompt" in cols
    assert "failed_backends" in cols
    assert "error_summary" in cols
    assert "retry_count" in cols
    assert "resolved" in cols


def test_logger_dlq_crud(tmp_path):
    db_file = tmp_path / "test_dlq_crud.db"
    logger = TaskLogger(db_path=db_file)

    # Log a dead letter
    logger.log_dead_letter(
        dead_letter_id="dlq_123",
        task_id="task_abc",
        prompt="Process quarterly transaction dataset",
        category="data",
        failed_backends=["direct_llm", "bedrock"],
        error_summary="503 Service Unavailable: All downstream endpoints timed out",
        failure_stage="executor_exhausted",
    )

    # Retrieve all
    all_dlq = logger.get_dead_letters()
    assert len(all_dlq) == 1
    item = all_dlq[0]
    assert item["dead_letter_id"] == "dlq_123"
    assert item["task_id"] == "task_abc"
    assert item["prompt"] == "Process quarterly transaction dataset"
    assert item["category"] == "data"
    assert item["failed_backends"] == ["direct_llm", "bedrock"]
    assert item["resolved"] is False
    assert item["retry_count"] == 0

    # Retrieve single
    single = logger.get_dead_letter("dlq_123")
    assert single is not None
    assert single["dead_letter_id"] == "dlq_123"

    # Non-existent
    assert logger.get_dead_letter("dlq_nonexistent") is None

    # Increment retry
    logger.increment_dead_letter_retry("dlq_123")
    assert logger.get_dead_letter("dlq_123")["retry_count"] == 1

    # Filter unresolved
    unresolved = logger.get_dead_letters(resolved=False)
    assert len(unresolved) == 1

    resolved = logger.get_dead_letters(resolved=True)
    assert len(resolved) == 0

    # Resolve dead letter
    success = logger.resolve_dead_letter("dlq_123")
    assert success is True

    # Check updated resolution
    updated = logger.get_dead_letter("dlq_123")
    assert updated["resolved"] is True
    assert updated["resolved_at"] is not None

    resolved_list = logger.get_dead_letters(resolved=True)
    assert len(resolved_list) == 1


@pytest.mark.asyncio
async def test_sdk_auto_dead_lettering_on_failure(tmp_path, monkeypatch):
    leader = Leader(auto_load_config=False)
    leader.logger = TaskLogger(db_path=tmp_path / "sdk_dlq.db")

    # Force executor run to return failed result
    async def mock_run_fail(task, decision, parallel=False):
        return TaskResult(
            task_id=task.task_id,
            backend_id="none",
            output="",
            success=False,
            latency_ms=10.0,
            error="Connection refused on all backends",
        )

    monkeypatch.setattr(leader.executor, "run", mock_run_fail)

    result = await leader.run("Perform complex calculation", category="coding")
    assert result.success is False

    dlq_items = leader.get_dead_letters(resolved=False)
    assert len(dlq_items) == 1
    assert dlq_items[0]["prompt"] == "Perform complex calculation"
    assert dlq_items[0]["category"] == "coding"
    assert "Connection refused" in dlq_items[0]["error_summary"]


@pytest.mark.asyncio
async def test_sdk_replay_dead_letter(tmp_path, monkeypatch):
    leader = Leader(auto_load_config=False)
    leader.logger = TaskLogger(db_path=tmp_path / "sdk_replay.db")

    leader.logger.log_dead_letter(
        dead_letter_id="dlq_replay_1",
        task_id="task_fail",
        prompt="Write a Python quicksort",
        category="coding",
        failed_backends=["direct_llm"],
        error_summary="500 Internal Server Error",
    )

    # Mock successful run on retry
    async def mock_run_success(task, decision, parallel=False):
        return TaskResult(
            task_id=task.task_id,
            backend_id="direct_llm",
            output="def quicksort(arr): return arr",
            success=True,
            latency_ms=45.0,
        )

    monkeypatch.setattr(leader.executor, "run", mock_run_success)

    # Replay
    result = await leader.replay_dead_letter("dlq_replay_1")
    assert result.success is True
    assert "quicksort" in result.output

    # Verify DLQ item marked resolved
    item = leader.get_dead_letter("dlq_replay_1")
    assert item["resolved"] is True
    assert item["retry_count"] == 1


@pytest.mark.asyncio
async def test_server_dlq_api_endpoints(tmp_path, monkeypatch):
    app = create_app()
    app["leader"].logger = TaskLogger(db_path=tmp_path / "server_dlq.db")
    leader = app["leader"]

    leader.logger.log_dead_letter(
        dead_letter_id="dlq_api_test",
        task_id="t_api_1",
        prompt="Summarize whitepaper",
        category="research",
        failed_backends=["direct_llm"],
        error_summary="Rate limit exceeded",
    )

    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        # GET /api/dlq
        resp = await client.get("/api/dlq")
        assert resp.status == 200
        data = await resp.json()
        assert data["count"] == 1
        assert data["dead_letters"][0]["dead_letter_id"] == "dlq_api_test"

        # POST /api/dlq/resolve
        resp_resolve = await client.post(
            "/api/dlq/resolve", json={"dead_letter_id": "dlq_api_test"}
        )
        assert resp_resolve.status == 200
        data_resolve = await resp_resolve.json()
        assert data_resolve["status"] == "resolved"

        # Check resolution via GET /api/dlq?resolved=true
        resp_resolved = await client.get("/api/dlq?resolved=true")
        assert resp_resolved.status == 200
        data_resolved = await resp_resolved.json()
        assert data_resolved["count"] == 1
    finally:
        await client.close()
