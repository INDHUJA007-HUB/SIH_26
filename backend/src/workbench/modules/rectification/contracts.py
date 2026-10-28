"""Phase 9 contracts for response windows, rectification responses, and reassessment diffs."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WindowStatus(StrEnum):
    OPEN = "OPEN"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class FindingDiffClassification(StrEnum):
    RESOLVED = "RESOLVED"
    UNCHANGED = "UNCHANGED"
    NEW = "NEW"
    CHANGED = "CHANGED"
    NO_LONGER_EVALUABLE = "NO_LONGER_EVALUABLE"


class FindingDiffItem(BaseModel):
    finding_key: str
    rule_id: str
    clause: str | None = None
    classification: FindingDiffClassification
    baseline_state: dict[str, Any] | None = None
    reassessed_state: dict[str, Any] | None = None
    rationale: str


class ResponseWindowRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str
    opened_by: str
    authority_reference: str
    round_number: int = 1
    max_rounds: int = 2
    allowed_slots: list[str] = Field(default_factory=list)
    allowed_fields: list[str] = Field(default_factory=list)
    deadline: str
    status: WindowStatus = WindowStatus.OPEN
    current_revision: int
    created_at: str
    closed_at: str | None = None


class RectificationResponseRecord(BaseModel):
    id: str
    window_id: str
    institution_id: str
    application_id: str
    submitted_by: str
    application_revision: int
    response_manifest: dict[str, Any] = Field(default_factory=dict)
    declared_field_updates: dict[str, Any] = Field(default_factory=dict)
    reassessment_run_id: str | None = None
    created_at: str


class ReassessmentDiffRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str
    response_id: str | None = None
    baseline_run_id: str
    reassessment_run_id: str
    diff_summary: dict[str, int] = Field(default_factory=dict)
    finding_diffs: list[FindingDiffItem] = Field(default_factory=list)
    created_at: str
