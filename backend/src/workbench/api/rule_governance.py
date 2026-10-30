"""Phase 12 API endpoints: Rule-change governance, dual control, impact simulation,
offline replay bundles, and advisory remedy scenarios.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Connection, select, text

from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore
from workbench.contracts.intake import Principal
from workbench.modules.rule_governance import (
    CandidateRuleChange,
    CandidateStatus,
    FourGates,
    RemedyProposal,
    ReplayBundle,
    RuleGovernanceService,
)
from workbench.modules.rule_governance.service import compute_canonical_hash
from workbench.platform.errors import ApplicationError, NotFoundError


def _check_institution_access(
    conn: Connection,
    institution_id: str,
    application_id: str | None = None,
    write: bool = False,
) -> None:
    app_param = application_id if application_id is not None else None
    allowed = conn.scalar(
        text("SELECT wb.can_access(:inst, :app, :write) OR wb.manages(:inst)"),
        {"inst": institution_id, "app": app_param, "write": write},
    )
    if allowed:
        return
    is_elevated = conn.scalar(
        text("SELECT wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('auditor'))")
    )
    if not is_elevated:
        raise ApplicationError(
            "ACCESS_DENIED", "Access to institution or application is denied", 403
        )


class CreateCandidateBody(BaseModel):
    candidate_code: str
    target_academic_cycle: str
    numeric_academic_year: int
    effective_date: str
    submission_date: str
    evaluation_time: str
    candidate_rules: list[CandidateRuleChange]
    is_hypothetical: bool = False


class UpdateGatesBody(BaseModel):
    source_text_checked: bool | None = None
    scope_and_ambiguity_resolved: bool | None = None
    software_behaviour_tested: bool | None = None
    authorized_policy_approved: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ApproveCandidateBody(BaseModel):
    approver_identity: str | None = None


class CalculateRemedyBody(BaseModel):
    finding_id: str
    rule_id: str
    clause: str
    facts: dict[str, Any] = Field(default_factory=dict)
    is_open_window: bool = True


ELEVATED_ROLES_SQL = (
    "SELECT wb.elevated() AND ("
    "wb.has_role('supervisor') OR wb.has_role('officer') OR "
    "wb.has_role('admin') OR wb.has_role('identity_admin'))"
)
SUPERVISOR_OR_ADMIN_SQL = (
    "SELECT wb.elevated() AND ("
    "wb.has_role('supervisor') OR wb.has_role('admin') OR wb.has_role('identity_admin'))"
)


def create_phase_12_router(store: DomainStore, principal: Callable[..., Principal]) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["phase_12_rule_governance"])

    @router.post("/rule-candidates")
    def create_candidate_endpoint(
        body: CreateCandidateBody,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            is_elevated = conn.scalar(text(ELEVATED_ROLES_SQL))
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED", "Applicants cannot manage rule candidates", 403
                )

            # Check existing candidate code uniqueness
            existing = conn.execute(
                select(t.rule_candidates.c.id).where(
                    t.rule_candidates.c.candidate_code == body.candidate_code
                )
            ).first()
            if existing:
                raise ApplicationError(
                    "DUPLICATE_CANDIDATE", f"Candidate '{body.candidate_code}' already exists", 409
                )

            # Check for scope conflicts against other active candidates
            active_cands = (
                conn.execute(
                    select(t.rule_candidates.c.candidate_rules).where(
                        t.rule_candidates.c.status.in_(["DRAFT", "TESTED", "SOURCE_CHECKED"])
                    )
                )
                .scalars()
                .all()
            )
            all_existing_rules = []
            for r_list in active_cands:
                if isinstance(r_list, list):
                    all_existing_rules.extend(r_list)

            conflicts = RuleGovernanceService.detect_conflicts(
                candidate_rules=[r.model_dump() for r in body.candidate_rules],
                existing_candidate_rules=all_existing_rules,
            )

            candidate_dict = RuleGovernanceService.create_candidate_manifest(
                candidate_code=body.candidate_code,
                academic_cycle=body.target_academic_cycle,
                numeric_academic_year=body.numeric_academic_year,
                effective_date=body.effective_date,
                submission_date=body.submission_date,
                evaluation_time=body.evaluation_time,
                author_id=actor.subject,
                author_identity=str(store.actor(conn)["person_id"]),
                candidate_rules=body.candidate_rules,
                is_hypothetical=body.is_hypothetical,
            )
            candidate_dict["conflicts_detected"] = conflicts

            conn.execute(
                t.rule_candidates.insert().values(
                    id=candidate_dict["id"],
                    candidate_code=candidate_dict["candidate_code"],
                    target_academic_cycle=candidate_dict["target_academic_cycle"],
                    numeric_academic_year=candidate_dict["numeric_academic_year"],
                    effective_date=candidate_dict["effective_date"],
                    submission_date=candidate_dict["submission_date"],
                    evaluation_time=candidate_dict["evaluation_time"],
                    author_id=candidate_dict["author_id"],
                    author_identity=candidate_dict["author_identity"],
                    status=candidate_dict["status"],
                    four_gates=candidate_dict["four_gates"],
                    candidate_rules=candidate_dict["candidate_rules"],
                    release_manifest=candidate_dict["release_manifest"],
                    manifest_hash=candidate_dict["manifest_hash"],
                    conflicts_detected=conflicts,
                    what_if_banner=True,
                    is_hypothetical=body.is_hypothetical,
                )
            )
            return candidate_dict

    @router.get("/rule-candidates")
    def list_candidates_endpoint(
        actor: Principal = Depends(principal),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            is_elevated = conn.scalar(text(ELEVATED_ROLES_SQL))
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED", "Applicants cannot view rule candidates", 403
                )
            rows = conn.execute(select(t.rule_candidates)).mappings().all()
            return [dict(r) for r in rows]

    @router.get("/rule-candidates/{candidate_id}")
    def get_candidate_endpoint(
        candidate_id: str,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            is_elevated = conn.scalar(text(ELEVATED_ROLES_SQL))
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED", "Applicants cannot view rule candidates", 403
                )
            row = (
                conn.execute(
                    select(t.rule_candidates)
                    .where(t.rule_candidates.c.id == candidate_id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFoundError("RuleCandidate")
            return dict(row)

    @router.post("/rule-candidates/{candidate_id}/gates")
    def update_gates_endpoint(
        candidate_id: str,
        body: UpdateGatesBody,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            is_elevated = conn.scalar(text(ELEVATED_ROLES_SQL))
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED", "Applicants cannot update rule candidate gates", 403
                )
            row = (
                conn.execute(
                    select(t.rule_candidates)
                    .where(t.rule_candidates.c.id == candidate_id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFoundError("RuleCandidate")

            if row["status"] == "PUBLISHED":
                raise ApplicationError(
                    "IMMUTABLE_RELEASE", "Published candidates cannot be edited", 409
                )
            gates = FourGates.model_validate(row["four_gates"])
            gates.details.pop("approved_rules_hash", None)
            if body.source_text_checked is not None:
                gates.source_text_checked = body.source_text_checked
            if body.scope_and_ambiguity_resolved is not None:
                gates.scope_and_ambiguity_resolved = body.scope_and_ambiguity_resolved
            if body.software_behaviour_tested is not None:
                gates.software_behaviour_tested = body.software_behaviour_tested
            if body.authorized_policy_approved is not None:
                gates.authorized_policy_approved = body.authorized_policy_approved
            if body.details:
                gates.details.update(body.details)

            # Determine transition state
            new_status = row["status"]
            if gates.software_behaviour_tested and gates.scope_and_ambiguity_resolved:
                new_status = CandidateStatus.TESTED.value
            elif gates.source_text_checked:
                new_status = CandidateStatus.SOURCE_CHECKED.value

            conn.execute(
                t.rule_candidates.update()
                .where(t.rule_candidates.c.id == candidate_id)
                .values(
                    four_gates=gates.model_dump(),
                    status=new_status,
                    approver_id=None,
                    approver_identity=None,
                )
            )
            return {
                "candidate_id": candidate_id,
                "four_gates": gates.model_dump(),
                "status": new_status,
            }

    @router.post("/rule-candidates/{candidate_id}/simulate")
    def simulate_impact_endpoint(
        candidate_id: str,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            is_elevated = conn.scalar(text(ELEVATED_ROLES_SQL))
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED", "Applicants cannot run or view rule candidate simulations", 403
                )

            is_supervisor_or_admin = conn.scalar(text(SUPERVISOR_OR_ADMIN_SQL))

            row = (
                conn.execute(
                    select(t.rule_candidates)
                    .where(t.rule_candidates.c.id == candidate_id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFoundError("RuleCandidate")

            candidate_rules = row["candidate_rules"]

            # Load frozen runs to simulate against
            run_rows = conn.execute(select(t.evaluation_runs)).mappings().all()
            frozen_runs = []
            for r in run_rows:
                run_id = r["id"]
                # If actor is not a supervisor or admin (e.g. an officer),
                # verify assignment access to this institution
                if not is_supervisor_or_admin:
                    has_access = conn.scalar(
                        text("SELECT wb.can_access(:inst, :app, false) OR wb.manages(:inst)"),
                        {"inst": r["institution_id"], "app": r["application_id"]},
                    )
                    if not has_access:
                        continue

                # Get requirement outcomes for baseline
                outcomes = (
                    conn.execute(
                        select(
                            t.requirement_outcomes.c.rule_id,
                            t.requirement_outcomes.c.outcome,
                        ).where(t.requirement_outcomes.c.run_id == run_id)
                    )
                    .mappings()
                    .all()
                )
                outcome_map = {
                    o["rule_id"]: {"POTENTIAL_DEFICIENCY": "DEFICIENT"}.get(
                        o["outcome"], o["outcome"]
                    )
                    for o in outcomes
                }

                snapshot = r.get("manifest") or {}
                facts = {**snapshot.get("facts", {}), **snapshot.get("claims", {})}
                frozen_runs.append(
                    {
                        "run_id": run_id,
                        "application_id": r["application_id"],
                        "facts": facts,
                        "requirement_outcomes": outcome_map,
                    }
                )

            sim_result = RuleGovernanceService.simulate_candidate_impact(
                candidate_id=candidate_id,
                candidate_rules=candidate_rules,
                frozen_runs=frozen_runs,
                is_hypothetical=row["is_hypothetical"],
            )

            # Store simulation record
            sim_id = str(uuid.uuid4())
            conn.execute(
                t.rule_impact_simulations.insert().values(
                    id=sim_id,
                    candidate_id=candidate_id,
                    simulated_by=actor.subject,
                    total_runs_simulated=sim_result.total_runs_simulated,
                    what_if_banner=True,
                    diff_summary=sim_result.diff_summary,
                    run_diffs=[rd.model_dump(mode="json") for rd in sim_result.run_diffs],
                    is_hypothetical=row["is_hypothetical"],
                )
            )

            return sim_result.model_dump(mode="json")

    @router.get("/rule-candidates/{candidate_id}/simulations")
    def get_candidate_simulations_endpoint(
        candidate_id: str,
        actor: Principal = Depends(principal),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            is_elevated = conn.scalar(text(ELEVATED_ROLES_SQL))
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED", "Applicants cannot view rule candidate simulations", 403
                )

            is_supervisor_or_admin = conn.scalar(text(SUPERVISOR_OR_ADMIN_SQL))

            sim_rows = (
                conn.execute(
                    select(t.rule_impact_simulations).where(
                        t.rule_impact_simulations.c.candidate_id == candidate_id
                    )
                )
                .mappings()
                .all()
            )

            results: list[dict[str, Any]] = []
            for sim in sim_rows:
                sim_dict = dict(sim)
                raw_diffs = sim_dict.get("run_diffs", [])
                if not is_supervisor_or_admin:
                    filtered_diffs = []
                    for rd in raw_diffs:
                        app_id = rd.get("application_id")
                        inst_id = conn.scalar(
                            select(t.applications.c.institution_id).where(
                                t.applications.c.id == app_id
                            )
                        )
                        if inst_id and conn.scalar(
                            text("SELECT wb.can_access(:inst, :app, false) OR wb.manages(:inst)"),
                            {"inst": inst_id, "app": app_id},
                        ):
                            filtered_diffs.append(rd)
                    sim_dict["run_diffs"] = filtered_diffs
                results.append(sim_dict)
            return results

    @router.post("/rule-candidates/{candidate_id}/approve")
    def approve_candidate_endpoint(
        candidate_id: str,
        body: ApproveCandidateBody | None = None,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            is_elevated = conn.scalar(text(ELEVATED_ROLES_SQL))
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED", "Applicants cannot approve rule candidates", 403
                )

            row = (
                conn.execute(
                    select(t.rule_candidates)
                    .where(t.rule_candidates.c.id == candidate_id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFoundError("RuleCandidate")

            approver_id = actor.subject
            if (
                body
                and body.approver_identity
                and body.approver_identity.strip().lower() == row["author_identity"].strip().lower()
            ):
                raise ApplicationError(
                    "DUAL_CONTROL_VIOLATION", "Author identity cannot approve", 403
                )
            approver_identity = str(store.actor(conn)["person_id"])

            # Enforce dual control and alias check
            try:
                RuleGovernanceService.validate_dual_control(
                    author_id=row["author_id"],
                    author_identity=row["author_identity"],
                    approver_id=approver_id,
                    approver_identity=approver_identity,
                )
            except ValueError as err:
                raise ApplicationError("DUAL_CONTROL_VIOLATION", str(err), 403) from err

            # Check unresolved conflicts first
            conflicts = row.get("conflicts_detected", [])
            if conflicts:
                raise ApplicationError(
                    "UNRESOLVED_SCOPE_CONFLICTS",
                    f"Candidate has {len(conflicts)} unresolved scope conflicts blocking approval.",
                    409,
                )

            # Check four gates
            gates = FourGates.model_validate(row["four_gates"])
            gates.authorized_policy_approved = True
            gates.details["approver_id"] = approver_id
            gates.details["approved_rules_hash"] = compute_canonical_hash(row["candidate_rules"])

            if not gates.all_passed:
                raise ApplicationError(
                    "INCOMPLETE_GATES",
                    "All four qualification gates must be satisfied before candidate approval.",
                    422,
                )

            conn.execute(
                t.rule_candidates.update()
                .where(t.rule_candidates.c.id == candidate_id)
                .values(
                    approver_id=approver_id,
                    approver_identity=approver_identity,
                    four_gates=gates.model_dump(),
                    status=CandidateStatus.TESTED.value,
                )
            )
            return {
                "candidate_id": candidate_id,
                "status": CandidateStatus.TESTED.value,
                "approved_by": approver_id,
                "gates_passed": True,
            }

    @router.post("/rule-candidates/{candidate_id}/publish")
    def publish_candidate_endpoint(
        candidate_id: str,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            is_elevated = conn.scalar(text(ELEVATED_ROLES_SQL))
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED", "Applicants cannot publish rule releases", 403
                )

            row = (
                conn.execute(
                    select(t.rule_candidates)
                    .where(t.rule_candidates.c.id == candidate_id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFoundError("RuleCandidate")

            if not row["approver_id"]:
                raise ApplicationError(
                    "UNAPPROVED_CANDIDATE",
                    "Candidate must be approved by an independent second identity before "
                    "publication.",
                    422,
                )

            approved_gates = FourGates.model_validate(row["four_gates"])
            if not approved_gates.all_passed or approved_gates.details.get(
                "approved_rules_hash"
            ) != compute_canonical_hash(row["candidate_rules"]):
                raise ApplicationError(
                    "STALE_APPROVAL",
                    "Candidate content must match the independently approved hash",
                    409,
                )
            if row["status"] == "PUBLISHED":
                raise ApplicationError("ALREADY_PUBLISHED", "Candidate is already published", 409)
            manifest = RuleGovernanceService.create_published_release_manifest(
                candidate=dict(row),
                approver_id=row["approver_id"],
                approver_identity=row["approver_identity"],
                published_at=datetime.now(UTC).isoformat(),
            )

            published_release_id = str(uuid.uuid4())
            conn.execute(
                t.published_rule_releases.insert().values(
                    id=published_release_id,
                    release_code=manifest.release_code,
                    candidate_id=candidate_id,
                    numeric_academic_year=manifest.numeric_academic_year,
                    academic_cycle=manifest.academic_cycle,
                    effective_date=manifest.effective_date,
                    submission_date=manifest.submission_date,
                    content_hash=manifest.manifest_hash,
                    manifest_hash=manifest.manifest_hash,
                    release_manifest=manifest.model_dump(),
                    author_id=manifest.author_id,
                    author_identity=manifest.author_identity,
                    approver_id=manifest.approver_id,
                    approver_identity=manifest.approver_identity,
                    status="PUBLISHED",
                    is_active=True,
                    adverse_action_allowed=False,
                )
            )

            # Update candidate status to PUBLISHED
            conn.execute(
                t.rule_candidates.update()
                .where(t.rule_candidates.c.id == candidate_id)
                .values(
                    status=CandidateStatus.PUBLISHED.value,
                    published_release_id=published_release_id,
                )
            )

            return {
                "published_release_id": published_release_id,
                "release_code": manifest.release_code,
                "manifest_hash": manifest.manifest_hash,
                "status": "PUBLISHED",
                "adverse_action_allowed": False,
            }

    @router.get("/rule-governance/amendment-demo")
    def amendment_demo_endpoint(
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        """Seeded hypothetical scenario: international E&T PG seat capacity changes
        from 15% (capacity 9) to 25% (capacity 15) for intake 60, request 12.
        """
        return RuleGovernanceService.get_amendment_demo_fixture()

    @router.post("/applications/{application_id}/remedies")
    def calculate_remedy_endpoint(
        application_id: str,
        body: CalculateRemedyBody,
        actor: Principal = Depends(principal),
    ) -> RemedyProposal:
        with store.transaction(actor) as conn:
            app_row = conn.execute(
                select(t.applications.c.institution_id).where(t.applications.c.id == application_id)
            ).first()
            if not app_row:
                raise NotFoundError("Application")
            institution_id = app_row[0]
            _check_institution_access(
                conn, institution_id, application_id=application_id, write=True
            )

            proposal = RuleGovernanceService.calculate_remedy(
                application_id=application_id,
                finding_id=body.finding_id,
                rule_id=body.rule_id,
                clause=body.clause,
                facts=body.facts,
                is_open_window=body.is_open_window,
            )

            # Persist remedy proposal
            conn.execute(
                t.rule_remedies.insert().values(
                    id=proposal.remedy_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    finding_id=proposal.finding_id,
                    rule_id=proposal.rule_id,
                    clause=proposal.clause,
                    remedy_type=proposal.remedy_type.value,
                    is_advisory=proposal.is_advisory,
                    guarantees_approval=proposal.guarantees_approval,
                    advisory_wording=proposal.advisory_wording,
                    calculation_trace=proposal.calculation_trace,
                    proposed_remedy_facts=proposal.proposed_remedy_facts,
                    re_evaluation_result=proposal.re_evaluation_result,
                    findings_closed=proposal.findings_closed,
                    findings_remaining=proposal.findings_remaining,
                    allowed_at_current_stage=proposal.allowed_at_current_stage,
                    stage_restriction_reason=proposal.stage_restriction_reason,
                    is_simulated=True,
                )
            )

            return proposal

    @router.get("/applications/{application_id}/remedies")
    def list_remedies_endpoint(
        application_id: str,
        actor: Principal = Depends(principal),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            app_row = conn.execute(
                select(t.applications.c.institution_id).where(t.applications.c.id == application_id)
            ).first()
            if not app_row:
                raise NotFoundError("Application")
            institution_id = app_row[0]
            _check_institution_access(
                conn, institution_id, application_id=application_id, write=False
            )

            rows = (
                conn.execute(
                    select(t.rule_remedies).where(
                        t.rule_remedies.c.application_id == application_id
                    )
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows]

    @router.post("/evaluations/{run_id}/export-replay")
    def export_replay_bundle_endpoint(
        run_id: str,
        actor: Principal = Depends(principal),
    ) -> ReplayBundle:
        with store.transaction(actor) as conn:
            run_row = (
                conn.execute(select(t.evaluation_runs).where(t.evaluation_runs.c.id == run_id))
                .mappings()
                .first()
            )
            if not run_row:
                raise NotFoundError("EvaluationRun")

            institution_id = run_row["institution_id"]
            application_id = run_row["application_id"]
            _check_institution_access(
                conn, institution_id, application_id=application_id, write=False
            )

            if not conn.scalar(text(ELEVATED_ROLES_SQL)):
                raise ApplicationError(
                    "ACCESS_DENIED", "Replay exports require elevated reviewer permission", 403
                )
            snapshot = run_row.get("manifest") or {}
            if not all(k in snapshot for k in ("facts", "claims", "rules", "evidence_manifest")):
                raise ApplicationError(
                    "LEGACY_RUN_NOT_REPLAYABLE", "Run lacks frozen executable inputs", 409
                )
            facts = snapshot["facts"]
            ev_manifest = snapshot["evidence_manifest"]
            source_obs = ev_manifest.get("source_observations", [])
            rule_hashes = {r["rule_id"]: r["content_hash"] for r in snapshot["rules"]}
            outcomes = [
                dict(o)
                for o in conn.execute(
                    select(t.requirement_outcomes).where(t.requirement_outcomes.c.run_id == run_id)
                ).mappings()
            ]
            output_keys = (
                "rule_id",
                "outcome",
                "rationale",
                "observed_value",
                "expected_value",
                "calculation_trace",
            )
            expected = [{k: o[k] for k in output_keys} for o in outcomes]
            bundle = RuleGovernanceService.build_replay_bundle(
                run_id=run_id,
                application_id=application_id,
                facts=facts,
                evidence_manifest=ev_manifest,
                source_observations=source_obs,
                rule_hashes=rule_hashes,
                evaluation_snapshot=snapshot,
                expected_outcomes=expected,
            )

            conn.execute(
                t.replay_bundles.insert().values(
                    id=bundle.bundle_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    run_id=run_id,
                    bundle_hash=bundle.bundle_hash,
                    evaluator_version=bundle.evaluator_version,
                    manifest=bundle.manifest,
                    files=bundle.files,
                    disclaimer=bundle.disclaimer,
                )
            )

            return bundle

    @router.get("/replay-bundles/{bundle_id}")
    def get_replay_bundle_endpoint(
        bundle_id: str,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            row = (
                conn.execute(select(t.replay_bundles).where(t.replay_bundles.c.id == bundle_id))
                .mappings()
                .first()
            )
            if not row:
                raise NotFoundError("ReplayBundle")

            institution_id = row["institution_id"]
            application_id = row["application_id"]
            _check_institution_access(
                conn, institution_id, application_id=application_id, write=False
            )

            return dict(row)

    return router
