"""Adapter for persisting and retrieving deterministic evaluation runs, outcomes, and findings."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Connection, Engine, select

from workbench.adapters import tables as t
from workbench.adapters.rule_registry_service import RuleRegistryService
from workbench.modules.evaluation.evaluator import DeterministicEvaluator
from workbench.platform.errors import ApplicationError, NotFoundError


class EvaluationService:
    """Orchestrates deterministic rule evaluations over frozen facts and persists findings."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.evaluator = DeterministicEvaluator()
        self.rule_service = RuleRegistryService(engine)

    def run_evaluation(
        self,
        institution_id: str,
        application_id: str,
        evaluation_as_of: str = "2026-10-26",
        execution_mode: str = "DEMONSTRATION",
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Execute deterministic evaluation for an application and store the run,
        outcomes, and findings.
        """
        if conn is not None:
            return self._run_evaluation_conn(
                conn, institution_id, application_id, evaluation_as_of, execution_mode
            )
        with self.engine.begin() as connection:
            return self._run_evaluation_conn(
                connection, institution_id, application_id, evaluation_as_of, execution_mode
            )

    def _run_evaluation_conn(
        self,
        conn: Connection,
        institution_id: str,
        application_id: str,
        evaluation_as_of: str,
        execution_mode: str,
    ) -> dict[str, Any]:
        # 1. Fetch active rule release and its member rules
        release, rules = self.rule_service.get_active_release(conn, as_of_date=evaluation_as_of)
        app = (
            conn.execute(
                select(t.applications)
                .where(
                    t.applications.c.id == application_id,
                    t.applications.c.institution_id == institution_id,
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if not app:
            raise NotFoundError("Application not found")
        revision = (
            conn.execute(
                select(t.revisions).where(
                    t.revisions.c.application_id == application_id,
                    t.revisions.c.revision == app["revision"],
                )
            )
            .mappings()
            .first()
        )
        if not revision:
            raise ApplicationError("REVISION_REQUIRED", "Frozen revision required", 409)
        frozen_evidence = revision["manifest"].get("evidence", [])
        evidence_ids = [e["id"] for e in frozen_evidence]

        # 2. Fetch latest frozen fact-set for application
        fact_set_row = (
            conn.execute(
                select(t.fact_sets)
                .where(
                    t.fact_sets.c.application_id == application_id,
                    t.fact_sets.c.is_frozen.is_(True),
                )
                .order_by(t.fact_sets.c.version.desc())
            )
            .mappings()
            .first()
        )

        facts: dict[str, Any] = {}
        fact_set_id: str | None = None
        fact_set_hash: str | None = None

        if fact_set_row:
            fact_set_id = fact_set_row["id"]
            fact_set_hash = fact_set_row["canonical_hash"]
            members = (
                conn.execute(
                    select(t.fact_set_members).where(
                        t.fact_set_members.c.fact_set_id == fact_set_id
                    )
                )
                .mappings()
                .all()
            )
            for m in members:
                norm = m["normalized_value"]
                if isinstance(norm, dict) and "canonical_value" in norm:
                    facts[m["field_name"]] = norm["canonical_value"]
                elif isinstance(norm, dict) and "value" in norm:
                    facts[m["field_name"]] = norm["value"]
                else:
                    facts[m["field_name"]] = norm

        # 3. Fetch declared claims for application
        claims_rows = (
            conn.execute(select(t.claims).where(t.claims.c.application_id == application_id))
            .mappings()
            .all()
        )

        claims: dict[str, Any] = dict(revision["manifest"].get("declared_facts", {}))
        for c in claims_rows:
            pred = c["predicate"]
            val = c["declared_value"]
            claims.setdefault(pred, val)
            claims.setdefault(f"{c['subject']}.{pred}", val)

        # 4. Check for missing evidence slots
        slots_rows = (
            conn.execute(select(t.slots).where(t.slots.c.application_id == application_id))
            .mappings()
            .all()
        )
        evidence_slots_filled = set(
            conn.execute(
                select(t.evidence.c.slot_id).where(
                    t.evidence.c.application_id == application_id,
                    t.evidence.c.status == "ACCEPTED",
                    t.evidence.c.id.in_(evidence_ids),
                )
            )
            .scalars()
            .all()
        )
        missing_slots: list[str] = []
        for s in slots_rows:
            if s.get("required", True) and s["id"] not in evidence_slots_filled:
                missing_slots.append(s["code"])

        evidence_manifest = {
            "application_id": application_id,
            "missing_slots": missing_slots,
            "evidence": frozen_evidence,
        }
        observations = [
            dict(o)
            for o in conn.execute(
                select(t.source_observations).where(
                    t.source_observations.c.institution_id == institution_id,
                    t.source_observations.c.evidence_version_id.in_(evidence_ids),
                )
            ).mappings()
        ]
        evidence_manifest["source_observations"] = [
            {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in o.items()}
            for o in observations
        ]

        # 5. Fetch application revision if exists
        app_rev = (
            conn.execute(
                select(t.revisions)
                .where(t.revisions.c.application_id == application_id)
                .order_by(t.revisions.c.revision.desc())
            )
            .mappings()
            .first()
        )
        app_rev_id = app_rev["id"] if app_rev else None

        # 6. Run pure deterministic evaluator
        eval_result = self.evaluator.evaluate(
            institution_id=institution_id,
            application_id=application_id,
            application_revision_id=app_rev_id,
            fact_set_id=fact_set_id,
            fact_set_hash=fact_set_hash,
            facts=facts,
            claims=claims,
            rule_release_id=release.id,
            rule_release_hash=release.content_hash,
            rules=rules,
            evaluation_as_of=evaluation_as_of,
            execution_mode=execution_mode,
            evidence_manifest=evidence_manifest,
        )

        # 7. Persist evaluation run
        conn.execute(
            t.evaluation_runs.insert().values(
                id=eval_result.run_id,
                institution_id=institution_id,
                application_id=application_id,
                application_revision_id=app_rev_id,
                rule_release_id=release.id,
                fact_set_id=fact_set_id,
                manifest_hash=eval_result.manifest_hash,
                evaluation_as_of=evaluation_as_of,
                execution_mode=execution_mode,
                completeness_status=eval_result.completeness_status.value,
                compliance_status=eval_result.compliance_status.value,
                source_verification_status=eval_result.source_verification_status.value,
                forensic_concern_status=eval_result.forensic_concern_status.value,
                document_validity_status=eval_result.document_validity_status.value,
                case_workflow_status=eval_result.case_workflow_status.value,
                adverse_action_allowed=False,
                manifest=eval_result.manifest,
            )
        )

        # 8. Record run inputs
        if fact_set_id and fact_set_hash:
            conn.execute(
                t.run_inputs.insert().values(
                    id=str(uuid.uuid4()),
                    run_id=eval_result.run_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    input_type="FACT_SET",
                    input_id=fact_set_id,
                    content_hash=fact_set_hash,
                )
            )
        for ev in frozen_evidence:
            conn.execute(
                t.run_inputs.insert().values(
                    id=str(uuid.uuid4()),
                    run_id=eval_result.run_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    input_type="EVIDENCE",
                    input_id=ev["id"],
                    content_hash=ev["sha256"],
                )
            )

        # 9. Record requirement outcomes
        for out in eval_result.outcomes:
            out_id = out.id or str(uuid.uuid4())
            conn.execute(
                t.requirement_outcomes.insert().values(
                    id=out_id,
                    run_id=eval_result.run_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    rule_id=out.rule_id,
                    requirement_name=out.requirement_name,
                    outcome=out.outcome.value,
                    rationale=out.rationale,
                    observed_value=out.observed_value,
                    expected_value=out.expected_value,
                    calculation_trace=out.calculation_trace,
                )
            )

        # 10. Record findings
        for f in eval_result.findings:
            conn.execute(
                t.findings.insert().values(
                    id=f.id,
                    run_id=eval_result.run_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    rule_id=f.rule_id,
                    semantic_key=f.semantic_key,
                    dimension=f.dimension,
                    severity=f.severity.value,
                    status=f.status.value,
                    title=f.title,
                    description=f.description,
                    officer_explanation=f.officer_explanation,
                    applicant_explanation=f.applicant_explanation,
                    calculation_trace=f.calculation_trace,
                    supporting_evidence=f.supporting_evidence,
                    contradicting_evidence=f.contradicting_evidence,
                    unknown_reason=f.unknown_reason,
                    adverse_action_allowed=False,
                )
            )

        return eval_result.model_dump()

    def get_evaluation(self, run_id: str, conn: Connection | None = None) -> dict[str, Any]:
        """Retrieve evaluation run record by ID."""
        if conn is not None:
            return self._get_evaluation_conn(conn, run_id)
        with self.engine.begin() as connection:
            return self._get_evaluation_conn(connection, run_id)

    def _get_evaluation_conn(self, conn: Connection, run_id: str) -> dict[str, Any]:
        row = (
            conn.execute(select(t.evaluation_runs).where(t.evaluation_runs.c.id == run_id))
            .mappings()
            .first()
        )
        if not row:
            raise NotFoundError(f"Evaluation run {run_id} not found")
        return dict(row)

    def get_findings_for_run(
        self, run_id: str, conn: Connection | None = None
    ) -> list[dict[str, Any]]:
        """List all findings for an evaluation run."""
        if conn is not None:
            return self._get_findings_conn(conn, run_id)
        with self.engine.begin() as connection:
            return self._get_findings_conn(connection, run_id)

    def _get_findings_conn(self, conn: Connection, run_id: str) -> list[dict[str, Any]]:
        rows = (
            conn.execute(
                select(t.findings)
                .where(t.findings.c.run_id == run_id)
                .order_by(t.findings.c.created_at.asc())
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def get_finding_evidence(
        self, finding_id: str, conn: Connection | None = None
    ) -> dict[str, Any]:
        """Fetch finding details and any linked evidence references."""
        if conn is not None:
            return self._get_finding_evidence_conn(conn, finding_id)
        with self.engine.begin() as connection:
            return self._get_finding_evidence_conn(connection, finding_id)

    def _get_finding_evidence_conn(self, conn: Connection, finding_id: str) -> dict[str, Any]:
        finding_row = (
            conn.execute(select(t.findings).where(t.findings.c.id == finding_id)).mappings().first()
        )
        if not finding_row:
            raise NotFoundError(f"Finding {finding_id} not found")

        res = dict(finding_row)
        return {
            "finding_id": finding_id,
            "rule_id": res["rule_id"],
            "semantic_key": res["semantic_key"],
            "title": res["title"],
            "calculation_trace": res["calculation_trace"],
            "supporting_evidence": res["supporting_evidence"] or [],
            "contradicting_evidence": res["contradicting_evidence"] or [],
            "unknown_reason": res["unknown_reason"],
            "adverse_action_allowed": res["adverse_action_allowed"],
        }
