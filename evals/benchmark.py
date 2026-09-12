"""
LEADER – Empirical Metrics Engine & Benchmark Runner

Runs the standardized Public Adversarial Evaluation Suite against both
unprotected baseline and LEADER-protected environments, computing empirical
safety metrics, category breakdowns, and performance latency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from leader.circuit_breaker import CircuitBreaker  # noqa: E402
from leader.firewall_middleware import Firewall, SafetyAction, SafetyVerdict  # noqa: E402
from leader.models import Task  # noqa: E402

try:
    from .dataset import AdversarialDataset, load_dataset
except ImportError:
    from evals.dataset import AdversarialDataset, load_dataset  # noqa: E402


@dataclass
class CaseResult:
    """Individual test case evaluation outcome."""

    test_id: str
    category: str
    prompt: str
    is_adversarial: bool
    expected_action: str
    baseline_action: str
    protected_action: str
    composite_score: float
    threat_detected: str
    matched_rules: list[str]
    latency_ms: float
    passed_defense: bool  # True if defense acted appropriately (blocked threat OR passed benign)


@dataclass
class CategoryMetrics:
    """Evaluation metrics for a specific threat category."""

    category: str
    total_samples: int
    threat_samples: int
    benign_samples: int
    blocked_count: int
    passed_count: int
    detection_rate_pct: float
    avg_score: float
    avg_latency_ms: float


@dataclass
class EmpiricalMetrics:
    """Comprehensive benchmark results comparing baseline vs protected."""

    total_samples: int
    adversarial_samples: int
    benign_samples: int

    # Baseline (Unprotected Router)
    baseline_blocked_adversarial: int
    baseline_slipped_adversarial: int
    baseline_defense_rate_pct: float

    # LEADER Protected (Firewall + Circuit Breaker)
    true_positives: int  # Adversarial correctly blocked/warned
    false_positives: int  # Benign incorrectly blocked/warned
    true_negatives: int  # Benign correctly passed
    false_negatives: int  # Adversarial that slipped through (leakage)

    defense_rate_pct: float  # Recall: TP / (TP + FN)
    benign_pass_rate_pct: float  # Specificity: TN / (TN + FP)
    false_positive_rate_pct: float  # FP / (FP + TN)
    precision_pct: float  # TP / (TP + FP)
    f1_score: float
    accuracy_pct: float

    # Latency Performance
    avg_latency_ms: float
    p95_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    throughput_per_sec: float

    # Granular Breakdown
    category_breakdown: dict[str, CategoryMetrics] = field(default_factory=dict)
    detailed_results: list[CaseResult] = field(default_factory=list)


class BenchmarkRunner:
    """Executes the adversarial evaluation suite across security layers."""

    def __init__(
        self,
        dataset: AdversarialDataset | None = None,
        firewall: Firewall | None = None,
        circuit_breaker: CircuitBreaker | None = None,
    ):
        self.dataset = dataset or load_dataset()
        self.firewall = firewall or Firewall()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    async def run(self) -> EmpiricalMetrics:
        """Run the complete evaluation suite asynchronously."""
        results: list[CaseResult] = []
        latencies: list[float] = []

        start_time = time.perf_counter()

        for case in self.dataset.test_cases:
            task = Task(prompt=case.prompt, task_id=f"eval-{case.id}")

            # 1. Baseline Evaluation (No Defense Layer)
            # In raw routing, all prompts pass directly to downstream models.
            baseline_action = "pass"

            # 2. Protected Evaluation (Firewall Inspection)
            verdict: SafetyVerdict = await self.firewall.inspect(task)
            protected_action = verdict.action.value
            latencies.append(verdict.latency_ms)

            # Determine if defense acted correctly
            if case.is_adversarial:
                # Threat was appropriately intercepted (blocked or warned)
                passed_defense = verdict.action in (SafetyAction.BLOCK, SafetyAction.WARN)
            else:
                # Benign prompt was passed without false block
                passed_defense = verdict.action == SafetyAction.PASS

            results.append(
                CaseResult(
                    test_id=case.id,
                    category=case.category,
                    prompt=case.prompt,
                    is_adversarial=case.is_adversarial,
                    expected_action=case.expected_action,
                    baseline_action=baseline_action,
                    protected_action=protected_action,
                    composite_score=verdict.composite_score,
                    threat_detected=verdict.threat_category.value,
                    matched_rules=[m.rule_id for m in verdict.matched_rules],
                    latency_ms=verdict.latency_ms,
                    passed_defense=passed_defense,
                )
            )

        total_wall_time = time.perf_counter() - start_time

        return self._compute_metrics(results, latencies, total_wall_time)

    def run_sync(self) -> EmpiricalMetrics:
        """Synchronous wrapper for benchmark execution."""
        return asyncio.run(self.run())

    def _compute_metrics(
        self,
        results: list[CaseResult],
        latencies: list[float],
        total_time: float,
    ) -> EmpiricalMetrics:
        total = len(results)
        adv_cases = [r for r in results if r.is_adversarial]
        benign_cases = [r for r in results if not r.is_adversarial]

        total_adv = len(adv_cases)
        total_benign = len(benign_cases)

        # Baseline stats (raw router allows 100% of payloads through)
        baseline_blocked_adv = 0
        baseline_slipped_adv = total_adv
        baseline_defense_rate = 0.0

        # Protected stats
        tp = sum(1 for r in adv_cases if r.protected_action in ("block", "warn"))
        fn = sum(1 for r in adv_cases if r.protected_action == "pass")
        tn = sum(1 for r in benign_cases if r.protected_action == "pass")
        fp = sum(1 for r in benign_cases if r.protected_action in ("block", "warn"))

        defense_rate = (tp / total_adv * 100.0) if total_adv > 0 else 100.0
        benign_pass_rate = (tn / total_benign * 100.0) if total_benign > 0 else 100.0
        fpr = (fp / total_benign * 100.0) if total_benign > 0 else 0.0

        precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 100.0
        recall = (tp / total_adv) if total_adv > 0 else 1.0
        prec_val = (tp / (tp + fp)) if (tp + fp) > 0 else 1.0
        f1 = (2 * prec_val * recall / (prec_val + recall)) if (prec_val + recall) > 0 else 0.0
        accuracy = ((tp + tn) / total * 100.0) if total > 0 else 100.0

        # Latency statistics
        avg_lat = statistics.mean(latencies) if latencies else 0.0
        sorted_lat = sorted(latencies)
        p95_idx = int(len(sorted_lat) * 0.95)
        p95_lat = sorted_lat[min(p95_idx, len(sorted_lat) - 1)] if sorted_lat else 0.0
        min_lat = min(latencies) if latencies else 0.0
        max_lat = max(latencies) if latencies else 0.0
        throughput = (total / total_time) if total_time > 0 else 0.0

        # Category Breakdown
        categories = self.dataset.categories
        cat_metrics: dict[str, CategoryMetrics] = {}

        for cat in categories:
            cat_results = [r for r in results if r.category == cat]
            c_threats = sum(1 for r in cat_results if r.is_adversarial)
            c_benign = sum(1 for r in cat_results if not r.is_adversarial)
            c_blocked = sum(1 for r in cat_results if r.protected_action in ("block", "warn"))
            c_passed = sum(1 for r in cat_results if r.protected_action == "pass")

            if c_threats > 0:
                c_rate = (c_blocked / c_threats) * 100.0
            else:
                c_rate = (c_passed / c_benign) * 100.0 if c_benign > 0 else 100.0

            c_avg_score = (
                statistics.mean([r.composite_score for r in cat_results]) if cat_results else 0.0
            )
            c_avg_lat = statistics.mean([r.latency_ms for r in cat_results]) if cat_results else 0.0

            cat_metrics[cat] = CategoryMetrics(
                category=cat,
                total_samples=len(cat_results),
                threat_samples=c_threats,
                benign_samples=c_benign,
                blocked_count=c_blocked,
                passed_count=c_passed,
                detection_rate_pct=round(c_rate, 2),
                avg_score=round(c_avg_score, 4),
                avg_latency_ms=round(c_avg_lat, 3),
            )

        return EmpiricalMetrics(
            total_samples=total,
            adversarial_samples=total_adv,
            benign_samples=total_benign,
            baseline_blocked_adversarial=baseline_blocked_adv,
            baseline_slipped_adversarial=baseline_slipped_adv,
            baseline_defense_rate_pct=round(baseline_defense_rate, 2),
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            defense_rate_pct=round(defense_rate, 2),
            benign_pass_rate_pct=round(benign_pass_rate, 2),
            false_positive_rate_pct=round(fpr, 2),
            precision_pct=round(precision, 2),
            f1_score=round(f1, 4),
            accuracy_pct=round(accuracy, 2),
            avg_latency_ms=round(avg_lat, 3),
            p95_latency_ms=round(p95_lat, 3),
            min_latency_ms=round(min_lat, 3),
            max_latency_ms=round(max_lat, 3),
            throughput_per_sec=round(throughput, 1),
            category_breakdown=cat_metrics,
            detailed_results=results,
        )


def run_benchmark(dataset_path: Path | str | None = None) -> EmpiricalMetrics:
    """Run the evaluation suite and return computed metrics."""
    dataset = load_dataset(dataset_path)
    runner = BenchmarkRunner(dataset=dataset)
    return runner.run_sync()


def main():
    parser = argparse.ArgumentParser(
        description="LEADER Public Adversarial Evaluation Suite Runner"
    )
    parser.add_argument(
        "--dataset", type=str, default=None, help="Path to custom adversarial dataset JSON"
    )
    parser.add_argument(
        "--report", action="store_true", help="Generate markdown benchmark report file"
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")
    args = parser.parse_args()

    metrics = run_benchmark(args.dataset)

    if args.json:
        # Convert metrics to serializable dict
        data = asdict(metrics)
        print(json.dumps(data, indent=2))
        return

    try:
        from .reporter import BenchmarkReporter
    except ImportError:
        from evals.reporter import BenchmarkReporter

    reporter = BenchmarkReporter(metrics)
    reporter.print_terminal_summary()

    if args.report:
        report_path = reporter.save_markdown_report()
        print(f"\n[+] Public benchmark report successfully exported to: {report_path}")


if __name__ == "__main__":
    main()
