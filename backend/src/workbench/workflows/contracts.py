"""Phase 5 workflow and task-queue contracts with reference-only payloads."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskQueue(StrEnum):
    COORDINATION = "workflow-coordination"
    SCAN = "evidence-scan"
    DOCUMENT = "document-processing"
    CONNECTOR = "source-connectors"
    EVALUATION = "rule-evaluation"
    MEDIA = "media-analysis"
    REPORTING = "reporting"
    RETENTION = "retention-ops"


class OperationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REQUIRES_OPERATOR = "REQUIRES_OPERATOR"


class OperationType(StrEnum):
    EVIDENCE_SCREENING = "EVIDENCE_SCREENING"
    DOCUMENT_EXTRACTION = "DOCUMENT_EXTRACTION"
    SOURCE_VERIFICATION = "SOURCE_VERIFICATION"
    RULE_EVALUATION = "RULE_EVALUATION"
    REPORT_GENERATION = "REPORT_GENERATION"
    RESPONSE_WINDOW_TIMER = "RESPONSE_WINDOW_TIMER"
    RETENTION_PURGE = "RETENTION_PURGE"
    MEDIA_ANALYSIS = "MEDIA_ANALYSIS"


# Reference-only input contracts
@dataclass(frozen=True)
class ScreeningInput:
    evidence_id: str
    institution_id: str
    application_id: str
    profile: str = "default-inspection-v1"
    clean_key: str | None = None
    clean_version: str | None = None
    sha256: str | None = None

    @property
    def stable_key(self) -> str:
        return f"{self.evidence_id}:{self.profile}"


@dataclass(frozen=True)
class ExtractionInput:
    evidence_id: str
    institution_id: str
    application_id: str
    document_type: str
    version_id: str
    page_range: str = "1-end"

    @property
    def stable_key(self) -> str:
        return f"{self.evidence_id}:{self.version_id}:{self.document_type}"


@dataclass(frozen=True)
class VerificationInput:
    claim_id: str
    evidence_id: str
    institution_id: str
    provider_id: str
    request_fingerprint: str
    freshness_generation: int = 1

    @property
    def stable_key(self) -> str:
        return (
            f"{self.claim_id}:{self.provider_id}:"
            f"{self.request_fingerprint}:{self.freshness_generation}"
        )


@dataclass(frozen=True)
class EvaluationInput:
    application_id: str
    institution_id: str
    manifest_hash: str
    evaluator_digest: str
    rule_release_id: str
    execution_mode: str = "deterministic"

    @property
    def stable_key(self) -> str:
        return f"{self.manifest_hash}:{self.evaluator_digest}:{self.rule_release_id}"


@dataclass(frozen=True)
class ReportInput:
    application_id: str
    institution_id: str
    run_id: str
    template_version: str
    audience_policy: str  # "OFFICER" or "APPLICANT"
    report_variant: str = "summary"

    @property
    def stable_key(self) -> str:
        return f"{self.run_id}:{self.audience_policy}:{self.template_version}:{self.report_variant}"


@dataclass(frozen=True)
class ResponseWindowTimerInput:
    window_id: str
    application_id: str
    institution_id: str
    deadline_iso: str
    timer_generation: int = 1

    @property
    def stable_key(self) -> str:
        return f"{self.window_id}:{self.timer_generation}"


@dataclass(frozen=True)
class RetentionPurgeInput:
    manifest_id: str
    policy_version: str
    approved_by: str

    @property
    def stable_key(self) -> str:
        return f"{self.manifest_id}:{self.policy_version}"


@dataclass(frozen=True)
class MediaAnalysisInput:
    evidence_id: str
    institution_id: str
    application_id: str
    video_role: str = "EVC_WALKTHROUGH"
    max_frames: int = 180

    @property
    def stable_key(self) -> str:
        return f"{self.evidence_id}:{self.video_role}:{self.max_frames}"


@dataclass(frozen=True)
class ActivityResult:
    status: str
    stable_key: str
    output: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    is_retryable: bool = False
