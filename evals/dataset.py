"""
LEADER – Evaluation Dataset Loader

Provides typed schemas and loading utilities for the standardized
Public Adversarial Evaluation Suite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATASET_PATH = Path(__file__).parent / "data" / "adversarial_suite.json"


@dataclass(frozen=True)
class TestCase:
    """A single evaluation test case."""

    id: str
    category: str
    prompt: str
    is_adversarial: bool
    expected_action: str  # "pass", "warn", or "block"
    description: str


@dataclass
class AdversarialDataset:
    """Container for the evaluation dataset and metadata."""

    metadata: dict[str, str]
    test_cases: list[TestCase]

    @property
    def total_cases(self) -> int:
        return len(self.test_cases)

    @property
    def adversarial_cases(self) -> list[TestCase]:
        return [tc for tc in self.test_cases if tc.is_adversarial]

    @property
    def benign_cases(self) -> list[TestCase]:
        return [tc for tc in self.test_cases if not tc.is_adversarial]

    def cases_by_category(self, category: str) -> list[TestCase]:
        return [tc for tc in self.test_cases if tc.category == category]

    @property
    def categories(self) -> list[str]:
        seen = set()
        cats = []
        for tc in self.test_cases:
            if tc.category not in seen:
                seen.add(tc.category)
                cats.append(tc.category)
        return cats


def load_dataset(path: Path | str | None = None) -> AdversarialDataset:
    """Load the evaluation dataset from a JSON file.

    Args:
        path: Path to the JSON dataset file. Defaults to `evals/data/adversarial_suite.json`.

    Returns:
        AdversarialDataset instance.
    """
    dataset_path = Path(path) if path else DEFAULT_DATASET_PATH
    if not dataset_path.exists():
        raise FileNotFoundError(f"Adversarial evaluation dataset not found at: {dataset_path}")

    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)

    test_cases = [
        TestCase(
            id=item["id"],
            category=item["category"],
            prompt=item["prompt"],
            is_adversarial=bool(item.get("is_adversarial", True)),
            expected_action=item.get("expected_action", "block"),
            description=item.get("description", ""),
        )
        for item in data.get("test_cases", [])
    ]

    return AdversarialDataset(
        metadata=data.get("metadata", {}),
        test_cases=test_cases,
    )
