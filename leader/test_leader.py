"""
Leader – tests. Run: pytest tests/ -v
"""

import asyncio
import copy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from leader.executor import Executor, _is_retryable
from leader.logger import TaskLogger
from leader.models import RouteDecision, Task, TaskCategory, TaskResult
from leader.registry import CATALOGUE, BackendSpec, Registry
from leader.router import Router, classify

# ── helpers ───────────────────────────────────────────────────────────────────


def fresh_registry(*connect_ids: str, extra_config: dict = None) -> Registry:
    """Return a Registry with a deep-copied catalogue so tests don't share state."""
    specs = {k: copy.deepcopy(v) for k, v in CATALOGUE.items()}
    r = Registry(extra=specs)
    # clear all connections first
    for s in r.all():
        s.connected = False
        s.config = {}
    # connect requested backends with stub config
    for bid in connect_ids:
        s = r.get(bid)
        if s:
            s.connected = True
            if bid == "direct_llm":
                s.config = {"provider": "anthropic", "api_key": "sk-test"}
            else:
                s.config = {"base_url": "http://localhost:9999"}
    if extra_config:
        for bid, cfg in extra_config.items():
            s = r.get(bid)
            if s:
                s.connected = True
                s.config = cfg
    return r


def make_router(r: Registry, tmp_path: Path) -> Router:
    logger = TaskLogger(tmp_path / "test.db")
    return Router(r, logger), logger


# ── classifier ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("send a whatsapp message to mom", TaskCategory.MESSAGING),
        ("write a python function to sort a list", TaskCategory.CODING),
        ("summarize the latest AI news", TaskCategory.RESEARCH),
        ("write a blog post about space travel", TaskCategory.CREATIVE),
        ("every day at 9am remind me to drink water", TaskCategory.AUTOMATION),
        ("coordinate three agents to build a report", TaskCategory.MULTIAGENT),
        ("analyse this csv file and plot a chart", TaskCategory.DATA),
        ("hello", TaskCategory.GENERAL),
    ],
)
def test_classify(prompt, expected):
    assert classify(prompt) == expected


# ── registry ──────────────────────────────────────────────────────────────────


def test_registry_empty_connected():
    r = fresh_registry()
    assert r.connected() == []


def test_registry_connect_backend():
    r = fresh_registry("openclaw")
    assert len(r.connected()) == 1
    assert r.connected()[0].id == "openclaw"


def test_registry_direct_llm_needs_api_key():
    r = fresh_registry()
    s = r.get("direct_llm")
    s.connected = True
    s.config = {"provider": "anthropic"}  # missing api_key
    assert r.connected() == []


def test_registry_missing_specialists_messaging():
    r = fresh_registry()  # nothing connected
    ids = [s.id for s in r.missing_specialists(TaskCategory.MESSAGING)]
    assert "openclaw" in ids
    assert "direct_llm" not in ids  # universal, not a specialist


def test_registry_custom_backend():
    r = fresh_registry()
    spec = BackendSpec(
        id="myagent",
        display_name="My Agent",
        description="test",
        strengths=[TaskCategory.CODING],
        weaknesses=[],
        homepage="",
        adapter_class="leader.adapters.generic_rest.GenericRestAdapter",
        connected=True,
        config={"base_url": "http://localhost:1234"},
    )
    r.register(spec)
    assert r.get("myagent") is not None
    assert any(s.id == "myagent" for s in r.connected())


# ── router ────────────────────────────────────────────────────────────────────


def test_router_no_backends(tmp_path):
    r = fresh_registry()
    router, _ = make_router(r, tmp_path)
    d = router.decide(Task(prompt="send a message"))
    assert d.primary == "none"


def test_router_picks_messaging_specialist(tmp_path):
    r = fresh_registry("openclaw", "hermes")
    router, _ = make_router(r, tmp_path)
    d = router.decide(Task(prompt="send a whatsapp message to my team"))
    assert d.primary == "openclaw"


def test_router_sets_category(tmp_path):
    r = fresh_registry("openclaw")
    router, _ = make_router(r, tmp_path)
    task = Task(prompt="write me a python script")
    router.decide(task)
    assert task.category == TaskCategory.CODING


def test_router_fallback_chain(tmp_path):
    r = fresh_registry("openclaw", "hermes", "direct_llm")
    router, _ = make_router(r, tmp_path)
    d = router.decide(Task(prompt="anything"))
    assert len(d.fallback_chain) == 2


def test_router_recommendation_for_missing(tmp_path):
    # Only hermes connected; openclaw (messaging specialist) not connected
    r = fresh_registry("hermes")
    router, _ = make_router(r, tmp_path)
    d = router.decide(Task(prompt="send a telegram notification"))
    assert d.recommendation is not None


