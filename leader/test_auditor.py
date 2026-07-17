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


@pytest.mark.asyncio
async def test_auditor_no_issues(tmp_path, mock_registry):
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
            TaskResult(task_id="2", backend_id="mock", output="fixed", success=True, latency_ms=10),
        ]
    )

    auditor = AutonomousAuditor(mock_registry, MagicMock(), mock_executor)
    await auditor.audit_and_fix(str(tmp_path), auto_approve=True)

    assert mock_executor.run.call_count == 2
    assert f.read_text(encoding="utf-8") == "fixed"


@pytest.mark.asyncio
async def test_auditor_interactive_skip(tmp_path, mock_registry):
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
            TaskResult(task_id="2", backend_id="mock", output="fixed", success=True, latency_ms=10),
        ]
    )

    auditor = AutonomousAuditor(mock_registry, MagicMock(), mock_executor)

    with patch("rich.prompt.Confirm.ask", return_value=False):
        await auditor.audit_and_fix(str(tmp_path), auto_approve=False)

    # Executor still called twice (1 for audit, 1 for proposed fix)
    assert mock_executor.run.call_count == 2
    # But file is untouched
    assert f.read_text(encoding="utf-8") == "original"
