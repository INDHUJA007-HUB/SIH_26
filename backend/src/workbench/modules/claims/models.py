"""Claims and evidence reconciliation domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ClaimRelationship(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    INCONCLUSIVE = "INCONCLUSIVE"


class ClaimStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    MISMATCH_DETECTED = "MISMATCH_DETECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class DeclaredClaim:
    """An institutional claim declared in the application."""

    subject: str
    predicate: str
    declared_value: dict[str, Any]
    period_start: str | None = None
    period_end: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "declared_value": self.declared_value,
            "period_start": self.period_start,
            "period_end": self.period_end,
        }


@dataclass(frozen=True)
class ClaimReconciliationResult:
    """Outcome of reconciling a claim against extracted facts."""

    claim_id: str
    status: ClaimStatus
    reconciled_value: dict[str, Any]
    links: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "reconciled_value": self.reconciled_value,
            "links": self.links,
        }
