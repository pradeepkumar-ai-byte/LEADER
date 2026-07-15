"""
Leader – tests. Run: pytest tests/ -v
"""
import pytest
import asyncio
import copy
import tempfile
from pathlib import Path

from leader.models import Task, TaskCategory, RouteDecision, TaskResult
from leader.router import classify, Router
from leader.registry import Registry, BackendSpec, CATALOGUE
from leader.logger import TaskLogger
from leader.executor import Executor


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

@pytest.mark.parametrize("prompt,expected", [
    ("send a whatsapp message to mom",              TaskCategory.MESSAGING),
    ("write a python function to sort a list",      TaskCategory.CODING),
    ("summarize the latest AI news",                TaskCategory.RESEARCH),
    ("write a blog post about space travel",        TaskCategory.CREATIVE),
    ("every day at 9am remind me to drink water",   TaskCategory.AUTOMATION),
    ("coordinate three agents to build a report",   TaskCategory.MULTIAGENT),
    ("analyse this csv file and plot a chart",      TaskCategory.DATA),
    ("hello",                                       TaskCategory.GENERAL),
])
def test_classify(prompt, expected):
    assert classify(prompt) == expected


# ── registry ──────────────────────────────────────────────────────────────────

def test_registry_empty_connected():
    r = fresh_registry()
    assert r.connected() == []

def test_registry_connect_backend():
    r = fresh_registry("n8n")
    assert len(r.connected()) == 1
    assert r.connected()[0].id == "n8n"

def test_registry_direct_llm_needs_api_key():
    r = fresh_registry()
    s = r.get("direct_llm")
    s.connected = True
    s.config = {"provider": "anthropic"}  # missing api_key
    assert r.connected() == []

def test_registry_missing_specialists_messaging():
    r = fresh_registry()  # nothing connected
    ids = [s.id for s in r.missing_specialists(TaskCategory.MESSAGING)]
    assert "n8n" in ids
    assert "direct_llm" not in ids  # universal, not a specialist

def test_registry_custom_backend():
    r = fresh_registry()
    spec = BackendSpec(
        id="myagent", display_name="My Agent", description="test",
        strengths=[TaskCategory.CODING], weaknesses=[],
        homepage="", adapter_class="leader.adapters.generic_rest.GenericRestAdapter",
        connected=True, config={"base_url": "http://localhost:1234"},
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
    r = fresh_registry("n8n", "autogen")
    router, _ = make_router(r, tmp_path)
    d = router.decide(Task(prompt="send a whatsapp message to my team"))
    assert d.primary == "n8n"

def test_router_sets_category(tmp_path):
    r = fresh_registry("n8n")
    router, _ = make_router(r, tmp_path)
    task = Task(prompt="write me a python script")
    router.decide(task)
    assert task.category == TaskCategory.CODING

def test_router_fallback_chain(tmp_path):
    r = fresh_registry("n8n", "autogen", "direct_llm")
    router, _ = make_router(r, tmp_path)
    d = router.decide(Task(prompt="anything"))
    assert len(d.fallback_chain) == 2

def test_router_recommendation_for_missing(tmp_path):
    # Only autogen connected; n8n (messaging specialist) not connected
    r = fresh_registry("autogen")
    router, _ = make_router(r, tmp_path)
    d = router.decide(Task(prompt="send a telegram notification"))
    assert d.recommendation is not None

def test_router_evolves_with_history(tmp_path):
    r = fresh_registry("n8n", "autogen")
    logger = TaskLogger(tmp_path / "test.db")

    # autogen wins on research 5/5
    for _ in range(5):
        task = Task(prompt="research x", category=TaskCategory.RESEARCH)
        d = RouteDecision(primary="autogen", fallback_chain=[], rationale="t")
        logger.log_dispatch(task, d)
        logger.log_result(TaskResult(task_id=task.task_id, backend_id="autogen",
                                     output="ok", success=True, latency_ms=100))
    # n8n fails on research 5/5
    for _ in range(5):
        task = Task(prompt="research x", category=TaskCategory.RESEARCH)
        d = RouteDecision(primary="n8n", fallback_chain=[], rationale="t")
        logger.log_dispatch(task, d)
        logger.log_result(TaskResult(task_id=task.task_id, backend_id="n8n",
                                     output="", success=False, latency_ms=100))

    router = Router(r, logger)
    decision = router.decide(Task(prompt="find latest research papers"))
    assert decision.primary == "autogen"


# ── executor ──────────────────────────────────────────────────────────────────

def test_executor_no_backends(tmp_path):
    r = fresh_registry()
    executor = Executor(r)
    d = RouteDecision(primary="none", fallback_chain=[], rationale="none")
    result = asyncio.run(executor.run(Task(prompt="hello"), d))
    assert not result.success
    assert "No backends connected" in result.error

def test_executor_unreachable_fails_gracefully(tmp_path):
    r = fresh_registry("n8n")
    r.get("n8n").config = {"base_url": "http://localhost:1"}
    executor = Executor(r, timeout=2)
    d = RouteDecision(primary="n8n", fallback_chain=[], rationale="test")
    result = asyncio.run(executor.run(Task(prompt="hello"), d))
    assert not result.success  # fails gracefully

def test_executor_falls_back_to_second(tmp_path):
    r = fresh_registry("n8n")
    r.get("n8n").config = {"base_url": "http://localhost:1"}  # dead
    # direct_llm also misconfigured
    s = r.get("direct_llm")
    s.connected = True
    s.config = {}  # missing api_key — won't be in connected()

    executor = Executor(r, timeout=2)
    d = RouteDecision(primary="n8n", fallback_chain=["direct_llm"], rationale="test")
    result = asyncio.run(executor.run(Task(prompt="hello"), d))
    assert not result.success  # both fail gracefully


# ── logger ────────────────────────────────────────────────────────────────────

def test_logger_win_rate_success(tmp_path):
    logger = TaskLogger(tmp_path / "test.db")
    task = Task(prompt="x", category=TaskCategory.CODING)
    logger.log_dispatch(task, RouteDecision(primary="n8n", fallback_chain=[], rationale="t"))
    logger.log_result(TaskResult(task_id=task.task_id, backend_id="n8n",
                                 output="ok", success=True, latency_ms=100))
    assert logger.win_rates()["n8n"]["coding"] == 1.0

def test_logger_win_rate_mixed(tmp_path):
    logger = TaskLogger(tmp_path / "test.db")
    for success in [True, True, False, False]:
        task = Task(prompt="x", category=TaskCategory.CODING)
        logger.log_dispatch(task, RouteDecision(primary="autogpt", fallback_chain=[], rationale="t"))
        logger.log_result(TaskResult(task_id=task.task_id, backend_id="autogpt",
                                     output="", success=success, latency_ms=50))
    assert logger.win_rates()["autogpt"]["coding"] == 0.5

def test_logger_feedback(tmp_path):
    logger = TaskLogger(tmp_path / "test.db")
    logger.log_feedback("task123", 5, "perfect")
    cur = logger.conn.execute("SELECT rating FROM feedback WHERE task_id='task123'")
    assert cur.fetchone()[0] == 5
