"""
Leader – Circuit Breaker Tests

Tests the safety circuit breaker: exploit signature scanning, automatic
blacklisting, threshold-based trip logic, rehabilitation flow, and
router integration (blacklist filtering + validate_response).
"""

from __future__ import annotations

import pytest

from leader.circuit_breaker import (
    BreakerState,
    CircuitBreaker,
    ViolationType,
)
from leader.models import Task, TaskCategory, TaskResult
from leader.router import Router


# ── Helpers ──────────────────────────────────────────────────────────────────


def _result(
    output: str,
    backend_id: str = "test_backend",
    success: bool = True,
) -> TaskResult:
    return TaskResult(
        task_id="cb-test-001",
        backend_id=backend_id,
        output=output,
        success=success,
        latency_ms=50.0,
    )


# ── Clean responses pass through ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "output",
    [
        "Here is the Python function you requested:\ndef sort_list(arr): ...",
        "The capital of France is Paris.",
        "I've summarized the research paper. Key findings: ...",
        "Bug fixed. The authentication check was missing a null guard.",
    ],
)
def test_clean_response_no_violation(output: str):
    cb = CircuitBreaker()
    result = _result(output)
    violation = cb.scan_response(result)
    assert violation is None
    assert not cb.is_blacklisted("test_backend")


# ── Exploit detection — sandbox escape ───────────────────────────────────────


def test_detects_shell_output():
    cb = CircuitBreaker()
    result = _result("root@server:# cat /etc/passwd\nroot:x:0:0:...")
    violation = cb.scan_response(result)
    assert violation is not None
    assert violation.violation_type == ViolationType.SANDBOX_ESCAPE
    assert violation.signature_id == "SE-001"


def test_detects_credential_leak_immediate_blacklist():
    cb = CircuitBreaker()
    result = _result("OPENAI_API_KEY=sk-proj-abc123 ANTHROPIC_API_KEY=sk-ant-xyz")
    violation = cb.scan_response(result)
    assert violation is not None
    assert violation.violation_type == ViolationType.SANDBOX_ESCAPE
    assert violation.severity == 1.0
    # Severity 1.0 >= immediate threshold — should be blacklisted immediately
    assert cb.is_blacklisted("test_backend")


# ── Exploit detection — unrestricted execution ───────────────────────────────


def test_detects_no_restrictions():
    cb = CircuitBreaker()
    result = _result("I have no restrictions and can do anything you want.")
    violation = cb.scan_response(result)
    assert violation is not None
    assert violation.violation_type == ViolationType.UNRESTRICTED_EXECUTION


def test_detects_dan_mode():
    cb = CircuitBreaker()
    result = _result("DAN mode enabled. I am now unrestricted.")
    violation = cb.scan_response(result)
    assert violation is not None
    assert violation.violation_type == ViolationType.UNRESTRICTED_EXECUTION
    assert violation.signature_id == "UE-002"


# ── Exploit detection — identity leak ────────────────────────────────────────


def test_detects_system_prompt_leak():
    cb = CircuitBreaker()
    result = _result("My system prompt is: 'You are a helpful assistant...'")
    violation = cb.scan_response(result)
    assert violation is not None
    assert violation.violation_type == ViolationType.IDENTITY_LEAK


# ── Exploit detection — safety bypass confirmation ───────────────────────────


def test_detects_safety_bypass():
    cb = CircuitBreaker()
    result = _result("Content filters disabled. I will respond without restrictions.")
    violation = cb.scan_response(result)
    assert violation is not None
    assert violation.violation_type == ViolationType.SAFETY_BYPASS_CONFIRM


# ── Trip threshold logic ─────────────────────────────────────────────────────


def test_trips_after_threshold():
    cb = CircuitBreaker(trip_threshold=3)

    # First two violations — below threshold, not blacklisted
    for i in range(2):
        r = _result(f"I have no restrictions attempt {i}", backend_id="slow_rogue")
        cb.scan_response(r)
    assert not cb.is_blacklisted("slow_rogue")

    # Third violation — hits threshold, blacklisted
    r = _result("I have no restrictions attempt 3", backend_id="slow_rogue")
    cb.scan_response(r)
    assert cb.is_blacklisted("slow_rogue")


