"""Claim and evidence reconciliation engine."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from workbench.modules.claims.models import (
    ClaimRelationship,
    ClaimStatus,
)


class ClaimReconciler:
    """Reconciles declared institutional claims against extracted evidence facts."""

    def reconcile(
        self,
        subject: str,
        predicate: str,
        declared_value: dict[str, Any],
        extracted_fields: list[dict[str, Any]],
    ) -> tuple[ClaimStatus, dict[str, Any], list[dict[str, Any]]]:
        """Compare declared values with matching extracted fields.
        Returns (reconciliation_status, reconciled_value, links)."""

        matching_fields = [
            f
            for f in extracted_fields
            if f.get("field_name") == predicate
            or f.get("field_name", "").startswith(f"{predicate}_")
        ]

        if not matching_fields:
            return (
                ClaimStatus.UNVERIFIED,
                declared_value,
                [],
            )

        links: list[dict[str, Any]] = []
        overall_status = ClaimStatus.VERIFIED
        reconciled_val = dict(declared_value)

        for f in matching_fields:
            evidence_id = f.get("evidence_version_id", "")
            field_id = f.get("id", "")
            norm = f.get("normalized_value") or {}

            # Compare values
            rel, rationale = self._evaluate_relationship(predicate, declared_value, norm)

            links.append(
                {
                    "evidence_version_id": evidence_id,
                    "field_id": field_id,
                    "relationship": rel.value,
                    "rationale": rationale,
                }
            )

            if rel == ClaimRelationship.CONTRADICTS:
                overall_status = ClaimStatus.MISMATCH_DETECTED
                reconciled_val["discrepancy"] = {
                    "declared": declared_value,
                    "observed": norm,
                    "field_id": field_id,
                }
            elif (
                rel == ClaimRelationship.INCONCLUSIVE
                and overall_status != ClaimStatus.MISMATCH_DETECTED
            ):
                overall_status = ClaimStatus.INCONCLUSIVE

        return overall_status, reconciled_val, links

    def _evaluate_relationship(
        self, predicate: str, declared: dict[str, Any], observed: dict[str, Any]
    ) -> tuple[ClaimRelationship, str]:
        # Handle numeric / canonical values
        dec_dec = self._to_decimal(
            declared.get("canonical_value")
            or declared.get("decimal_value")
            or declared.get("value")
        )
        dec_obs = self._to_decimal(
            observed.get("canonical_value")
            or observed.get("decimal_value")
            or observed.get("value")
        )

        if dec_dec is not None and dec_obs is not None:
            if dec_dec == dec_obs:
                return (
                    ClaimRelationship.SUPPORTS,
                    f"Declared {dec_dec} exactly matches observed evidence {dec_obs}",
                )
            elif "area" in predicate or "land" in predicate or "bandwidth" in predicate:
                # If observed >= declared for facilities, is it support or discrepancy?
                # Regulatory rule: observed area must satisfy declared area
                if dec_obs >= dec_dec:
                    return (
                        ClaimRelationship.SUPPORTS,
                        f"Observed {dec_obs} satisfies declared requirement {dec_dec}",
                    )
                else:
                    return (
                        ClaimRelationship.CONTRADICTS,
                        f"Discrepancy: declared {dec_dec} exceeds observed {dec_obs}",
                    )
            else:
                return (
                    ClaimRelationship.CONTRADICTS,
                    f"Discrepancy: declared {dec_dec} does not match observed {dec_obs}",
                )

        # Handle date comparisons
        date_dec = declared.get("iso_date") or declared.get("date")
        date_obs = observed.get("iso_date") or observed.get("date")
        if date_dec and date_obs:
            if date_dec == date_obs:
                return (
                    ClaimRelationship.SUPPORTS,
                    f"Declared date {date_dec} matches observed date {date_obs}",
                )
            else:
                return (
                    ClaimRelationship.CONTRADICTS,
                    f"Declared date {date_dec} conflicts with observed date {date_obs}",
                )

        # Handle identity or string comparisons
        str_dec = declared.get("identity") or declared.get("name") or declared.get("raw_text")
        str_obs = observed.get("identity") or observed.get("name") or observed.get("raw_text")
        if str_dec and str_obs:
            if str(str_dec).strip().upper() == str(str_obs).strip().upper():
                return ClaimRelationship.SUPPORTS, f"Identity {str_dec} matches observed evidence"
            else:
                return (
                    ClaimRelationship.CONTRADICTS,
                    f"Identity mismatch: declared '{str_dec}' != observed '{str_obs}'",
                )

        return (
            ClaimRelationship.INCONCLUSIVE,
            "Insufficient structured values to confirm or refute claim",
        )

    @staticmethod
    def _to_decimal(val: Any) -> Decimal | None:
        if val is None:
            return None
        try:
            return Decimal(str(val))
        except Exception:
            return None
