"""Subphase 15.2: Champion/Challenger extraction and rule-drift evaluation."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from workbench.modules.operations.contracts import (
    DriftEvaluationResult,
    FieldDriftMetric,
)

logger = logging.getLogger("workbench.modules.operations.drift")


# Ground-truth field expectations for benchmark packets
BENCHMARK_GROUND_TRUTH_FIELDS: dict[str, dict[str, Any]] = {
    "approved_intake": {"expected": 420, "type": "int", "template": "application_form"},
    "total_area_sqm": {"expected": 15000, "type": "int", "template": "land_document"},
    "bandwidth_mbps": {"expected": 300, "type": "int", "template": "isp_invoice"},
    "faculty_count": {"expected": 28, "type": "int", "template": "faculty_roster"},
    "built_up_area_sqm": {"expected": 12500, "type": "int", "template": "architect_certificate"},
}


class DriftAnalyzer:
    """Evaluates candidate model/extractor versions against frozen benchmark packets."""

    def __init__(self, manifests_path: Path | None = None) -> None:
        if manifests_path is None:
            # Look relative to repo root
            root = Path(__file__).resolve().parents[5]
            manifests_path = root / "benchmarks" / "manifests" / "packet_manifests.json"
        self.manifests_path = manifests_path
        self.packets = self._load_manifests()

    def _load_manifests(self) -> list[dict[str, Any]]:
        if not self.manifests_path.exists():
            return []
        with open(self.manifests_path, encoding="utf-8") as f:
            return cast(list[dict[str, Any]], json.load(f))

    def evaluate(
        self,
        candidate_version: str,
        champion_version: str = "aicte_ocr_extractor_v1.0.0",
        simulated_noise_rate: float = 0.05,
    ) -> DriftEvaluationResult:
        """Run champion vs challenger evaluation over frozen benchmark packets.

        This process is strictly read-only and does not mutate any historical
        extraction runs or frozen fact sets in the database.
        """
        packets = [
            p
            for p in self.packets
            if p.get("ground_truth")
            and champion_version in p.get("predictions", {})
            and candidate_version in p.get("predictions", {})
        ]
        if not packets:
            return DriftEvaluationResult(
                candidate_version=candidate_version,
                champion_version=champion_version,
                benchmark_packet_count=0,
                evaluated_field_count=0,
                champion_precision=0,
                challenger_precision=0,
                champion_recall=0,
                challenger_recall=0,
                macro_f1_delta=0,
                template_drift_detected=False,
                field_metrics=[],
                summary=(
                    "UNMEASURED: provide frozen ground truth and both versioned prediction captures"
                ),
                measurement_status="UNMEASURED",
            )
        packet_count = len(packets)
        field_names = sorted(set.intersection(*(set(p["ground_truth"]) for p in packets)))
        total_evaluations = packet_count * len(field_names)
        field_stats: dict[str, dict[str, int | float]] = {
            f: {
                "champion_matches": 0,
                "challenger_matches": 0,
                "agreement_count": 0,
                "conf_delta_sum": 0.0,
            }
            for f in field_names
        }
        template_mismatches: dict[str, int] = {}
        for packet in packets:
            template = packet.get("template_family", "unknown")
            for fname in field_names:
                stats = field_stats[fname]
                expected = packet["ground_truth"][fname]
                champion = packet["predictions"][champion_version].get(fname, {})
                candidate = packet["predictions"][candidate_version].get(fname, {})
                stats["champion_matches"] += int(champion.get("value") == expected)
                stats["challenger_matches"] += int(candidate.get("value") == expected)
                agrees = champion.get("value") == candidate.get("value")
                stats["agreement_count"] += int(agrees)
                stats["conf_delta_sum"] += float(candidate.get("confidence", 0)) - float(
                    champion.get("confidence", 0)
                )
                if not agrees:
                    template_mismatches[template] = template_mismatches.get(template, 0) + 1

        # Aggregate field-level metrics
        field_metrics: list[FieldDriftMetric] = []
        total_champ_matches = 0
        total_chall_matches = 0

        for fname in field_names:
            s = field_stats[fname]
            champ_m = int(s["champion_matches"])
            chall_m = int(s["challenger_matches"])
            agree_m = int(s["agreement_count"])
            conf_delta = float(s["conf_delta_sum"]) / max(1, packet_count)
            agree_rate = agree_m / max(1, packet_count)

            total_champ_matches += champ_m
            total_chall_matches += chall_m

            # Drift detected if agreement rate < 90% or significant confidence drop
            drift_detected = agree_rate < 0.90 or conf_delta < -0.10

            field_metrics.append(
                FieldDriftMetric(
                    field_name=fname,
                    ground_truth_matches=packet_count,
                    champion_matches=champ_m,
                    challenger_matches=chall_m,
                    agreement_rate=round(agree_rate, 4),
                    confidence_delta=round(conf_delta, 4),
                    drift_detected=drift_detected,
                )
            )

        champ_precision = round(total_champ_matches / max(1, total_evaluations), 4)
        chall_precision = round(total_chall_matches / max(1, total_evaluations), 4)
        champ_recall = champ_precision
        chall_recall = chall_precision

        champ_f1 = (2 * champ_precision * champ_recall) / max(
            0.0001, champ_precision + champ_recall
        )
        chall_f1 = (2 * chall_precision * chall_recall) / max(
            0.0001, chall_precision + chall_recall
        )
        f1_delta = round(chall_f1 - champ_f1, 4)

        # Template drift if any template has disproportionate errors (>25% mismatch)
        template_drift = any(
            errs > (packet_count * len(field_names) * 0.15) for errs in template_mismatches.values()
        )

        champ_score = round(champ_f1, 4)
        chall_score = round(chall_f1, 4)
        summary_parts = [
            (
                f"Evaluated {packet_count} frozen benchmark packets "
                f"across {len(field_names)} target fields."
            ),
            (
                f"Champion ({champion_version}) F1: {champ_score}; "
                f"Challenger ({candidate_version}) F1: {chall_score} (Delta: {f1_delta:+0.4f})."
            ),
        ]
        if any(fm.drift_detected for fm in field_metrics):
            drifted = [fm.field_name for fm in field_metrics if fm.drift_detected]
            summary_parts.append(f"Regulatory field drift detected on: {', '.join(drifted)}.")
        else:
            summary_parts.append("No critical field drift detected across evaluated packets.")

        return DriftEvaluationResult(
            candidate_version=candidate_version,
            champion_version=champion_version,
            benchmark_packet_count=packet_count,
            evaluated_field_count=total_evaluations,
            champion_precision=champ_precision,
            challenger_precision=chall_precision,
            champion_recall=champ_recall,
            challenger_recall=chall_recall,
            macro_f1_delta=f1_delta,
            template_drift_detected=template_drift,
            field_metrics=field_metrics,
            summary=" ".join(summary_parts),
            immutable_historical_data_preserved=True,
            evaluated_at=datetime.now(UTC),
        )


def evaluate_champion_challenger(
    candidate_version: str,
    champion_version: str = "aicte_ocr_extractor_v1.0.0",
    manifests_path: Path | None = None,
) -> DriftEvaluationResult:
    """Convenience functional API for drift evaluation."""
    analyzer = DriftAnalyzer(manifests_path=manifests_path)
    return analyzer.evaluate(candidate_version=candidate_version, champion_version=champion_version)


def main() -> None:
    """CLI entrypoint for drift analysis."""
    parser = argparse.ArgumentParser(
        description="Evaluate champion/challenger extractor drift against frozen benchmarks."
    )
    parser.add_argument(
        "--candidate", required=True, help="Candidate extractor/model version identifier"
    )
    parser.add_argument(
        "--champion",
        default="aicte_ocr_extractor_v1.0.0",
        help="Champion extractor version baseline",
    )
    parser.add_argument("--manifests", default=None, help="Path to packet_manifests.json")
    args = parser.parse_args()

    manifest_path = Path(args.manifests) if args.manifests else None
    result = evaluate_champion_challenger(
        candidate_version=args.candidate,
        champion_version=args.champion,
        manifests_path=manifest_path,
    )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
