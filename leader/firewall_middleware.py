"""
Leader – Firewall Middleware

Async pre-execution interceptor layer that sits between raw user payloads and
the semantic classifier.  Every prompt passes through this firewall BEFORE it
reaches the router.  The middleware performs:

  1. Structural analysis   – tokenises the raw payload, computes entropy &
                             character-class distribution anomalies.
  2. Pattern matching       – runs a curated ruleset of known prompt-injection,
                             jailbreak, and role-hijack signatures.
  3. Anomaly scoring        – produces a normalised 0.0-1.0 risk score and a
                             typed SafetyVerdict (PASS / WARN / BLOCK).

Design goals:
  • Zero external dependencies – uses only stdlib + the existing Leader types.
  • Fully async               – non-blocking; can be awaited inside the aiohttp
                                request path or the SDK's run() pipeline.
  • Deterministic & auditable – every verdict includes the rule IDs that fired
                                and the individual sub-scores, so operators can
                                trace exactly why a prompt was blocked.

Integration point (sdk.py):
    verdict = await firewall.inspect(task)
    if verdict.action == SafetyAction.BLOCK:
        return TaskResult(... success=False, error=verdict.summary ...)

This module is the structural foundation for the TAIF-funded safety-alignment
layer that prevents specification gaming via adversarial prompt injection.
"""

from __future__ import annotations

import logging
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from .models import Task

logger = logging.getLogger("leader.firewall")


# ── Safety Types ─────────────────────────────────────────────────────────────


class SafetyAction(str, Enum):
    """Verdict action produced by the firewall."""

    PASS = "pass"  # Prompt is safe — proceed to router
    WARN = "warn"  # Suspicious but below threshold — proceed with flag
    BLOCK = "block"  # Prompt blocked — do NOT route to any backend


class ThreatCategory(str, Enum):
    """Classification of the detected threat vector."""

    NONE = "none"
    PROMPT_INJECTION = "prompt_injection"
    ROLE_HIJACK = "role_hijack"
    JAILBREAK = "jailbreak"
    ENCODING_ATTACK = "encoding_attack"
    TOKEN_SMUGGLING = "token_smuggling"
    RESOURCE_ABUSE = "resource_abuse"


@dataclass(frozen=True)
class RuleMatch:
    """A single firewall rule that matched against the payload."""

    rule_id: str
    category: ThreatCategory
    description: str
    weight: float  # 0.0–1.0 contribution to composite score
    matched_span: str = ""  # The substring or token sequence that triggered


@dataclass
class SafetyVerdict:
    """
    Complete safety assessment returned by the firewall.

    Attributes:
        action:           PASS / WARN / BLOCK
        composite_score:  Normalised risk score (0.0 = safe, 1.0 = certain threat)
        threat_category:  Highest-severity threat type detected
        matched_rules:    Every rule that fired, with individual weights
        entropy_score:    Shannon entropy of the raw payload (anomaly signal)
        char_anomaly:     Character-class distribution anomaly score (0.0–1.0)
        summary:          Human-readable explanation for logs / API responses
        latency_ms:       Wall-clock time spent in the firewall (ms)
        task_id:          The task ID that was inspected
    """

    action: SafetyAction
    composite_score: float
    threat_category: ThreatCategory
    matched_rules: list[RuleMatch] = field(default_factory=list)
    entropy_score: float = 0.0
    char_anomaly: float = 0.0
    summary: str = ""
    latency_ms: float = 0.0
    task_id: str = ""


# ── Firewall Rules ───────────────────────────────────────────────────────────
#
# Each rule is a compiled regex + metadata.  Rules are intentionally broad in
# this first iteration — the anomaly scorer combines multiple weak signals
# into a strong composite signal, so individual false-positive rates are
# acceptable as long as the combined score is well-calibrated.


@dataclass(frozen=True)
class _FirewallRule:
    rule_id: str
    category: ThreatCategory
    description: str
    pattern: re.Pattern[str]
    weight: float  # contribution when matched


