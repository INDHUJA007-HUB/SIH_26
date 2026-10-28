"""Phase 9 contracts for validation reports, audience separation, and disclosure policy."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ReportAudience(StrEnum):
    OFFICER = "OFFICER"
    APPLICANT = "APPLICANT"


class ReportStatus(StrEnum):
    FINAL = "FINAL"
    DRAFT = "DRAFT"


class DisclosurePolicy(BaseModel):
    audience: ReportAudience
    include_forensic_signals: bool = False
    include_internal_stacktraces: bool = False
    include_investigator_identities: bool = False
    include_remediation_instructions: bool = True
    simulated_results_labeled: bool = True


class ValidationReportRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str
    evaluation_run_id: str
    audience: ReportAudience
    version: int = 1
    report_hash: str
    status: ReportStatus = ReportStatus.FINAL
    summary: dict[str, Any] = Field(default_factory=dict)
    content: dict[str, Any] = Field(default_factory=dict)
    disclosure_policy: dict[str, Any] = Field(default_factory=dict)
    created_at: str
