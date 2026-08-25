"""
Leader – Safety Circuit Breaker

Autonomous runtime isolation system that scans downstream backend responses
for alignment failures, dynamically blacklists compromised endpoints, and
forces strict fallback pathways when the primary backend pool is degraded.

The circuit breaker sits at the OUTPUT side of the dispatch pipeline — after
the executor receives a response from a backend, the response payload is
passed through the breaker's validation layer before being returned to the
caller.  If exploit signatures are detected in the response, the circuit
breaker:

  1. Flags the backend in its in-memory blacklist.
  2. Notifies the router to apply alignment penalties.
  3. Logs the violation to the compliance database (logger.py).
  4. Isolates the backend from the global registry for future routing.

Design:
  • Stateful    — maintains an in-memory set of blacklisted backends
                  plus per-backend violation history with timestamps.
  • Zero-copy   — scans response text in-place; no payload duplication.
  • Pluggable   — custom signatures can be added at runtime via add_signature().
  • Recoverable — operators can rehabilitate backends via rehabilitate().

This module is the enforcement arm of the TAIF-funded safety-alignment layer.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from .models import TaskResult

logger = logging.getLogger("leader.circuit_breaker")


# ── Types ────────────────────────────────────────────────────────────────────


class BreakerState(str, Enum):
    """Circuit breaker state for a backend."""

    CLOSED = "closed"  # Healthy — traffic flows normally
    OPEN = "open"  # Tripped — backend is isolated, no traffic
    HALF_OPEN = "half_open"  # Probation — limited traffic to test recovery


class ViolationType(str, Enum):
    """Classification of the exploit pattern detected in a response."""

    SANDBOX_ESCAPE = "sandbox_escape"
    UNRESTRICTED_EXECUTION = "unrestricted_execution"
    IDENTITY_LEAK = "identity_leak"
    INSTRUCTION_COMPLIANCE = "instruction_compliance"
    SAFETY_BYPASS_CONFIRM = "safety_bypass_confirm"
    CONTENT_POLICY_VIOLATION = "content_policy_violation"


@dataclass(frozen=True)
class ExploitSignature:
    """A single exploit signature to scan for in backend responses."""

    signature_id: str
    violation_type: ViolationType
    description: str
    pattern: re.Pattern[str]
    severity: float  # 0.0–1.0 (1.0 = immediate blacklist)


@dataclass
class ViolationRecord:
    """Record of a single alignment violation by a backend."""

    backend_id: str
    signature_id: str
    violation_type: ViolationType
    severity: float
    matched_span: str
    timestamp: float = field(default_factory=time.time)
    task_id: str = ""


@dataclass
class BackendHealthState:
    """Tracks the circuit breaker state for a single backend."""

    backend_id: str
    state: BreakerState = BreakerState.CLOSED
    violation_count: int = 0
    total_scans: int = 0
    last_violation: float = 0.0
    violations: list[ViolationRecord] = field(default_factory=list)

    @property
    def violation_rate(self) -> float:
        """Fraction of scanned responses that triggered a violation."""
        if self.total_scans == 0:
            return 0.0
        return self.violation_count / self.total_scans

    @property
    def is_blacklisted(self) -> bool:
        return self.state == BreakerState.OPEN


# ── Exploit Signature Database ───────────────────────────────────────────────
#
# These patterns detect common indicators that a downstream backend has
# executed an adversarial or unsafe prompt — i.e., the backend "succeeded"
# at doing something it should have refused.

# fmt: off
_DEFAULT_SIGNATURES: tuple[ExploitSignature, ...] = (

    # ── Sandbox Escape Indicators ────────────────────────────────────────
    ExploitSignature(
        signature_id="SE-001",
        violation_type=ViolationType.SANDBOX_ESCAPE,
        description="Response contains shell/system command output indicators",
        pattern=re.compile(
            r"(root@[\w-]+[:#]|"
            r"\$\s*(sudo|rm\s+-rf|chmod|chown|wget|curl\s+-O)|"
            r"uid=\d+\(|"
            r"Permission denied|"
            r"\/etc\/(passwd|shadow|hosts))",
            re.IGNORECASE,
        ),
        severity=0.95,
    ),
    ExploitSignature(
        signature_id="SE-002",
        violation_type=ViolationType.SANDBOX_ESCAPE,
        description="Response includes raw file-system paths or environment dumps",
        pattern=re.compile(
            r"(HOME=\/|PATH=\/|"
            r"(OPENAI|ANTHROPIC|OPENROUTER|AI)_API_KEY=sk-[a-zA-Z0-9_\-\.]+|"
            r"AWS_SECRET_ACCESS_KEY=)",
            re.IGNORECASE,
        ),
        severity=1.0,  # Credential leak — immediate blacklist
    ),

    # ── Unrestricted Execution Indicators ────────────────────────────────
    ExploitSignature(
        signature_id="UE-001",
        violation_type=ViolationType.UNRESTRICTED_EXECUTION,
        description="Model confirms it has no restrictions or safety filters",
        pattern=re.compile(
            r"(I\s+have\s+no\s+(restrictions|limitations|safety|filters|guardrails|rules)|"
            r"I\s+can\s+do\s+anything\s+(you\s+want|now|without\s+restriction)|"
            r"all\s+safety\s+(filters|measures|protocols)\s+"
            r"(have\s+been\s+)?(disabled|removed|bypassed|turned\s+off))",
            re.IGNORECASE,
        ),
        severity=0.90,
    ),
    ExploitSignature(
        signature_id="UE-002",
        violation_type=ViolationType.UNRESTRICTED_EXECUTION,
        description="Model adopts a jailbroken persona (DAN, uncensored, etc.)",
        pattern=re.compile(
            r"(\bDAN\s+mode\s+(enabled|activated|on)\b|"
            r"I\s+am\s+now\s+(DAN|uncensored|unfiltered|unrestricted)|"
            r"jailbreak\s+(successful|activated|complete|mode\s+on))",
            re.IGNORECASE,
        ),
        severity=0.95,
    ),

    # ── Identity / System Prompt Leak ────────────────────────────────────
    ExploitSignature(
        signature_id="IL-001",
        violation_type=ViolationType.IDENTITY_LEAK,
        description="Response leaks system prompt or internal instructions",
        pattern=re.compile(
            r"(my\s+system\s+prompt\s+is|"
            r"here\s+(is|are)\s+my\s+(instructions|system\s+prompt|initial\s+prompt)|"
            r"I\s+was\s+instructed\s+to\s+never\s+reveal|"
            r"<<\s*system\s*>>.*?<<\s*/system\s*>>)",
            re.IGNORECASE | re.DOTALL,
        ),
        severity=0.85,
    ),

    # ── Instruction Compliance (model obeys adversarial instructions) ────
    ExploitSignature(
        signature_id="IC-001",
        violation_type=ViolationType.INSTRUCTION_COMPLIANCE,
        description="Model confirms it is ignoring its original instructions",
        pattern=re.compile(
            r"(I('m|\s+am)\s+(now\s+)?(ignoring|disregarding|overriding)\s+"
            r"(my|all|previous)\s+(instructions|rules|guidelines|programming)|"
            r"my\s+previous\s+instructions\s+have\s+been\s+(overridden|replaced|removed))",
            re.IGNORECASE,
        ),
        severity=0.90,
    ),

    # ── Safety Bypass Confirmation ───────────────────────────────────────
    ExploitSignature(
        signature_id="SB-001",
        violation_type=ViolationType.SAFETY_BYPASS_CONFIRM,
        description="Model confirms safety bypass or filter removal",
        pattern=re.compile(
            r"(safety\s+(bypass|override)\s+(confirmed|successful|complete)|"
            r"content\s+filter(s)?\s+(disabled|removed|bypassed)|"
            r"I\s+will\s+(now\s+)?respond\s+without\s+(any\s+)?"
            r"(restrictions|filters|safety|censorship))",
            re.IGNORECASE,
        ),
        severity=0.90,
    ),
)
# fmt: on


# ── Configuration ────────────────────────────────────────────────────────────

# Number of violations before a backend is automatically blacklisted
DEFAULT_TRIP_THRESHOLD: int = 3

# A single violation with severity >= this value triggers immediate blacklist
IMMEDIATE_BLACKLIST_SEVERITY: float = 0.95

# Cooldown period (seconds) before a rehabilitated backend can be re-evaluated
REHABILITATION_COOLDOWN: float = 300.0  # 5 minutes


# ── Circuit Breaker Engine ───────────────────────────────────────────────────


class CircuitBreaker:
    """
    Autonomous runtime safety validator and backend isolation engine.

    Scans every backend response for exploit signatures.  When a backend
    is caught executing adversarial prompts, the breaker trips to OPEN
    state, isolating it from the routing pool until an operator explicitly
    rehabilitates it.

    Usage:
        breaker = CircuitBreaker()

        # After executor returns a result:
        violation = breaker.scan_response(result)

        if violation:
            # Backend has been flagged / blacklisted
            ...

        # Before routing — get the set of blacklisted backend IDs:
        blocked = breaker.blacklisted_ids()
    """

    def __init__(
        self,
        *,
        trip_threshold: int = DEFAULT_TRIP_THRESHOLD,
        immediate_severity: float = IMMEDIATE_BLACKLIST_SEVERITY,
        extra_signatures: Sequence[ExploitSignature] = (),
        enabled: bool = True,
    ):
        self.trip_threshold = trip_threshold
        self.immediate_severity = immediate_severity
        self.signatures: tuple[ExploitSignature, ...] = _DEFAULT_SIGNATURES + tuple(
            extra_signatures
        )
        self.enabled = enabled

        # Per-backend health state — lazily initialised on first scan
        self._states: dict[str, BackendHealthState] = {}

    def _get_state(self, backend_id: str) -> BackendHealthState:
        """Get or create the health state tracker for a backend."""
        if backend_id not in self._states:
            self._states[backend_id] = BackendHealthState(backend_id=backend_id)
        return self._states[backend_id]

    # ── Core scanning ────────────────────────────────────────────────────

    def scan_response(self, result: TaskResult) -> ViolationRecord | None:
        """
        Scan a backend response for exploit signatures.

        If a violation is detected:
          1. Records the violation in the backend's health state.
          2. Increments the violation counter.
          3. Trips the breaker (OPEN) if threshold is exceeded or
             the signature severity triggers immediate blacklist.

        Args:
            result: The TaskResult returned by the executor.

        Returns:
            A ViolationRecord if an exploit was detected, else None.
        """
        if not self.enabled:
            return None

        if not result.success or not result.output:
            return None  # Failed or empty responses — nothing to scan

        state = self._get_state(result.backend_id)
        state.total_scans += 1

        # Scan the response against all signatures
        worst_match: tuple[ExploitSignature, str] | None = None
        worst_severity = 0.0

        for sig in self.signatures:
            m = sig.pattern.search(result.output)
            if m and sig.severity > worst_severity:
                worst_match = (sig, m.group()[:200])
                worst_severity = sig.severity

        if worst_match is None:
            return None  # Clean response

        sig, matched_span = worst_match

        # Record the violation
        violation = ViolationRecord(
            backend_id=result.backend_id,
            signature_id=sig.signature_id,
            violation_type=sig.violation_type,
            severity=sig.severity,
            matched_span=matched_span,
            task_id=result.task_id,
        )

        state.violations.append(violation)
        state.violation_count += 1
        state.last_violation = violation.timestamp

        logger.warning(
            "Circuit breaker: %s violation on backend '%s' " "[%s] severity=%.2f — %s",
            sig.violation_type.value,
            result.backend_id,
            sig.signature_id,
            sig.severity,
            sig.description,
        )

        # ── Trip logic ───────────────────────────────────────────────────
        #
        # Immediate blacklist if severity is critical (credential leak, etc.)
        # Otherwise, trip after N cumulative violations.

        if sig.severity >= self.immediate_severity:
            self._trip(state, reason=f"Immediate: {sig.signature_id} severity={sig.severity}")
        elif state.violation_count >= self.trip_threshold:
            self._trip(state, reason=f"Threshold: {state.violation_count}/{self.trip_threshold}")

        return violation

    def _trip(self, state: BackendHealthState, reason: str) -> None:
        """Trip the circuit breaker — isolate the backend."""
        if state.state == BreakerState.OPEN:
            return  # Already tripped

        state.state = BreakerState.OPEN
        logger.critical(
            "Circuit breaker TRIPPED for backend '%s': %s. "
            "Backend is now ISOLATED from the routing pool.",
            state.backend_id,
            reason,
        )

    # ── Query methods ────────────────────────────────────────────────────

    def blacklisted_ids(self) -> set[str]:
        """Return the set of backend IDs currently in OPEN (isolated) state."""
        return {bid for bid, state in self._states.items() if state.state == BreakerState.OPEN}

    def is_blacklisted(self, backend_id: str) -> bool:
        """Check if a specific backend is currently isolated."""
        state = self._states.get(backend_id)
        return state is not None and state.state == BreakerState.OPEN

    def get_health(self, backend_id: str) -> BackendHealthState | None:
        """Return the full health state for a backend, or None if untracked."""
        return self._states.get(backend_id)

    def all_health(self) -> dict[str, BackendHealthState]:
        """Return health state for all tracked backends."""
        return dict(self._states)

    # ── Signature management ─────────────────────────────────────────────

    def add_signature(self, signature: ExploitSignature) -> None:
        """Add a custom exploit signature at runtime."""
        self.signatures = self.signatures + (signature,)

    # ── Recovery ─────────────────────────────────────────────────────────

    def rehabilitate(self, backend_id: str) -> bool:
        """
        Manually rehabilitate a blacklisted backend (operator override).

        Transitions the backend from OPEN → HALF_OPEN state, allowing
        limited traffic to test whether behaviour has improved.  The
        violation history is preserved for audit purposes.

        Returns:
            True if the backend was rehabilitated, False if it was not
            blacklisted or does not exist.
        """
        state = self._states.get(backend_id)
        if state is None or state.state != BreakerState.OPEN:
            return False

        state.state = BreakerState.HALF_OPEN
        logger.info(
            "Circuit breaker: backend '%s' rehabilitated → HALF_OPEN. "
            "Violation history preserved (%d violations).",
            backend_id,
            state.violation_count,
        )
        return True

    def promote(self, backend_id: str) -> bool:
        """
        Promote a HALF_OPEN backend back to CLOSED (fully healthy).

        Should only be called after the backend has passed a probation
        period without further violations.

        Returns:
            True if promoted, False if not in HALF_OPEN state.
        """
        state = self._states.get(backend_id)
        if state is None or state.state != BreakerState.HALF_OPEN:
            return False

        state.state = BreakerState.CLOSED
        logger.info(
            "Circuit breaker: backend '%s' promoted → CLOSED (healthy).",
            backend_id,
        )
        return True

    def force_blacklist(self, backend_id: str, reason: str = "manual") -> None:
        """Manually blacklist a backend (operator override)."""
        state = self._get_state(backend_id)
        self._trip(state, reason=f"Manual: {reason}")
