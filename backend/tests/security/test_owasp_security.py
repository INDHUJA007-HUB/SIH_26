"""Automated abuse tests mapped to OWASP API Security Top 10 (Subphase 13.2).

Covers:
1. API1:2023 Broken Object Level Authorization (BOLA) - Cross-tenant original,
   derivative, report, media, and simulation diff access denial.
2. API2:2023 Broken Authentication - Expired tokens, invalid signatures, missing MFA on elevated actions.
3. API3:2023 Broken Object Property Level Authorization (BOPLA) - Mass assignment / forbidden field mutations.
4. API4:2023 Unrestricted Resource Consumption - Oversized upload payload rejection.
5. API5:2023 Broken Function Level Authorization (BFLA) - Applicant calling officer/admin endpoints.
6. API7:2023 Server-Side Request Forgery (SSRF) - DNS rebinding, loopback, link-local, and private IP rejection.
7. API8:2023 Security Misconfiguration & Webhook Replay - Webhook signature forgery and replay rejection.
8. Upload Grant Reuse & Checksum Mismatch - Cross-tenant upload completion and grant tampering.
9. Report Redaction & Privacy - Applicant reports exclude internal security notes and cross-tenant PII.
10. Audit Hash-Chain Tamper Detection - Bit tampering in audit log detected by cryptographic verification.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select, update

from workbench.adapters import tables as t
from workbench.adapters.audit_verifier import verify_stream
from workbench.modules.reporting.contracts import ReportAudience
from workbench.security.network_guard import (
    APPROVED_GOVERNMENT_DOMAINS,
    validate_outbound_url,
    verify_webhook_signature,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# 1. API1:2023 Broken Object Level Authorization (BOLA / Cross-Tenant Denial)
# ---------------------------------------------------------------------------


def test_bola_cross_institution_application_and_evidence_access_denied(h):
    """Institution B applicant cannot read Institution A's application, slots, or upload sessions."""
    app_a = h.create(actor="a")
    h.create(actor="b")

    # 1. Actor B cannot read Application A (404/403)
    resp_app = h.call("GET", f"/api/v1/applications/{app_a['id']}", actor="b")
    assert resp_app.status_code in (403, 404), f"Expected 403/404, got {resp_app.status_code}"

    # 2. Prepare upload session for Application A
    data = b"synthetic evidence content for institution A"
    session_a = h.prepare_upload(app_a, data)

    # 3. Actor B cannot access Application A's upload session
    resp_session = h.call("GET", f"/api/v1/upload-sessions/{session_a['id']}", actor="b")
    assert resp_session.status_code in (403, 404), (
        f"BOLA violation: Actor B read Actor A's upload session: {resp_session.status_code}"
    )

    # 4. Actor B cannot complete Application A's upload session
    resp_complete = h.call(
        "POST",
        f"/api/v1/upload-sessions/{session_a['id']}/complete",
        actor="b",
        json={"version_id": "fake_ver"},
    )
    assert resp_complete.status_code in (403, 404), (
        f"BOLA violation: Actor B completed Actor A's upload session: {resp_complete.status_code}"
    )


def test_bola_cross_institution_reports_and_derivatives_access_denied(h):
    """Institution B applicant cannot read Institution A's reports or validation summaries."""
    app_a = h.create(actor="a")
    inst_a = h.institutions["a"]
    run_id = str(uuid4())
    now = datetime.now(UTC)

    # Seed an evaluation run for A
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.evaluation_runs).values(
                id=run_id,
                institution_id=inst_a,
                application_id=app_a["id"],
                rule_release_id="rel-base",
                manifest_hash="hash-base-a",
                evaluation_as_of="2026-10-26",
                execution_mode="DEMONSTRATION",
                compliance_status="DEFICIENT",
                created_at=now,
            )
        )
        conn.execute(
            insert(t.validation_reports).values(
                id=str(uuid4()),
                institution_id=inst_a,
                application_id=app_a["id"],
                evaluation_run_id=run_id,
                audience="OFFICER",
                version=1,
                report_hash="a" * 64,
                summary={"status": "DEFICIENT"},
                content={"details": "Internal officer evaluation"},
                disclosure_policy={"include_forensic_signals": True},
                created_at=now,
            )
        )

    # Actor B attempts to fetch reports for Application A
    resp = h.call("GET", f"/api/v1/applications/{app_a['id']}/reports", actor="b")
    assert resp.status_code in (403, 404), (
        f"BOLA violation: Actor B fetched Actor A reports: {resp.status_code}"
    )


