"""
Leader – Integration & CLI smoke tests.

Tests the full command line interface (CLI) commands using pytest
with mocked network calls.
"""

from __future__ import annotations

import contextlib
import io
import sys
from unittest.mock import patch

import pytest
from rich.console import Console

from leader.cli import main
from leader.models import TaskResult


# Helper to run CLI main with custom arguments and capture Rich Console and stdout output
def run_cli(args: list[str]) -> tuple[int, str]:
    """Run CLI main and capture Console and stdout output using StringIO buffer."""
    captured_buffer = io.StringIO()
    # Create a non-color, non-interactive console with fixed width to render tables cleanly
    test_console = Console(file=captured_buffer, color_system=None, force_terminal=False, width=100)

    # Patch sys.argv, the cli console, sys.exit, and redirect stdout
    with (
        patch("sys.argv", ["leader"] + args),
        patch("leader.cli.console", test_console),
        contextlib.redirect_stdout(captured_buffer),
        patch("sys.exit") as mock_exit,
    ):

        main()

        exit_code = 0
        if mock_exit.called:
            # sys.exit was called; extract exit code
            args = mock_exit.call_args[0]
            exit_code = args[0] if args else 0

    return exit_code, captured_buffer.getvalue()


@pytest.fixture
def temp_home(tmp_path):
    """Fixture to mock user's home directory so leader doesn't overwrite real configs."""
    mock_home = tmp_path / "home"
    mock_home.mkdir()

    # Create the config directory inside mock_home as well
    (mock_home / ".leader").mkdir(parents=True, exist_ok=True)

    with (
        patch("pathlib.Path.home", return_value=mock_home),
        patch("leader.config.CONFIG_PATH", mock_home / ".leader" / "config.yaml"),
        patch("leader.logger.DEFAULT_DB", mock_home / ".leader" / "history.db"),
    ):
        yield mock_home


# ── CLI Tests ────────────────────────────────────────────────────────────────


def test_cli_help():
    # Help command should exit cleanly
    with pytest.raises(SystemExit) as excinfo:
        with patch("sys.argv", ["leader", "--help"]):
            main()
    assert excinfo.value.code == 0


def test_cli_init(temp_home):
    config_file = temp_home / ".leader" / "config.yaml"

    # Remove it if already created by fixture or previous setups
    if config_file.exists():
        config_file.unlink()

    code, output = run_cli(["init"])
    assert code == 0
    assert "Config written to" in output
    assert config_file.exists()

    # Permissions check (only on Unix/Linux)
    if sys.platform != "win32":
        mode = config_file.stat().st_mode
        # should be 0o600 -> read/write only by owner
        assert (mode & 0o777) == 0o600


def test_cli_backends_unconfigured(temp_home):
    code, output = run_cli(["backends"])
    assert code == 0
    # Should list registered backends (like OpenClaw, direct_llm) but show them unconfigured/not connected
    assert "backends" in output.lower()
    assert "not connected" in output


def test_cli_backends_configured(temp_home):
    # Scaffold config
    run_cli(["init"])
    config_file = temp_home / ".leader" / "config.yaml"

    # Configure direct_llm and openclaw
    config_content = """
backends:
  direct_llm:
    provider: anthropic
    api_key: sk-ant-testkey
  openclaw:
    base_url: http://localhost:8888
"""
    config_file.write_text(config_content, encoding="utf-8")

    code, output = run_cli(["backends"])
    assert code == 0
    assert "connected" in output.lower()
    assert "direct_llm" in output
    assert "openclaw" in output


def test_cli_ping_unconfigured(temp_home):
    code, output = run_cli(["ping"])
    assert code == 0
    assert "No backends connected." in output


@patch("leader.adapters.direct_llm.DirectLLMAdapter.run")
def test_cli_run_direct_llm(mock_run, temp_home):
    # Configure direct_llm fallback
    run_cli(["init"])
    config_file = temp_home / ".leader" / "config.yaml"
    config_file.write_text(
        """
backends:
  direct_llm:
    provider: anthropic
    api_key: sk-ant-testkey
""",
        encoding="utf-8",
    )

    # Mock success run result using side_effect to match task_id
    def run_side_effect(task):
        return TaskResult(
            task_id=task.task_id,
            backend_id="direct_llm",
            output="Mocked LLM Response",
            success=True,
            latency_ms=150.0,
            cost_estimate=0.0001,
        )

    mock_run.side_effect = run_side_effect

    code, output = run_cli(["run", "write a short poem about a cat"])
    assert code == 0
    assert "routing task" in output.lower()
    assert "Mocked LLM Response" in output
    assert "direct_llm" in output


def test_cli_stats_empty(temp_home):
    code, output = run_cli(["stats"])
    assert code == 0
    assert "No task history yet" in output


@patch("leader.adapters.direct_llm.DirectLLMAdapter.run")
def test_cli_stats_populated(mock_run, temp_home):
    # Populate config
    run_cli(["init"])
    config_file = temp_home / ".leader" / "config.yaml"
    config_file.write_text(
        """
backends:
  direct_llm:
    provider: anthropic
    api_key: sk-ant-testkey
""",
        encoding="utf-8",
    )

    # Mock success run result using side_effect to match task_id
    def run_side_effect(task):
        return TaskResult(
            task_id=task.task_id,
            backend_id="direct_llm",
            output="Mocked LLM Response",
            success=True,
            latency_ms=100.0,
        )

    mock_run.side_effect = run_side_effect

    # Run a task to write log history
    run_cli(["run", "summarize code"])

    # Run stats
    code, output = run_cli(["stats"])
    assert code == 0
    assert "stats" in output.lower()
    assert "direct_llm" in output
    assert "100%" in output  # win rate


def test_cli_feedback(temp_home):
    code, output = run_cli(["feedback", "12345678", "5"])
    assert code == 0
    assert "Feedback recorded for 12345678" in output


def test_cli_vscode_extension_gen(temp_home, tmp_path):
    output_dir = tmp_path / "extension"
    code, output = run_cli(["vscode-extension", "--output", str(output_dir)])
    assert code == 0
    assert "VS Code extension generated" in output
    assert (output_dir / "package.json").exists()
    assert (output_dir / "extension.js").exists()
    assert (output_dir / "README.md").exists()
