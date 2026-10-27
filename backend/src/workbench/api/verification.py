"""API endpoints for Phase 8 source verification, historical records, and signature validation."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text

from workbench.adapters.domain_store import DomainStore
from workbench.contracts.intake import Principal
from workbench.modules.institutional_records.service import HistoricalRecordService
from workbench.modules.verification.service import VerificationService
from workbench.modules.verification.simulator import SimulatorRegistry
from workbench.platform.errors import ApplicationError


def _check_institution_access(
    conn: Connection,
    institution_id: str,
    write: bool = False,
) -> None:
    allowed = conn.scalar(
        text("SELECT wb.can_access(:id, NULL, :write) OR wb.manages(:id)"),
        {"id": institution_id, "write": write},
    )
    if allowed:
        return
    is_elevated = conn.scalar(text("SELECT wb.elevated()"))
    if not is_elevated:
        raise ApplicationError("ACCESS_DENIED", "Access to institution is denied", 403)


class VerifyRequestBody(BaseModel):
    institution_id: str
    evidence_id: str | None = None
    evidence_version_id: str | None = None
    claim_id: str | None = None
    document_type: str = "UNKNOWN_DOCUMENT_TYPE"
    predicate: str | None = None
    declared_value: dict[str, Any] | None = None
    as_of_date: str | None = None
    force_fault: str | None = None
    provider_code: str | None = None


class ManualConfirmBody(BaseModel):
    institution_id: str
    evidence_id: str
    evidence_version_id: str
    claim_id: str | None = None
    rationale: str
    authority_reference: str


class ValidateSignatureBody(BaseModel):
    institution_id: str
    evidence_id: str
    evidence_version_id: str
    content_base64: str


class ValidateQrBody(BaseModel):
    institution_id: str
    evidence_id: str
    evidence_version_id: str
    qr_text_or_url: str


class HistoricalImportBody(BaseModel):
    institution_id: str
    source: str = "AICTE_PORTAL"
    record_type: str = "INTAKE"  # EOA, INTAKE, ACCREDITATION, DEFICIENCY, FACULTY_TER
    academic_cycle: int = 2026
    payload: dict[str, Any]
    external_reference: str
    valid_from: str | None = None
    valid_to: str | None = None


class HistoricalReconcileBody(BaseModel):
    institution_id: str
    academic_cycle: int = 2026
    declared_facts: dict[str, Any] = Field(default_factory=dict)


def create_verification_router(
    store: DomainStore,
    principal_dep: Any,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["verification"])
    registry = SimulatorRegistry()
    verification_svc = VerificationService(store.engine, registry=registry)
    historical_svc = HistoricalRecordService(store.engine)

    @router.get("/verification/providers")
    def list_providers(actor: Principal = Depends(principal_dep)) -> list[dict[str, Any]]:
        caps = registry.list_capabilities()
        return [c.model_dump() for c in caps]

    @router.post("/verification/verify")
    def verify_endpoint(
        body: VerifyRequestBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            return verification_svc.verify_claim_or_evidence(
                institution_id=body.institution_id,
                evidence_id=body.evidence_id,
                evidence_version_id=body.evidence_version_id,
                claim_id=body.claim_id,
                document_type=body.document_type,
                predicate=body.predicate,
                declared_value=body.declared_value,
                as_of_date=body.as_of_date,
                force_fault=body.force_fault,
                provider_code=body.provider_code,
                conn=conn,
            )

    @router.get("/verification/observations")
    def list_observations_endpoint(
        institution_id: str,
        evidence_id: str | None = None,
        claim_id: str | None = None,
        actor: Principal = Depends(principal_dep),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, institution_id, write=False)
            return verification_svc.list_observations(
                institution_id=institution_id,
                evidence_id=evidence_id,
                claim_id=claim_id,
                conn=conn,
            )

    @router.post("/verification/manual-confirm")
    def manual_confirm_endpoint(
        body: ManualConfirmBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            act = store.actor(conn)
            is_elevated = actor.mfa and any(
                m["role"] in {"officer", "supervisor"} for m in act.get("memberships", [])
            )
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED", "Officer or supervisor with fresh MFA required", 403
                )

            return verification_svc.manual_confirm(
                institution_id=body.institution_id,
                evidence_id=body.evidence_id,
                evidence_version_id=body.evidence_version_id,
                claim_id=body.claim_id,
                officer_id=str(act["id"]),
                rationale=body.rationale,
                authority_reference=body.authority_reference,
                conn=conn,
            )

    @router.post("/verification/signatures/validate")
    def validate_signatures_endpoint(
        body: ValidateSignatureBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            try:
                raw_bytes = base64.b64decode(body.content_base64)
            except Exception as err:
                raise ApplicationError("INVALID_INPUT", "Invalid base64 payload", 400) from err

            return verification_svc.validate_signatures(
                institution_id=body.institution_id,
                evidence_id=body.evidence_id,
                evidence_version_id=body.evidence_version_id,
                content_bytes=raw_bytes,
                conn=conn,
            )

    @router.post("/verification/qr/validate")
    def validate_qr_endpoint(
        body: ValidateQrBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            return verification_svc.validate_qr_code(
                institution_id=body.institution_id,
                evidence_id=body.evidence_id,
                evidence_version_id=body.evidence_version_id,
                qr_text_or_url=body.qr_text_or_url,
                conn=conn,
            )

    @router.post("/historical-records/import")
    def import_historical_record_endpoint(
        body: HistoricalImportBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            valid_from = (
                datetime.fromisoformat(body.valid_from) if body.valid_from else datetime.now(UTC)
            )
            valid_to = datetime.fromisoformat(body.valid_to) if body.valid_to else None

            return historical_svc.import_record(
                institution_id=body.institution_id,
                source=body.source,
                record_type=body.record_type,
                academic_cycle=body.academic_cycle,
                payload=body.payload,
                external_reference=body.external_reference,
                valid_from=valid_from,
                valid_to=valid_to,
                imported_by=actor.subject,
                conn=conn,
            )

    @router.get("/historical-records")
    def list_historical_records_endpoint(
        institution_id: str,
        record_type: str | None = None,
        academic_cycle: int | None = None,
        actor: Principal = Depends(principal_dep),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, institution_id, write=False)
            return historical_svc.list_records(
                institution_id=institution_id,
                record_type=record_type,
                academic_cycle=academic_cycle,
                conn=conn,
            )

    @router.post("/historical-records/reconcile")
    def reconcile_historical_endpoint(
        body: HistoricalReconcileBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=False)
            return historical_svc.reconcile_claims(
                institution_id=body.institution_id,
                declared_facts=body.declared_facts,
                academic_cycle=body.academic_cycle,
                conn=conn,
            )

    return router