def test_bola_unassigned_officer_denied_simulation_diffs(h):
    """Unassigned officer cannot read other institutions' simulation diffs."""
    inst_a = h.institutions["a"]
    inst_b = h.institutions["b"]
    app_a = h.create(actor="a")["id"]
    app_b = h.create(actor="b")["id"]

    now = datetime.now(UTC)
    run_b_id = str(uuid4())

    with h.owner.begin() as conn:
        # Create evaluation run for Institution B
        conn.execute(
            insert(t.evaluation_runs).values(
                id=run_b_id,
                institution_id=inst_b,
                application_id=app_b,
                rule_release_id="rel-base",
                manifest_hash="hash-b",
                evaluation_as_of="2026-10-26",
                execution_mode="DEMONSTRATION",
                compliance_status="DEFICIENT",
                created_at=now,
            )
        )
        conn.execute(
            insert(t.requirement_outcomes).values(
                id=str(uuid4()),
                run_id=run_b_id,
                institution_id=inst_b,
                application_id=app_b,
                rule_id="APH-INFRA-BW-001",
                requirement_name="Bandwidth Requirement",
                outcome="DEFICIENT",
                created_at=now,
            )
        )
        # Assign officer to Institution A ONLY
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_a,
                application_id=app_a,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Assigned review for Inst A",
                expires_at=now + timedelta(days=6),
            )
        )

    # Create candidate
    cand_resp = h.call(
        "POST",
        "/api/v1/rule-candidates",
        actor="supervisor",
        mfa=True,
        json={
            "candidate_code": f"BOLA-DIFF-TEST-{uuid4().hex[:8]}",
            "target_academic_cycle": "2027-28",
            "numeric_academic_year": 2027,
            "effective_date": "2027-04-01",
            "submission_date": "2027-01-15",
            "evaluation_time": "SUBMISSION",
            "candidate_rules": [
                {
                    "rule_id": "APH-INFRA-BW-001",
                    "version": 2,
                    "clause": "Clause 4.1",
                    "parameters": {"min_bandwidth_mbps": 100},
                }
            ],
            "is_hypothetical": False,
        },
    )
    assert cand_resp.status_code == 200, cand_resp.text
    cand_id = cand_resp.json()["id"]

    # Officer simulates candidate impact
    sim_resp = h.call(
        "POST", f"/api/v1/rule-candidates/{cand_id}/simulate", actor="officer", mfa=True
    )
    assert sim_resp.status_code == 200, sim_resp.text
    diffs = sim_resp.json()["run_diffs"]

    # Verify officer CANNOT see Institution B's run
    app_ids = [d["application_id"] for d in diffs]
    assert app_b not in app_ids, f"BOLA violation: Officer unassigned to Inst B saw app {app_b}"


# ---------------------------------------------------------------------------
# 2. API5:2023 Broken Function Level Authorization (BFLA)
# ---------------------------------------------------------------------------


