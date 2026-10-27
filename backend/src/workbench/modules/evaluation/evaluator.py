"""Pure deterministic evaluation engine executing rules against frozen facts
and evidence manifests.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from workbench.modules.evaluation.dsl import RuleEvaluatorDSL
from workbench.modules.evaluation.models import (
    CaseWorkflowStatus,
    CompletenessStatus,
    ComplianceOutcome,
    DocumentValidityStatus,
    EvaluationRunResult,
    Finding,
    FindingSeverity,
    FindingStatus,
    ForensicConcernStatus,
    RequirementOutcome,
    SourceVerificationStatus,
)
from workbench.modules.rule_registry.models import RuleVersionRecord


def compute_manifest_hash(manifest: dict[str, Any]) -> str:
    """Compute SHA-256 over canonical JSON of the evaluation run manifest."""
    canonical_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


class DeterministicEvaluator:
    """Evaluates rules over frozen application facts, claims, and evidence manifests.
    Enforces orthogonal status dimensions, pure Python execution, and adverse_action_allowed=False.
    """

    def __init__(self) -> None:
        self.dsl_evaluator = RuleEvaluatorDSL()

    def evaluate(
        self,
        institution_id: str,
        application_id: str,
        application_revision_id: str | None,
        fact_set_id: str | None,
        fact_set_hash: str | None,
        facts: dict[str, Any],
        claims: dict[str, Any],
        rule_release_id: str | None,
        rule_release_hash: str | None,
        rules: list[RuleVersionRecord],
        evaluation_as_of: str = "2026-10-26",
        execution_mode: str = "DEMONSTRATION",
        evidence_manifest: dict[str, Any] | None = None,
    ) -> EvaluationRunResult:
        """Run pure evaluation over frozen facts and generate orthogonal results and findings."""
        run_id = str(uuid.uuid4())
        outcomes: list[RequirementOutcome] = []
        findings: list[Finding] = []

        overall_validity = DocumentValidityStatus.VALID_ON_REVIEW_DATE
        overall_compliance = ComplianceOutcome.PASS
        completeness = CompletenessStatus.COMPLETE

        # Check evidence completeness if manifest provided
        ev_manifest = evidence_manifest or {}
        missing_slots = ev_manifest.get("missing_slots", [])
        if missing_slots:
            completeness = CompletenessStatus.MISSING
            for slot in missing_slots:
                finding_id = str(uuid.uuid4())
                findings.append(
                    Finding(
                        id=finding_id,
                        rule_id="COMPLETENESS.SLOT",
                        semantic_key=f"completeness:slot:{slot}",
                        dimension="COMPLETENESS",
                        severity=FindingSeverity.DEFICIENCY,
                        status=FindingStatus.OPEN,
                        title=f"Missing Required Document: {slot}",
                        description=f"Required evidence slot {slot} has not been provided.",
                        officer_explanation=(
                            f"Applicant has not uploaded mandatory evidence for slot {slot}."
                        ),
                        applicant_explanation=(
                            f"Please provide the required document for slot {slot}."
                        ),
                        adverse_action_allowed=False,
                    )
                )

        # Evaluate all applicable rules
        for r_ver in rules:
            rule_id = r_ver.rule_id
            dsl_expr = r_ver.dsl_expression or {}
            params = r_ver.parameters or {}

            outcome, doc_validity = self.dsl_evaluator.evaluate_rule(
                rule_id=rule_id,
                dsl_expression=dsl_expr,
                facts=facts,
                claims=claims,
                evaluation_as_of=evaluation_as_of,
                rule_parameters=params,
            )
            outcome.id = str(uuid.uuid4())
            outcomes.append(outcome)

            # Update orthogonal dimensions for document validity requirements
            if (
                dsl_expr.get("dimension") == "DOCUMENT_VALIDITY"
                or dsl_expr.get("operation") == "date_validity_check"
            ):
                if doc_validity == DocumentValidityStatus.EXPIRED_ON_REVIEW_DATE:
                    overall_validity = DocumentValidityStatus.EXPIRED_ON_REVIEW_DATE
                elif (
                    doc_validity == DocumentValidityStatus.UNKNOWN
                    and overall_validity != DocumentValidityStatus.EXPIRED_ON_REVIEW_DATE
                ):
                    overall_validity = DocumentValidityStatus.UNKNOWN

            if outcome.outcome == ComplianceOutcome.POTENTIAL_DEFICIENCY:
                overall_compliance = ComplianceOutcome.POTENTIAL_DEFICIENCY

                # Generate a preliminary machine finding (never adverse action)
                finding_id = str(uuid.uuid4())
                semantic_key = f"requirement:{rule_id}:2024"
                dimension = dsl_expr.get("dimension", "COMPLIANCE")

                findings.append(
                    Finding(
                        id=finding_id,
                        rule_id=rule_id,
                        semantic_key=semantic_key,
                        dimension=dimension,
                        severity=FindingSeverity.DEFICIENCY,
                        status=FindingStatus.OPEN,
                        title=f"Potential Deficiency: {outcome.requirement_name}",
                        description=outcome.rationale,
                        officer_explanation=(
                            f"Deterministic evaluation for rule {rule_id} observed "
                            f"non-compliance: {outcome.rationale}. Source locator: "
                            f"printed page {r_ver.printed_page}, clause {r_ver.clause}."
                        ),
                        applicant_explanation=(
                            f"Requirement {outcome.requirement_name} indicates an issue: "
                            f"{outcome.rationale}. Please verify your submitted documentation."
                        ),
                        calculation_trace=outcome.calculation_trace,
                        adverse_action_allowed=False,  # strictly invariant
                    )
                )
            elif outcome.outcome == ComplianceOutcome.NOT_EVALUABLE:
                if overall_compliance == ComplianceOutcome.PASS:
                    overall_compliance = ComplianceOutcome.NOT_EVALUABLE

                # For unresolved rules, produce an informative limitation finding
                finding_id = str(uuid.uuid4())
                semantic_key = f"limitation:{rule_id}:2024"
                findings.append(
                    Finding(
                        id=finding_id,
                        rule_id=rule_id,
                        semantic_key=semantic_key,
                        dimension="COMPLIANCE",
                        severity=FindingSeverity.LIMITATION,
                        status=FindingStatus.OPEN,
                        title=f"Rule Abstention: {rule_id}",
                        description=outcome.rationale,
                        officer_explanation=(
                            f"Rule {rule_id} was not evaluable: {outcome.rationale}. "
                            "Human review required."
                        ),
                        applicant_explanation=(
                            f"Requirement {rule_id} is pending regulatory interpretation."
                        ),
                        unknown_reason=outcome.rationale,
                        calculation_trace=outcome.calculation_trace,
                        adverse_action_allowed=False,
                    )
                )

        manifest = {
            "schema_version": "1.0",
            "run_id": run_id,
            "institution_id": institution_id,
            "application_id": application_id,
            "application_revision_id": application_revision_id,
            "fact_set_id": fact_set_id,
            "fact_set_sha256": fact_set_hash,
            "rule_release_id": rule_release_id,
            "rule_release_sha256": rule_release_hash,
            "evaluation_as_of": evaluation_as_of,
            "execution_mode": execution_mode,
            "contains_simulated_sources": True,
            "canonicalization_version": "jcs-and-project-types-v1",
        }
        manifest_hash = compute_manifest_hash(manifest)

        return EvaluationRunResult(
            run_id=run_id,
            institution_id=institution_id,
            application_id=application_id,
            application_revision_id=application_revision_id,
            rule_release_id=rule_release_id,
            fact_set_id=fact_set_id,
            manifest_hash=manifest_hash,
            evaluation_as_of=evaluation_as_of,
            execution_mode=execution_mode,
            completeness_status=completeness,
            compliance_status=overall_compliance,
            source_verification_status=SourceVerificationStatus.VERIFICATION_PENDING,
            forensic_concern_status=ForensicConcernStatus.NONE_OBSERVED,
            document_validity_status=overall_validity,
            case_workflow_status=CaseWorkflowStatus.SCREENED,
            adverse_action_allowed=False,
            outcomes=outcomes,
            findings=findings,
            manifest=manifest,
        )
