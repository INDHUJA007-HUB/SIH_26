"""Regression coverage for the phase 8–15 review defects, without service dependencies."""

import copy
import io
import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import create_engine, select

from workbench.adapters import tables as t
from workbench.adapters.media_analysis_application_service import MediaAnalysisService
from workbench.adapters.rectification_application_service import RectificationService
from workbench.modules.operations.drift import DriftAnalyzer
from workbench.modules.reporting.pdf import render_report_pdf
from workbench.modules.rule_governance.service import RuleGovernanceService as Governance
from workbench.modules.verification.signatures import SignatureVerificationEngine
from workbench.processing.media_decoder import decode_video


def bundle():
    return Governance.build_replay_bundle(
        "run", "application", {"intake": 420}, {}, [], {}
    ).model_dump()


def test_replay_hash_list_cannot_be_detached_from_manifest():
    data = bundle()
    data["files"]["facts.json"] = "tampered"
    data["file_hashes"] = {}
    assert Governance.verify_replay_bundle_offline(data)[0] is False


@pytest.mark.parametrize("mutation", ["missing", "extra", "changed"])
def test_replay_checks_complete_file_set(mutation):
    data = bundle()
    if mutation == "missing":
        del data["files"]["facts.json"]
    elif mutation == "extra":
        data["files"]["extra.json"] = "{}"
    else:
        data["files"]["facts.json"] += " "
    assert not Governance.verify_replay_bundle_offline(data)[0]


def test_clean_replay_bundle_passes():
    assert Governance.verify_replay_bundle_offline(bundle()) == (True, None)


def test_offline_export_reexecutes_frozen_rules_and_compares_outputs():
    import hashlib

    from workbench.modules.evaluation.evaluator import DeterministicEvaluator
    from workbench.modules.rule_governance.service import compute_canonical_hash
    from workbench.modules.rule_registry.models import RuleVersionRecord

    result = DeterministicEvaluator().evaluate(
        "institution",
        "application",
        "revision",
        None,
        None,
        {"intake": 420, "bandwidth_mbps": 100},
        {},
        "release",
        "release-hash",
        [
            RuleVersionRecord(
                id="r",
                rule_id="bandwidth",
                content_hash="rule-hash",
                dsl_expression={
                    "operation": "threshold_lookup",
                    "input_field": "intake",
                    "target_field": "bandwidth_mbps",
                    "tiers": [{"min": 1, "max": 600, "required": 300}],
                },
            )
        ],
    )
    keys = (
        "rule_id",
        "outcome",
        "rationale",
        "observed_value",
        "expected_value",
        "calculation_trace",
    )
    expected = [{k: o.model_dump(mode="json")[k] for k in keys} for o in result.outcomes]
    data = Governance.build_replay_bundle(
        result.run_id,
        "application",
        result.manifest["facts"],
        {},
        [],
        {"bandwidth": "rule-hash"},
        evaluation_snapshot=result.manifest,
        expected_outcomes=expected,
    ).model_dump()
    assert Governance.verify_replay_bundle_offline(data) == (True, None)
    payload = json.loads(data["files"]["evaluation.json"])
    payload["expected_outcomes"][0]["outcome"] = "PASS"
    data["files"]["evaluation.json"] = json.dumps(payload)
    digest = hashlib.sha256(data["files"]["evaluation.json"].encode()).hexdigest()
    data["file_hashes"]["evaluation.json"] = digest
    data["manifest"]["file_hashes"]["evaluation.json"] = digest
    data["bundle_hash"] = compute_canonical_hash(data["manifest"])
    assert Governance.verify_replay_bundle_offline(data)[1].startswith("REPLAY_MISMATCH")


@pytest.mark.parametrize("rule,facts", [("UNKNOWN", {}), ("APH-INFRA-BW-001", {})])
def test_unsupported_or_missing_scenario_inputs_abstain(rule, facts):
    assert Governance._evaluate_single_rule(rule, {}, facts) == "NOT_EVALUABLE"


def test_zero_bandwidth_is_a_value_not_missing():
    assert (
        Governance._evaluate_single_rule(
            "APH-INFRA-BW-001",
            {},
            {
                "approved_intake": 420,
                "bandwidth_mbps": 0,
            },
        )
        == "DEFICIENT"
    )


def test_no_intake_optimization_without_approved_policy():
    with pytest.raises(ValueError, match="independently approved"):
        Governance.calculate_remedy("a", "f", "APH-INTAKE-REDUCE-001", "clause", {})


def test_blank_image_produces_explicit_manual_fallback():
    engine = create_engine("sqlite://")
    t.equipment_detections.create(engine)
    image = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(image, format="PNG")
    with engine.begin() as conn:
        result = MediaAnalysisService(conn).run_equipment_detection(
            "inst",
            "app",
            "evidence",
            "room",
            30,
            image_bytes=image.getvalue(),
        )
    assert result.model_mode == "EXPRESS_MANUAL_FALLBACK"
    assert result.detected_boxes == []
    assert result.confidence_score == 0
    assert result.coverage_assessment["count_known"] is False
    assert result.model_name == "manual-comparison"


def test_signature_markers_never_establish_validity():
    result = SignatureVerificationEngine().inspect_pdf_signatures(
        b"%PDF /ByteRange /Contents /SubFilter fabricated"
    )
    assert result["status"] != "VALID"
    assert result["simulated"] is False


@pytest.mark.parametrize(
    "url", ["http://aicte-india.org/a", "https://aicte-india.org.evil.test/a", "ftp://gov.in/a"]
)
def test_qr_requires_https_and_allowlisted_host(url):
    assert not SignatureVerificationEngine().decode_and_verify_qr(url)["destination_safe"]


