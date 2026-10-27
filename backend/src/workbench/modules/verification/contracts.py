"""Contracts and provider interface for Phase 8 source verification."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    MISMATCH_DETECTED = "MISMATCH_DETECTED"
    EXPIRED = "EXPIRED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class ProviderMode(StrEnum):
    SIMULATED = "SIMULATED"
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"


class SignatureStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    REVOKED = "REVOKED"
    CHAIN_INCOMPLETE = "CHAIN_INCOMPLETE"
    UNKNOWN = "UNKNOWN"
    MALFORMED = "MALFORMED"


class SignerRole(StrEnum):
    APPLICANT = "APPLICANT"
    ISSUER = "ISSUER"
    THIRD_PARTY = "THIRD_PARTY"
    UNKNOWN = "UNKNOWN"


class ProviderCapability(BaseModel):
    name: str
    code: str
    mode: ProviderMode = ProviderMode.SIMULATED
    supported_doc_types: list[str] = Field(default_factory=list)
    supported_predicates: list[str] = Field(default_factory=list)
    live_coverage_available: bool = False
    blocked_reason: str | None = None


class VerificationRequest(BaseModel):
    institution_id: str
    evidence_id: str
    evidence_version_id: str
    claim_id: str | None = None
    document_type: str = "UNKNOWN_DOCUMENT_TYPE"
    predicate: str | None = None
    declared_value: dict[str, Any] | None = None
    extracted_value: dict[str, Any] | None = None
    as_of_date: str | None = None
    force_fault: str | None = (
        None  # Deterministic fault injection e.g. "OUTAGE", "TIMEOUT", "MISMATCH"
    )


class VerificationResponse(BaseModel):
    status: SourceVerificationStatus
    observed_value: dict[str, Any] | None = None
    discrepancy_details: dict[str, Any] | None = None
    freshness_timestamp: str
    request_fingerprint: str
    simulated: bool = True
    live_success: bool = False
    error_code: str | None = None
    error_message: str | None = None
    requires_manual_review: bool = False


class SourceVerificationProvider(ABC):
    """Abstract adapter contract for external source verification providers."""

    @abstractmethod
    def get_capability(self) -> ProviderCapability:
        """Return provider capabilities, supported documents, and live/simulated mode."""
        pass

    @abstractmethod
    def verify(self, request: VerificationRequest) -> VerificationResponse:
        """Verify claim or evidence against external authoritative records."""
        pass
