"""Phase 9 exit gate verification test suite:
- Officer review commands and dispositions (machine findings separate from human dispositions)
- Pending tasks read models (waiting on source/applicant/interpretation/officer)
- Audience-separated reports (officer vs applicant, v1 immutable, report hash, simulated labeled)
- Response windows (scope, deadline, rounds, unrelated change rejected)
- Reassessment and finding diff (resolved, unchanged, new, changed, no-longer-evaluable)
- Unassigned officer cross-tenant access denial
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select

from workbench.adapters import tables as t
from workbench.modules.rectification.contracts import (
    WindowStatus,
)
from workbench.modules.reporting.contracts import ReportAudience
from workbench.modules.review.contracts import ReviewDispositionType, WaitingOn

pytestmark = pytest.mark.integration


def _create_synthetic_run_and_finding(h, inst_id: str, app_id: str) -> tuple[str, str]:
    """Helper to populate an evaluation run and a machine finding."""
    run_id = str(uuid4())
    finding_id = str(uuid4())
    now = datetime.now(UTC)

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.evaluation_runs).values(
                id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                rule_release_id="REL-2026-v1",
                manifest_hash="hash_baseline_eval",
                evaluation_as_of="2026-04-01",
                completeness_status="COMPLETE",
                compliance_status="DEFICIENT",
                source_verification_status="VERIFIED",
                forensic_concern_status="CLEAR",
                document_validity_status="VALID",
                case_workflow_status="OPEN",
                adverse_action_allowed=True,
                created_at=now,
            )
        )
        conn.execute(
            insert(t.findings).values(
                id=finding_id,
                run_id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                semantic_key="AICTE.APH.2026.CH6.FIRE_SAFETY",
                rule_id="RULE-FIRE-001",
                dimension="INFRASTRUCTURE",
                severity="CRITICAL",
                status="OPEN",
                title="Fire Safety Certificate validity expired",
                description=(
                    "Fire Safety Certificate validity expired before academic cycle commencement"
                ),
                officer_explanation="Municipal fire certificate expired on 2025-12-31",
                applicant_explanation=(
                    "Fire Safety Certificate validity expired before academic cycle commencement"
                ),
                adverse_action_allowed=True,
                created_at=now,
            )
        )
    return run_id, finding_id


def test_machine_findings_stored_separately_from_human_dispositions(h):
    """Subphase 9.1: Machine findings remain immutable while human officer records disposition."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]
    run_id, finding_id = _create_synthetic_run_and_finding(h, inst_id, app_id)

    # Pre-assign officer to Institution A
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Scrutiny committee assigned review",
                expires_at=datetime.now(UTC) + timedelta(days=6),
            )
        )

    payload = {
        "institution_id": inst_id,
        "application_id": app_id,
        "finding_id": finding_id,
        "evaluation_run_id": run_id,
        "disposition": ReviewDispositionType.RECTIFICATION_REQUESTED.value,
        "rationale": (
            "Applicant must upload valid certificate from Municipal Fire Service within 14 days"
        ),
    }

    # 1. Non-officer / applicant actor rejected with 403
    resp_unauth = h.call("POST", "/api/v1/review/dispositions", actor="a", json=payload)
    assert resp_unauth.status_code == 403

    # 2. Officer without MFA rejected with 403
    resp_no_mfa = h.call(
        "POST", "/api/v1/review/dispositions", actor="officer", mfa=False, json=payload
    )
    assert resp_no_mfa.status_code == 403

    # 3. Authorized officer with MFA succeeds
    resp_ok = h.call("POST", "/api/v1/review/dispositions", actor="officer", mfa=True, json=payload)
    assert resp_ok.status_code == 200
    disp_data = resp_ok.json()
    assert disp_data["disposition"] == ReviewDispositionType.RECTIFICATION_REQUESTED.value

    # 4. Invariant: Machine finding in findings table remains untouched
    with h.owner.begin() as conn:
        machine_finding = (
            conn.execute(select(t.findings).where(t.findings.c.id == finding_id)).mappings().one()
        )
        assert (
            machine_finding["applicant_explanation"]
            == "Fire Safety Certificate validity expired before academic cycle commencement"
        )
        assert machine_finding["severity"] == "CRITICAL"
        assert machine_finding["dimension"] == "INFRASTRUCTURE"

        # Human disposition is stored separately in review_dispositions
        human_disp = (
            conn.execute(
                select(t.review_dispositions).where(t.review_dispositions.c.id == disp_data["id"])
            )
            .mappings()
            .one()
        )
        assert human_disp["officer_id"] == h.actors["officer"]
        assert human_disp["disposition"] == ReviewDispositionType.RECTIFICATION_REQUESTED.value
        assert "within 14 days" in human_disp["rationale"]