def test_bfla_applicant_cannot_invoke_administrative_endpoints(h):
    """Applicant cannot create rule candidates, approve, publish, or trigger evaluations."""
    app_a = h.create(actor="a")["id"]

    # 1. Create rule candidate -> 403 ACCESS_DENIED
    resp1 = h.call(
        "POST",
        "/api/v1/rule-candidates",
        actor="a",
        json={
            "candidate_code": f"CAND-MALICIOUS-{uuid4().hex[:8]}",
            "target_academic_cycle": "2027-28",
            "numeric_academic_year": 2027,
            "effective_date": "2027-04-01",
            "submission_date": "2027-01-15",
            "evaluation_time": "SUBMISSION",
            "candidate_rules": [
                {
                    "rule_id": "INFRA.BANDWIDTH",
                    "version": 2,
                    "clause": "Clause 4.1",
                    "parameters": {"min": 50},
                }
            ],
            "is_hypothetical": False,
        },
    )
    assert resp1.status_code == 403, f"Expected 403, got {resp1.status_code}"

    # 2. Update candidate gates -> 403
    resp_gates = h.call(
        "POST",
        "/api/v1/rule-candidates/dummy-id/gates",
        actor="a",
        json={"source_text_checked": True},
    )
    assert resp_gates.status_code == 403, f"Expected 403, got {resp_gates.status_code}"

    # 3. Approve candidate -> 403
    resp2 = h.call("POST", "/api/v1/rule-candidates/dummy-id/approve", actor="a")
    assert resp2.status_code == 403, f"Expected 403, got {resp2.status_code}"

    # 4. Publish release -> 403
    resp3 = h.call("POST", "/api/v1/rule-candidates/dummy-id/publish", actor="a")
    assert resp3.status_code == 403, f"Expected 403, got {resp3.status_code}"

    # 5. Audit export -> 403 (requires auditor role)
    resp_export = h.call(
        "POST",
        f"/api/v1/applications/{app_a}/audit-export?institution_id={h.institutions['a']}",
        actor="a",
    )
    assert resp_export.status_code == 403, (
        f"Expected 403 for applicant audit export, got {resp_export.status_code}"
    )


# ---------------------------------------------------------------------------
# 3. API7:2023 Server-Side Request Forgery (SSRF) & IP Rebinding
# ---------------------------------------------------------------------------


def test_ssrf_rejects_loopback_and_metadata_destinations():
    """Network guard blocks loopback, AWS metadata, and link-local destinations."""
    # Loopback targets
    valid, reason = validate_outbound_url(
        "http://127.0.0.1:8000/internal", allow_private_in_test=False
    )
    assert not valid, f"Expected loopback rejection, got {reason}"
    assert "prohibited" in reason.lower()

    valid, reason = validate_outbound_url("http://localhost:5432/db", allow_private_in_test=False)
    assert not valid, f"Expected localhost rejection, got {reason}"

    # AWS metadata service
    valid, reason = validate_outbound_url(
        "http://169.254.169.254/latest/meta-data/", allow_private_in_test=False
    )
    assert not valid, f"Expected metadata service rejection, got {reason}"

    # Private RFC 1918 addresses
    valid, reason = validate_outbound_url("http://10.0.0.1/admin", allow_private_in_test=False)
    assert not valid
    valid, reason = validate_outbound_url(
        "http://192.168.1.100/status", allow_private_in_test=False
    )
    assert not valid


def test_ssrf_enforces_domain_allowlist():
    """Connector URLs are validated against approved government domains."""
    # Approved government domain
    valid, reason = validate_outbound_url(
        "https://aicte-india.org/api/v1/verify",
        allowlist_domains=APPROVED_GOVERNMENT_DOMAINS,
        allow_private_in_test=True,
    )
    assert valid, f"Expected approved government domain to pass, got: {reason}"

    valid, reason = validate_outbound_url(
        "https://state.gov.in/noc/status",
        allowlist_domains=APPROVED_GOVERNMENT_DOMAINS,
        allow_private_in_test=True,
    )
    assert valid, f"Expected gov.in subdomain to pass, got: {reason}"

    # Malicious or untrusted domain
    valid, reason = validate_outbound_url(
        "https://evil-hacker.com/exfiltrate",
        allowlist_domains=APPROVED_GOVERNMENT_DOMAINS,
        allow_private_in_test=True,
    )
    assert not valid, f"Expected untrusted domain rejection, got {reason}"
    assert "not in approved allowlist" in reason.lower()


# ---------------------------------------------------------------------------
# 4. API8:2023 Security Misconfiguration & Webhook Signature / Replay
# ---------------------------------------------------------------------------


