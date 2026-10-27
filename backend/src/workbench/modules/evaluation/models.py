"""Domain models for deterministic rule evaluation, orthogonal dimensions, and findings."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CompletenessStatus(StrEnum):
    COMPLETE = "COMPLETE"
    MISSING = "MISSING"
    INCOMPLETE = "INCOMPLETE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SourceVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    MISMATCH_DETECTED = "MISMATCH_DETECTED"
    EXPIRED = "EXPIRED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class ForensicConcernStatus(StrEnum):
    NONE_OBSERVED = "NONE_OBSERVED"
    FLAGGED = "FLAGGED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REVIEWED_BENIGN = "REVIEWED_BENIGN"
    REVIEWED_ESCALATE = "REVIEWED_ESCALATE"


class DocumentValidityStatus(StrEnum):
    VALID_ON_REVIEW_DATE = "VALID_ON_REVIEW_DATE"
    EXPIRED_ON_REVIEW_DATE = "EXPIRED_ON_REVIEW_DATE"
    UNKNOWN = "UNKNOWN"


class ComplianceOutcome(StrEnum):
    PASS = "PASS"  # noqa: S105
    POTENTIAL_DEFICIENCY = "POTENTIAL_DEFICIENCY"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CaseWorkflowStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    SCREENED = "SCREENED"
    OFFICER_REVIEW = "OFFICER_REVIEW"
    AWAITING_RESPONSE = "AWAITING_RESPONSE"
    RESPONSE_SUBMITTED = "RESPONSE_SUBMITTED"
    REASSESSMENT = "REASSESSMENT"
    READY_FOR_AUTHORITY = "READY_FOR_AUTHORITY"
    CLOSED = "CLOSED"


class FindingSeverity(StrEnum):
    DEFICIENCY = "DEFICIENCY"
    LIMITATION = "LIMITATION"
    INFO = "INFO"


class FindingStatus(StrEnum):
    OPEN = "OPEN"
    ACCEPTED_FOR_REVIEW = "ACCEPTED_FOR_REVIEW"
    RECTIFIED = "RECTIFIED"
    DISMISSED = "DISMISSED"


class RequirementOutcome(BaseModel):
    id: str | None = None
    rule_id: str
    requirement_name: str
    outcome: ComplianceOutcome
    rationale: str
    observed_value: dict[str, Any] | None = None
    expected_value: dict[str, Any] | None = None
    calculation_trace: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    id: str
    rule_id: str
    semantic_key: str
    dimension: str = "COMPLIANCE"
    severity: FindingSeverity = FindingSeverity.DEFICIENCY
    status: FindingStatus = FindingStatus.OPEN
    title: str
    description: str
    officer_explanation: str | None = None
    applicant_explanation: str | None = None
    calculation_trace: dict[str, Any] = Field(default_factory=dict)
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    contradicting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    unknown_reason: str | None = None
    adverse_action_allowed: bool = False  # strictly invariant


class EvaluationRunResult(BaseModel):
    run_id: str
    institution_id: str
    application_id: str
    application_revision_id: str | None = None
    rule_release_id: str | None = None
    fact_set_id: str | None = None
    manifest_hash: str
    evaluation_as_of: str
    execution_mode: str = "DEMONSTRATION"
    completeness_status: CompletenessStatus = CompletenessStatus.COMPLETE
    compliance_status: ComplianceOutcome = ComplianceOutcome.PASS
    source_verification_status: SourceVerificationStatus = (
        SourceVerificationStatus.VERIFICATION_PENDING
    )
    forensic_concern_status: ForensicConcernStatus = ForensicConcernStatus.NONE_OBSERVED
    document_validity_status: DocumentValidityStatus = DocumentValidityStatus.VALID_ON_REVIEW_DATE
    case_workflow_status: CaseWorkflowStatus = CaseWorkflowStatus.SCREENED
    adverse_action_allowed: bool = False  # strictly invariant
    outcomes: list[RequirementOutcome] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    manifest: dict[str, Any] = Field(default_factory=dict)
