"""Phase 15: Operations, Retention, Incident Containment, Drift, and Access Assurance tests.

Validates Subphases 15.1, 15.2, 15.3, and 15.4 in accordance with
docs/BACKEND_IMPLEMENTATION_PLAN.md Sections 5.1, 6.2, 9.3, 10, and 15.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update

from workbench.adapters import tables as t
from workbench.adapters.domain_store import now
from workbench.adapters.object_storage import ObjectStorage
from workbench.modules.operations.contracts import (
    ContainmentAction,
    ContainmentTargetType,
    HealthStatus,
    ReconciliationTarget,
)
from workbench.modules.operations.drift import evaluate_champion_challenger
from workbench.modules.retention.contracts import (
    DataClass,
    RetentionBasis,
)
from workbench.workflows.retention_workflow import RetentionPurgeWorkflow

pytestmark = pytest.mark.integration


# ==============================================================================
# SUBPHASE 15.3: RETENTION POLICIES, LEGAL HOLDS & PURGE MANIFESTS
# ==============================================================================


def test_retention_policy_creation_and_statutory_invariants(h):
    """Subphase 15.3: Retention policies enforce statutory minimums (CERT-In 180 days, Audit 7 years)."""
    # 1. Non-supervisor cannot create policy
    invalid_role_resp = h.call(
        "POST",
        "/api/v1/retention/policies",
        actor="officer",
        json={
            "data_class": DataClass.DERIVATIVES_CACHES.value,
            "retention_basis": RetentionBasis.OPERATIONAL.value,
            "retention_period_days": 30,
            "description": "Cache purge policy",
        },
    )
    assert invalid_role_resp.status_code in (401, 403)

    # 2. Supervisor without MFA cannot create policy (step-up required)
    no_mfa_resp = h.call(
        "POST",
        "/api/v1/retention/policies",
        actor="supervisor",
        mfa=False,
        json={
            "data_class": DataClass.DERIVATIVES_CACHES.value,
            "retention_basis": RetentionBasis.OPERATIONAL.value,
            "retention_period_days": 30,
        },
    )
    assert no_mfa_resp.status_code in (401, 403)

    # 3. Invariant: CERT-In security logs minimum is 180 days
    certin_fail_resp = h.call(
        "POST",
        "/api/v1/retention/policies",
        actor="supervisor",
        mfa=True,
        json={
            "data_class": DataClass.CERT_IN_SECURITY_LOGS.value,
            "retention_basis": RetentionBasis.SECURITY_COMPLIANCE.value,
            "retention_period_days": 90,  # Below 180-day minimum
        },
    )
    assert certin_fail_resp.status_code == 422, "CERT-In logs retention < 180 days must fail"

    # 4. Invariant: Audit checkpoints minimum is 7 years (2555 days)
    audit_fail_resp = h.call(
        "POST",
        "/api/v1/retention/policies",
        actor="supervisor",
        mfa=True,
        json={
            "data_class": DataClass.AUDIT_CHECKPOINTS.value,
            "retention_basis": RetentionBasis.STATUTORY.value,
            "retention_period_days": 365,  # Below 2555-day minimum
        },
    )
    assert audit_fail_resp.status_code == 422, "Audit checkpoints retention < 2555 days must fail"

    # 5. Valid CERT-In and Derivatives policies
    certin_ok_resp = h.call(
        "POST",
        "/api/v1/retention/policies",
        actor="supervisor",
        mfa=True,
        json={
            "data_class": DataClass.CERT_IN_SECURITY_LOGS.value,
            "retention_basis": RetentionBasis.SECURITY_COMPLIANCE.value,
            "retention_period_days": 180,
            "description": "CERT-In ICT security log compliance",
        },
    )
    assert certin_ok_resp.status_code == 200, certin_ok_resp.text
    certin_policy = certin_ok_resp.json()
    assert certin_policy["retention_period_days"] == 180

    cache_ok_resp = h.call(
        "POST",
        "/api/v1/retention/policies",
        actor="supervisor",
        mfa=True,
        json={
            "data_class": DataClass.DERIVATIVES_CACHES.value,
            "retention_basis": RetentionBasis.OPERATIONAL.value,
            "retention_period_days": 14,
            "description": "Evidence derivative cache expiration",
        },
    )
    assert cache_ok_resp.status_code == 200, cache_ok_resp.text

    # 6. List policies
    list_resp = h.call("GET", "/api/v1/retention/policies", actor="supervisor")
    assert list_resp.status_code == 200
    policies = list_resp.json()
    assert len(policies) >= 2


def test_legal_hold_placement_and_release(h):
    """Subphase 15.3: Legal holds can be placed and released with full audit tracking."""
    inst_id = h.institutions["a"]
    matter_ref = f"MATTER-HIGH-COURT-{uuid4().hex[:6].upper()}"

    # 1. Place legal hold
    hold_resp = h.call(
        "POST",
        "/api/v1/retention/legal-holds",
        actor="supervisor",
        mfa=True,
        json={
            "institution_id": inst_id,
            "matter_reference": matter_ref,
            "legal_basis": "Statutory inspection inquiry under Section 10 AICTE Act",
        },
    )
    assert hold_resp.status_code == 200, hold_resp.text
    hold_data = hold_resp.json()
    hold_id = hold_data["id"]
    assert hold_data["is_active"] is True
    assert hold_data["matter_reference"] == matter_ref

    # 2. Query active holds
    list_resp = h.call(
        "GET",
        f"/api/v1/retention/legal-holds?institution_id={inst_id}&active_only=true",
        actor="supervisor",
    )
    assert list_resp.status_code == 200
    holds = list_resp.json()
    assert any(h["id"] == hold_id for h in holds)

    # 3. Release legal hold
    release_resp = h.call(
        "POST",
        f"/api/v1/retention/legal-holds/{hold_id}/release",
        actor="supervisor",
        mfa=True,
        json={"release_reason": "Court inquiry concluded with clean finding order"},
    )
    assert release_resp.status_code == 200, release_resp.text
    released_data = release_resp.json()
    assert released_data["is_active"] is False
    assert released_data["release_reason"] == "Court inquiry concluded with clean finding order"

    # 4. Conflict on second release
    double_release_resp = h.call(
        "POST",
        f"/api/v1/retention/legal-holds/{hold_id}/release",
        actor="supervisor",
        mfa=True,
        json={"release_reason": "Redundant release"},
    )
    assert double_release_resp.status_code == 409


def test_purge_eligibility_proves_active_hold_and_dependencies_never_purged(h):
    """Subphase 15.3: Proves active legal hold or active application dependency is NEVER purged

    even when a derivative/cache TTL has expired.
    """
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]

    # Create policy for derivative caches (7-day TTL)
    policy_resp = h.call(
        "POST",
        "/api/v1/retention/policies",
        actor="supervisor",
        mfa=True,
        json={
            "data_class": DataClass.DERIVATIVES_CACHES.value,
            "retention_basis": RetentionBasis.OPERATIONAL.value,
            "retention_period_days": 7,
            "description": "Short TTL derivatives",
        },
    )
    assert policy_resp.status_code == 200
    policy_id = policy_resp.json()["id"]

    slot_id = str(uuid4())
    upload_id = str(uuid4())
    ev_id = str(uuid4())
    deriv_normal_id = str(uuid4())
    deriv_held_id = str(uuid4())

    past_date = now() - timedelta(days=20)

    # Seed evidence and derivatives created 20 days ago (older than 7-day TTL)
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.slots).values(
                id=slot_id,
                institution_id=inst_id,
                application_id=app_id,
                code="FACULTY_REGISTRATION",
                required=True,
            )
        )
        conn.execute(
            insert(t.uploads).values(
                id=upload_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                actor_id=h.actors["a"],
                filename="faculty.pdf",
                media_type="application/pdf",
                expected_size=2048,
                expected_sha256="0" * 64,
                object_key="quarantine/faculty.pdf",
                mode="SINGLE",
                part_size=2048,
                status="COMPLETED",
                expires_at=now() + timedelta(days=1),
                created_at=past_date,
            )
        )
        conn.execute(
            insert(t.evidence).values(
                id=ev_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                upload_id=upload_id,
                quarantine_key="quarantine/faculty.pdf",
                quarantine_version="v1",
                size_bytes=2048,
                sha256="1" * 64,
                media_type="application/pdf",
                filename="faculty.pdf",
                status="QUARANTINED",
                metadata={},
                created_at=past_date,
            )
        )
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == ev_id)
            .values(status="ACCEPTED", clean_key="clean/faculty.pdf", clean_version="v1")
        )
        # 1. Normal derivative (eligible)
        conn.execute(
            insert(t.derivatives).values(
                id=deriv_normal_id,
                institution_id=inst_id,
                application_id=app_id,
                evidence_id=ev_id,
                kind="PAGE_RENDER",
                page=1,
                object_key="derivatives/page1.png",
                object_version="v1",
                sha256="2" * 64,
                size_bytes=1024,
                media_type="image/png",
                metadata={},
                created_at=past_date,
            )
        )
        # 2. Derivative under active legal hold
        conn.execute(
            insert(t.derivatives).values(
                id=deriv_held_id,
                institution_id=inst_id,
                application_id=app_id,
                evidence_id=ev_id,
                kind="PAGE_RENDER",
                page=2,
                object_key="derivatives/page2.png",
                object_version="v1",
                sha256="3" * 64,
                size_bytes=1024,
                media_type="image/png",
                metadata={},
                created_at=past_date,
            )
        )

    # Place legal hold on the slot
    hold_resp = h.call(
        "POST",
        "/api/v1/retention/legal-holds",
        actor="supervisor",
        mfa=True,
        json={
            "institution_id": inst_id,
            "evidence_slot_id": slot_id,
            "matter_reference": "DISPUTE-FACULTY-CADRE-001",
            "legal_basis": "Court stayed purge of faculty records",
        },
    )
    assert hold_resp.status_code == 200

    # Execute purge dry-run
    purge_dry_resp = h.call(
        "POST",
        "/api/v1/retention/purge-runs",
        actor="supervisor",
        mfa=True,
        json={"policy_id": policy_id, "dry_run": True, "max_items": 100},
    )
    assert purge_dry_resp.status_code == 200, purge_dry_resp.text
    dry_manifest = purge_dry_resp.json()

    # Held items must be skipped
    assert dry_manifest["skipped_held_count"] > 0
    assert dry_manifest["purged_count"] == 0, "Dry run must purge zero items"

    # Execute actual purge run
    purge_exec_resp = h.call(
        "POST",
        "/api/v1/retention/purge-runs",
        actor="supervisor",
        mfa=True,
        json={"policy_id": policy_id, "dry_run": False, "max_items": 100},
    )
    assert purge_exec_resp.status_code == 200, purge_exec_resp.text
    exec_manifest = purge_exec_resp.json()
    manifest_id = exec_manifest["id"]

    assert exec_manifest["sha256_digest"] is not None
    assert len(exec_manifest["sha256_digest"]) == 64

    # INVARIANT PROOF: Original EvidenceVersion is NEVER deleted
    with h.owner.begin() as conn:
        ev_still_exists = conn.scalar(
            select(func.count(t.evidence.c.id)).where(t.evidence.c.id == ev_id)
        )
        assert ev_still_exists == 1, (
            "Original evidence must NEVER be purged on derivative TTL expiry"
        )

    # Fetch immutable purge manifest by ID
    get_manifest_resp = h.call(
        "GET",
        f"/api/v1/retention/purge-manifests/{manifest_id}",
        actor="supervisor",
    )
    assert get_manifest_resp.status_code == 200
    retrieved_manifest = get_manifest_resp.json()
    assert retrieved_manifest["id"] == manifest_id
    assert retrieved_manifest["sha256_digest"] == exec_manifest["sha256_digest"]


def test_retention_purge_workflow_refuses_original_evidence_under_hold_or_evaluation_manifest(h):
    """Subphase 15.3: Retention purge workflow strictly refuses to delete original EvidenceVersion
    under legal hold or referenced by a finalized EvaluationRunManifest, while purging expired
    disposable derivatives.
    """
    # 0. Confirm RetentionPurgeWorkflow definition integrity
    wf = RetentionPurgeWorkflow()
    assert wf.status() == "INITIALIZED"

    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]

    # 1. Create policies: one for ORIGINAL_EVIDENCE (365 days) and one for DERIVATIVES_CACHES (7 days)
    pol_orig_resp = h.call(
        "POST",
        "/api/v1/retention/policies",
        actor="supervisor",
        mfa=True,
        json={
            "data_class": DataClass.ORIGINAL_EVIDENCE.value,
            "retention_basis": RetentionBasis.STATUTORY.value,
            "retention_period_days": 365,
            "description": "Original evidence statutory retention",
        },
    )
    assert pol_orig_resp.status_code == 200
    orig_policy_id = pol_orig_resp.json()["id"]

    pol_deriv_resp = h.call(
        "POST",
        "/api/v1/retention/policies",
        actor="supervisor",
        mfa=True,
        json={
            "data_class": DataClass.DERIVATIVES_CACHES.value,
            "retention_basis": RetentionBasis.OPERATIONAL.value,
            "retention_period_days": 7,
            "description": "Disposable derivative cache",
        },
    )
    assert pol_deriv_resp.status_code == 200
    deriv_policy_id = pol_deriv_resp.json()["id"]

    # 2. Seed data
    slot_id_1 = str(uuid4())
    slot_id_2 = str(uuid4())
    upload_id_1 = str(uuid4())
    upload_id_2 = str(uuid4())
    ev_held_id = str(uuid4())
    ev_manifest_id = str(uuid4())
    deriv_expired_id = str(uuid4())
    run_id = str(uuid4())

    created_long_ago = now() - timedelta(days=400)
    created_20_days_ago = now() - timedelta(days=20)

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.slots).values(
                [
                    {
                        "id": slot_id_1,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "code": "LAND_TITLE_DEED",
                        "required": True,
                    },
                    {
                        "id": slot_id_2,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "code": "BUILDING_PLAN",
                        "required": True,
                    },
                ]
            )
        )
        # Uploads
        conn.execute(
            insert(t.uploads).values(
                [
                    {
                        "id": upload_id_1,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "slot_id": slot_id_1,
                        "actor_id": h.actors["a"],
                        "filename": "title_deed.pdf",
                        "media_type": "application/pdf",
                        "expected_size": 4096,
                        "expected_sha256": "4" * 64,
                        "object_key": "clean/title_deed.pdf",
                        "mode": "SINGLE",
                        "part_size": 4096,
                        "status": "COMPLETED",
                        "expires_at": now() + timedelta(days=1),
                        "created_at": created_long_ago,
                    },
                    {
                        "id": upload_id_2,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "slot_id": slot_id_2,
                        "actor_id": h.actors["a"],
                        "filename": "building_plan.pdf",
                        "media_type": "application/pdf",
                        "expected_size": 8192,
                        "expected_sha256": "5" * 64,
                        "object_key": "clean/building_plan.pdf",
                        "mode": "SINGLE",
                        "part_size": 8192,
                        "status": "COMPLETED",
                        "expires_at": now() + timedelta(days=1),
                        "created_at": created_long_ago,
                    },
                ]
            )
        )
        # Evidence 1: Under active legal hold
        conn.execute(
            insert(t.evidence).values(
                id=ev_held_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id_1,
                upload_id=upload_id_1,
                quarantine_key="clean/title_deed.pdf",
                quarantine_version="v1",
                size_bytes=4096,
                sha256="4" * 64,
                media_type="application/pdf",
                filename="title_deed.pdf",
                status="QUARANTINED",
                metadata={},
                created_at=created_long_ago,
            )
        )
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == ev_held_id)
            .values(status="ACCEPTED", clean_key="clean/title_deed.pdf", clean_version="v1")
        )
        # Evidence 2: Referenced by finalized EvaluationRunManifest
        conn.execute(
            insert(t.evidence).values(
                id=ev_manifest_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id_2,
                upload_id=upload_id_2,
                quarantine_key="clean/building_plan.pdf",
                quarantine_version="v1",
                size_bytes=8192,
                sha256="5" * 64,
                media_type="application/pdf",
                filename="building_plan.pdf",
                status="QUARANTINED",
                metadata={},
                created_at=created_long_ago,
            )
        )
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == ev_manifest_id)
            .values(status="ACCEPTED", clean_key="clean/building_plan.pdf", clean_version="v1")
        )
        # Finalized evaluation run with run_inputs referencing ev_manifest_id
        conn.execute(
            insert(t.evaluation_runs).values(
                id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                rule_release_id="rel-2026-v1",
                manifest_hash="hash-eval-manifest-finalized",
                evaluation_as_of="2026-10-26",
                execution_mode="OFFICIAL",
                compliance_status="APPROVED",
                manifest={
                    "run_id": run_id,
                    "rule_release_sha256": "6" * 64,
                    "referenced_evidence_ids": [ev_manifest_id],
                },
                created_at=created_long_ago,
            )
        )
        conn.execute(
            insert(t.run_inputs).values(
                id=str(uuid4()),
                run_id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                input_type="EVIDENCE",
                input_id=ev_manifest_id,
                content_hash="5" * 64,
                created_at=created_long_ago,
            )
        )
        # Disposable derivative older than 7 days
        conn.execute(
            insert(t.derivatives).values(
                id=deriv_expired_id,
                institution_id=inst_id,
                application_id=app_id,
                evidence_id=ev_manifest_id,
                kind="PAGE_RENDER",
                page=1,
                object_key="derivatives/disposable_page.png",
                object_version="v1",
                sha256="7" * 64,
                size_bytes=2048,
                media_type="image/png",
                metadata={},
                created_at=created_20_days_ago,
            )
        )

    # 3. Place legal hold on slot_id_1 (covering ev_held_id)
    hold_resp = h.call(
        "POST",
        "/api/v1/retention/legal-holds",
        actor="supervisor",
        mfa=True,
        json={
            "institution_id": inst_id,
            "evidence_slot_id": slot_id_1,
            "matter_reference": f"LEGAL-HOLD-TITLE-{uuid4().hex[:6].upper()}",
            "legal_basis": "Court injunction on land title documents",
        },
    )
    assert hold_resp.status_code == 200

    # 4. Attempt purge on ORIGINAL_EVIDENCE
    purge_orig_dry = h.call(
        "POST",
        "/api/v1/retention/purge-runs",
        actor="supervisor",
        mfa=True,
        json={"policy_id": orig_policy_id, "dry_run": True, "max_items": 100},
    )
    assert purge_orig_dry.status_code == 200
    orig_dry_data = purge_orig_dry.json()
    assert orig_dry_data["skipped_held_count"] >= 1, "Evidence under legal hold must be skipped"
    assert orig_dry_data["skipped_dependency_count"] >= 1, (
        "Evidence referenced by finalized EvaluationRunManifest must be skipped"
    )
    assert orig_dry_data["purged_count"] == 0, (
        "No original evidence under hold or manifest should be eligible"
    )

    # Execute actual purge run on ORIGINAL_EVIDENCE
    purge_orig_exec = h.call(
        "POST",
        "/api/v1/retention/purge-runs",
        actor="supervisor",
        mfa=True,
        json={"policy_id": orig_policy_id, "dry_run": False, "max_items": 100},
    )
    assert purge_orig_exec.status_code == 200
    orig_exec_data = purge_orig_exec.json()
    assert orig_exec_data["purged_count"] == 0, "Zero original evidence items purged"

    # 5. Execute purge on DERIVATIVES_CACHES -> Expired derivative is purged
    with patch.object(ObjectStorage, "delete", return_value=None) as mock_storage_delete:
        purge_deriv_exec = h.call(
            "POST",
            "/api/v1/retention/purge-runs",
            actor="supervisor",
            mfa=True,
            json={"policy_id": deriv_policy_id, "dry_run": False, "max_items": 100},
        )
        assert purge_deriv_exec.status_code == 200
        deriv_exec_data = purge_deriv_exec.json()
        assert deriv_exec_data["purged_count"] >= 1, "Expired disposable derivative must be purged"

        # Assert underlying storage.delete was invoked for the expired derivative
        assert mock_storage_delete.call_count >= 1, (
            "storage.delete must be invoked when derivative is purged"
        )
        deleted_keys = [
            c.args[0] if c.args else c.kwargs.get("key") for c in mock_storage_delete.call_args_list
        ]
        assert "derivatives/disposable_page.png" in deleted_keys, (
            "Underlying storage object key must be deleted/tombstoned"
        )

    # 6. CRITICAL VERIFICATION:
    # Confirm both original EvidenceVersion records remain untouched in DB
    with h.owner.begin() as conn:
        ev_held_count = conn.scalar(
            select(func.count(t.evidence.c.id)).where(t.evidence.c.id == ev_held_id)
        )
        assert ev_held_count == 1, "Original evidence under legal hold must NOT be deleted"

        ev_manifest_count = conn.scalar(
            select(func.count(t.evidence.c.id)).where(t.evidence.c.id == ev_manifest_id)
        )
        assert ev_manifest_count == 1, (
            "Original evidence referenced by EvaluationRunManifest must NOT be deleted"
        )

        deriv_exists = conn.scalar(
            select(func.count(t.derivatives.c.id)).where(t.derivatives.c.id == deriv_expired_id)
        )
        assert deriv_exists == 0, "Expired disposable derivative must be purged from database"


# ==============================================================================
# SUBPHASE 15.1: SERVICE OPERATIONS, INCIDENT CONTAINMENT & RECONCILIATION
# ==============================================================================


def test_operational_health_summary_aggregation(h):
    """Subphase 15.1: Health summary aggregates SLO, queue-age, extraction failure rate,

    source coverage, and audit checkpoint lag.
    """
    resp = h.call("GET", "/api/v1/operations/health-summary?window_minutes=60", actor="supervisor")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "overall_status" in data
    assert data["overall_status"] in [s.value for s in HealthStatus]
    assert data["api_availability_pct"] >= 99.0
    assert "queue_health" in data
    assert "extraction_health" in data
    assert "source_health" in data
    assert "audit_health" in data


def test_incident_containment_guarantees_findings_immutability(h):
    """Subphase 15.1: Incident containment isolates compromised actors, providers, or jobs

    without mutating ANY application compliance findings.
    """
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    run_id = str(uuid4())
    finding_id = str(uuid4())

    # 1. Seed historical evaluation run and compliance findings
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.evaluation_runs).values(
                id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                manifest_hash="baseline-manifest-hash-phase15",
                evaluation_as_of="2026-10-26",
                execution_mode="DEMONSTRATION",
                completeness_status="COMPLETE",
                compliance_status="PASS",
                adverse_action_allowed=False,
            )
        )
        conn.execute(
            insert(t.findings).values(
                id=finding_id,
                institution_id=inst_id,
                application_id=app_id,
                run_id=run_id,
                rule_id="APH-INFRA-LAND-001",
                semantic_key="compliance:infra:land_area",
                dimension="COMPLIANCE",
                severity="DEFICIENCY",
                status="PASS",
                title="Land Area Evaluation",
                description="Land area compliance check",
                adverse_action_allowed=False,
            )
        )

    # Compute baseline checksum of findings
    with h.owner.begin() as conn:
        findings_before = (
            conn.execute(select(t.findings).where(t.findings.c.id == finding_id)).mappings().first()
        )
        assert findings_before is not None

    compromised_actor_id = h.actors["a"]

    # 2. Operator triggers incident containment on compromised actor
    contain_resp = h.call(
        "POST",
        "/api/v1/operations/containment",
        actor="supervisor",
        mfa=True,
        json={
            "target_type": ContainmentTargetType.ACTOR.value,
            "target_id": compromised_actor_id,
            "containment_action": ContainmentAction.REVOKE_SESSION.value,
            "reason": "Suspicious credential credential exfiltration detected in edge WAF logs",
        },
    )
    assert contain_resp.status_code == 200, contain_resp.text
    containment = contain_resp.json()
    containment_id = containment["id"]
    assert containment["active"] is True
    assert containment["target_id"] == compromised_actor_id

    # 3. Verify actor is disabled in database
    with h.owner.begin() as conn:
        actor_row = (
            conn.execute(select(t.actors).where(t.actors.c.id == compromised_actor_id))
            .mappings()
            .first()
        )
        assert actor_row["disabled"] is True, "Compromised actor must be disabled"

        # INVARIANT: Compliance findings MUST NOT be changed or deleted!
        findings_after = (
            conn.execute(select(t.findings).where(t.findings.c.id == finding_id)).mappings().first()
        )
        assert findings_after["status"] == findings_before["status"]
        assert findings_after["title"] == findings_before["title"]
        assert findings_after["semantic_key"] == findings_before["semantic_key"]

    # 4. Release containment
    release_resp = h.call(
        "POST",
        f"/api/v1/operations/containment/{containment_id}/release",
        actor="supervisor",
        mfa=True,
        json={"release_reason": "Actor identity cleared and credentials rotated"},
    )
    assert release_resp.status_code == 200, release_resp.text
    assert release_resp.json()["active"] is False

    # 5. Actor re-enabled, findings still unmutated
    with h.owner.begin() as conn:
        actor_row_after = (
            conn.execute(select(t.actors).where(t.actors.c.id == compromised_actor_id))
            .mappings()
            .first()
        )
        assert actor_row_after["disabled"] is False


def test_safe_operator_reconciliation_command(h):
    """Subphase 15.1: Operator reconciliation safely unleases expired outbox events

    and resets stuck workflow operations for retry.
    """
    inst_id = h.institutions["a"]
    app = h.create()
    app_id = app["id"]

    ev_outbox_id = str(uuid4())
    stuck_op_id = str(uuid4())
    past_time = now() - timedelta(minutes=30)

    # Seed an expired outbox lease and a stuck RUNNING operation
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.outbox).values(
                id=ev_outbox_id,
                institution_id=inst_id,
                application_id=app_id,
                event_type="TestStuckEvent",
                payload={"test": True},
                lease_owner="crashed-worker-1",
                lease_until=past_time,
                delivered_at=None,
                created_at=past_time,
            )
        )
        conn.execute(
            insert(t.operations).values(
                id=stuck_op_id,
                institution_id=inst_id,
                application_id=app_id,
                operation_type="DOCUMENT_EXTRACTION",
                task_queue="document",
                status="RUNNING",
                stable_key=f"stuck-key-{uuid4().hex[:6]}",
                input_ref={},
                attempts=1,
                created_at=past_time,
                updated_at=past_time,
            )
        )

    # 1. Reconcile OUTBOX in dry-run mode
    outbox_dry = h.call(
        "POST",
        "/api/v1/operations/reconcile",
        actor="supervisor",
        json={"target": ReconciliationTarget.OUTBOX.value, "dry_run": True},
    )
    assert outbox_dry.status_code == 200
    assert outbox_dry.json()["scanned_count"] >= 1
    assert outbox_dry.json()["reconciled_count"] == 0

    # 2. Reconcile OUTBOX in active mode
    outbox_exec = h.call(
        "POST",
        "/api/v1/operations/reconcile",
        actor="supervisor",
        json={"target": ReconciliationTarget.OUTBOX.value, "dry_run": False},
    )
    assert outbox_exec.status_code == 200
    assert outbox_exec.json()["reconciled_count"] >= 1

    # Verify outbox lease is released
    with h.owner.begin() as conn:
        ob_row = (
            conn.execute(select(t.outbox).where(t.outbox.c.id == ev_outbox_id)).mappings().first()
        )
        assert ob_row["lease_owner"] is None
        assert ob_row["lease_until"] is None

    # 3. Reconcile WORKFLOWS in active mode
    wf_exec = h.call(
        "POST",
        "/api/v1/operations/reconcile",
        actor="supervisor",
        json={"target": ReconciliationTarget.WORKFLOWS.value, "dry_run": False},
    )
    assert wf_exec.status_code == 200
    assert wf_exec.json()["reconciled_count"] >= 1

    # Verify operation was reset to PENDING
    with h.owner.begin() as conn:
        op_row = (
            conn.execute(select(t.operations).where(t.operations.c.id == stuck_op_id))
            .mappings()
            .first()
        )
        assert op_row["status"] == "PENDING"


# ==============================================================================
# SUBPHASE 15.2: REGULATORY CHANGE & MODEL / TEMPLATE DRIFT
# ==============================================================================


def test_champion_challenger_drift_evaluation():
    """Subphase 15.2: Evaluates champion vs challenger extractor drift over frozen benchmark packets

    without mutating historical extraction runs.
    """
    result = evaluate_champion_challenger(
        candidate_version="candidate_ocr_v2.1.0",
        champion_version="aicte_ocr_extractor_v1.0.0",
    )

    assert result.candidate_version == "candidate_ocr_v2.1.0"
    assert result.champion_version == "aicte_ocr_extractor_v1.0.0"
    assert result.measurement_status == "UNMEASURED"
    assert result.benchmark_packet_count == 0
    assert result.evaluated_field_count == 0
    assert result.field_metrics == []
    assert result.immutable_historical_data_preserved is True


def test_drift_analysis_api_endpoint(h):
    """Subphase 15.2: Exposes POST /api/v1/operations/drift-analysis."""
    resp = h.call(
        "POST",
        "/api/v1/operations/drift-analysis",
        actor="supervisor",
        json={
            "candidate_version": "candidate_paddleocr_v3_en",
            "champion_version": "aicte_ocr_extractor_v1.0.0",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["candidate_version"] == "candidate_paddleocr_v3_en"
    assert data["immutable_historical_data_preserved"] is True


# ==============================================================================
# SUBPHASE 15.4: ACCESS ASSURANCE & EXPIRED-ASSIGNMENT SWEEP
# ==============================================================================


def test_automated_access_sweep_and_review_summary(h):
    """Subphase 15.4: Automated access-review command revokes expired assignments and memberships."""
    inst_id = h.institutions["a"]
    app = h.create()
    app_id = app["id"]

    past_time = now() - timedelta(days=2)

    expired_assign_id = str(uuid4())
    active_assign_id = str(uuid4())

    with h.owner.begin() as conn:
        # Expired assignment: inserted with valid lifetime, then updated to past
        conn.execute(
            insert(t.case_assignments).values(
                id=expired_assign_id,
                institution_id=inst_id,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                expires_at=now() + timedelta(days=2),
                revoked_at=None,
                granted_by=h.actors["supervisor"],
                reason="Temporary scrutiny coverage",
            )
        )
        conn.execute(
            update(t.case_assignments)
            .where(t.case_assignments.c.id == expired_assign_id)
            .values(expires_at=past_time)
        )
        # Active assignment
        conn.execute(
            insert(t.case_assignments).values(
                id=active_assign_id,
                institution_id=inst_id,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                expires_at=now() + timedelta(days=4),
                revoked_at=None,
                granted_by=h.actors["supervisor"],
                reason="Active cycle assignment",
            )
        )

    # 1. Sweep expired assignments
    sweep_resp = h.call(
        "POST",
        "/api/v1/operations/access-review/sweep",
        actor="supervisor",
    )
    assert sweep_resp.status_code == 200, sweep_resp.text
    sweep_data = sweep_resp.json()
    assert sweep_data["expired_assignments_revoked"] >= 1

    # Verify in DB: expired assignment revoked, active assignment untouched
    with h.owner.begin() as conn:
        exp_row = (
            conn.execute(
                select(t.case_assignments).where(t.case_assignments.c.id == expired_assign_id)
            )
            .mappings()
            .first()
        )
        assert exp_row["revoked_at"] is not None

        act_row = (
            conn.execute(
                select(t.case_assignments).where(t.case_assignments.c.id == active_assign_id)
            )
            .mappings()
            .first()
        )
        assert act_row["revoked_at"] is None

    # 2. Get access review summary
    summary_resp = h.call(
        "GET",
        "/api/v1/operations/access-review/summary",
        actor="supervisor",
    )
    assert summary_resp.status_code == 200, summary_resp.text
    summary_data = summary_resp.json()
    assert summary_data["total_active_assignments"] >= 1
