"""Domain models for the rule registry and regulatory interpretation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class InterpretationState(StrEnum):
    REQUIRES_AUTHORIZED_REVIEW = "REQUIRES_AUTHORIZED_REVIEW"
    INTERPRETATION_PENDING = "INTERPRETATION_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PublicationState(StrEnum):
    DRAFT = "DRAFT"
    SOURCE_CHECKED = "SOURCE_CHECKED"
    APPROVED_FOR_PUBLICATION = "APPROVED_FOR_PUBLICATION"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"


class ContentStatus(StrEnum):
    VERIFIED_UPLOADED = "V-U"
    VERIFIED_MIRROR = "V-M"
    UNVERIFIED = "U"
    USER_SCOPE = "USER_SCOPE"


class RuleSourceRecord(BaseModel):
    id: str
    source_code: str
    title: str
    sha256: str
    bytes_size: int | None = None
    status: str
    publisher_reference: str | None = None
    pdf_pages: int | None = None
    checked_on: str | None = None


class RuleInterpretationRecord(BaseModel):
    id: str
    rule_id: str
    clause: str | None = None
    source_id: str | None = None
    interpretation_state: InterpretationState = InterpretationState.REQUIRES_AUTHORIZED_REVIEW
    content_status: str = "V-U"
    summary: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class RuleVersionRecord(BaseModel):
    id: str
    rule_id: str
    version: int = 1
    content_hash: str
    source_id: str | None = None
    clause: str | None = None
    printed_page: int | None = None
    pdf_page: int | None = None
    page_offset: int = 16
    applicability: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    dsl_expression: dict[str, Any] = Field(default_factory=dict)
    status: PublicationState = PublicationState.DRAFT
    production_enabled: bool = False
    adverse_action_allowed: bool = False


class RuleReleaseRecord(BaseModel):
    id: str
    release_code: str
    version: int = 1
    academic_cycle: str
    content_hash: str
    status: PublicationState = PublicationState.DRAFT
    approved_by: str | None = None
    is_active: bool = False
    member_rule_ids: list[str] = Field(default_factory=list)
