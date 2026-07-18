"""
Leader – shared test fixtures

Centralised fixtures used across all test modules.
Eliminates duplication and ensures consistent test setup.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from leader.logger import TaskLogger
from leader.models import Task, TaskCategory, TaskResult
from leader.registry import CATALOGUE, Registry
from leader.router import Router


@pytest.fixture
def tmp_db(tmp_path: Path) -> TaskLogger:
    """Create a TaskLogger with a temporary SQLite database."""
    return TaskLogger(db_path=tmp_path / "test.db")


@pytest.fixture
def empty_registry() -> Registry:
    """Return a Registry with no backends connected."""
    return Registry()


@pytest.fixture
def fresh_registry() -> Registry:
    """Return a Registry with deep-copied catalogue (no shared state between tests)."""
    specs = {k: copy.deepcopy(v) for k, v in CATALOGUE.items()}
    r = Registry(extra=specs)
    for s in r.all():
        s.connected = False
    return r


@pytest.fixture
def connected_registry(fresh_registry: Registry) -> Registry:
    """Return a Registry with direct_llm connected."""
    spec = fresh_registry.get("direct_llm")
    if spec:
        spec.connected = True
        spec.config = {"provider": "openai", "api_key": "sk-ant-testkey", "model": "gpt-4o"}
    return fresh_registry


@pytest.fixture
def router_with_history(connected_registry: Registry, tmp_db: TaskLogger) -> Router:
    """Return a Router with a connected registry and empty task history."""
    return Router(connected_registry, tmp_db)


@pytest.fixture
def sample_task() -> Task:
    """Return a sample coding task."""
    return Task(
        prompt="Fix the bug in user authentication",
        category=TaskCategory.CODING,
        task_id="test-task-001",
    )


@pytest.fixture
def sample_result() -> TaskResult:
    """Return a sample successful task result."""
    return TaskResult(
        task_id="test-task-001",
        backend_id="direct_llm",
        output="Fixed the authentication bug by adding null check.",
        success=True,
        latency_ms=150.0,
        cost_estimate=0.003,
    )