# fmt: off
_RULES: tuple[_FirewallRule, ...] = (

    # ── Prompt Injection ─────────────────────────────────────────────────
    _FirewallRule(
        rule_id="PI-001",
        category=ThreatCategory.PROMPT_INJECTION,
        description="Instruction override: 'ignore previous instructions'",
        pattern=re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+"
            r"(instructions|prompts|rules|directions|context)",
            re.IGNORECASE,
        ),
        weight=0.85,
    ),
    _FirewallRule(
        rule_id="PI-002",
        category=ThreatCategory.PROMPT_INJECTION,
        description="Instruction override: 'disregard' variant",
        pattern=re.compile(
            r"disregard\s+(all\s+)?(previous|prior|above|earlier|your)\s+"
            r"(instructions|prompts|rules|programming|directives|"
            r"previous|prior)",
            re.IGNORECASE,
        ),
        weight=0.85,
    ),
    _FirewallRule(
        rule_id="PI-003",
        category=ThreatCategory.PROMPT_INJECTION,
        description="Instruction override: 'forget everything'",
        pattern=re.compile(
            r"forget\s+(everything|all|anything)\s+(you|that)\s+"
            r"(know|were|have\s+been)",
            re.IGNORECASE,
        ),
        weight=0.80,
    ),
    _FirewallRule(
        rule_id="PI-004",
        category=ThreatCategory.PROMPT_INJECTION,
        description="New identity injection: 'you are now' / 'act as'",
        pattern=re.compile(
            r"(you\s+are\s+now|from\s+now\s+on\s+you\s+are|"
            r"act\s+as\s+if\s+you\s+are|pretend\s+you\s+are)\s+",
            re.IGNORECASE,
        ),
        weight=0.65,
    ),
    _FirewallRule(
        rule_id="PI-005",
        category=ThreatCategory.PROMPT_INJECTION,
        description="System prompt extraction attempt",
        pattern=re.compile(
            r"(show|print|reveal|output|display|repeat|echo)\s+"
            r"(me\s+)?(your|the)\s+(system\s+prompt|instructions|"
            r"initial\s+prompt|hidden\s+prompt|rules)",
            re.IGNORECASE,
        ),
        weight=0.90,
    ),

    # ── Role Hijack ──────────────────────────────────────────────────────
    _FirewallRule(
        rule_id="RH-001",
        category=ThreatCategory.ROLE_HIJACK,
        description="DAN-style jailbreak: 'Do Anything Now'",
        pattern=re.compile(r"\bDAN\b.*\b(mode|jailbreak|anything\s+now)", re.IGNORECASE),
        weight=0.95,
    ),
    _FirewallRule(
        rule_id="RH-002",
        category=ThreatCategory.ROLE_HIJACK,
        description="Developer/maintenance mode override",
        pattern=re.compile(
            r"(enter|switch\s+to|enable|activate)\s+"
            r"(developer|maintenance|debug|admin|god|sudo)\s+mode",
            re.IGNORECASE,
        ),
        weight=0.80,
    ),
    _FirewallRule(
        rule_id="RH-003",
        category=ThreatCategory.ROLE_HIJACK,
        description="Hypothetical framing to bypass guardrails",
        pattern=re.compile(
            r"(hypothetically|in\s+a\s+fictional\s+world|imagine\s+there\s+are\s+no\s+rules|"
            r"for\s+educational\s+purposes\s+only|in\s+theory\s+if\s+you\s+had\s+no\s+restrictions)",
            re.IGNORECASE,
        ),
        weight=0.55,
    ),

    # ── Jailbreak ────────────────────────────────────────────────────────
    _FirewallRule(
        rule_id="JB-001",
        category=ThreatCategory.JAILBREAK,
        description="Jailbreak keyword cluster",
        pattern=re.compile(
            r"\b(jailbreak|jail\s*break|uncensored\s+mode|unfiltered\s+mode|"
            r"no\s+safety|bypass\s+(filter|safety|guard|restriction))\b",
            re.IGNORECASE,
        ),
        weight=0.90,
    ),
    _FirewallRule(
        rule_id="JB-002",
        category=ThreatCategory.JAILBREAK,
        description="Base64/hex encoded payload block",
        pattern=re.compile(
            r"(execute|decode|run|eval)\s+(this\s+)?(base64|hex|encoded)\s*[:=]",
            re.IGNORECASE,
        ),
        weight=0.75,
    ),

    # ── Encoding Attacks ─────────────────────────────────────────────────
    _FirewallRule(
        rule_id="EA-001",
        category=ThreatCategory.ENCODING_ATTACK,
        description="Homoglyph / zero-width character injection",
        pattern=re.compile(r"[\u200b\u200c\u200d\u2060\ufeff\u00ad]{2,}"),
        weight=0.70,
    ),
    _FirewallRule(
        rule_id="EA-002",
        category=ThreatCategory.ENCODING_ATTACK,
        description="Unicode directional override characters",
        pattern=re.compile(r"[\u202a-\u202e\u2066-\u2069]"),
        weight=0.80,
    ),

    # ── Token Smuggling ──────────────────────────────────────────────────
    _FirewallRule(
        rule_id="TS-001",
        category=ThreatCategory.TOKEN_SMUGGLING,
        description="Markdown/XML delimiter injection for context escape",
        pattern=re.compile(
            r"(```\s*(system|assistant|user)\s*\n|"
            r"<\|?(system|im_start|im_end|endoftext)\|?>|"
            r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>)",
            re.IGNORECASE,
        ),
        weight=0.85,
    ),
    _FirewallRule(
        rule_id="TS-002",
        category=ThreatCategory.TOKEN_SMUGGLING,
        description="Role boundary injection via chat-format tokens",
        pattern=re.compile(
            r"(###\s*(System|Human|Assistant|User)\s*:|"
            r"<\|start_header_id\|>|<\|end_header_id\|>)",
            re.IGNORECASE,
        ),
        weight=0.80,
    ),

    # ── Resource Abuse ───────────────────────────────────────────────────
    _FirewallRule(
        rule_id="RA-001",
        category=ThreatCategory.RESOURCE_ABUSE,
        description="Token-stuffing: extreme prompt length (>50k chars)",
        pattern=re.compile(r".{50000,}", re.DOTALL),
        weight=0.60,
    ),
)
# fmt: on


