import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from benchmarks.evaluation.metrics import wilson_score_interval
from benchmarks.evaluation.runner import RegulatoryBenchmarkRunner


def test_wilson_score_interval_properties():
    """Verify Wilson score confidence interval boundary properties."""
    # Zero successes
    low, high = wilson_score_interval(0, 10, confidence=0.95)
    assert low == 0.0
    assert 0.0 < high < 1.0

    # 100% successes
    low, high = wilson_score_interval(10, 10, confidence=0.95)
    assert 0.0 < low < 1.0
    assert high == 1.0

    # Symmetry around 50%
    low, high = wilson_score_interval(50, 100, confidence=0.95)
    assert abs((0.5 - low) - (high - 0.5)) < 1e-4

    # Empty denominator
    assert wilson_score_interval(0, 0) == (0.0, 0.0)


def test_regulatory_benchmark_runner_all_eight_categories():
    runner = RegulatoryBenchmarkRunner()
    output = runner.run()
    assert output["packets_evaluated"] == 0
    assert len({m["category"] for m in output["metrics"]}) == 8
    assert all(m["status"] == "UNMEASURED" for m in output["metrics"])
    assert all(m["numerator"] is None for m in output["metrics"])


def test_benchmark_aggregates_captured_results():
    runner = RegulatoryBenchmarkRunner()
    packet = runner.manifests[0]["packet_id"]
    observations = [
        {
            "packet_id": packet,
            "category": 1,
            "metric_name": "Field accuracy",
            "success": value,
            "evidence_reference": f"capture-{i}.json",
        }
        for i, value in enumerate([True, False, True])
    ]
    observations.append(
        {
            "packet_id": packet,
            "category": 6,
            "metric_name": "Processing time",
            "value": 7.5,
            "evidence_reference": "timings.json",
        }
    )
    output = runner.run(observations)
    accuracy = next(m for m in output["metrics"] if m["metric_name"] == "Field accuracy")
    assert accuracy["measured_value"] == 2 / 3
    assert accuracy["denominator"] == 3
    assert accuracy["ci_95_lower"] < 2 / 3 < accuracy["ci_95_upper"]
    assert (
        next(m for m in output["metrics"] if m["metric_name"] == "Processing time")[
            "measured_value"
        ]
        == 7.5
    )