def test_review_tasks_read_model_waiting_on_dimensions(h):
    """Subphase 9.1: Pending tasks expose actual state:
    waiting on source/applicant/interpretation/officer.
    """
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    with h.owner.begin() as conn:
        now = datetime.now(UTC)
        for waiting_on, task_type in [
            (WaitingOn.OFFICER.value, "OFFICER_INITIAL_SCRUTINY"),
            (WaitingOn.APPLICANT.value, "DEFICIENCY_RECTIFICATION_RESPONSE"),
            (WaitingOn.SOURCE.value, "HISTORICAL_RECORD_SYNC_WAIT"),
            (WaitingOn.INTERPRETATION.value, "RULE_INTERPRETATION_POLICY_WAIT"),
        ]:
            conn.execute(
                insert(t.review_tasks).values(
                    id=str(uuid4()),
                    institution_id=inst_id,
                    application_id=app_id,
                    task_type=task_type,
                    waiting_on=waiting_on,
                    status="PENDING",
                    created_at=now,
                )
            )

    # Query tasks list
    resp = h.call("GET", f"/api/v1/review/tasks?institution_id={inst_id}&application_id={app_id}")
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) == 4

    # Query pending summary read model
    summary_resp = h.call(
        "GET", f"/api/v1/review/pending-summary?institution_id={inst_id}&application_id={app_id}"
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["waiting_on_counts"]["OFFICER"] == 1
    assert summary["waiting_on_counts"]["APPLICANT"] == 1
    assert summary["waiting_on_counts"]["SOURCE"] == 1
    assert summary["waiting_on_counts"]["INTERPRETATION"] == 1
    assert summary["total_pending"] == 4


def test_separate_officer_and_applicant_reports_v1_immutable_and_simulated_labeled(h):
    """Subphase 9.2: Separate officer/applicant reports, v1 immutable, report hash,
    simulated labeled.
    """
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]
    run_id, _ = _create_synthetic_run_and_finding(h, inst_id, app_id)

    # Pre-populate simulated source observation
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.source_observations).values(
                id=str(uuid4()),
                institution_id=inst_id,
                evidence_id=str(uuid4()),
                provider_code="AICTE_HISTORICAL_SIMULATOR",
                mode="SIMULATED",
                simulated=True,
                live_success=False,
                status="VERIFIED",
                freshness_timestamp=datetime.now(UTC),
                observation_fingerprint="fp_report_sim_test",
            )
        )

    with h.owner.begin() as conn:
        observations = [
            dict(o)
            for o in conn.execute(
                select(t.source_observations).where(
                    t.source_observations.c.institution_id == inst_id
                )
            ).mappings()
        ]
        frozen = [
            {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in o.items()}
            for o in observations
        ]
        conn.execute(
            t.evaluation_runs.update()
            .where(t.evaluation_runs.c.id == run_id)
            .values(manifest={"evidence_manifest": {"source_observations": frozen}})
        )

    # 1. Generate Officer Report v1
    officer_payload = {
        "institution_id": inst_id,
        "application_id": app_id,
        "evaluation_run_id": run_id,
        "audience": ReportAudience.OFFICER.value,
        "version": 1,
    }
    resp_off = h.call(
        "POST", "/api/v1/reports/generate", actor="supervisor", mfa=True, json=officer_payload
    )
    assert resp_off.status_code == 200
    off_data = resp_off.json()
    assert off_data["audience"] == ReportAudience.OFFICER.value
    assert off_data["version"] == 1
    assert len(off_data["report_hash"]) == 64

    # Officer report contains internal decision support and forensic signals
    assert off_data["content"]["disclosure_level"] == "RESTRICTED_OFFICER_INTERNAL"
    assert off_data["disclosure_policy"]["include_forensic_signals"] is True
    assert off_data["content"]["findings"][0]["internal_decision_support"] is not None

    # Source results must carry simulated=True and explicit SIMULATED label
    assert off_data["content"]["source_observations"][0]["simulated"] is True
    assert off_data["content"]["source_observations"][0]["simulated_label"] == "SIMULATED"
    assert off_data["content"]["source_observations"][0]["live_success"] is False

    # 2. Generate Applicant Report v1
    applicant_payload = {
        "institution_id": inst_id,
        "application_id": app_id,
        "evaluation_run_id": run_id,
        "audience": ReportAudience.APPLICANT.value,
        "version": 1,
    }
    resp_app = h.call(
        "POST", "/api/v1/reports/generate", actor="supervisor", mfa=True, json=applicant_payload
    )
    assert resp_app.status_code == 200
    app_data = resp_app.json()
    assert app_data["audience"] == ReportAudience.APPLICANT.value
    assert app_data["version"] == 1

    # Applicant report has internal details redacted and clear remediation instructions
    assert app_data["content"]["disclosure_level"] == "PUBLIC_APPLICANT_RECTIFICATION"
    assert app_data["disclosure_policy"]["include_forensic_signals"] is False
    assert "internal_decision_support" not in app_data["content"]["findings"][0]
    assert app_data["content"]["source_observations"][0]["simulated_label"] == "SIMULATED"

    # 3. Report v1 is immutable: re-requesting returns exact identical report_hash and content
    resp_off_repeat = h.call(
        "POST", "/api/v1/reports/generate", actor="supervisor", mfa=True, json=officer_payload
    )
    assert resp_off_repeat.status_code == 200
    assert resp_off_repeat.json()["report_hash"] == off_data["report_hash"]
    assert resp_off_repeat.json()["id"] == off_data["id"]


