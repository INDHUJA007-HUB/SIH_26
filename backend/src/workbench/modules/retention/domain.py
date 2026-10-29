"""Domain invariants for retention, legal holds, and immutable purge manifests."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from workbench.modules.retention.contracts import (
    DataClass,
    PurgeCandidate,
    RetentionPolicyCreate,
)
from workbench.platform.errors import ApplicationError


def validate_retention_policy_rules(payload: RetentionPolicyCreate) -> None:
    """Enforce regulatory minimum retention periods per Section 9.3."""
    if (
        payload.data_class == DataClass.CERT_IN_SECURITY_LOGS
        and payload.retention_period_days < 180
    ):
        raise ApplicationError(
            "POLICY_VIOLATION",
            (
                "CERT-In ICT security logs require minimum 180 days retention "
                "per statutory directions."
            ),
            422,
        )
    elif payload.data_class == DataClass.AUDIT_CHECKPOINTS and payload.retention_period_days < 2555:
        raise ApplicationError(
            "POLICY_VIOLATION",
            "Audit checkpoints require minimum 7 years (2555 days) statutory retention.",
            422,
        )
    elif payload.data_class == DataClass.ORIGINAL_EVIDENCE and payload.retention_period_days < 365:
        raise ApplicationError(
            "POLICY_VIOLATION",
            "Original institutional evidence requires minimum 1 year retention.",
            422,
        )


def is_candidate_held(candidate: PurgeCandidate, active_holds: list[dict[str, Any]]) -> bool:
    """Returns True if candidate matches ANY active legal hold scope."""
    for hold in active_holds:
        if not hold.get("is_active", True):
            continue

        hold_inst = hold.get("institution_id")
        hold_app = hold.get("application_id")
        hold_slot = hold.get("evidence_slot_id")

        # 1. Specific slot hold match
        if hold_slot:
            if candidate.evidence_slot_id and hold_slot == candidate.evidence_slot_id:
                return True
            continue

        # 2. Application-wide hold match
        if hold_app:
            if candidate.application_id and hold_app == candidate.application_id:
                return True
            continue

        # 3. Institution-wide hold match
        if hold_inst and candidate.institution_id and hold_inst == candidate.institution_id:
            return True

    return False


def is_dependent_evidence(
    candidate: PurgeCandidate,
    active_application_ids: set[str],
    manifest_evidence_ids: set[str] | None = None,
) -> bool:
    """Returns True if original evidence is referenced by an active regulatory lifecycle
    or finalized evaluation manifest.
    """
    if candidate.data_class != DataClass.ORIGINAL_EVIDENCE:
        return False

    if manifest_evidence_ids and candidate.item_id in manifest_evidence_ids:
        return True

    return bool(candidate.application_id and candidate.application_id in active_application_ids)


def compute_manifest_digest(
    policy_id: str,
    data_class: str,
    purged_evidence_ids: list[str],
    purged_derivative_keys: list[str],
    bytes_freed: int,
    executed_at: datetime,
) -> str:
    """Computes deterministic SHA-256 digest over canonical manifest content."""
    payload = {
        "policy_id": policy_id,
        "data_class": data_class,
        "purged_evidence_ids": sorted(purged_evidence_ids),
        "purged_derivative_keys": sorted(purged_derivative_keys),
        "bytes_freed": bytes_freed,
        "executed_at": executed_at.isoformat(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
