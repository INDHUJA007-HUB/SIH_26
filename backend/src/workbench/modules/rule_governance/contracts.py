"""Domain contracts and data models for Phase 12 rule governance, replay, dual control,
and remedy scenarios.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CandidateStatus(StrEnum):
    DRAFT = "DRAFT"
    SOURCE_CHECKED = "SOURCE_CHECKED"
    INTERPRETATION_PENDING = "INTERPRETATION_PENDING"
    TESTED = "TESTED"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class DiffOutcome(StrEnum):
    UNCHANGED = "UNCHANGED"
    NEWLY_DEFICIENT = "NEWLY_DEFICIENT"
    NEWLY_CLEAR = "NEWLY_CLEAR"
    NEWLY_NOT_EVALUABLE = "NEWLY_NOT_EVALUABLE"


class RemedyType(StrEnum):
    MISSING_CERTIFICATE = "MISSING_CERTIFICATE"
    BANDWIDTH_TIER = "BANDWIDTH_TIER"
    PRINTER_SHORTFALL = "PRINTER_SHORTFALL"
    INTAKE_REDUCTION_AUTHORIZED = "INTAKE_REDUCTION_AUTHORIZED"


class FourGates(BaseModel):
    """The four required qualification gates before a candidate rule release can be published."""

    source_text_checked: bool = False
    scope_and_ambiguity_resolved: bool = False
    software_behaviour_tested: bool = False
    authorized_policy_approved: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

    @property
    def all_passed(self) -> bool:
        return (
            self.source_text_checked
            and self.scope_and_ambiguity_resolved
            and self.software_behaviour_tested
            and self.authorized_policy_approved
        )


class CandidateRuleChange(BaseModel):
    rule_id: str
    change_type: str = "MODIFY"  # ADD, MODIFY, RETIRE
    clause: str
    base_version: int | None = None
    proposed_parameters: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    dsl_expression: dict[str, Any] = Field(default_factory=dict)
    scope: str = "GLOBAL"
    rationale: str = ""


class ReleaseManifest(BaseModel):
    release_code: str
    academic_cycle: str
    numeric_academic_year: int
    effective_date: str
    submission_date: str
    evaluation_time: str
    author_id: str
    author_identity: str
    approver_id: str
    approver_identity: str
    member_rule_hashes: dict[str, str] = Field(default_factory=dict)
    manifest_hash: str
    published_at: str
    disclaimer: str = "Reproducing the evaluator does not reproduce a fresh OCR run."


class RunDiff(BaseModel):
    run_id: str
    application_id: str
    requirement_diffs: dict[str, DiffOutcome] = Field(default_factory=dict)
    diff_summary: dict[str, int] = Field(default_factory=dict)


class SimulationResult(BaseModel):
    candidate_id: str
    what_if_banner: bool = True
    total_runs_simulated: int
    diff_summary: dict[str, int] = Field(default_factory=dict)
    run_diffs: list[RunDiff] = Field(default_factory=list)
    is_hypothetical: bool = False


class RemedyProposal(BaseModel):
    remedy_id: str
    application_id: str
    finding_id: str
    rule_id: str
    clause: str
    remedy_type: RemedyType
    is_advisory: bool = True
    guarantees_approval: bool = False
    advisory_wording: str
    calculation_trace: dict[str, Any] = Field(default_factory=dict)
    proposed_remedy_facts: dict[str, Any] = Field(default_factory=dict)
    re_evaluation_result: dict[str, Any] = Field(default_factory=dict)
    findings_closed: list[str] = Field(default_factory=list)
    findings_remaining: list[str] = Field(default_factory=list)
    allowed_at_current_stage: bool = True
    stage_restriction_reason: str | None = None
    is_simulated: bool = True


class ReplayBundle(BaseModel):
    bundle_id: str
    run_id: str
    application_id: str
    bundle_hash: str
    evaluator_version: str
    manifest: dict[str, Any] = Field(default_factory=dict)
    files: dict[str, str] = Field(default_factory=dict)  # filename -> content
    file_hashes: dict[str, str] = Field(default_factory=dict)  # filename -> sha256
    disclaimer: str = (
        "Offline replay verification bundle. Reproducing the evaluator "
        "does not reproduce a fresh OCR run."
    )
