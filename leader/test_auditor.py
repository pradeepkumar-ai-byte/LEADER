"""
Leader – Auditor Tests

Tests the autonomous audit engine including deduplication,
malformed JSON handling, file-not-found handling, and interactive mode.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from leader.auditor import AutonomousAuditor
from leader.models import TaskCategory, TaskResult
from leader.registry import BackendSpec, Registry


@pytest.fixture
def mock_registry():
    r = Registry()
    r.connected = MagicMock(
        return_value=[
            BackendSpec(
                id="mock",
                display_name="Mock",
                description="",
                homepage="",
                adapter_class="",
                strengths=[TaskCategory.CODING],
                weaknesses=[],
            )
        ]
    )
    return r


# ── Basic audit scenarios ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auditor_no_issues(tmp_path, mock_registry):
    """When agents find no issues, auditor should report clean."""
    (tmp_path / "test.py").write_text("pass", encoding="utf-8")

    mock_executor = MagicMock()
    mock_executor.run = AsyncMock(
        return_value=TaskResult(
            task_id="1", backend_id="mock", output="[]", success=True, latency_ms=10
        )
    )

    auditor = AutonomousAuditor(mock_registry, MagicMock(), mock_executor)
    await auditor.audit_and_fix(str(tmp_path))

    assert mock_executor.run.call_count == 1


@pytest.mark.asyncio
async def test_auditor_auto_fix(tmp_path, mock_registry):
    """Auto-fix should overwrite the file when auto_approve=True."""
    f = tmp_path / "test.py"
    f.write_text("original", encoding="utf-8")

    mock_executor = MagicMock()
    mock_executor.run = AsyncMock(
        side_effect=[
            TaskResult(
                task_id="1",
                backend_id="mock",
                output='[{"file": "test.py", "problem": "bad code"}]',
                success=True,
                latency_ms=10,
            ),
            TaskResult(
                task_id="2",
                backend_id="mock",
                output="fixed",
                success=True,
                latency_ms=10,
            ),
        ]
    )

    auditor = AutonomousAuditor(mock_registry, MagicMock(), mock_executor)
    await auditor.audit_and_fix(str(tmp_path), auto_approve=True)

    assert mock_executor.run.call_count == 2
    assert f.read_text(encoding="utf-8") == "fixed"


@pytest.mark.asyncio
async def test_auditor_interactive_skip(tmp_path, mock_registry):
    """When user declines a fix, the file should remain unchanged."""
    f = tmp_path / "test.py"
    f.write_text("original", encoding="utf-8")

    mock_executor = MagicMock()
    mock_executor.run = AsyncMock(
        side_effect=[
            TaskResult(
                task_id="1",
                backend_id="mock",
                output='[{"file": "test.py", "problem": "bad"}]',
                success=True,
                latency_ms=10,
            ),
            TaskResult(
                task_id="2",
                backend_id="mock",
                output="fixed",
                success=True,
                latency_ms=10,
            ),
        ]
    )

    auditor = AutonomousAuditor(mock_registry, MagicMock(), mock_executor)

    with patch("rich.prompt.Confirm.ask", return_value=False):
        await auditor.audit_and_fix(str(tmp_path), auto_approve=False)

    assert mock_executor.run.call_count == 2
    assert f.read_text(encoding="utf-8") == "original"


# ── Edge cases ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auditor_malformed_json(tmp_path, mock_registry):
    """Auditor should handle LLMs returning non-JSON garbage gracefully."""
    (tmp_path / "test.py").write_text("pass", encoding="utf-8")

    mock_executor = MagicMock()
    mock_executor.run = AsyncMock(
        return_value=TaskResult(
            task_id="1",
            backend_id="mock",
            output="Sorry, I can't parse that. Here's some text instead.",
            success=True,
            latency_ms=10,
        )
    )

    auditor = AutonomousAuditor(mock_registry, MagicMock(), mock_executor)
    # Should not crash
    await auditor.audit_and_fix(str(tmp_path))
    assert mock_executor.run.call_count == 1


@pytest.mark.asyncio
async def test_auditor_missing_file_in_issue(tmp_path, mock_registry):
    """If LLM reports an issue in a file that doesn't exist, skip it gracefully."""
    (tmp_path / "real.py").write_text("pass", encoding="utf-8")

    mock_executor = MagicMock()
    mock_executor.run = AsyncMock(
        return_value=TaskResult(
            task_id="1",
            backend_id="mock",
            output='[{"file": "nonexistent.py", "problem": "bad"}]',
            success=True,
            latency_ms=10,
        )
    )

    auditor = AutonomousAuditor(mock_registry, MagicMock(), mock_executor)
    await auditor.audit_and_fix(str(tmp_path), auto_approve=True)
    # Should not crash; 1 for audit, 0 for fix (file not found)
    assert mock_executor.run.call_count == 1


@pytest.mark.asyncio
async def test_auditor_deduplication(tmp_path, mock_registry):
    """Duplicate issues from multiple agents should be deduplicated."""
    f = tmp_path / "test.py"
    f.write_text("original", encoding="utf-8")

    # Simulate 2 agents returning the same issue
    mock_registry.connected = MagicMock(
        return_value=[
            BackendSpec(
                id="mock1",
                display_name="Mock1",
                description="",
                homepage="",
                adapter_class="",
                strengths=[TaskCategory.CODING],
                weaknesses=[],
            ),
            BackendSpec(
                id="mock2",
                display_name="Mock2",
                description="",
                homepage="",
                adapter_class="",
                strengths=[TaskCategory.CODING],
                weaknesses=[],
            ),
        ]
    )

    same_issue = '[{"file": "test.py", "problem": "missing error handling"}]'

    mock_executor = MagicMock()
    mock_executor.run = AsyncMock(
        side_effect=[
            # Both agents return the same issue
            TaskResult(
                task_id="1",
                backend_id="mock1",
                output=same_issue,
                success=True,
                latency_ms=10,
            ),
            TaskResult(
                task_id="2",
                backend_id="mock2",
                output=same_issue,
                success=True,
                latency_ms=10,
            ),
            # Only ONE fix should be dispatched (deduplication)
            TaskResult(
                task_id="3",
                backend_id="mock1",
                output="fixed code",
                success=True,
                latency_ms=10,
            ),
        ]
    )

    auditor = AutonomousAuditor(mock_registry, MagicMock(), mock_executor)
    await auditor.audit_and_fix(str(tmp_path), auto_approve=True)

    # 2 audit calls + 1 fix call (not 2, because dedup)
    assert mock_executor.run.call_count == 3


@pytest.mark.asyncio
async def test_auditor_no_connected_backends(tmp_path):
    """Auditor should handle no connected backends gracefully."""
    (tmp_path / "test.py").write_text("pass", encoding="utf-8")

    registry = Registry()
    mock_executor = MagicMock()

    auditor = AutonomousAuditor(registry, MagicMock(), mock_executor)
    # Should not crash
    await auditor.audit_and_fix(str(tmp_path))
    assert mock_executor.run.call_count == 0
