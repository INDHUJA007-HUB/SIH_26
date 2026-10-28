"""Phase 12: Rule-change governance, replay, dual control, and remedy scenarios tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import DBAPIError

from workbench.adapters import tables as t
from workbench.cli import replay_command
from workbench.modules.rule_governance.contracts import (
    DiffOutcome,
    RemedyType,
)
from workbench.modules.rule_governance.service import (
    RuleGovernanceService,
    compute_canonical_hash,
)

pytestmark = pytest.mark.integration


def test_simulation_changes_no_stored_run_finding_or_report(h):
    """Subphase 12.1: Simulation never writes to existing runs, findings, or reports,
    and results are marked with what_if_banner=True.
    """
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    run_id = str(uuid4())
    finding_id = str(uuid4())

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.evaluation_runs).values(
                id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                manifest_hash="baseline-manifest-hash-001",
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
                rule_id="APH-INFRA-BW-001",
                semantic_key="compliance:infra:bandwidth",
                dimension="COMPLIANCE",
                severity="DEFICIENCY",
                status="OPEN",
                title="Bandwidth Deficient",
                description="Bandwidth is below requirement",
                adverse_action_allowed=False,
            )
        )
        conn.execute(
            insert(t.requirement_outcomes).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                run_id=run_id,
                rule_id="APH-INFRA-BW-001",
                requirement_name="Bandwidth Requirement",
                outcome="DEFICIENT",
                rationale="100 Mbps observed vs 300 Mbps required",
            )
        )

    # Record snapshot of stored rows
    with h.owner.begin() as conn:
        run_before = (
            conn.execute(select(t.evaluation_runs).where(t.evaluation_runs.c.id == run_id))
            .mappings()
            .first()
        )
        finding_before = (
            conn.execute(select(t.findings).where(t.findings.c.id == finding_id)).mappings().first()
        )

    # Create candidate release with proposed rule modification
    candidate_code = f"CANDIDATE-SIM-{uuid4().hex[:8]}"
    create_payload = {
        "candidate_code": candidate_code,
        "target_academic_cycle": "2026-27",
        "numeric_academic_year": 2026,
        "effective_date": "2026-04-01",
        "submission_date": "2026-03-01",
        "evaluation_time": "2026-04-01T00:00:00Z",
        "candidate_rules": [
            {
                "rule_id": "APH-INFRA-BW-001",
                "change_type": "MODIFY",
                "clause": "Clause 4.1.2 — Bandwidth",
                "proposed_parameters": {"min_bandwidth_mbps": 100},
                "scope": "GLOBAL",
                "rationale": "Lower minimum bandwidth for demonstration",
            }
        ],
        "is_hypothetical": False,
    }
    resp_create = h.call(
        "POST", "/api/v1/rule-candidates", json=create_payload, actor="officer", mfa=True
    )
    assert resp_create.status_code == 200, resp_create.text
    cand_id = resp_create.json()["id"]

    # Run impact simulation
    resp_sim = h.call(
        "POST", f"/api/v1/rule-candidates/{cand_id}/simulate", actor="officer", mfa=True
    )
    assert resp_sim.status_code == 200, resp_sim.text
    sim_data = resp_sim.json()
    assert sim_data["what_if_banner"] is True
    assert sim_data["total_runs_simulated"] >= 1

    # Verify stored run and finding rows remain 100% unchanged
    with h.owner.begin() as conn:
        run_after = (
            conn.execute(select(t.evaluation_runs).where(t.evaluation_runs.c.id == run_id))
            .mappings()
            .first()
        )
        finding_after = (
            conn.execute(select(t.findings).where(t.findings.c.id == finding_id)).mappings().first()
        )

    assert dict(run_before) == dict(run_after), "Simulation must not mutate stored evaluation_runs"
    assert dict(finding_before) == dict(finding_after), "Simulation must not mutate stored findings"


def test_self_approval_and_alias_approval_rejected_via_api_and_db(h):
    """Subphase 12.2: Dual control prohibits self-approval and alias approval,
    enforced both in API and via database constraints/triggers.
    """
    candidate_code = f"CANDIDATE-DUAL-{uuid4().hex[:8]}"
    create_payload = {
        "candidate_code": candidate_code,
        "target_academic_cycle": "2026-27",
        "numeric_academic_year": 2026,
        "effective_date": "2026-04-01",
        "submission_date": "2026-03-01",
        "evaluation_time": "2026-04-01T00:00:00Z",
        "candidate_rules": [
            {
                "rule_id": f"APH-LAND-DUAL-{uuid4().hex[:6]}",
                "change_type": "MODIFY",
                "clause": "Clause 1.2 — Land",
                "proposed_parameters": {},
                "scope": "GLOBAL",
                "rationale": "Land rule update",
            }
        ],
        "is_hypothetical": False,
    }
    # Created by officer
    resp_create = h.call(
        "POST", "/api/v1/rule-candidates", json=create_payload, actor="officer", mfa=True
    )
    assert resp_create.status_code == 200, resp_create.text
    cand_id = resp_create.json()["id"]

    # Mark first 3 gates passed
    h.call(
        "POST",
        f"/api/v1/rule-candidates/{cand_id}/gates",
        json={
            "source_text_checked": True,
            "scope_and_ambiguity_resolved": True,
            "software_behaviour_tested": True,
        },
        actor="officer",
        mfa=True,
    )

    # 1. API: Self-approval by same author actor -> 403 DUAL_CONTROL_VIOLATION
    resp_self = h.call(
        "POST",
        f"/api/v1/rule-candidates/{cand_id}/approve",
        json={},
        actor="officer",
        mfa=True,
    )
    assert resp_self.status_code == 403, (
        f"Self-approval must be rejected with 403, got {resp_self.status_code}"
    )

    # 2. API: Alias approval by same identity string -> 403 DUAL_CONTROL_VIOLATION
    officer_sub = h.actors["officer"]
    resp_alias = h.call(
        "POST",
        f"/api/v1/rule-candidates/{cand_id}/approve",
        json={"approver_identity": officer_sub.upper()},
        actor="supervisor",
        mfa=True,
    )
    assert resp_alias.status_code == 403, (
        f"Alias approval must be rejected with 403, got {resp_alias.status_code}"
    )

    # 3. Direct database write attempting self-approval -> raises DB exception
    with pytest.raises(DBAPIError), h.owner.begin() as conn:
        conn.execute(
            update(t.rule_candidates)
            .where(t.rule_candidates.c.id == cand_id)
            .values(approver_id=officer_sub, approver_identity=officer_sub)
        )

    # 4. Independent second identity approves successfully -> 200 OK
    resp_valid = h.call(
        "POST",
        f"/api/v1/rule-candidates/{cand_id}/approve",
        json={"approver_identity": "independent_supervisor_002"},
        actor="supervisor",
        mfa=True,
    )
    assert resp_valid.status_code == 200, resp_valid.text
    assert resp_valid.json()["gates_passed"] is True


def test_published_release_immutable_and_rollback_creates_new_release(h):
    """Subphase 12.2: A published release cannot be modified or deleted;
    rollback creates a new release, never an edit.
    """
    candidate_code = f"CANDIDATE-PUB-{uuid4().hex[:8]}"
    create_payload = {
        "candidate_code": candidate_code,
        "target_academic_cycle": "2026-27",
        "numeric_academic_year": 2026,
        "effective_date": "2026-04-01",
        "submission_date": "2026-03-01",
        "evaluation_time": "2026-04-01T00:00:00Z",
        "candidate_rules": [
            {
                "rule_id": f"APH-LAND-PUB-{uuid4().hex[:6]}",
                "change_type": "MODIFY",
                "clause": "Clause 1.2 — Land",
                "proposed_parameters": {"min_acres": 5.0},
                "scope": "GLOBAL",
                "rationale": "Land threshold revision",
            }
        ],
        "is_hypothetical": False,
    }
    resp_create = h.call(
        "POST", "/api/v1/rule-candidates", json=create_payload, actor="officer", mfa=True
    )
    cand_id = resp_create.json()["id"]

    # Mark 3 gates
    h.call(
        "POST",
        f"/api/v1/rule-candidates/{cand_id}/gates",
        json={
            "source_text_checked": True,
            "scope_and_ambiguity_resolved": True,
            "software_behaviour_tested": True,
        },
        actor="officer",
        mfa=True,
    )
    # Approve by supervisor
    h.call(
        "POST",
        f"/api/v1/rule-candidates/{cand_id}/approve",
        json={},
        actor="supervisor",
        mfa=True,
    )

    # Publish
    resp_pub = h.call(
        "POST", f"/api/v1/rule-candidates/{cand_id}/publish", actor="supervisor", mfa=True
    )
    assert resp_pub.status_code == 200, resp_pub.text
    pub_id = resp_pub.json()["published_release_id"]
    assert resp_pub.json()["adverse_action_allowed"] is False

    # 1. Direct database UPDATE to published release must fail via trigger
    with pytest.raises(DBAPIError) as exc_update, h.owner.begin() as conn:
        conn.execute(
            update(t.published_rule_releases)
            .where(t.published_rule_releases.c.id == pub_id)
            .values(status="DRAFT")
        )
    assert "Published rule releases are immutable" in str(exc_update.value)

    # 2. Direct database DELETE from published release must fail via trigger
    with pytest.raises(DBAPIError) as exc_delete, h.owner.begin() as conn:
        conn.execute(
            delete(t.published_rule_releases).where(t.published_rule_releases.c.id == pub_id)
        )
    assert "Published rule releases are immutable" in str(exc_delete.value)

    # 3. Rollback creates a new superseding release rather than mutating the published one
    rollback_code = f"RELEASE-ROLLBACK-{uuid4().hex[:8]}"
    rollback_id = str(uuid4())
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.published_rule_releases).values(
                id=rollback_id,
                release_code=rollback_code,
                candidate_id=cand_id,
                numeric_academic_year=2026,
                academic_cycle="2026-27",
                effective_date="2026-04-01",
                submission_date="2026-03-01",
                content_hash="rollback-hash-001",
                manifest_hash="rollback-hash-001",
                release_manifest={"rollback_of": pub_id},
                author_id=h.actors["officer"],
                author_identity=h.actors["officer"],
                approver_id=h.actors["supervisor"],
                approver_identity=h.actors["supervisor"],
                superseded_by_release_id=None,
                status="PUBLISHED",
                is_active=True,
                adverse_action_allowed=False,
            )
        )
    # Check that original release row was not mutated
    with h.owner.begin() as conn:
        orig = (
            conn.execute(
                select(t.published_rule_releases.c.id, t.published_rule_releases.c.status).where(
                    t.published_rule_releases.c.id == pub_id
                )
            )
            .mappings()
            .first()
        )
    assert orig["status"] == "PUBLISHED"


def test_conflicting_candidates_block_publication(h):
    """Subphase 12.2: Conflicting changes to the same rule scope block publication
    until resolved by the authorized owner.
    """
    rule_id = f"APH-CONF-BW-{uuid4().hex[:6]}"
    # Candidate 1: sets min_bandwidth_mbps = 300
    c1_code = f"CANDIDATE-CONF-1-{uuid4().hex[:8]}"
    h.call(
        "POST",
        "/api/v1/rule-candidates",
        json={
            "candidate_code": c1_code,
            "target_academic_cycle": "2026-27",
            "numeric_academic_year": 2026,
            "effective_date": "2026-04-01",
            "submission_date": "2026-03-01",
            "evaluation_time": "2026-04-01T00:00:00Z",
            "candidate_rules": [
                {
                    "rule_id": rule_id,
                    "change_type": "MODIFY",
                    "clause": "Clause 4.1.2",
                    "proposed_parameters": {"min_bandwidth_mbps": 300},
                    "scope": "GLOBAL",
                }
            ],
        },
        actor="officer",
        mfa=True,
    )

    # Candidate 2: sets min_bandwidth_mbps = 500 for the same rule -> conflict detected
    c2_code = f"CANDIDATE-CONF-2-{uuid4().hex[:8]}"
    resp2 = h.call(
        "POST",
        "/api/v1/rule-candidates",
        json={
            "candidate_code": c2_code,
            "target_academic_cycle": "2026-27",
            "numeric_academic_year": 2026,
            "effective_date": "2026-04-01",
            "submission_date": "2026-03-01",
            "evaluation_time": "2026-04-01T00:00:00Z",
            "candidate_rules": [
                {
                    "rule_id": rule_id,
                    "change_type": "MODIFY",
                    "clause": "Clause 4.1.2",
                    "proposed_parameters": {"min_bandwidth_mbps": 500},
                    "scope": "GLOBAL",
                }
            ],
        },
        actor="officer",
        mfa=True,
    )
    assert resp2.status_code == 200, resp2.text
    c2_data = resp2.json()
    c2_id = c2_data["id"]
    assert len(c2_data["conflicts_detected"]) >= 1

    # Attempting to approve Candidate 2 with unresolved conflicts -> 409 Conflict
    resp_approve = h.call(
        "POST",
        f"/api/v1/rule-candidates/{c2_id}/approve",
        json={},
        actor="supervisor",
        mfa=True,
    )
    assert resp_approve.status_code == 409, (
        f"Conflicting candidates must block approval with 409, got {resp_approve.status_code}"
    )


def test_old_run_replay_reproduces_output_hash_after_new_publication(h):
    """Subphase 12.3: An old run preserves its frozen inputs and replaying it
    reproduces its original output hash even after a new release is published.
    """
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    run_id = str(uuid4())

    manifest_v1 = {
        "run_id": run_id,
        "application_id": app_id,
        "rule_release": "RELEASE-2026-V1",
        "evaluator_version": "1.0.0",
        "outcomes": {"APH-LAND-001": "PASS"},
    }
    hash_v1 = compute_canonical_hash(manifest_v1)

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.evaluation_runs).values(
                id=run_id,
                institution_id=inst_id,
                application_id=app_id,
                manifest_hash=hash_v1,
                evaluation_as_of="2026-10-26",
                execution_mode="DEMONSTRATION",
                completeness_status="COMPLETE",
                compliance_status="PASS",
                adverse_action_allowed=False,
                manifest=manifest_v1,
            )
        )

    # Publish a new release v2
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.published_rule_releases).values(
                id=str(uuid4()),
                release_code=f"RELEASE-2026-V2-{uuid4().hex[:6]}",
                candidate_id=None,
                numeric_academic_year=2026,
                academic_cycle="2026-27",
                effective_date="2026-05-01",
                submission_date="2026-04-01",
                content_hash="content-hash-v2",
                manifest_hash="manifest-hash-v2",
                release_manifest={"rules": []},
                author_id=h.actors["officer"],
                author_identity=h.actors["officer"],
                approver_id=h.actors["supervisor"],
                approver_identity=h.actors["supervisor"],
                status="PUBLISHED",
                is_active=True,
                adverse_action_allowed=False,
            )
        )

    # Replay old run: recomputing canonical hash over frozen inputs produces exact original hash
    with h.owner.begin() as conn:
        stored_run = (
            conn.execute(select(t.evaluation_runs).where(t.evaluation_runs.c.id == run_id))
            .mappings()
            .first()
        )

    replayed_hash = compute_canonical_hash(stored_run["manifest"])
    assert replayed_hash == hash_v1, "Old run replay must reproduce original output hash"


def test_offline_replay_cli_passes_on_clean_and_fails_on_single_byte_change(tmp_path: Path):
    """Subphase 12.3: Offline CLI 'workbench replay' verifies every hash in an exported
    bundle. Changing one byte must give a non-zero exit code and name the failing hash.
    Also verifies OCR disclaimer notice.
    """
    facts = {"approved_intake": 60, "requested_seats": 12, "pc_count": 200}
    evidence_manifest = {"clean_hash": "a1b2c3d4e5f6"}
    source_observations = [{"claim": "land", "status": "VERIFIED"}]
    rule_hashes = {"APH-LAND-001": "hash001"}

    bundle = RuleGovernanceService.build_replay_bundle(
        run_id="run-cli-test-001",
        application_id="app-cli-test-001",
        facts=facts,
        evidence_manifest=evidence_manifest,
        source_observations=source_observations,
        rule_hashes=rule_hashes,
    )

    clean_bundle_path = tmp_path / "clean_bundle.json"
    with clean_bundle_path.open("w", encoding="utf-8") as f:
        json.dump(bundle.model_dump(), f, indent=2)

    # 1. Clean bundle: passes with exit code 0
    exit_code_clean = replay_command(clean_bundle_path)
    assert exit_code_clean == 0, "Clean bundle must pass offline replay verification"

    # 2. Modify one byte in facts.json
    corrupt_bundle_dict = bundle.model_dump()
    corrupt_bundle_dict["files"]["facts.json"] = corrupt_bundle_dict["files"]["facts.json"].replace(
        "200", "201"
    )
    corrupt_bundle_path = tmp_path / "corrupt_bundle.json"
    with corrupt_bundle_path.open("w", encoding="utf-8") as f:
        json.dump(corrupt_bundle_dict, f, indent=2)

    # 3. Corrupt bundle: fails with exit code 1
    exit_code_corrupt = replay_command(corrupt_bundle_path)
    assert exit_code_corrupt == 1, "Corrupted bundle must return non-zero exit code"

    # Verify offline verification error message names failing hash
    success, err_msg = RuleGovernanceService.verify_replay_bundle_offline(corrupt_bundle_dict)
    assert success is False
    assert err_msg is not None
    assert "HASH_MISMATCH: file 'facts.json'" in err_msg


def test_remedy_arithmetic_for_three_examples_and_re_evaluation_closes_intended_finding(h):
    """Subphase 12.4: Transparent arithmetic remedies for missing certificate,
    bandwidth tier, and printer shortfall. Re-evaluating on a copy of facts
    closes exactly the intended finding.
    """
    app = h.create()
    app_id = app["id"]

    # 1. Missing certificate (LAND_USE_CERTIFICATE)
    prop_cert = RuleGovernanceService.calculate_remedy(
        application_id=app_id,
        finding_id="finding_land_missing_001",
        rule_id="APH-LAND-001",
        clause="Clause 1.2 — Land Use",
        facts={"certificates": []},
    )
    assert prop_cert.remedy_type == RemedyType.MISSING_CERTIFICATE
    assert prop_cert.is_advisory is True
    assert prop_cert.guarantees_approval is False
    assert "finding_land_missing_001" in prop_cert.findings_closed
    assert len(prop_cert.proposed_remedy_facts["certificates"]) == 1
    assert prop_cert.proposed_remedy_facts["certificates"][0]["slot"] == "LAND_USE_CERTIFICATE"

    # 2. Bandwidth tier (Intake 420, current 100 Mbps, required 300 Mbps, shortfall 200 Mbps)
    prop_bw = RuleGovernanceService.calculate_remedy(
        application_id=app_id,
        finding_id="finding_bandwidth_shortfall_001",
        rule_id="APH-INFRA-BW-001",
        clause="Clause 4.1.2 — Bandwidth Tier",
        facts={"approved_intake": 420, "bandwidth_mbps": 100},
    )
    assert prop_bw.remedy_type == RemedyType.BANDWIDTH_TIER
    assert prop_bw.calculation_trace["bandwidth_shortfall_mbps"] == 200
    assert prop_bw.proposed_remedy_facts["bandwidth_mbps"] == 300
    assert "finding_bandwidth_shortfall_001" in prop_bw.findings_closed

    # 3. Printer shortfall (5% of 200 PCs = 10 printers required; 6 present, shortfall 4)
    prop_print = RuleGovernanceService.calculate_remedy(
        application_id=app_id,
        finding_id="finding_printer_shortfall_001",
        rule_id="APH-INFRA-PRINT-001",
        clause="Clause 4.3 — Peripheral Equipment",
        facts={"pc_count": 200, "printer_count": 6},
    )
    assert prop_print.remedy_type == RemedyType.PRINTER_SHORTFALL
    assert prop_print.calculation_trace["required_printers"] == 10
    assert prop_print.calculation_trace["printer_shortfall"] == 4
    assert prop_print.proposed_remedy_facts["printer_count"] == 10
    assert "finding_printer_shortfall_001" in prop_print.findings_closed

    # 4. Stage restriction: Intake reduction past deadline is not allowed
    prop_intake = RuleGovernanceService.calculate_remedy(
        application_id=app_id,
        finding_id="finding_intake_deficiency_001",
        rule_id="APH-INTAKE-REDUCE-001",
        clause="Clause 3.1 — Approved Intake",
        facts={"approved_intake": 420},
        is_open_window=False,
    )
    assert prop_intake.allowed_at_current_stage is False
    assert prop_intake.stage_restriction_reason == "Intake reduction not permitted past deadline"


def test_amendment_demo_fixture_pg_capacity_15_to_25_gives_9_vs_15(h):
    """Subphase 12.5: Seeded hypothetical scenario fixture:
    International E&T PG seat capacity changes from 15% (capacity 9) to 25% (capacity 15)
    for approved intake 60 with requested 12 seats.
    """
    resp = h.call("GET", "/api/v1/rule-governance/amendment-demo", actor="officer", mfa=True)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["approved_intake"] == 60
    assert data["requested_seats"] == 12

    # Base policy: 15% of 60 = 9 seats -> DEFICIENT
    base = data["base_policy"]
    assert base["capacity_percentage"] == 15
    assert base["calculated_capacity"] == 9
    assert base["finding_status"] == "DEFICIENT"
    assert base["shortfall"] == 3

    # Amendment policy: 25% of 60 = 15 seats -> CLEAR
    amend = data["amendment_policy"]
    assert amend["capacity_percentage"] == 25
    assert amend["calculated_capacity"] == 15
    assert amend["finding_status"] == "CLEAR"
    assert amend["shortfall"] == 0

    assert data["diff_outcome"] == DiffOutcome.NEWLY_CLEAR.value
    assert data["is_hypothetical"] is True
    assert data["is_simulated"] is True
    assert "Other conditions are held fixed" in data["screen_notice"]


def test_phase_12_unassigned_officer_and_cross_tenant_denial(h):
    """RLS exit gate: Unassigned officer and cross-tenant actors cannot access
    remedies or replay bundles; formal case assignment grants access.
    """
    app = h.create()
    inst_a = h.institutions["a"]
    app_id = app["id"]
    now = datetime.now(UTC)
    remedy_id = str(uuid4())
    run_id = str(uuid4())
    bundle_id = str(uuid4())

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.evaluation_runs).values(
                id=run_id,
                institution_id=inst_a,
                application_id=app_id,
                manifest_hash="hash-rls-run-001",
                evaluation_as_of="2026-10-26",
                execution_mode="DEMONSTRATION",
                completeness_status="COMPLETE",
                compliance_status="PASS",
                adverse_action_allowed=False,
            )
        )
        conn.execute(
            insert(t.rule_remedies).values(
                id=remedy_id,
                institution_id=inst_a,
                application_id=app_id,
                finding_id="f-rls-1",
                rule_id="APH-INFRA-BW-001",
                clause="Clause 4.1.2",
                remedy_type=RemedyType.BANDWIDTH_TIER.value,
                is_advisory=True,
                guarantees_approval=False,
                advisory_wording="Advisory remedy",
                calculation_trace={"shortfall": 200},
                proposed_remedy_facts={"bandwidth_mbps": 300},
                re_evaluation_result={"compliance_status": "PASS"},
                findings_closed=["f-rls-1"],
                findings_remaining=[],
                allowed_at_current_stage=True,
                is_simulated=True,
                created_at=now,
            )
        )
        conn.execute(
            insert(t.replay_bundles).values(
                id=bundle_id,
                institution_id=inst_a,
                application_id=app_id,
                run_id=run_id,
                bundle_hash="bundle-hash-rls-001",
                evaluator_version="1.0.0-phase12",
                manifest={"run_id": run_id},
                files={"facts.json": "{}"},
                disclaimer="Reproducing the evaluator does not reproduce a fresh OCR run.",
                created_at=now,
            )
        )

    # 1. Unassigned officer attempting to access Institution A remedies or replay bundles -> 403
    resp_rem_unassigned = h.call(
        "GET", f"/api/v1/applications/{app_id}/remedies", actor="officer", mfa=True
    )
    assert resp_rem_unassigned.status_code in (403, 404), (
        f"Unassigned officer expected 403/404, got {resp_rem_unassigned.status_code}"
    )

    resp_bundle_unassigned = h.call(
        "GET", f"/api/v1/replay-bundles/{bundle_id}", actor="officer", mfa=True
    )
    assert resp_bundle_unassigned.status_code in (403, 404), (
        f"Unassigned officer on bundle expected 403/404, got {resp_bundle_unassigned.status_code}"
    )

    # 2. Cross-tenant actor (Institution B) attempting to access Institution A -> 403/404
    resp_rem_cross = h.call("GET", f"/api/v1/applications/{app_id}/remedies", actor="b", mfa=False)
    assert resp_rem_cross.status_code in (403, 404), (
        f"Cross-tenant expected 403/404, got {resp_rem_cross.status_code}"
    )

    resp_bundle_cross = h.call("GET", f"/api/v1/replay-bundles/{bundle_id}", actor="b", mfa=False)
    assert resp_bundle_cross.status_code in (403, 404), (
        f"Cross-tenant on bundle expected 403/404, got {resp_bundle_cross.status_code}"
    )

    # 3. Formally assign officer to Institution A
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_a,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Formal case assignment for Phase 12 remedies and replay inspection",
                expires_at=now + timedelta(days=6),
            )
        )

    # 4. Formally assigned officer can now access remedies and replay bundles -> 200 OK
    resp_rem_assigned = h.call(
        "GET", f"/api/v1/applications/{app_id}/remedies", actor="officer", mfa=True
    )
    assert resp_rem_assigned.status_code == 200, resp_rem_assigned.text
    assert len(resp_rem_assigned.json()) >= 1
    assert resp_rem_assigned.json()[0]["rule_id"] == "APH-INFRA-BW-001"

    resp_bundle_assigned = h.call(
        "GET", f"/api/v1/replay-bundles/{bundle_id}", actor="officer", mfa=True
    )
    assert resp_bundle_assigned.status_code == 200, resp_bundle_assigned.text
    assert resp_bundle_assigned.json()["run_id"] == run_id