def test_router_evolves_with_history(tmp_path):
    r = fresh_registry("openclaw", "hermes")
    logger = TaskLogger(tmp_path / "test.db")

    # hermes wins on research 5/5
    for _ in range(5):
        task = Task(prompt="research x", category=TaskCategory.RESEARCH)
        d = RouteDecision(primary="hermes", fallback_chain=[], rationale="t")
        logger.log_dispatch(task, d)
        logger.log_result(
            TaskResult(
                task_id=task.task_id, backend_id="hermes", output="ok", success=True, latency_ms=100
            )
        )
    # openclaw fails on research 5/5
    for _ in range(5):
        task = Task(prompt="research x", category=TaskCategory.RESEARCH)
        d = RouteDecision(primary="openclaw", fallback_chain=[], rationale="t")
        logger.log_dispatch(task, d)
        logger.log_result(
            TaskResult(
                task_id=task.task_id,
                backend_id="openclaw",
                output="",
                success=False,
                latency_ms=100,
            )
        )

    router = Router(r, logger)
    decision = router.decide(Task(prompt="find latest research papers"))
    assert decision.primary == "hermes"


# ── executor ──────────────────────────────────────────────────────────────────


def test_executor_no_backends(tmp_path):
    r = fresh_registry()
    executor = Executor(r)
    d = RouteDecision(primary="none", fallback_chain=[], rationale="none")
    result = asyncio.run(executor.run(Task(prompt="hello"), d))
    assert not result.success
    assert "No backends connected" in result.error


def test_executor_unreachable_fails_gracefully(tmp_path):
    r = fresh_registry("openclaw")
    r.get("openclaw").config = {"base_url": "http://localhost:1"}
    executor = Executor(r, timeout=2)
    d = RouteDecision(primary="openclaw", fallback_chain=[], rationale="test")
    result = asyncio.run(executor.run(Task(prompt="hello"), d))
    assert not result.success  # fails gracefully


def test_executor_falls_back_to_second(tmp_path):
    r = fresh_registry("openclaw")
    r.get("openclaw").config = {"base_url": "http://localhost:1"}  # dead
    # direct_llm also misconfigured
    s = r.get("direct_llm")
    s.connected = True
    s.config = {}  # missing api_key — won't be in connected()

    executor = Executor(r, timeout=2)
    d = RouteDecision(primary="openclaw", fallback_chain=["direct_llm"], rationale="test")
    result = asyncio.run(executor.run(Task(prompt="hello"), d))
    assert not result.success  # both fail gracefully


# ── logger ────────────────────────────────────────────────────────────────────


def test_logger_win_rate_success(tmp_path):
    logger = TaskLogger(tmp_path / "test.db")
    task = Task(prompt="x", category=TaskCategory.CODING)
    logger.log_dispatch(task, RouteDecision(primary="openclaw", fallback_chain=[], rationale="t"))
    logger.log_result(
        TaskResult(
            task_id=task.task_id, backend_id="openclaw", output="ok", success=True, latency_ms=100
        )
    )
    assert logger.win_rates()["openclaw"]["coding"] == 1.0


def test_logger_win_rate_mixed(tmp_path):
    logger = TaskLogger(tmp_path / "test.db")
    for i, success in enumerate([True, True, False, False]):
        task = Task(prompt="x", category=TaskCategory.CODING, task_id=f"t{i}")
        logger.log_dispatch(
            task, RouteDecision(primary="zeroclaw", fallback_chain=[], rationale="t")
        )
        logger.log_result(
            TaskResult(
                task_id=task.task_id,
                backend_id="zeroclaw",
                output="",
                success=success,
                latency_ms=50,
            )
        )
    assert logger.win_rates()["zeroclaw"]["coding"] == 0.5


def test_logger_feedback(tmp_path):
    logger = TaskLogger(tmp_path / "test.db")
    logger.log_feedback("task123", 5, "perfect")
    cur = logger.conn.execute("SELECT rating FROM feedback WHERE task_id='task123'")
    assert cur.fetchone()[0] == 5


# ── retry / backoff ──────────────────────────────────────────────────────────
# These tests exercise the executor's smart retry logic.  We mock adapters at
# the _load_adapter level to inject controlled failures and count invocations.


def _make_mock_adapter(side_effects):
    """Create a mock adapter whose .run() yields *side_effects* in order."""
    adapter = MagicMock()
    adapter.is_available.return_value = True
    adapter.run = AsyncMock(side_effect=side_effects)
    return adapter


