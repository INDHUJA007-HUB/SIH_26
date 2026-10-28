"""Contracts for audit events, access history, and checkpointed exports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AccessAction(StrEnum):
    VIEW = "VIEW"
    DOWNLOAD = "DOWNLOAD"
    UPLOAD = "UPLOAD"
    EXPORT = "EXPORT"


class AccessResult(StrEnum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    ABORTED = "ABORTED"


class StreamOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    INTERRUPTED = "INTERRUPTED"
    FAILED = "FAILED"


class AuditEventRecord(BaseModel):
    id: str
    stream: str
    institution_id: str | None = None
    application_id: str | None = None
    sequence: int
    previous_hash: str
    sha256: str
    event: dict[str, Any]
    created_at: datetime


class AccessEventRecord(BaseModel):
    id: str
    actor_id: str | None = None
    institution_id: str | None = None
    application_id: str | None = None
    evidence_id: str | None = None
    resource_id: str
    action: str
    result: str
    bytes_served: int
    request_id: str
    parent_event_id: str | None = None
    created_at: datetime


class AuditExportManifest(BaseModel):
    checkpoint_id: str
    institution_id: str
    application_id: str | None = None
    auditor_id: str
    stream: str
    start_sequence: int
    end_sequence: int
    event_count: int
    checkpoint_hash: str
    archive_lag_seconds: float
    integrity_status: str
    exported_at: datetime
    events: list[dict[str, Any]] = Field(default_factory=list)


class CheckpointRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str | None = None
    auditor_id: str
    stream: str
    start_sequence: int
    end_sequence: int
    event_count: int
    checkpoint_hash: str
    archive_lag_seconds: float
    integrity_status: str
    manifest: dict[str, Any]
    created_at: datetime