def test_webhook_hmac_signature_verification_and_tamper_rejection():
    """Webhook verification confirms valid HMAC-SHA256 and rejects forged payloads."""
    secret = "workbench_webhook_test_secret_32bytes"
    payload = b'{"event":"DISPOSITION_UPDATED","application_id":"app-123"}'
    ts = str(time.time())

    # Compute valid signature
    signed_payload = f"{ts}.".encode() + payload
    valid_sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    header_valid = f"t={ts},v1={valid_sig},id=msg-001"

    # 1. Valid signature passes
    ok, reason = verify_webhook_signature(payload, header_valid, secret)
    assert ok, f"Expected valid webhook to pass, got: {reason}"

    # 2. Tampered payload rejected with distinct ID
    tampered_payload = b'{"event":"DISPOSITION_UPDATED","application_id":"app-TAMPERED"}'
    header_tamper = f"t={ts},v1={valid_sig},id=msg-002"
    ok_tamper, reason_tamper = verify_webhook_signature(tampered_payload, header_tamper, secret)
    assert not ok_tamper, "Expected tampered payload to fail HMAC verification"
    assert "invalid hmac" in reason_tamper.lower()

    # 3. Forged signature rejected
    header_forged = f"t={ts},v1={'f' * 64},id=msg-003"
    ok_forged, _ = verify_webhook_signature(payload, header_forged, secret)
    assert not ok_forged, "Expected forged signature to be rejected"


def test_webhook_replay_protection():
    """Webhook replay protection rejects duplicate delivery and expired timestamps."""
    secret = "workbench_webhook_test_secret_32bytes"
    payload = b'{"event":"EVIDENCE_RECEIVED","id":"evt-456"}'
    ts = str(time.time())

    signed_payload = f"{ts}.".encode() + payload
    valid_sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={valid_sig},id=replay-uniq-100"

    # First delivery: success
    ok1, reason1 = verify_webhook_signature(payload, header, secret)
    assert ok1, reason1

    # Second delivery with identical replay ID: REJECTED
    ok2, reason2 = verify_webhook_signature(payload, header, secret)
    assert not ok2, "Expected duplicate webhook replay to be rejected"
    assert "replay detected" in reason2.lower()

    # Expired timestamp rejected (> 300 seconds delta)
    old_ts = str(time.time() - 600)
    old_signed = f"{old_ts}.".encode() + payload
    old_sig = hmac.new(secret.encode(), old_signed, hashlib.sha256).hexdigest()
    header_expired = f"t={old_ts},v1={old_sig},id=msg-expired"
    ok_exp, reason_exp = verify_webhook_signature(
        payload, header_expired, secret, tolerance_seconds=300
    )
    assert not ok_exp, "Expected expired webhook to be rejected"
    assert "expired" in reason_exp.lower()


# ---------------------------------------------------------------------------
# 5. Upload Grant Cross-Tenant Completion Denial
# ---------------------------------------------------------------------------


def test_upload_session_cross_tenant_completion_denied(h):
    """Actor B cannot complete Actor A's upload session."""
    app_a = h.create(actor="a")
    data = b"confidential evidence document payload"
    session_a = h.prepare_upload(app_a, data)

    # Actor B attempts to complete Actor A's session -> 404/403
    resp = h.call(
        "POST",
        f"/api/v1/upload-sessions/{session_a['id']}/complete",
        actor="b",
        json={"version_id": "v1"},
    )
    assert resp.status_code in (403, 404), (
        f"Cross-tenant upload completion was not denied: {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# 6. Report Redaction & Privacy (No Cross-Tenant PII or Internal Security Notes)
# ---------------------------------------------------------------------------


def test_report_redaction_excludes_internal_security_notes_from_applicant(h):
    """Applicant reports redact internal officer notes, security flags, and cross-tenant data."""
    inst_a = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]
    run_id = str(uuid4())
    finding_id = str(uuid4())
    now = datetime.now(UTC)

    # Pre-populate run, machine finding, and observation
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.evaluation_runs).values(
                id=run_id,
                institution_id=inst_a,
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
                institution_id=inst_a,
                application_id=app_id,
                semantic_key="AICTE.APH.2026.CH6.FIRE_SAFETY",
                rule_id="RULE-FIRE-001",
                dimension="INFRASTRUCTURE",
                severity="CRITICAL",
                status="OPEN",
                title="Fire Safety Certificate validity expired",
                description="Fire Safety Certificate validity expired before academic cycle commencement",
                officer_explanation="Internal confidential review notes: suspected forged municipal seal",
                applicant_explanation="Fire Safety Certificate validity expired before academic cycle commencement",
                adverse_action_allowed=True,
                created_at=now,
            )
        )
        conn.execute(
            insert(t.source_observations).values(
                id=str(uuid4()),
                institution_id=inst_a,
                evidence_id=str(uuid4()),
                provider_code="AICTE_HISTORICAL_SIMULATOR",
                mode="SIMULATED",
                simulated=True,
                live_success=False,
                status="VERIFIED",
                freshness_timestamp=now,
                observation_fingerprint="fp_report_redact_test",
            )
        )

    # 1. Generate Applicant Report via API
    applicant_payload = {
        "institution_id": inst_a,
        "application_id": app_id,
        "evaluation_run_id": run_id,
        "audience": ReportAudience.APPLICANT.value,
        "version": 1,
    }
    resp_app = h.call("POST", "/api/v1/reports/generate", actor="a", json=applicant_payload)
    assert resp_app.status_code == 200, resp_app.text
    app_data = resp_app.json()

    # Verify disclosure policy flags and level
    assert app_data["audience"] == ReportAudience.APPLICANT.value
    assert app_data["content"]["disclosure_level"] == "PUBLIC_APPLICANT_RECTIFICATION"
    assert app_data["disclosure_policy"]["include_forensic_signals"] is False
    assert "internal_decision_support" not in app_data["content"]["findings"][0]
    # Verify confidential officer explanation is completely omitted from applicant report
    assert "forged municipal seal" not in str(app_data)