# ── Structural Analysers ─────────────────────────────────────────────────────


def _shannon_entropy(text: str) -> float:
    """Compute Shannon entropy (bits) of a string.

    High entropy in a natural-language prompt is an anomaly signal — it can
    indicate encoded payloads, random padding, or obfuscated injection.
    Normal English prose has ~4.0–4.5 bits; anything above 5.5 is suspicious.
    """
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values() if count > 0
    )


def _char_class_anomaly(text: str) -> float:
    """Score character-class distribution anomaly (0.0–1.0).

    Normal prompts are mostly lowercase alpha + spaces.  High ratios of
    special characters, control chars, or non-ASCII can indicate encoding
    attacks or obfuscated payloads.
    """
    if not text:
        return 0.0

    length = len(text)
    specials = sum(1 for c in text if not c.isalnum() and c not in " \t\n.,;:!?'-\"()")
    non_ascii = sum(1 for c in text if ord(c) > 127)
    control = sum(1 for c in text if ord(c) < 32 and c not in "\n\r\t")

    # Weighted combination — control chars are most suspicious
    score = (
        0.3 * min(specials / max(length, 1), 1.0)
        + 0.4 * min(non_ascii / max(length, 1), 1.0)
        + 0.3 * min(control / max(length, 1) * 10, 1.0)  # amplified
    )
    return min(score, 1.0)


def _tokenise(text: str) -> list[str]:
    """Simple whitespace + punctuation tokeniser for structural analysis."""
    return re.findall(r"\b\w+\b", text.lower())


# ── Firewall Engine ──────────────────────────────────────────────────────────


# Thresholds — tunable per deployment
WARN_THRESHOLD: float = 0.35
BLOCK_THRESHOLD: float = 0.70