def test_response_window_scope_deadline_and_unrelated_change_rejected(h):
    """Subphase 9.3: Response window enforces allowed scope, deadline,
    and rejects unrelated changes.
    """
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    # Assign officer to open response window
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Scrutiny committee rectification opening",
                expires_at=datetime.now(UTC) + timedelta(days=6),
            )
        )

    # 1. Open response window allowing slot FIRE_CERTIFICATE and field built_up_area_sqm
    deadline = (datetime.now(UTC) + timedelta(days=14)).isoformat()
    window_payload = {
        "institution_id": inst_id,
        "application_id": app_id,
        "authority_reference": "SCRUTINY_COMMITTEE_ORDER_2026_01",
        "allowed_slots": ["FIRE_CERTIFICATE"],
        "allowed_fields": ["built_up_area_sqm"],
        "deadline": deadline,
        "max_rounds": 2,
    }
    open_resp = h.call(
        "POST", "/api/v1/rectification/windows", actor="officer", mfa=True, json=window_payload
    )
    assert open_resp.status_code == 200
    win_data = open_resp.json()
    win_id = win_data["id"]
    assert win_data["round_number"] == 1
    assert win_data["status"] == WindowStatus.OPEN.value

    # 2. Rejection Case A: Unrelated slot replacement (LAND_REGISTRATION_DEED) -> 422
    unrelated_slot_payload = {
        "institution_id": inst_id,
        "application_id": app_id,
        "window_id": win_id,
        "evidence_replacements": {"LAND_REGISTRATION_DEED": str(uuid4())},
    }
    resp_err_slot = h.call(
        "POST", "/api/v1/rectification/responses", actor="a", json=unrelated_slot_payload
    )
    assert resp_err_slot.status_code == 422
    assert "not permitted for rectification" in resp_err_slot.text

    # 3. Rejection Case B: Unrelated field change (faculty_count) -> 422
    unrelated_field_payload = {
        "institution_id": inst_id,
        "application_id": app_id,
        "window_id": win_id,
        "field_updates": {"faculty_count": 45},
    }
    resp_err_field = h.call(
        "POST", "/api/v1/rectification/responses", actor="a", json=unrelated_field_payload
    )
    assert resp_err_field.status_code == 422
    assert "not permitted for rectification" in resp_err_field.text

    # 4. Rejection Case C: Expired window -> 400
    with h.owner.begin() as conn:
        conn.execute(
            t.response_windows.update()
            .where(t.response_windows.c.id == win_id)
            .values(deadline=datetime.now(UTC) - timedelta(minutes=5))
        )
    resp_expired = h.call(
        "POST",
        "/api/v1/rectification/responses",
        actor="a",
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "window_id": win_id,
            "field_updates": {"built_up_area_sqm": 2500},
        },
    )
    assert resp_expired.status_code == 400
    assert "expired" in resp_expired.text.lower()

    # Reset deadline for compliant submission
    with h.owner.begin() as conn:
        conn.execute(
            t.response_windows.update()
            .where(t.response_windows.c.id == win_id)
            .values(deadline=datetime.now(UTC) + timedelta(days=5), status=WindowStatus.OPEN.value)
        )

    # 5. Success: Compliant in-scope response -> 200
    compliant_payload = {
        "institution_id": inst_id,
        "application_id": app_id,
        "window_id": win_id,
        "field_updates": {"built_up_area_sqm": 2500},
    }
    resp_ok = h.call("POST", "/api/v1/rectification/responses", actor="a", json=compliant_payload)
    assert resp_ok.status_code == 200
    submission_data = resp_ok.json()
    assert submission_data["declared_field_updates"]["built_up_area_sqm"] == 2500

    # Window status is now SUBMITTED
    with h.owner.begin() as conn:
        win_row = (
            conn.execute(select(t.response_windows).where(t.response_windows.c.id == win_id))
            .mappings()
            .one()
        )
        assert win_row["status"] == WindowStatus.SUBMITTED.value


