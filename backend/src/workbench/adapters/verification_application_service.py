"""Service orchestrating authorized source verification, attempts,
signatures, and observations (Phase 8).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, Engine, insert, select, update

from workbench.adapters import tables as t
from workbench.modules.verification.contracts import (
    SourceVerificationStatus,
    VerificationRequest,
    VerificationResponse,
)
from workbench.modules.verification.signatures import SignatureVerificationEngine
from workbench.modules.verification.simulator import SimulatorRegistry
from workbench.platform.errors import ApplicationError


class VerificationService:
    """Orchestrates source verification attempts, observations, and signature inspections."""

    def __init__(
        self,
        engine: Engine,
        registry: SimulatorRegistry | None = None,
        signatures: SignatureVerificationEngine | None = None,
    ) -> None:
        self.engine = engine
        self.registry = registry or SimulatorRegistry()
        self.signatures = signatures or SignatureVerificationEngine()

    @contextmanager
    def _connection(self, conn: Connection | None = None) -> Iterator[Connection]:
        if conn is not None:
            yield conn
        else:
            with self.engine.begin() as connection:
                yield connection

    def verify_claim_or_evidence(
        self,
        institution_id: str,
        evidence_id: str | None,
        evidence_version_id: str | None,
        claim_id: str | None = None,
        document_type: str = "UNKNOWN_DOCUMENT_TYPE",
        predicate: str | None = None,
        declared_value: dict[str, Any] | None = None,
        as_of_date: str | None = None,
        force_fault: str | None = None,
        provider_code: str | None = None,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Perform source verification attempt and persist source observation.
        CRITICAL INVARIANT: A missing document must NEVER receive a verification attempt.
        """
        # 1. Enforce missing document invariant
        if not evidence_id or not evidence_version_id or evidence_id == "MISSING":
            raise ApplicationError(
                "CANNOT_VERIFY_MISSING_DOCUMENT",
                "A missing document must never receive a verification attempt.",
                400,
            )

        # 2. Select appropriate provider
        provider = None
        if provider_code:
            provider = self.registry.get_provider(provider_code)
        if not provider:
            provider = self.registry.find_provider_for_doc_type(document_type)
        if not provider:
            provider = self.registry.get_provider("AICTE_HISTORICAL_SIMULATOR")

        assert provider is not None
        actual_provider_code = provider.get_capability().code

        req = VerificationRequest(
            institution_id=institution_id,
            evidence_id=evidence_id,
            evidence_version_id=evidence_version_id,
            claim_id=claim_id,
            document_type=document_type,
            predicate=predicate,
            declared_value=declared_value,
            as_of_date=as_of_date,
            force_fault=force_fault,
        )

        # 3. Execute provider verification
        resp: VerificationResponse = provider.verify(req)

        # 4. Outage-to-manual-task transition path
        outage_escalated = False
        manual_task_id = None
        final_observation_status = resp.status

        if (
            resp.status == SourceVerificationStatus.SOURCE_UNAVAILABLE
            or resp.requires_manual_review
        ):
            outage_escalated = True
            manual_task_id = f"task_rev_{uuid.uuid4().hex[:12]}"
            final_observation_status = SourceVerificationStatus.MANUAL_REVIEW_REQUIRED

        # 5. Persist verification attempt
        attempt_id = str(uuid.uuid4())
        with self._connection(conn) as c:
            c.execute(
                insert(t.verification_attempts).values(
                    id=attempt_id,
                    institution_id=institution_id,
                    evidence_id=evidence_id,
                    evidence_version_id=evidence_version_id,
                    claim_id=claim_id,
                    provider_code=actual_provider_code,
                    attempt_number=1,
                    status="FAILED" if outage_escalated else "SUCCEEDED",
                    error_code=resp.error_code,
                    error_message=resp.error_message,
                    request_fingerprint=resp.request_fingerprint,
                    simulated=True,
                    outage_escalated_to_task=outage_escalated,
                    manual_task_id=manual_task_id,
                )
            )

            # 6. Persist source observation
            observation_id = str(uuid.uuid4())
            obs_fingerprint = hashlib.sha256(
                f"{observation_id}_{final_observation_status}_{resp.freshness_timestamp}".encode()
            ).hexdigest()

            c.execute(
                insert(t.source_observations).values(
                    id=observation_id,
                    institution_id=institution_id,
                    evidence_id=evidence_id,
                    evidence_version_id=evidence_version_id,
                    claim_id=claim_id,
                    provider_code=actual_provider_code,
                    mode="SIMULATED",
                    simulated=True,
                    live_success=False,  # CRITICAL INVARIANT: NEVER TRUE FOR SIMULATED
                    status=final_observation_status.value,
                    observed_value=resp.observed_value,
                    discrepancy_details=resp.discrepancy_details,
                    freshness_timestamp=datetime.now(UTC),
                    observation_fingerprint=obs_fingerprint,
                )
            )

            # 7. Update claim status if claim_id is provided
            if claim_id:
                c.execute(
                    update(t.claims)
                    .where(t.claims.c.id == claim_id)
                    .values(
                        status=final_observation_status.value,
                        reconciled_value=resp.observed_value or declared_value,
                    )
                )

        # 8. Record telemetry metrics
        try:
            from workbench.platform.intake_metrics import increment

            increment('workbench_source_verification_attempts_total{mode="simulated"}')
            if not outage_escalated:
                increment(
                    'workbench_source_verification_success_total{mode="simulated",live_success="false"}'
                )
        except Exception:  # noqa: S110
            pass

        return {
            "observation_id": observation_id,
            "attempt_id": attempt_id,
            "institution_id": institution_id,
            "evidence_id": evidence_id,
            "claim_id": claim_id,
            "provider_code": actual_provider_code,
            "status": final_observation_status.value,
            "simulated": True,
            "live_success": False,
            "observed_value": resp.observed_value,
            "discrepancy_details": resp.discrepancy_details,
            "outage_escalated_to_task": outage_escalated,
            "manual_task_id": manual_task_id,
        }

    def manual_confirm(
        self,
        institution_id: str,
        evidence_id: str,
        evidence_version_id: str,
        claim_id: str | None,
        officer_id: str,
        rationale: str,
        authority_reference: str,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Authorized officer manual confirmation path for resolving review or outage."""
        if not rationale or not authority_reference:
            raise ApplicationError(
                "INVALID_INPUT", "Rationale and authority reference are required", 400
            )

        observation_id = str(uuid.uuid4())
        now_dt = datetime.now(UTC)
        fingerprint = hashlib.sha256(
            f"manual_{officer_id}_{evidence_id}_{now_dt}".encode()
        ).hexdigest()

        details = {
            "officer_id": officer_id,
            "rationale": rationale,
            "authority_reference": authority_reference,
            "confirmed_at": now_dt.isoformat(),
        }

        with self._connection(conn) as c:
            c.execute(
                insert(t.source_observations).values(
                    id=observation_id,
                    institution_id=institution_id,
                    evidence_id=evidence_id,
                    evidence_version_id=evidence_version_id,
                    claim_id=claim_id,
                    provider_code="OFFICER_MANUAL_CONFIRMATION",
                    mode="SIMULATED",
                    simulated=True,
                    live_success=False,
                    status=SourceVerificationStatus.VERIFIED.value,
                    observed_value=details,
                    discrepancy_details=None,
                    freshness_timestamp=now_dt,
                    observation_fingerprint=fingerprint,
                )
            )

            if claim_id:
                c.execute(
                    update(t.claims)
                    .where(t.claims.c.id == claim_id)
                    .values(status=SourceVerificationStatus.VERIFIED.value)
                )

        return {
            "observation_id": observation_id,
            "status": SourceVerificationStatus.VERIFIED.value,
            "provider_code": "OFFICER_MANUAL_CONFIRMATION",
            "simulated": True,
            "live_success": False,
            "officer_confirmation": details,
        }

    def validate_signatures(
        self,
        institution_id: str,
        evidence_id: str,
        evidence_version_id: str,
        content_bytes: bytes,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Validate PDF digital signatures and record signature validation."""
        result = self.signatures.inspect_pdf_signatures(content_bytes)
        validation_id = str(uuid.uuid4())

        with self._connection(conn) as c:
            c.execute(
                insert(t.signature_validations).values(
                    id=validation_id,
                    institution_id=institution_id,
                    evidence_id=evidence_id,
                    evidence_version_id=evidence_version_id,
                    validation_type=result["validation_type"],
                    status=result["status"].value,
                    signer_identity=result["signer_identity"],
                    signer_role=result["signer_role"].value,
                    signing_time=datetime.now(UTC) if result.get("signing_time") else None,
                    certificate_sha256=result.get("certificate_sha256"),
                    destination_safe=True,
                    simulated=result["simulated"],
                    details=result["details"],
                )
            )

        return {
            "id": validation_id,
            "validation_type": result["validation_type"],
            "status": result["status"].value,
            "signer_identity": result["signer_identity"],
            "signer_role": result["signer_role"].value,
            "simulated": result["simulated"],
            "details": result["details"],
        }

    def validate_qr_code(
        self,
        institution_id: str,
        evidence_id: str,
        evidence_version_id: str,
        qr_text_or_url: str,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Validate structured QR destination and record validation."""
        result = self.signatures.decode_and_verify_qr(qr_text_or_url)
        validation_id = str(uuid.uuid4())

        with self._connection(conn) as c:
            c.execute(
                insert(t.signature_validations).values(
                    id=validation_id,
                    institution_id=institution_id,
                    evidence_id=evidence_id,
                    evidence_version_id=evidence_version_id,
                    validation_type=result["validation_type"],
                    status=result["status"].value,
                    qr_payload=result["qr_payload"],
                    qr_target_url=result["qr_target_url"],
                    destination_safe=result["destination_safe"],
                    simulated=True,
                    details=result["details"],
                )
            )

        return {
            "id": validation_id,
            "validation_type": result["validation_type"],
            "status": result["status"].value,
            "destination_safe": result["destination_safe"],
            "simulated": True,
            "qr_payload": result["qr_payload"],
            "details": result["details"],
        }

    def list_observations(
        self,
        institution_id: str,
        evidence_id: str | None = None,
        claim_id: str | None = None,
        conn: Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List source observations for an institution."""
        query = select(t.source_observations).where(
            t.source_observations.c.institution_id == institution_id
        )
        if evidence_id:
            query = query.where(t.source_observations.c.evidence_id == evidence_id)
        if claim_id:
            query = query.where(t.source_observations.c.claim_id == claim_id)

        query = query.order_by(t.source_observations.c.created_at.desc())

        with self._connection(conn) as c:
            rows = c.execute(query).fetchall()
            return [
                {
                    "id": r.id,
                    "institution_id": r.institution_id,
                    "evidence_id": r.evidence_id,
                    "claim_id": r.claim_id,
                    "provider_code": r.provider_code,
                    "mode": r.mode,
                    "status": r.status,
                    "simulated": r.simulated,
                    "live_success": r.live_success,
                    "observed_value": r.observed_value,
                    "discrepancy_details": r.discrepancy_details,
                    "freshness_timestamp": r.freshness_timestamp.isoformat()
                    if r.freshness_timestamp
                    else None,
                }
                for r in rows
            ]