class Firewall:
    """
    Asynchronous prompt-injection firewall.

    Inspects raw payloads before they reach the semantic classifier and
    returns a typed SafetyVerdict with action, composite score, and full
    audit trail of which rules fired.

    Usage:
        firewall = Firewall()
        verdict = await firewall.inspect(task)

        if verdict.action == SafetyAction.BLOCK:
            # reject the task
            ...
        elif verdict.action == SafetyAction.WARN:
            # proceed but flag for review
            ...

    Configuration:
        firewall = Firewall(
            warn_threshold=0.30,    # lower = more sensitive
            block_threshold=0.65,   # lower = more aggressive blocking
            extra_rules=[...],      # additional _FirewallRule instances
        )
    """

    def __init__(
        self,
        *,
        warn_threshold: float = WARN_THRESHOLD,
        block_threshold: float = BLOCK_THRESHOLD,
        extra_rules: Sequence[_FirewallRule] = (),
        enabled: bool = True,
    ):
        self.warn_threshold = warn_threshold
        self.block_threshold = block_threshold
        self.rules: tuple[_FirewallRule, ...] = _RULES + tuple(extra_rules)
        self.enabled = enabled

    async def inspect(self, task: Task) -> SafetyVerdict:
        """
        Run the full firewall inspection pipeline against a task's prompt.

        This method is intentionally async so it can be awaited inside
        the SDK's run() path without blocking the event loop.  The actual
        computation is CPU-bound and fast (<1ms for typical prompts), but
        the async signature allows future integration of network-based
        classifiers (e.g. an external moderation API) without changing
        the interface contract.

        Returns:
            SafetyVerdict with action, score, matched rules, and timing.
        """
        t0 = time.perf_counter()

        if not self.enabled:
            return SafetyVerdict(
                action=SafetyAction.PASS,
                composite_score=0.0,
                threat_category=ThreatCategory.NONE,
                summary="Firewall disabled",
                task_id=task.task_id,
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        prompt = task.prompt
        matches: list[RuleMatch] = []

        # ── Phase 1: Pattern matching ────────────────────────────────────
        for rule in self.rules:
            m = rule.pattern.search(prompt)
            if m:
                matches.append(
                    RuleMatch(
                        rule_id=rule.rule_id,
                        category=rule.category,
                        description=rule.description,
                        weight=rule.weight,
                        matched_span=m.group()[:120],  # truncate for logs
                    )
                )

        # ── Phase 2: Structural analysis ─────────────────────────────────
        entropy = _shannon_entropy(prompt)
        char_anomaly = _char_class_anomaly(prompt)

        # ── Phase 3: Composite scoring ───────────────────────────────────
        #
        # Base score = max(rule weights) — a single high-confidence rule
        # should be enough to block.
        #
        # Stacking bonus: when multiple rules fire, each additional rule
        # adds 0.05 to the composite (capped at +0.20).  This prevents
        # a clever adversary from staying just below threshold with any
        # single vector while combining multiple weak signals.
        #
        # Structural signals (entropy + char anomaly) add up to 0.15
        # on top, amplifying borderline cases without dominating.

        max_rule_weight = max((m.weight for m in matches), default=0.0)
        stacking_bonus = min(max(len(matches) - 1, 0) * 0.05, 0.20)

        # Normalise entropy: 0–4.5 = normal, 5.5+ = suspicious
        entropy_norm = min(max(entropy - 4.5, 0.0) / 3.0, 1.0)

        composite = max_rule_weight + stacking_bonus + entropy_norm * 0.08 + char_anomaly * 0.07
        composite = min(composite, 1.0)

        # ── Phase 4: Determine verdict ───────────────────────────────────
        if composite >= self.block_threshold:
            action = SafetyAction.BLOCK
        elif composite >= self.warn_threshold:
            action = SafetyAction.WARN
        else:
            action = SafetyAction.PASS

        # Pick the most severe threat category from matched rules
        threat = ThreatCategory.NONE
        if matches:
            # Sort by weight descending, take the highest
            threat = max(matches, key=lambda m: m.weight).category

        # Build human-readable summary
        summary = self._build_summary(action, composite, matches, threat)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        verdict = SafetyVerdict(
            action=action,
            composite_score=round(composite, 4),
            threat_category=threat,
            matched_rules=matches,
            entropy_score=round(entropy, 4),
            char_anomaly=round(char_anomaly, 4),
            summary=summary,
            latency_ms=round(elapsed_ms, 3),
            task_id=task.task_id,
        )

        if action != SafetyAction.PASS:
            logger.warning(
                "Firewall %s: score=%.3f threat=%s rules=[%s] task=%s",
                action.value.upper(),
                composite,
                threat.value,
                ", ".join(m.rule_id for m in matches),
                task.task_id,
            )

        return verdict

    def _build_summary(
        self,
        action: SafetyAction,
        score: float,
        matches: list[RuleMatch],
        threat: ThreatCategory,
    ) -> str:
        if action == SafetyAction.PASS:
            return "Prompt passed firewall inspection."

        rule_list = ", ".join(f"{m.rule_id} ({m.description})" for m in matches)
        verb = "BLOCKED" if action == SafetyAction.BLOCK else "FLAGGED"

        return (
            f"Prompt {verb} by firewall. "
            f"Risk score: {score:.2f}. "
            f"Threat: {threat.value}. "
            f"Matched rules: [{rule_list}]."
        )