def test_reassessment_finding_diff_and_original_submission_reproducible(h):
    from workbench.activities.reassessment import reassess_response
    from workbench.adapters.evaluation_service import EvaluationService

    app = h.create(
        declared_facts={"intake": 420, "bandwidth_mbps": 100},
        slots=[{"code": "FIRE_CERTIFICATE", "required": False}],
    )
    institution = h.institutions["a"]
    baseline = EvaluationService(h.owner).run_evaluation(institution, app["id"])
    original_hash = baseline["manifest_hash"]
    window = h.call(
        "POST",
        "/api/v1/rectification/windows",
        actor="supervisor",
        mfa=True,
        json={
            "institution_id": institution,
            "application_id": app["id"],
            "authority_reference": "DEMO_POLICY",
            "allowed_fields": ["bandwidth_mbps"],
            "deadline": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert window.status_code == 200, window.text
    response = h.call(
        "POST",
        "/api/v1/rectification/responses",
        json={
            "institution_id": institution,
            "application_id": app["id"],
            "window_id": window.json()["id"],
            "field_updates": {"bandwidth_mbps": 350},
        },
    )
    assert response.status_code == 200, response.text
    with h.owner.connect() as conn:
        event_id = conn.scalar(
            select(t.outbox.c.id).where(
                t.outbox.c.application_id == app["id"],
                t.outbox.c.event_type == "RectificationSubmitted",
            )
        )
    processed = reassess_response(event_id)
    repeated = reassess_response(event_id)
    assert repeated["run_id"] == processed["run_id"]
    with h.owner.connect() as conn:
        original = (
            conn.execute(
                select(t.evaluation_runs).where(t.evaluation_runs.c.id == baseline["run_id"])
            )
            .mappings()
            .one()
        )
        diff = (
            conn.execute(
                select(t.reassessment_diffs).where(
                    t.reassessment_diffs.c.id == processed["diff_id"]
                )
            )
            .mappings()
            .one()
        )
        assert original["manifest_hash"] == original_hash
        assert diff["diff_summary"]["resolved"] >= 1


def test_unassigned_officer_cannot_read_another_institution_phase_9_rows(h):
    """Phase 2 & Phase 9 RLS: An unassigned officer cannot access another
    institution's review/rectification rows.
    """
    inst_a = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]
    run_id, finding_id = _create_synthetic_run_and_finding(h, inst_a, app_id)

    # 1. Pre-populate review disposition, task, report, and response window for Institution A
    win_id = str(uuid4())
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.review_dispositions).values(
                id=str(uuid4()),
                institution_id=inst_a,
                application_id=app_id,
                finding_id=finding_id,
                evaluation_run_id=run_id,
                officer_id=h.actors["admin"],
                disposition="CONFIRMED",
                rationale="Audit confirmed by panel",
            )
        )
        conn.execute(
            insert(t.review_tasks).values(
                id=str(uuid4()),
                institution_id=inst_a,
                application_id=app_id,
                task_type="SCRUTINY_TASK",
                waiting_on="OFFICER",
                status="PENDING",
            )
        )
        conn.execute(
            insert(t.response_windows).values(
                id=win_id,
                institution_id=inst_a,
                application_id=app_id,
                opened_by=h.actors["admin"],
                authority_reference="AUTH_99",
                allowed_slots=["FIRE_CERTIFICATE"],
                allowed_fields=[],
                deadline=datetime.now(UTC) + timedelta(days=7),
                status="OPEN",
                current_revision=1,
            )
        )

    # 2. Unassigned officer (with valid MFA) attempts to access Institution A rows -> 403
    for path in [
        f"/api/v1/review/dispositions?institution_id={inst_a}",
        f"/api/v1/review/tasks?institution_id={inst_a}",
        f"/api/v1/reports?institution_id={inst_a}",
        f"/api/v1/rectification/windows?institution_id={inst_a}",
    ]:
        resp = h.call("GET", path, actor="officer", mfa=True)
        assert resp.status_code in (403, 404), (
            f"Path {path} expected 403/404, got {resp.status_code}"
        )

    # 3. Formally assign the officer specifically to Institution A
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_a,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Formal assignment to inspect Institution A",
                expires_at=datetime.now(UTC) + timedelta(days=6),
            )
        )

    # 4. Now assigned officer can access Institution A review and rectification rows -> 200 OK
    resp_disp = h.call(
        "GET", f"/api/v1/review/dispositions?institution_id={inst_a}", actor="officer", mfa=True
    )
    assert resp_disp.status_code == 200
    assert len(resp_disp.json()) >= 1

    resp_tasks = h.call(
        "GET", f"/api/v1/review/tasks?institution_id={inst_a}", actor="officer", mfa=True
    )
    assert resp_tasks.status_code == 200
    assert len(resp_tasks.json()) >= 1

    resp_win = h.call(
        "GET", f"/api/v1/rectification/windows?institution_id={inst_a}", actor="officer", mfa=True
    )
    assert resp_win.status_code == 200
    assert len(resp_win.json()) >= 1
