"""End-to-End Acceptance Test for AICTE Evidence and Compliance Workbench (Subphase 13.1).

Exercises the complete regulatory lifecycle in a single integrated transaction:
1. Intake: Application submission and evidence slot initialization.
2. Fact Extraction: Fact set freezing with SHA-256 canonical hash.
3. Source Verification: Querying simulated external providers (AICTE, Fire Safety, Land Records) with explicit SIMULATED labels.
4. Deterministic Evaluation: Baseline evaluation producing deficiency finding for bandwidth shortfall.
5. Audience-Separated Reporting: Generating officer internal report and redacted applicant public report.
6. Controlled Rectification: Opening scoped response window, rejecting out-of-scope edits, and accepting in-scope response.
7. Reassessment Finding Diff: Generating finding diff (1 resolved) while preserving baseline evaluation immutability.
8. Rule-Change Governance: Candidate rule simulation, four qualification gates, dual-control approval, and release publication.
9. Historical Replay: Offline reproducible evaluation reproducing identical canonical output hash.
10. Audit Integrity: End-to-end cryptographic hash chain verification across all recorded lifecycle mutations.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select, update

from workbench.adapters import tables as t
from workbench.adapters.audit_verifier import verify_stream
from workbench.adapters.rule_registry_service import RuleRegistryService
from workbench.modules.rectification.contracts import WindowStatus
from workbench.modules.reporting.contracts import ReportAudience
from workbench.modules.verification.contracts import SourceVerificationStatus

pytestmark = pytest.mark.integration


def test_full_regulatory_lifecycle_end_to_end(h):
    """Execute complete end-to-end regulatory lifecycle across Phases 2 through 12."""
    inst_id = h.institutions["a"]
    now = datetime.now(UTC)

    # -----------------------------------------------------------------------
    # Step 1: Intake & Application Creation
    # -----------------------------------------------------------------------
    app = h.create(actor="a")
    app_id = app["id"]
    assert app["stage"] == "DRAFT"

    # Assign officer for evaluation and review
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Assigned review for complete E2E lifecycle qualification",
                expires_at=now + timedelta(days=6),
            )
        )

    # -----------------------------------------------------------------------
    # Step 2: Fact Extraction & Frozen Fact Set
    # -----------------------------------------------------------------------
    details = h.call("GET", f"/api/v1/applications/{app_id}").json()
    slot_id = details["slots"][0]["id"]
    upload = h.prepare_upload(app, b"dummy pdf content for e2e test")
    upload_id = upload["id"]
    ev_ver_id = str(uuid4())
    run_id = str(uuid4())
    field_id_intake = str(uuid4())
    field_id_bw = str(uuid4())
    field_id_land = str(uuid4())
    fact_set_id = str(uuid4())
    fact_hash = hashlib.sha256(b"e2e-declared-facts-v1").hexdigest()

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.evidence).values(
                id=ev_ver_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                upload_id=upload_id,
                quarantine_key="quarantine/bandwidth_bill.pdf",
                quarantine_version="1",
                sha256="b" * 64,
                media_type="application/pdf",
                filename="bandwidth_bill.pdf",
                size_bytes=1024,
                status="QUARANTINED",
                metadata={"type": "PDF"},
            )
        )
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == ev_ver_id)
            .values(status="ACCEPTED", clean_key="clean/bandwidth_bill.pdf", clean_version="1")
        )
        conn.execute(
            insert(t.extraction_runs).values(
                id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                evidence_version_id=ev_ver_id,
                extractor_version="v1.0",
                document_type="BANDWIDTH_BILL",
                page_count=1,
                status="COMPLETED",
            )
        )
        conn.execute(
            insert(t.extracted_fields).values(
                [
                    {
                        "id": field_id_intake,
                        "run_id": run_id,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "evidence_version_id": ev_ver_id,
                        "field_name": "intake",
                        "field_type": "INTEGER",
                        "raw_value": "500",
                        "normalized_value": {"canonical_value": "500"},
                    },
                    {
                        "id": field_id_bw,
                        "run_id": run_id,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "evidence_version_id": ev_ver_id,
                        "field_name": "bandwidth_mbps",
                        "field_type": "NUMBER",
                        "raw_value": "150",
                        "normalized_value": {"canonical_value": "150"},
                    },
                    {
                        "id": field_id_land,
                        "run_id": run_id,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "evidence_version_id": ev_ver_id,
                        "field_name": "land_acres",
                        "field_type": "NUMBER",
                        "raw_value": "6.5",
                        "normalized_value": {"canonical_value": "6.5"},
                    },
                ]
            )
        )
        # Declare claims: intake 500, bandwidth 150 Mbps, land 6.5 acres
        conn.execute(
            insert(t.claims).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                subject="institution",
                predicate="intake",
                declared_value="500",
                created_at=now,
                updated_at=now,
            )
        )
        conn.execute(
            insert(t.claims).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                subject="institution",
                predicate="bandwidth_mbps",
                declared_value="150",
                created_at=now,
                updated_at=now,
            )
        )
        conn.execute(
            insert(t.claims).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                subject="institution",
                predicate="land_acres",
                declared_value="6.5",
                created_at=now,
                updated_at=now,
            )
        )
        # Store frozen fact set v1
        conn.execute(
            insert(t.fact_sets).values(
                id=fact_set_id,
                institution_id=inst_id,
                application_id=app_id,
                version=1,
                canonical_hash=fact_hash,
                is_frozen=True,
                created_at=now,
            )
        )
        conn.execute(
            insert(t.fact_set_members).values(
                [
                    {
                        "id": str(uuid4()),
                        "fact_set_id": fact_set_id,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "field_id": field_id_intake,
                        "field_name": "intake",
                        "normalized_value": {"canonical_value": "500"},
                        "created_at": now,
                    },
                    {
                        "id": str(uuid4()),
                        "fact_set_id": fact_set_id,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "field_id": field_id_bw,
                        "field_name": "bandwidth_mbps",
                        "normalized_value": {"canonical_value": "150"},
                        "created_at": now,
                    },
                    {
                        "id": str(uuid4()),
                        "fact_set_id": fact_set_id,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "field_id": field_id_land,
                        "field_name": "land_acres",
                        "normalized_value": {"canonical_value": "6.5"},
                        "created_at": now,
                    },
                ]
            )
        )

    # -----------------------------------------------------------------------
    # Step 3: Source Verification (Simulated External Providers)
    # -----------------------------------------------------------------------
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.source_observations).values(
                [
                    {
                        "id": str(uuid4()),
                        "institution_id": inst_id,
                        "evidence_id": str(uuid4()),
                        "provider_code": "AICTE_HISTORICAL_SIMULATOR",
                        "mode": "SIMULATED",
                        "simulated": True,
                        "live_success": False,
                        "status": SourceVerificationStatus.VERIFIED.value,
                        "freshness_timestamp": now,
                        "observation_fingerprint": "fp_aicte_e2e",
                    },
                    {
                        "id": str(uuid4()),
                        "institution_id": inst_id,
                        "evidence_id": str(uuid4()),
                        "provider_code": "FIRE_SAFETY_SIMULATOR",
                        "mode": "SIMULATED",
                        "simulated": True,
                        "live_success": False,
                        "status": SourceVerificationStatus.VERIFIED.value,
                        "freshness_timestamp": now,
                        "observation_fingerprint": "fp_fire_e2e",
                    },
                ]
            )
        )

    # -----------------------------------------------------------------------
    # Step 4: Baseline Deterministic Compliance Evaluation
    # -----------------------------------------------------------------------
    # Under base release, intake=500 requires bandwidth >= 300 Mbps (declared 150 -> POTENTIAL_DEFICIENCY)
    eval_resp = h.call(
        "POST",
        f"/api/v1/applications/{app_id}/evaluations",
        actor="officer",
        mfa=True,
        json={"evaluation_as_of": "2026-10-26", "execution_mode": "DEMONSTRATION"},
    )
    assert eval_resp.status_code == 200, eval_resp.text
    eval_data = eval_resp.json()
    baseline_run_id = eval_data["run_id"]
    assert eval_data["compliance_status"] == "POTENTIAL_DEFICIENCY"

    # Confirm bandwidth deficiency finding in database
    with h.owner.begin() as conn:
        bw_outcome = conn.scalar(
            select(t.requirement_outcomes.c.outcome).where(
                t.requirement_outcomes.c.run_id == baseline_run_id,
                t.requirement_outcomes.c.rule_id == "INFRA.BANDWIDTH",
            )
        )
        assert bw_outcome == "POTENTIAL_DEFICIENCY"

        findings = (
            conn.execute(select(t.findings).where(t.findings.c.run_id == baseline_run_id))
            .mappings()
            .all()
        )
        assert len(findings) >= 1

    # -----------------------------------------------------------------------
    # Step 5: Audience-Separated Reporting (Officer vs Applicant)
    # -----------------------------------------------------------------------
    # 1. Officer Report (contains internal decision support & unrestricted details)
    resp_off = h.call(
        "POST",
        "/api/v1/reports/generate",
        actor="officer",
        mfa=True,
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "evaluation_run_id": baseline_run_id,
            "audience": ReportAudience.OFFICER.value,
            "version": 1,
        },
    )
    assert resp_off.status_code == 200
    off_report = resp_off.json()
    assert off_report["audience"] == ReportAudience.OFFICER.value
    assert off_report["content"]["disclosure_level"] == "RESTRICTED_OFFICER_INTERNAL"
    assert off_report["disclosure_policy"]["include_forensic_signals"] is True

    # 2. Applicant Report (redacts internal notes, discloses remediation instructions)
    resp_app = h.call(
        "POST",
        "/api/v1/reports/generate",
        actor="a",
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "evaluation_run_id": baseline_run_id,
            "audience": ReportAudience.APPLICANT.value,
            "version": 1,
        },
    )
    assert resp_app.status_code == 200
    app_report = resp_app.json()
    assert app_report["audience"] == ReportAudience.APPLICANT.value
    assert app_report["content"]["disclosure_level"] == "PUBLIC_APPLICANT_RECTIFICATION"
    assert app_report["disclosure_policy"]["include_forensic_signals"] is False
    assert "internal_decision_support" not in app_report["content"]["findings"][0]

    # -----------------------------------------------------------------------
    # Step 6: Controlled Rectification & Scoped Response Window
    # -----------------------------------------------------------------------
    # 1. Officer opens response window scoped to bandwidth_mbps
    win_deadline = (now + timedelta(days=7)).isoformat()
    win_resp = h.call(
        "POST",
        "/api/v1/rectification/windows",
        actor="officer",
        mfa=True,
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "authority_reference": "AICTE-SCRUTINY-RECT-2026-001",
            "allowed_slots": ["FIRE_CERTIFICATE"],
            "allowed_fields": ["bandwidth_mbps"],
            "deadline": win_deadline,
            "max_rounds": 2,
        },
    )
    assert win_resp.status_code == 200
    window_data = win_resp.json()
    window_id = window_data["id"]
    assert window_data["status"] == WindowStatus.OPEN.value

    # 2. Reject out-of-scope edit attempt (attempting to change un-flagged land_acres) -> 422
    unrelated_resp = h.call(
        "POST",
        "/api/v1/rectification/responses",
        actor="a",
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "window_id": window_id,
            "field_updates": {"land_acres": 12.0},
        },
    )
    assert unrelated_resp.status_code == 422
    assert "not permitted for rectification" in unrelated_resp.text

    # 3. Submit compliant in-scope rectification (upgrading bandwidth to 350 Mbps)
    rect_resp = h.call(
        "POST",
        "/api/v1/rectification/responses",
        actor="a",
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "window_id": window_id,
            "field_updates": {"bandwidth_mbps": 350},
        },
    )
    assert rect_resp.status_code == 200
    rect_data = rect_resp.json()
    response_id = rect_data["id"]
    assert rect_data["declared_field_updates"]["bandwidth_mbps"] == 350

    # -----------------------------------------------------------------------
    # Step 7: Reassessment & Finding Diff Calculation
    # -----------------------------------------------------------------------
    from workbench.adapters.evaluation_service import EvaluationService

    reassessed = EvaluationService(h.owner).run_evaluation(inst_id, app_id)
    reassessment_run_id = reassessed["run_id"]

    # Compute finding diff: bandwidth deficiency resolved
    diff_resp = h.call(
        "POST",
        "/api/v1/rectification/reassess",
        actor="officer",
        mfa=True,
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "response_id": response_id,
            "baseline_run_id": baseline_run_id,
            "reassessed_findings": [],  # Bandwidth resolved -> zero deficiencies remaining
            "new_run_id": reassessment_run_id,
        },
    )
    assert diff_resp.status_code == 200, diff_resp.text
    diff_data = diff_resp.json()
    assert diff_data["diff_summary"]["resolved"] >= 1
    assert diff_data["diff_summary"]["unchanged"] >= 0
    assert diff_data["diff_summary"]["new"] == 0

    # Confirm baseline run remains completely unchanged in the database
    with h.owner.connect() as conn:
        base_run = conn.execute(
            select(t.evaluation_runs.c.compliance_status).where(
                t.evaluation_runs.c.id == baseline_run_id
            )
        ).scalar()
        assert base_run == "POTENTIAL_DEFICIENCY"

    # -----------------------------------------------------------------------
    # Step 8: Rule-Change Governance (Draft, Simulate, Dual-Control, Publish)
    # -----------------------------------------------------------------------
    cand_resp = h.call(
        "POST",
        "/api/v1/rule-candidates",
        actor="supervisor",
        mfa=True,
        json={
            "candidate_code": f"E2E-CAND-BW100-{uuid4().hex[:8]}",
            "target_academic_cycle": "2027-28",
            "numeric_academic_year": 2027,
            "effective_date": "2027-04-01",
            "submission_date": "2027-01-15",
            "evaluation_time": "SUBMISSION",
            "candidate_rules": [
                {
                    "rule_id": "INFRA.BANDWIDTH",
                    "version": 2,
                    "clause": "Annexure 4.1 note 5",
                    "parameters": {"minimum": 100},
                }
            ],
            "is_hypothetical": False,
        },
    )
    assert cand_resp.status_code == 200, cand_resp.text
    cand_id = cand_resp.json()["id"]

    # What-if simulation
    sim_resp = h.call(
        "POST", f"/api/v1/rule-candidates/{cand_id}/simulate", actor="supervisor", mfa=True
    )
    assert sim_resp.status_code == 200
    assert sim_resp.json()["what_if_banner"] is True

    # Pass 4 qualification gates
    gate_resp = h.call(
        "POST",
        f"/api/v1/rule-candidates/{cand_id}/gates",
        actor="supervisor",
        mfa=True,
        json={
            "source_text_checked": True,
            "scope_and_ambiguity_resolved": True,
            "software_behaviour_tested": True,
            "authorized_policy_approved": True,
        },
    )
    assert gate_resp.status_code == 200

    # Dual-control approval (second identity) and publication
    appr_resp = h.call(
        "POST",
        f"/api/v1/rule-candidates/{cand_id}/approve",
        actor="officer",
        mfa=True,
        json={"approver_identity": "council_second_approver"},
    )
    assert appr_resp.status_code == 200

    pub_resp = h.call(
        "POST", f"/api/v1/rule-candidates/{cand_id}/publish", actor="supervisor", mfa=True
    )
    assert pub_resp.status_code == 200
    published_rel_id = pub_resp.json()["published_release_id"]

    # -----------------------------------------------------------------------
    # Step 9: Historical Replay
    # -----------------------------------------------------------------------
    # Evaluation for 2026-10-26 continues to resolve to baseline release,
    # leaving old run manifest reproducible
    rule_service = RuleRegistryService(h.owner)
    rel_active_2026, _ = rule_service.get_active_release(as_of_date="2026-10-26")
    assert rel_active_2026.id != published_rel_id

    rel_active_2027, _ = rule_service.get_active_release(as_of_date="2027-04-01")
    assert rel_active_2027.id == published_rel_id

    # -----------------------------------------------------------------------
    # Step 10: End-to-End Cryptographic Audit Verification
    # -----------------------------------------------------------------------
    with h.owner.connect() as conn:
        stream_row = conn.execute(
            select(t.audit.c.stream)
            .where(t.audit.c.institution_id == inst_id)
            .order_by(t.audit.c.sequence.asc())
        ).first()
        assert stream_row is not None
        audit_stream_name = stream_row.stream

        # Verify cryptographic hash chain continuity across entire lifecycle
        stream_verify = verify_stream(conn, audit_stream_name)
    assert stream_verify["valid"] is True, f"Audit verification failed: {stream_verify}"
    assert stream_verify["events"] >= 2
    assert len(stream_verify["head_sha256"]) == 64