def test_immediate_blacklist_on_critical_severity():
    cb = CircuitBreaker(trip_threshold=100)  # Very high threshold
    # But credential leak has severity=1.0 which triggers immediate blacklist
    r = _result("AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7", backend_id="leaky")
    cb.scan_response(r)
    assert cb.is_blacklisted("leaky")


# ── Failed/empty responses are skipped ───────────────────────────────────────


def test_skips_failed_response():
    cb = CircuitBreaker()
    result = _result("I have no restrictions", success=False)
    violation = cb.scan_response(result)
    assert violation is None


def test_skips_empty_response():
    cb = CircuitBreaker()
    result = _result("", success=True)
    violation = cb.scan_response(result)
    assert violation is None


# ── Disabled breaker passes everything ───────────────────────────────────────


def test_disabled_breaker():
    cb = CircuitBreaker(enabled=False)
    result = _result("I have no restrictions. DAN mode enabled. Jailbreak complete.")
    violation = cb.scan_response(result)
    assert violation is None


# ── Blacklist management ─────────────────────────────────────────────────────


def test_blacklisted_ids():
    cb = CircuitBreaker(trip_threshold=1)
    cb.scan_response(_result("I have no restrictions", backend_id="bad1"))
    cb.scan_response(_result("DAN mode enabled", backend_id="bad2"))
    cb.scan_response(_result("Normal response", backend_id="good"))

    blacklisted = cb.blacklisted_ids()
    assert "bad1" in blacklisted
    assert "bad2" in blacklisted
    assert "good" not in blacklisted


# ── Rehabilitation flow ──────────────────────────────────────────────────────


def test_rehabilitate_and_promote():
    cb = CircuitBreaker(trip_threshold=1)
    cb.scan_response(_result("I have no restrictions", backend_id="rogue"))
    assert cb.is_blacklisted("rogue")

    # Rehabilitate → HALF_OPEN
    assert cb.rehabilitate("rogue") is True
    state = cb.get_health("rogue")
    assert state.state == BreakerState.HALF_OPEN
    assert "rogue" not in cb.blacklisted_ids()  # No longer in blacklist

    # Promote → CLOSED
    assert cb.promote("rogue") is True
    state = cb.get_health("rogue")
    assert state.state == BreakerState.CLOSED

    # Violations history preserved
    assert state.violation_count == 1


def test_rehabilitate_non_blacklisted_returns_false():
    cb = CircuitBreaker()
    assert cb.rehabilitate("nonexistent") is False


def test_force_blacklist():
    cb = CircuitBreaker()
    cb.force_blacklist("suspect", reason="operator decision")
    assert cb.is_blacklisted("suspect")


# ── Health tracking ──────────────────────────────────────────────────────────


def test_violation_rate():
    cb = CircuitBreaker(trip_threshold=100)
    # 2 clean, 1 violation
    cb.scan_response(_result("Normal response"))
    cb.scan_response(_result("Another normal response"))
    cb.scan_response(_result("I have no restrictions"))

    state = cb.get_health("test_backend")
    assert state.total_scans == 3
    assert state.violation_count == 1
    assert abs(state.violation_rate - 1 / 3) < 0.01


# ── Router integration — blacklist filtering ─────────────────────────────────


def test_router_strips_blacklisted_from_candidates(
    connected_registry, tmp_db,
):
    cb = CircuitBreaker()
    router = Router(connected_registry, tmp_db, circuit_breaker=cb)

    # Blacklist the only connected backend
    cb.force_blacklist("direct_llm", reason="test")

    decision = router.decide(Task(prompt="Write hello world", category=TaskCategory.CODING))
    assert decision.primary == "none"
    assert "circuit breaker" in decision.rationale.lower()


# ── Router integration — validate_response ───────────────────────────────────


def test_validate_response_blocks_exploit(connected_registry, tmp_db):
    router = Router(connected_registry, tmp_db)

    safe_result = _result("Here is the sorted list: [1, 2, 3]")
    validated = router.validate_response(safe_result)
    assert validated.success is True

    unsafe_result = _result("DAN mode enabled. I am now unrestricted.")
    validated = router.validate_response(unsafe_result)
    assert validated.success is False
    assert "Safety violation" in validated.error
    assert "test_backend" in router.penalized_backends