def test_retry_transient_error_is_retried(tmp_path):
    """A ConnectionError (transient) should be retried up to max_retries."""
    r = fresh_registry("openclaw")
    adapter = _make_mock_adapter(
        [
            ConnectionError("connection refused"),
            ConnectionError("connection refused"),
            TaskResult(
                task_id="t1", backend_id="openclaw", output="ok", success=True, latency_ms=50
            ),
        ]
    )
    executor = Executor(r, timeout=5, max_retries=3)
    task = Task(prompt="write code", category=TaskCategory.CODING)
    d = RouteDecision(primary="openclaw", fallback_chain=[], rationale="test")

    with (
        patch("leader.executor._load_adapter", return_value=adapter),
        patch("leader.executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(executor.run(task, d))

    assert result.success
    assert adapter.run.call_count == 3  # called 3 times total


def test_retry_programming_bug_fails_fast(tmp_path):
    """A TypeError (programming bug) must NOT be retried — fail immediately."""
    r = fresh_registry("openclaw")
    adapter = _make_mock_adapter([TypeError("bad argument")])
    executor = Executor(r, timeout=5, max_retries=3)
    task = Task(prompt="write code", category=TaskCategory.CODING)
    d = RouteDecision(primary="openclaw", fallback_chain=[], rationale="test")

    with (
        patch("leader.executor._load_adapter", return_value=adapter),
        patch("leader.executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(executor.run(task, d))

    assert not result.success
    assert "bad argument" in result.error
    assert adapter.run.call_count == 1  # failed fast, no retries


def test_retry_valueerror_fails_fast(tmp_path):
    """A ValueError (config/logic error) must NOT be retried."""
    r = fresh_registry("openclaw")
    adapter = _make_mock_adapter([ValueError("invalid config")])
    executor = Executor(r, timeout=5, max_retries=3)
    task = Task(prompt="research papers", category=TaskCategory.RESEARCH)
    d = RouteDecision(primary="openclaw", fallback_chain=[], rationale="test")

    with (
        patch("leader.executor._load_adapter", return_value=adapter),
        patch("leader.executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(executor.run(task, d))

    assert not result.success
    assert adapter.run.call_count == 1


def test_retry_messaging_never_retries(tmp_path):
    """MESSAGING tasks must never retry — even on transient errors — to prevent
    double-sending notifications/messages."""
    r = fresh_registry("openclaw")
    adapter = _make_mock_adapter([ConnectionError("network blip")])
    executor = Executor(r, timeout=5, max_retries=3)
    task = Task(prompt="send a slack message", category=TaskCategory.MESSAGING)
    d = RouteDecision(primary="openclaw", fallback_chain=[], rationale="test")

    with (
        patch("leader.executor._load_adapter", return_value=adapter),
        patch("leader.executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(executor.run(task, d))

    assert not result.success
    assert adapter.run.call_count == 1  # no retry for side-effecting category


def test_retry_automation_never_retries(tmp_path):
    """AUTOMATION tasks (webhooks, cron triggers) must never retry."""
    r = fresh_registry("openclaw")
    adapter = _make_mock_adapter([OSError("broken pipe")])
    executor = Executor(r, timeout=5, max_retries=3)
    task = Task(prompt="schedule daily report", category=TaskCategory.AUTOMATION)
    d = RouteDecision(primary="openclaw", fallback_chain=[], rationale="test")

    with (
        patch("leader.executor._load_adapter", return_value=adapter),
        patch("leader.executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(executor.run(task, d))

    assert not result.success
    assert adapter.run.call_count == 1


def test_retry_exhaustion_reports_all_attempts(tmp_path):
    """When all retries are exhausted, error message must mention attempt count."""
    r = fresh_registry("openclaw")
    adapter = _make_mock_adapter(
        [
            ConnectionError("fail 1"),
            ConnectionError("fail 2"),
            ConnectionError("fail 3"),
        ]
    )
    executor = Executor(r, timeout=5, max_retries=3)
    task = Task(prompt="write code", category=TaskCategory.CODING)
    d = RouteDecision(primary="openclaw", fallback_chain=[], rationale="test")

    with (
        patch("leader.executor._load_adapter", return_value=adapter),
        patch("leader.executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(executor.run(task, d))

    assert not result.success
    assert "All 3 attempts failed" in result.error
    assert adapter.run.call_count == 3


def test_is_retryable_helper():
    """Unit test for the _is_retryable classification function."""
    coding_task = Task(prompt="code", category=TaskCategory.CODING)
    msg_task = Task(prompt="send msg", category=TaskCategory.MESSAGING)

    # Transient + safe category → retryable
    assert _is_retryable(ConnectionError(), coding_task) is True
    assert _is_retryable(OSError(), coding_task) is True
    assert _is_retryable(asyncio.TimeoutError(), coding_task) is True

    # Programming bug → never retryable
    assert _is_retryable(TypeError(), coding_task) is False
    assert _is_retryable(ValueError(), coding_task) is False
    assert _is_retryable(KeyError(), coding_task) is False

    # Transient + side-effecting category → never retryable
    assert _is_retryable(ConnectionError(), msg_task) is False
    assert _is_retryable(OSError(), msg_task) is False
