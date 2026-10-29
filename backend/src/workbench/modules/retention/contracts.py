"""Data contracts for retention policies, legal holds, and purge manifests."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class DataClass(StrEnum):
    ORIGINAL_EVIDENCE = "ORIGINAL_EVIDENCE"
    DERIVATIVES_CACHES = "DERIVATIVES_CACHES"
    REPORTS = "REPORTS"
    AUDIT_CHECKPOINTS = "AUDIT_CHECKPOINTS"
    CERT_IN_SECURITY_LOGS = "CERT_IN_SECURITY_LOGS"


class RetentionBasis(StrEnum):
    STATUTORY = "STATUTORY"
    OPERATIONAL = "OPERATIONAL"
    SECURITY_COMPLIANCE = "SECURITY_COMPLIANCE"


class RetentionPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_class: DataClass
    retention_basis: RetentionBasis
    retention_period_days: int = Field(ge=1, le=36500)
    description: str | None = None


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    data_class: DataClass
    retention_basis: RetentionBasis
    retention_period_days: int
    description: str | None
    approved_by: str
    is_active: bool
    created_at: datetime


class LegalHoldCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution_id: str | None = None
    application_id: str | None = None
    evidence_slot_id: str | None = None
    matter_reference: str = Field(min_length=3, max_length=150)
    legal_basis: str = Field(min_length=5)


class LegalHoldRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_reason: str = Field(min_length=5)


class LegalHoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    institution_id: str | None
    application_id: str | None
    evidence_slot_id: str | None
    matter_reference: str
    legal_basis: str
    placed_by: str
    placed_at: datetime
    is_active: bool
    released_by: str | None
    released_at: datetime | None
    release_reason: str | None


class PurgeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    dry_run: bool = True
    max_items: int = Field(default=100, ge=1, le=1000)


class PurgeCandidate(BaseModel):
    item_id: str
    data_class: DataClass
    created_at: datetime
    age_days: int
    institution_id: str | None = None
    application_id: str | None = None
    evidence_slot_id: str | None = None
    storage_key: str | None = None
    bytes_size: int = 0


class PurgeEligibilityResult(BaseModel):
    policy_id: str
    data_class: DataClass
    retention_period_days: int
    candidate_count: int
    eligible_count: int
    skipped_held_count: int
    skipped_dependency_count: int
    eligible_item_ids: list[str] = Field(default_factory=list)
    held_item_ids: list[str] = Field(default_factory=list)
    dependency_item_ids: list[str] = Field(default_factory=list)
    estimated_bytes_freed: int = 0


class PurgeManifestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: str
    data_class: DataClass
    candidate_count: int
    purged_count: int
    skipped_held_count: int
    skipped_dependency_count: int
    purged_evidence_ids: list[str]
    purged_derivative_keys: list[str]
    bytes_freed: int
    executed_by: str
    executed_at: datetime
    sha256_digest: str
    audit_event_id: str | None


class RetentionPurgeCompletedEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    manifest_id: str
    policy_id: str
    data_class: str
    purged_count: int
    bytes_freed: int
    sha256_digest: str
    timestamp: datetime
    executed_by: str
