"""Deterministic Benchmark Runner for Regulatory Evaluation Qualification (Subphase 13.3).

Executes across all eight mandatory metric categories defined in
docs/BACKEND_IMPLEMENTATION_PLAN.md Section 11.3:
1. Extraction accuracy (digital vs. scanned strata + coverage)
2. Validation accuracy (per-requirement + whole-packet + NOT_EVALUABLE abstentions)
3. Anomaly performance (precision/recall/F1 + clean false-flag and false-adverse rates)
4. Successful source verification (explicit simulated mapping vs. 0% live resolution)
5. Discrepancy reliability (localization + 100% resolvable locators)
6. Verification time (median and p95 active processing time with bootstrap CIs)
7. Alert timeliness (commit-to-alert latency + 0 duplicate open alerts on replay)
8. Manual effort reduction (honest STUDY_PENDING_UNMEASURED label)
"""

from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from benchmarks.evaluation.metrics import (
    bootstrap_confidence_interval,
    percentile_95,
    wilson_score_interval,
)


@dataclass
class MetricResult:
    category: str
    metric_name: str
    numerator: int | float | None
    denominator: int | float | None
    measured_value: float | str
    ci_95_lower: float | None
    ci_95_upper: float | None
    target: str
    status: str
    notes: str


class RegulatoryBenchmarkRunner:
    """Executes frozen synthetic benchmark evaluation and produces structured qualification report."""

    def __init__(self, manifests_path: Path | None = None) -> None:
        if manifests_path is None:
            manifests_path = (
                Path(__file__).resolve().parent.parent
                / "manifests"
                / "packet_manifests.json"
            )
        self.manifests_path = manifests_path
        with open(self.manifests_path, encoding="utf-8") as f:
            self.manifests = json.load(f)

    def run(self, observations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Aggregate captured predictions against labeled observations, never preset scores.

        Each observation identifies a packet, category (1..8), metric name, success
        boolean and evidence reference. Timing observations use a nonnegative value.
        Callers must retain the underlying immutable capture for independent review.
        """
        observations = observations or []
        packets = {p["packet_id"] for p in self.manifests}
        grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for item in observations:
            if item.get("packet_id") not in packets or not item.get(
                "evidence_reference"
            ):
                raise ValueError(
                    "Observations require a known packet and captured evidence reference"
                )
            category = item.get("category")
            if not isinstance(category, int) or category not in range(1, 9):
                raise ValueError("Observation category must be 1..8")
            grouped.setdefault((category, item["metric_name"]), []).append(item)
        categories = [
            "Extraction Accuracy",
            "Validation Accuracy",
            "Anomaly Performance",
            "Source Verification",
            "Discrepancy Reliability",
            "Verification Time",
            "Alert Timeliness",
            "Manual Effort Reduction",
        ]
        results: list[MetricResult] = []
        for category, name in enumerate(categories, 1):
            groups = [
                (key, rows) for key, rows in grouped.items() if key[0] == category
            ]
            if not groups:
                results.append(
                    MetricResult(
                        category=f"{category}. {name}",
                        metric_name=name,
                        numerator=None,
                        denominator=None,
                        measured_value="UNMEASURED",
                        ci_95_lower=None,
                        ci_95_upper=None,
                        target="Requires approved acceptance target",
                        status="UNMEASURED",
                        notes="No captured observations supplied; qualification blocked",
                    )
                )
                continue
            for (_, metric_name), rows in groups:
                if all(type(r.get("success")) is bool for r in rows):
                    successes = sum(r["success"] for r in rows)
                    low, high = wilson_score_interval(successes, len(rows))
                    result = MetricResult(
                        category=f"{category}. {name}",
                        metric_name=metric_name,
                        numerator=successes,
                        denominator=len(rows),
                        measured_value=successes / len(rows),
                        ci_95_lower=low,
                        ci_95_upper=high,
                        target="Requires approved acceptance target",
                        status="MEASURED",
                        notes="Aggregated from captured observations; not pilot sign-off",
                    )
                else:
                    values = [float(r["value"]) for r in rows]
                    if any(not math.isfinite(v) or v < 0 for v in values):
                        raise ValueError("Measurements must be finite and nonnegative")
                    low, high = bootstrap_confidence_interval(values, statistics.median)
                    result = MetricResult(
                        category=f"{category}. {name}",
                        metric_name=metric_name,
                        numerator=None,
                        denominator=len(values),
                        measured_value=statistics.median(values),
                        ci_95_lower=low,
                        ci_95_upper=high,
                        target="Requires approved acceptance target",
                        status="MEASURED",
                        notes=f"Median captured value; p95={percentile_95(values)}",
                    )
                results.append(result)
        return {
            "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "packets_evaluated": len({o["packet_id"] for o in observations}),
            "metrics": [asdict(r) for r in results],
            "qualification_status": "REQUIRES_REVIEW" if observations else "UNMEASURED",
        }


def format_markdown_table(benchmark_output: dict[str, Any]) -> str:
    """Format benchmark metrics into markdown table for documentation."""
    lines = [
        "| Metric Category | Metric Name | Numerator / Denom | Measured Value | 95% Confidence Interval | Target | Status | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for m in benchmark_output["metrics"]:
        nd = (
            f"{m['numerator']}/{m['denominator']}"
            if m["numerator"] is not None and m["denominator"] is not None
            else "N/A"
        )
        val = str(m["measured_value"])
        if m["ci_95_lower"] is not None and m["ci_95_upper"] is not None:
            ci = f"[{m['ci_95_lower']}, {m['ci_95_upper']}]"
        else:
            ci = "N/A"
        lines.append(
            f"| {m['category']} | {m['metric_name']} | {nd} | {val} | {ci} | {m['target']} | **{m['status']}** | {m['notes']} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    runner = RegulatoryBenchmarkRunner()
    report = runner.run()
    print(format_markdown_table(report))
