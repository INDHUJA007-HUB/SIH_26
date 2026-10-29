"""Contracts for operations health, containment, reconciliation, drift, access."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"


class ContainmentTargetType(StrEnum):
    ACTOR = "ACTOR"
    PROVIDER = "PROVIDER"
    WORKFLOW_JOB = "WORKFLOW_JOB"


class ContainmentAction(StrEnum):
    REVOKE_SESSION = "REVOKE_SESSION"
    TRIP_CIRCUIT = "TRIP_CIRCUIT"
    QUARANTINE_JOB = "QUARANTINE_JOB"


class ReconciliationTarget(StrEnum):
    OUTBOX = "OUTBOX"
    WORKFLOWS = "WORKFLOWS"
    STORAGE = "STORAGE"


# --- Health & SLO ---


class QueueAgeHealth(BaseModel):
    scan_queue_age_sec: float = 0.0
    document_queue_age_sec: float = 0.0
    media_queue_age_sec: float = 0.0
    extraction_queue_age_sec: float = 0.0
    evaluation_queue_age_sec: float = 0.0
    report_queue_age_sec: float = 0.0
    status: HealthStatus = HealthStatus.HEALTHY


class ExtractionFailureRate(BaseModel):
    window_minutes: int = 60
    total_runs: int = 0
    failed_runs: int = 0
    failure_rate_pct: float = 0.0
    status: HealthStatus = HealthStatus.HEALTHY


class SourceCoverageHealth(BaseModel):
    total_claims: int = 0
    verified_claims: int = 0
    coverage_pct: float = 100.0
    unavailable_providers: list[str] = Field(default_factory=list)
    degraded_providers: list[str] = Field(default_factory=list)
    status: HealthStatus = HealthStatus.HEALTHY


class AuditCheckpointLag(BaseModel):
    head_sequence: int = 0
    last_checkpoint_sequence: int = 0
    lag_events: int = 0
    lag_seconds: float = 0.0
    status: HealthStatus = HealthStatus.HEALTHY


class OperationalHealthSummary(BaseModel):
    overall_status: HealthStatus = HealthStatus.HEALTHY
    api_availability_pct: float = 99.95
    p95_latency_ms: float = 120.0
    queue_health: QueueAgeHealth = Field(default_factory=QueueAgeHealth)
    extraction_health: ExtractionFailureRate = Field(default_factory=ExtractionFailureRate)
    source_health: SourceCoverageHealth = Field(default_factory=SourceCoverageHealth)
    audit_health: AuditCheckpointLag = Field(default_factory=AuditCheckpointLag)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- Incident Containment ---


class IncidentContainmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str | None = None
    target_type: ContainmentTargetType
    target_id: str = Field(min_length=1, max_length=100)
    containment_action: ContainmentAction
    reason: str = Field(min_length=5, max_length=500)


class IncidentContainmentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    target_type: ContainmentTargetType
    target_id: str
    containment_action: ContainmentAction
    reason: str
    contained_by: str
    contained_at: datetime
    active: bool
    released_by: str | None = None
    released_at: datetime | None = None
    audit_event_id: str | None = None


class ReleaseContainmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_reason: str = Field(min_length=5, max_length=500)


# --- Reconciliation ---


class ReconciliationCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: ReconciliationTarget
    dry_run: bool = True
    batch_size: int = Field(default=50, ge=1, le=500)


class ReconciliationItem(BaseModel):
    item_type: str
    item_id: str
    action_taken: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class ReconciliationSummary(BaseModel):
    target: ReconciliationTarget
    dry_run: bool
    scanned_count: int
    reconciled_count: int
    items: list[ReconciliationItem] = Field(default_factory=list)
    executed_at: datetime = Field(default_factory=datetime.utcnow)


# --- Drift Analysis (Phase 15.2) ---


class FieldDriftMetric(BaseModel):
    field_name: str
    ground_truth_matches: int
    champion_matches: int
    challenger_matches: int
    agreement_rate: float
    confidence_delta: float
    drift_detected: bool


class DriftEvaluationResult(BaseModel):
    candidate_version: str
    champion_version: str
    benchmark_packet_count: int
    evaluated_field_count: int
    champion_precision: float
    challenger_precision: float
    champion_recall: float
    challenger_recall: float
    macro_f1_delta: float
    template_drift_detected: bool
    field_metrics: list[FieldDriftMetric] = Field(default_factory=list)
    summary: str
    immutable_historical_data_preserved: bool = True
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


# --- Access Assurance (Phase 15.4) ---


class AccessSweepResult(BaseModel):
    scanned_memberships: int = 0
    expired_memberships_revoked: int = 0
    scanned_case_assignments: int = 0
    expired_assignments_revoked: int = 0
    swept_at: datetime = Field(default_factory=datetime.utcnow)


class AccessReviewSummary(BaseModel):
    total_active_memberships: int
    total_active_assignments: int
    expiring_in_30_days: int
    orphaned_assignments: int
    last_sweep_at: datetime | None = None
