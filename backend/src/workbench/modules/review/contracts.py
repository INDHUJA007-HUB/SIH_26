"""Phase 9 contracts for officer review, finding dispositions, and pending tasks."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ReviewDispositionType(StrEnum):
    CONFIRMED = "CONFIRMED"
    OVERRIDDEN = "OVERRIDDEN"
    RECTIFICATION_REQUESTED = "RECTIFICATION_REQUESTED"
    EXEMPTED = "EXEMPTED"
    NOTED = "NOTED"


class WaitingOn(StrEnum):
    OFFICER = "OFFICER"
    APPLICANT = "APPLICANT"
    SOURCE = "SOURCE"
    INTERPRETATION = "INTERPRETATION"


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class ReviewDispositionRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str
    finding_id: str
    evaluation_run_id: str
    officer_id: str
    disposition: ReviewDispositionType
    rationale: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class ReviewTaskRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str
    task_type: str
    waiting_on: WaitingOn
    status: TaskStatus
    assigned_to: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    deadline: str | None = None
    created_at: str
    resolved_at: str | None = None
