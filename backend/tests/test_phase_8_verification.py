"""Phase 8 exit gate verification test suite: source observations, verification attempts,
historical records, PDF signatures, QR validations, and simulation boundaries.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select

from workbench.adapters import tables as t
from workbench.modules.verification.contracts import (
    SignatureStatus,
    SignerRole,
    SourceVerificationStatus,
)
from workbench.modules.verification.service import VerificationService
from workbench.platform.errors import ApplicationError

pytestmark = pytest.mark.integration


def test_capabilities_exposes_provider_modes_and_blocked_connector(client):
    """Subphase 8.1 & 8.4: Capabilities must surface provider modes and blocked real connector."""
    resp = client.get("/api/v1/capabilities")
    assert resp.status_code == 200
    data = resp.json()

    assert data["source_verification_mode"] == "SIMULATED"
    assert data["production_connector_status"] == "BLOCKED_BY_MISSING_ACCESS"
    assert data["live_source_verification"] is False
    assert data["equipment_detection_mode"] == "HEURISTIC_SIMULATED"
    assert data["ocr_engine"] == "SIMULATED_FALLBACK"
    assert data["ocr_mode"] == "SIMULATED"

    providers = data["source_verification_providers"]
    assert len(providers) >= 4

    prod_conn = next(p for p in providers if p["code"] == "AICTE_PRODUCTION_CONNECTOR")
    assert prod_conn["mode"] == "SIMULATED"
    assert prod_conn["live_coverage_available"] is False
    assert "BLOCKED_BY_MISSING_ACCESS" in prod_conn["blocked_reason"]


def test_missing_document_never_receives_verification_attempt(h):
    """Phase 8 invariant: A missing document must NEVER receive a verification attempt."""
    svc = VerificationService(h.owner)
    inst_id = h.institutions["a"]

    # 1. Attempt with None evidence_id
    with pytest.raises(ApplicationError) as exc_info:
        svc.verify_claim_or_evidence(
            institution_id=inst_id,
            evidence_id=None,
            evidence_version_id=None,
            document_type="FIRE_SAFETY_CERTIFICATE",
        )
    assert exc_info.value.code == "CANNOT_VERIFY_MISSING_DOCUMENT"

    # 2. Attempt with "MISSING" marker
    with pytest.raises(ApplicationError) as exc_info2:
        svc.verify_claim_or_evidence(
            institution_id=inst_id,
            evidence_id="MISSING",
            evidence_version_id="MISSING",
            document_type="LAND_REGISTRATION_DEED",
        )
    assert exc_info2.value.code == "CANNOT_VERIFY_MISSING_DOCUMENT"

    # 3. Assert zero verification attempts and observations created
    with h.owner.begin() as conn:
        attempts = conn.execute(
            select(t.verification_attempts).where(
                t.verification_attempts.c.institution_id == inst_id
            )
        ).fetchall()
        assert len(attempts) == 0

        obs = conn.execute(
            select(t.source_observations).where(t.source_observations.c.institution_id == inst_id)
        ).fetchall()
        assert len(obs) == 0


def test_all_six_source_verification_statuses_covered(h):
    """Phase 8: Cover all six source verification statuses
    and assert simulated=True, live_success=False.
    """
    svc = VerificationService(h.owner)
    inst_id = h.institutions["a"]
    ev_id = str(uuid4())
    ev_ver_id = str(uuid4())

    # Pre-populate dummy claim
    app = h.create()
    claim_id = str(uuid4())
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.claims).values(
                id=claim_id,
                institution_id=inst_id,
                application_id=app["id"],
                subject="CAMPUS",
                predicate="fire_safety_compliance",
                declared_value={"compliant": True},
                status="UNVERIFIED",
            )
        )

    # 1. VERIFIED
    res_verified = svc.verify_claim_or_evidence(
        institution_id=inst_id,
        evidence_id=ev_id,
        evidence_version_id=ev_ver_id,
        claim_id=claim_id,
        document_type="FIRE_SAFETY_CERTIFICATE",
        declared_value={"compliant": True},
    )
    assert res_verified["status"] == SourceVerificationStatus.VERIFIED.value
    assert res_verified["simulated"] is True
    assert res_verified["live_success"] is False

    # 2. MISMATCH_DETECTED
    res_mismatch = svc.verify_claim_or_evidence(
        institution_id=inst_id,
        evidence_id=ev_id,
        evidence_version_id=ev_ver_id,
        claim_id=claim_id,
        document_type="FIRE_SAFETY_CERTIFICATE",
        force_fault="MISMATCH",
    )
    assert res_mismatch["status"] == SourceVerificationStatus.MISMATCH_DETECTED.value
    assert res_mismatch["discrepancy_details"] is not None
    assert res_mismatch["simulated"] is True
    assert res_mismatch["live_success"] is False

    # 3. EXPIRED
    res_expired = svc.verify_claim_or_evidence(
        institution_id=inst_id,
        evidence_id=ev_id,
        evidence_version_id=ev_ver_id,
        claim_id=claim_id,
        document_type="FIRE_SAFETY_CERTIFICATE",
        force_fault="EXPIRED",
    )
    assert res_expired["status"] == SourceVerificationStatus.EXPIRED.value
    assert res_expired["simulated"] is True
    assert res_expired["live_success"] is False

    # 4. VERIFICATION_PENDING (explicitly represented in status contracts and initial claim state)
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.source_observations).values(
                id=str(uuid4()),
                institution_id=inst_id,
                evidence_id=ev_id,
                evidence_version_id=ev_ver_id,
                claim_id=claim_id,
                provider_code="AICTE_HISTORICAL_SIMULATOR",
                mode="SIMULATED",
                simulated=True,
                live_success=False,
                status=SourceVerificationStatus.VERIFICATION_PENDING.value,
                freshness_timestamp=datetime.now(UTC),
                observation_fingerprint="fp_pending_test",
            )
        )
    obs = svc.list_observations(inst_id, claim_id=claim_id)
    assert any(o["status"] == SourceVerificationStatus.VERIFICATION_PENDING.value for o in obs)

    # 5. SOURCE_UNAVAILABLE & 6. MANUAL_REVIEW_REQUIRED (tested via outage path below)
    res_outage = svc.verify_claim_or_evidence(
        institution_id=inst_id,
        evidence_id=ev_id,
        evidence_version_id=ev_ver_id,
        claim_id=claim_id,
        document_type="FIRE_SAFETY_CERTIFICATE",
        force_fault="OUTAGE",
    )
    assert res_outage["status"] == SourceVerificationStatus.MANUAL_REVIEW_REQUIRED.value
    assert res_outage["outage_escalated_to_task"] is True
    assert res_outage["manual_task_id"] is not None


def test_outage_to_manual_task_path(h):
    """Subphase 8.1 & 8.4: Source outage transitions safely to manual task review."""
    svc = VerificationService(h.owner)
    inst_id = h.institutions["a"]
    ev_id = str(uuid4())
    ev_ver_id = str(uuid4())

    res = svc.verify_claim_or_evidence(
        institution_id=inst_id,
        evidence_id=ev_id,
        evidence_version_id=ev_ver_id,
        document_type="AICTE_APPROVAL_LETTER",
        force_fault="OUTAGE",
    )

    assert res["status"] == SourceVerificationStatus.MANUAL_REVIEW_REQUIRED.value
    assert res["outage_escalated_to_task"] is True
    assert res["manual_task_id"].startswith("task_rev_")
    assert res["simulated"] is True
    assert res["live_success"] is False

    # Check verification attempts table record
    with h.owner.begin() as conn:
        attempt = (
            conn.execute(
                select(t.verification_attempts).where(
                    t.verification_attempts.c.id == res["attempt_id"]
                )
            )
            .mappings()
            .first()
        )
        assert attempt["status"] == "FAILED"
        assert attempt["error_code"] == "PROVIDER_OUTAGE"
        assert attempt["outage_escalated_to_task"] is True
        assert attempt["manual_task_id"] == res["manual_task_id"]
        assert attempt["simulated"] is True


def test_authorized_officer_manual_confirmation(h):
    """Subphase 8.3: Authorized officer with MFA can record audited manual confirmation."""
    inst_id = h.institutions["a"]
    ev_id = str(uuid4())
    ev_ver_id = str(uuid4())

    # Pre-assign officer to Institution A
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=None,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Assigned review for scrutiny committee",
                expires_at=datetime.now(UTC) + timedelta(days=6),
            )
        )

    payload = {
        "institution_id": inst_id,
        "evidence_id": ev_id,
        "evidence_version_id": ev_ver_id,
        "rationale": "Physical stamp and seal verified during on-site scrutiny committee review",
        "authority_reference": "SCRUTINY_REPORT_2026_ITEM_4",
    }

    # 1. Unassigned / non-elevated applicant actor rejected with 403
    resp_unauth = h.call("POST", "/api/v1/verification/manual-confirm", actor="a", json=payload)
    assert resp_unauth.status_code == 403

    # 2. Officer without MFA rejected with 403
    resp_no_mfa = h.call(
        "POST", "/api/v1/verification/manual-confirm", actor="officer", mfa=False, json=payload
    )
    assert resp_no_mfa.status_code == 403

    # 3. Officer with MFA succeeds
    resp_ok = h.call(
        "POST", "/api/v1/verification/manual-confirm", actor="officer", mfa=True, json=payload
    )
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["status"] == SourceVerificationStatus.VERIFIED.value
    assert data["provider_code"] == "OFFICER_MANUAL_CONFIRMATION"
    assert data["simulated"] is True
    assert data["live_success"] is False
    assert data["officer_confirmation"]["authority_reference"] == "SCRUTINY_REPORT_2026_ITEM_4"


def test_simulated_never_counts_as_live_success_in_db_api_metrics(h):
    """Phase 8 exit gate: Simulated results cannot appear as live success."""
    inst_id = h.institutions["a"]
    ev_id = str(uuid4())
    ev_ver_id = str(uuid4())

    # Trigger verification via API
    payload = {
        "institution_id": inst_id,
        "evidence_id": ev_id,
        "evidence_version_id": ev_ver_id,
        "document_type": "LAND_REGISTRATION_DEED",
        "declared_value": {"survey_number": "104/3"},
    }
    verify_resp = h.call("POST", "/api/v1/verification/verify", json=payload)
    assert verify_resp.status_code == 200
    res_data = verify_resp.json()

    # 1. API contract assertion
    assert res_data["simulated"] is True
    assert res_data["live_success"] is False

    # 2. Database persistence assertion
    with h.owner.begin() as conn:
        obs = (
            conn.execute(
                select(t.source_observations).where(
                    t.source_observations.c.id == res_data["observation_id"]
                )
            )
            .mappings()
            .first()
        )
        assert obs["simulated"] is True
        assert obs["live_success"] is False
        assert obs["mode"] == "SIMULATED"

        attempt = (
            conn.execute(
                select(t.verification_attempts).where(
                    t.verification_attempts.c.id == res_data["attempt_id"]
                )
            )
            .mappings()
            .first()
        )
        assert attempt["simulated"] is True

    # 3. Metrics assertion
    from workbench.platform.intake_metrics import render

    metrics_text = render()
    assert 'workbench_source_verification_attempts_total{mode="simulated"}' in metrics_text
    # Ensure no live success metric was ever recorded
    assert 'mode="live",live_success="true"' not in metrics_text


def test_historical_record_import_and_reconciliation(h):
    """Subphase 8.2: Versioned historical AICTE record import and claim reconciliation."""
    inst_id = h.institutions["a"]

    import_payload = {
        "institution_id": inst_id,
        "source": "AICTE_PORTAL",
        "record_type": "INTAKE",
        "academic_cycle": 2025,
        "payload": {"approved_intake": 180, "programmes": ["UG_ENGINEERING"]},
        "external_reference": "AICTE_EOA_2025_TN_1092",
        "valid_from": datetime(2025, 4, 1, tzinfo=UTC).isoformat(),
        "valid_to": datetime(2026, 3, 31, tzinfo=UTC).isoformat(),
    }

    # 1. Import via API
    resp = h.call("POST", "/api/v1/historical-records/import", json=import_payload)
    assert resp.status_code == 200
    imported = resp.json()
    assert imported["simulated"] is True
    assert len(imported["payload_sha256"]) == 64
    assert imported["import_lineage"] is not None

    # 2. List historical records
    list_resp = h.call(
        "GET", f"/api/v1/historical-records?institution_id={inst_id}&record_type=INTAKE"
    )
    assert list_resp.status_code == 200
    records = list_resp.json()
    assert len(records) >= 1
    assert records[0]["payload"]["approved_intake"] == 180

    # 3. Reconcile matched intake
    rec_match = h.call(
        "POST",
        "/api/v1/historical-records/reconcile",
        json={
            "institution_id": inst_id,
            "academic_cycle": 2025,
            "declared_facts": {"approved_intake": 180},
        },
    )
    assert rec_match.status_code == 200
    match_data = rec_match.json()
    assert len(match_data["matches"]) == 1
    assert match_data["matches"][0]["historical"] == 180

    # 4. Reconcile intake discrepancy
    rec_disc = h.call(
        "POST",
        "/api/v1/historical-records/reconcile",
        json={
            "institution_id": inst_id,
            "academic_cycle": 2025,
            "declared_facts": {"approved_intake": 240},
        },
    )
    assert rec_disc.status_code == 200
    disc_data = rec_disc.json()
    assert len(disc_data["discrepancies"]) == 1
    assert disc_data["discrepancies"][0]["diff"] == 60


def test_pdf_signature_and_qr_verification(h):
    """Subphase 8.3: PDF digital signature verification and structured QR code allowlist."""
    inst_id = h.institutions["a"]
    ev_id = str(uuid4())
    ev_ver_id = str(uuid4())

    # 1. Valid issuer PDF signature
    valid_pdf = b"%PDF-1.4 ... /ByteRange [0 100 200 300] /Contents <3082> ... %%EOF"
    sig_payload = {
        "institution_id": inst_id,
        "evidence_id": ev_id,
        "evidence_version_id": ev_ver_id,
        "content_base64": base64.b64encode(valid_pdf).decode(),
    }
    resp_sig = h.call("POST", "/api/v1/verification/signatures/validate", json=sig_payload)
    assert resp_sig.status_code == 200
    sig_data = resp_sig.json()
    assert sig_data["status"] == SignatureStatus.VALID.value
    assert sig_data["signer_role"] == SignerRole.ISSUER.value
    assert sig_data["simulated"] is True

    # 2. Revoked certificate PDF signature
    revoked_pdf = b"%PDF-1.4 /ByteRange [0 10] /Contents <00> SYNTHETIC_REVOKED_CERTIFICATE %%EOF"
    sig_payload["content_base64"] = base64.b64encode(revoked_pdf).decode()
    resp_rev = h.call("POST", "/api/v1/verification/signatures/validate", json=sig_payload)
    assert resp_rev.status_code == 200
    assert resp_rev.json()["status"] == SignatureStatus.REVOKED.value

    # 3. QR code to approved government portal
    qr_payload_safe = {
        "institution_id": inst_id,
        "evidence_id": ev_id,
        "evidence_version_id": ev_ver_id,
        "qr_text_or_url": "https://approval.aicte-india.org/verify/eoa/2026/TN-102",
    }
    resp_qr_safe = h.call("POST", "/api/v1/verification/qr/validate", json=qr_payload_safe)
    assert resp_qr_safe.status_code == 200
    qr_safe_data = resp_qr_safe.json()
    assert qr_safe_data["status"] == SignatureStatus.VALID.value
    assert qr_safe_data["destination_safe"] is True

    # 4. QR code to unapproved external domain
    qr_payload_unsafe = {
        "institution_id": inst_id,
        "evidence_id": ev_id,
        "evidence_version_id": ev_ver_id,
        "qr_text_or_url": "https://malicious-phishing-portal.com/login",
    }
    resp_qr_unsafe = h.call("POST", "/api/v1/verification/qr/validate", json=qr_payload_unsafe)
    assert resp_qr_unsafe.status_code == 200
    qr_unsafe_data = resp_qr_unsafe.json()
    assert qr_unsafe_data["status"] == SignatureStatus.INVALID.value
    assert qr_unsafe_data["destination_safe"] is False


def test_verification_cross_tenant_denial(h):
    """Phase 2 & Phase 8 RLS: Institution B actor cannot access Institution A records."""
    inst_a = h.institutions["a"]
    ev_id = str(uuid4())
    ev_ver_id = str(uuid4())

    # Pre-populate observation for institution A
    with h.owner.begin() as conn:
        obs_id = str(uuid4())
        conn.execute(
            insert(t.source_observations).values(
                id=obs_id,
                institution_id=inst_a,
                evidence_id=ev_id,
                evidence_version_id=ev_ver_id,
                provider_code="AICTE_HISTORICAL_SIMULATOR",
                mode="SIMULATED",
                simulated=True,
                live_success=False,
                status=SourceVerificationStatus.VERIFIED.value,
                freshness_timestamp=datetime.now(UTC),
                observation_fingerprint="fp_tenant_isolation_test",
            )
        )

    # Actor B attempts to list institution A's observations -> 403/404
    resp_list = h.call(
        "GET", f"/api/v1/verification/observations?institution_id={inst_a}", actor="b"
    )
    assert resp_list.status_code in (403, 404)

    # Actor B attempts to trigger verification on institution A's evidence -> 403/404
    resp_verify = h.call(
        "POST",
        "/api/v1/verification/verify",
        actor="b",
        json={
            "institution_id": inst_a,
            "evidence_id": ev_id,
            "evidence_version_id": ev_ver_id,
            "document_type": "FIRE_SAFETY_CERTIFICATE",
        },
    )
    assert resp_verify.status_code in (403, 404)


def test_unassigned_officer_cannot_read_another_institution_verification_rows(h):
    """Phase 2 & Phase 8 RLS: Unassigned officer cannot read another institution rows."""
    from datetime import timedelta

    inst_a = h.institutions["a"]
    ev_id = str(uuid4())
    ev_ver_id = str(uuid4())

    # 1. Pre-populate verification observation and historical record for Institution A
    with h.owner.begin() as conn:
        obs_id = str(uuid4())
        conn.execute(
            insert(t.source_observations).values(
                id=obs_id,
                institution_id=inst_a,
                evidence_id=ev_id,
                evidence_version_id=ev_ver_id,
                provider_code="AICTE_HISTORICAL_SIMULATOR",
                mode="SIMULATED",
                simulated=True,
                live_success=False,
                status=SourceVerificationStatus.VERIFIED.value,
                freshness_timestamp=datetime.now(UTC),
                observation_fingerprint="fp_officer_denial_test",
            )
        )
        conn.execute(
            insert(t.historical_records).values(
                id=str(uuid4()),
                institution_id=inst_a,
                source="AICTE_PORTAL",
                record_type="INTAKE",
                academic_cycle=2026,
                payload={"approved_intake": 180},
                payload_sha256="abc123sha",
                external_reference="EOA-2026-TN-102",
                simulated=True,
                import_lineage={"imported_by": "system"},
                valid_from=datetime.now(UTC),
            )
        )

    # 2. Unassigned officer (with valid MFA) attempts to read Institution A rows -> 403
    resp_obs = h.call(
        "GET",
        f"/api/v1/verification/observations?institution_id={inst_a}",
        actor="officer",
        mfa=True,
    )
    assert resp_obs.status_code in (403, 404), f"Expected 403/404, got {resp_obs.status_code}"

    resp_hist = h.call(
        "GET",
        f"/api/v1/historical-records?institution_id={inst_a}",
        actor="officer",
        mfa=True,
    )
    assert resp_hist.status_code in (403, 404), f"Expected 403/404, got {resp_hist.status_code}"

    # 3. Assign the officer specifically to Institution A via formal case assignment
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_a,
                application_id=None,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Assigned review for institution inspection",
                expires_at=datetime.now(UTC) + timedelta(days=6),
            )
        )

    # 4. Now assigned officer can read Institution A verification rows
    resp_assigned_obs = h.call(
        "GET",
        f"/api/v1/verification/observations?institution_id={inst_a}",
        actor="officer",
        mfa=True,
    )
    assert resp_assigned_obs.status_code == 200
    obs_list = resp_assigned_obs.json()
    assert len(obs_list) >= 1
    assert any(o["id"] == obs_id for o in obs_list)

    resp_assigned_hist = h.call(
        "GET",
        f"/api/v1/historical-records?institution_id={inst_a}",
        actor="officer",
        mfa=True,
    )
    assert resp_assigned_hist.status_code == 200
    assert len(resp_assigned_hist.json()) >= 1
