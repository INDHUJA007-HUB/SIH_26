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
    """Verify benchmark runner produces all 8 mandatory metric categories without prefilling."""
    runner = RegulatoryBenchmarkRunner()
    output = runner.run()

    assert output["packets_evaluated"] == 10
    metrics = output["metrics"]
    assert len(metrics) >= 16

    categories = {m["category"] for m in metrics}
    assert len(categories) == 8, f"Expected 8 mandatory categories, got {len(categories)}"

    # Category 1: Extraction accuracy
    digital_acc = next(
        m for m in metrics if m["metric_name"] == "Digital Strata Critical-Field Accuracy"
    )
    assert digital_acc["measured_value"] >= 0.95
    assert digital_acc["ci_95_lower"] is not None

    scanned_acc = next(
        m for m in metrics if m["metric_name"] == "Scanned Strata Critical-Field Accuracy"
    )
    assert scanned_acc["measured_value"] >= 0.90
    assert scanned_acc["ci_95_lower"] is not None

    # Category 2: Validation accuracy
    cadre_abst = next(
        m for m in metrics if m["metric_name"] == "Unresolved Interpretation Abstention Rate"
    )
    assert cadre_abst["measured_value"] == 1.0

    # Category 3: Anomaly performance
    cff = next(m for m in metrics if m["metric_name"] == "Clean-Packet False-Flag Rate")
    assert cff["measured_value"] == 0.0
    assert cff["ci_95_lower"] == 0.0

    false_adv = next(
        m for m in metrics if m["metric_name"] == "False Adverse Action Indicator Rate"
    )
    assert false_adv["measured_value"] == 0.0

    # Category 4: Source verification
    sim_ver = next(m for m in metrics if m["metric_name"] == "Simulated Status-Mapping Accuracy")
    assert sim_ver["measured_value"] == 1.0

    live_ver = next(m for m in metrics if m["metric_name"] == "Live Source Resolution Rate")
    assert "UNAVAILABLE" in str(live_ver["measured_value"])
    assert live_ver["ci_95_lower"] == 0.0
    assert live_ver["ci_95_upper"] == 0.0
    assert live_ver["status"] == "UNAVAILABLE_HONEST_DECLARATION"

    # Category 5: Discrepancy reliability
    loc = next(m for m in metrics if m["metric_name"] == "Evidence and Rule Locator Resolvability")
    assert loc["measured_value"] == 1.0

    # Category 6: Verification time
    med_time = next(m for m in metrics if m["metric_name"] == "Median Active Processing Time (s)")
    assert float(med_time["measured_value"]) < 30.0
    p95_time = next(m for m in metrics if m["metric_name"] == "p95 Active Processing Time (s)")
    assert float(p95_time["measured_value"]) < 120.0

    # Category 7: Alert timeliness
    replay_dedup = next(m for m in metrics if m["metric_name"] == "Replay Deduplication Rate")
    assert replay_dedup["measured_value"] == 1.0

    # Category 8: Manual effort reduction
    manual_effort = next(
        m for m in metrics if m["metric_name"] == "Paired Active Review Time Reduction"
    )
    assert manual_effort["measured_value"] == "STUDY_PENDING_UNMEASURED"
    assert manual_effort["status"] == "STUDY_PENDING_UNMEASURED"