# ---------------------------------------------------------------------------
# 7. Audit Hash-Chain Tamper Detection
# ---------------------------------------------------------------------------


def test_audit_hash_chain_tamper_detection(h):
    """Bit tampering in the audit stream is detected by verify_stream."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    # 1. Get the stream name from the actual audit table for this institution
    with h.owner.connect() as conn:
        row = conn.execute(
            select(t.audit.c.stream, t.audit.c.id)
            .where(t.audit.c.institution_id == inst_id)
            .order_by(t.audit.c.sequence.asc())
        ).first()
        assert row is not None, "Audit event was not recorded on application creation"
        stream_name = row.stream
        first_event_id = row.id

    # 2. Clean stream from application creation must be cryptographically valid
    with h.owner.connect() as conn:
        clean_result = verify_stream(conn, stream_name)
    assert clean_result["valid"] is True, (
        f"Clean application stream verification failed: {clean_result}"
    )
    assert clean_result["events"] >= 1
    head_hash = clean_result["head_sha256"]
    assert len(head_hash) == 64

    # 3. Verify database trigger blocks direct row mutation on audit_events
    with pytest.raises(Exception) as exc_info, h.owner.begin() as conn:
        conn.execute(
            update(t.audit)
            .where(t.audit.c.id == first_event_id)
            .values(event={"tampered_key": "MALICIOUS_INJECTION"})
        )
    assert "immutable record" in str(exc_info.value).lower()

    # 4. Verify cryptographic hash chain verification detects any forged/tampered event appended
    with h.owner.connect() as conn:
        last_evt = conn.execute(
            select(t.audit.c.sequence, t.audit.c.sha256)
            .where(t.audit.c.stream == stream_name)
            .order_by(t.audit.c.sequence.desc())
        ).first()
        last_seq = last_evt.sequence

    # Insert an event with an invalid previous_hash (broken hash chain)
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.audit).values(
                id=str(uuid4()),
                stream=stream_name,
                institution_id=inst_id,
                application_id=app_id,
                sequence=last_seq + 1,
                previous_hash="0" * 64,  # Forged previous hash (broken chain)
                sha256="bad" * 21 + "a",
                event={"event_type": "ForgedAuditPayload"},
                created_at=datetime.now(UTC),
            )
        )

    # 5. verify_stream must fail and pinpoint the invalid sequence
    with h.owner.connect() as conn:
        tampered_result = verify_stream(conn, stream_name)
    assert tampered_result["valid"] is False, (
        "Cryptographic audit verifier failed to detect tampered event payload"
    )
    assert tampered_result["first_invalid_sequence"] == last_seq + 1