def test_drift_uses_captured_predictions(tmp_path):
    packet = {
        "packet_id": "p",
        "ground_truth": {"intake": 60},
        "predictions": {
            "champion": {"intake": {"value": 60, "confidence": 0.9}},
            "candidate": {"intake": {"value": 50, "confidence": 0.7}},
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps([packet]))
    original = copy.deepcopy(packet)
    result = DriftAnalyzer(path).evaluate("candidate", "champion")
    assert result.measurement_status == "MEASURED"
    assert result.champion_precision == 1
    assert result.challenger_precision == 0
    assert result.field_metrics[0].drift_detected
    assert json.loads(path.read_text()) == [original]


def test_video_decodes_real_frames(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        pytest.skip("Requires installed ffmpeg and ffprobe")
    path = tmp_path / "video.mp4"
    subprocess.run(  # noqa: S603
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=160x90:d=2",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        timeout=20,
    )
    metadata, frames = decode_video(path.read_bytes(), max_frames=2)
    assert 1.9 <= metadata["duration_seconds"] <= 2.1
    assert 1 <= len(frames) <= 2
    with Image.open(io.BytesIO(frames[0][1])) as image:
        red, green, blue = image.convert("RGB").getpixel((20, 20))
        assert red > 200 and green < 40 and blue < 40


def test_response_creates_revision_and_stored_run_diff():
    engine = create_engine("sqlite://")
    t.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            t.applications.insert().values(
                id="app",
                institution_id="inst",
                category="EOA",
                cycle_start=2026,
                programme="E&T",
                level="UG",
                jurisdiction="TN",
                stage="SUBMITTED",
                revision=1,
                declared_facts={"bandwidth_mbps": 100},
                created_by="applicant",
            )
        )
        conn.execute(
            t.revisions.insert().values(
                id="revision1",
                institution_id="inst",
                application_id="app",
                revision=1,
                stage="SUBMITTED",
                manifest={"evidence": [], "declared_facts": {"bandwidth_mbps": 100}},
                sha256="original",
            )
        )
        conn.execute(
            t.evaluation_runs.insert().values(
                id="baseline",
                institution_id="inst",
                application_id="app",
                application_revision_id="revision1",
                manifest_hash="base",
                evaluation_as_of="2026-10-29",
            )
        )
        conn.execute(
            t.findings.insert().values(
                id="finding",
                run_id="baseline",
                institution_id="inst",
                application_id="app",
                rule_id="bandwidth",
                semantic_key="requirement:bandwidth",
                dimension="COMPLIANCE",
                severity="DEFICIENCY",
                status="OPEN",
                title="Bandwidth",
                description="Too low",
            )
        )
    service = RectificationService(engine)
    window = service.open_response_window(
        institution_id="inst",
        application_id="app",
        opened_by="officer",
        authority_reference="policy-demo",
        allowed_slots=[],
        allowed_fields=["bandwidth_mbps"],
        deadline=datetime.now(UTC) + timedelta(days=1),
    )
    response = service.submit_rectification_response(
        institution_id="inst",
        application_id="app",
        window_id=window["id"],
        submitted_by="applicant",
        field_updates={"bandwidth_mbps": 300},
    )
    with engine.begin() as conn:
        old = (
            conn.execute(select(t.revisions).where(t.revisions.c.id == "revision1"))
            .mappings()
            .one()
        )
        new = conn.execute(select(t.revisions).where(t.revisions.c.revision == 2)).mappings().one()
        assert old["manifest"]["declared_facts"]["bandwidth_mbps"] == 100
        assert new["manifest"]["declared_facts"]["bandwidth_mbps"] == 300
        assert conn.scalar(
            select(t.outbox.c.id).where(t.outbox.c.event_type == "RectificationSubmitted")
        )
        conn.execute(
            t.evaluation_runs.insert().values(
                id="reassessment",
                institution_id="inst",
                application_id="app",
                application_revision_id=new["id"],
                manifest_hash="new",
                evaluation_as_of="2026-10-29",
            )
        )
        conn.execute(
            t.requirement_outcomes.insert().values(
                id="outcome",
                run_id="reassessment",
                institution_id="inst",
                application_id="app",
                rule_id="bandwidth",
                requirement_name="Bandwidth",
                outcome="PASS",
                rationale="Meets requirement",
            )
        )
    result = service.reassess_and_diff(
        institution_id="inst",
        application_id="app",
        response_id=response["id"],
        baseline_run_id="baseline",
        reassessed_findings=[],
        new_run_id="reassessment",
    )
    assert result["diff_summary"]["resolved"] == 1
    assert (
        service.reassess_and_diff(
            institution_id="inst",
            application_id="app",
            response_id=response["id"],
            baseline_run_id="baseline",
            reassessed_findings=[],
            new_run_id="reassessment",
        )["id"]
        == result["id"]
    )


def test_pdf_is_deterministic_and_text_is_readable():
    from pypdf import PdfReader

    report = {
        "audience": "APPLICANT",
        "report_hash": "abc123",
        "content": {
            "report_metadata": {"application_id": "application1"},
            "findings": [{"rule_id": "bandwidth", "explanation": "Provide 300 Mbps evidence."}],
        },
    }
    first = render_report_pdf(report)
    assert first == render_report_pdf(report)
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(first)).pages)
    assert "Provide 300 Mbps evidence." in text
    assert "Preliminary decision support" in text
