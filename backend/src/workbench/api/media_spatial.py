"""Phase 11 API endpoints: media metadata inspection, frame sampling, perceptual hashing,
equipment detection, and spatial floor plan reconciliation.
"""

from __future__ import annotations

import base64
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import Connection, select, text

from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore
from workbench.adapters.media_analysis_application_service import MediaAnalysisService
from workbench.adapters.object_storage import ObjectStorage
from workbench.contracts.intake import Principal
from workbench.modules.media_analysis import (
    EquipmentCategory,
    EquipmentDetectionRecord,
    FloorPlanReconciliationRecord,
    ModelMode,
    SimilarityMatch,
)
from workbench.platform.errors import ApplicationError, NotFoundError


def _check_institution_access(
    conn: Connection,
    institution_id: str,
    application_id: str | None = None,
    write: bool = False,
) -> None:
    app_param = application_id if application_id is not None else None
    allowed = conn.scalar(
        text("SELECT wb.can_access(:inst, :app, :write) OR wb.manages(:inst)"),
        {"inst": institution_id, "app": app_param, "write": write},
    )
    if allowed:
        return
    is_elevated = conn.scalar(
        text("SELECT wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('auditor'))")
    )
    if not is_elevated:
        raise ApplicationError(
            "ACCESS_DENIED", "Access to institution or application is denied", 403
        )


class InspectMediaBody(BaseModel):
    evidence_version_id: str
    media_type: str
    video_role: str = "NONE"
    duration_seconds: float = 0.0
    dimensions: dict[str, int] | None = None
    codec: str = "h264"
    frame_rate: float = 30.0
    bitrate_kbps: int = 2500
    image_bytes_base64: str | None = None


class SimilarityCheckBody(BaseModel):
    target_evidence_version_id: str


class DetectEquipmentBody(BaseModel):
    evidence_version_id: str
    room_identifier: str
    declared_quantity: int
    equipment_category: str = EquipmentCategory.WORKSTATION.value
    model_mode: str = ModelMode.EXPRESS_MANUAL_FALLBACK.value
    image_bytes_base64: str | None = None


class CorrectEquipmentCountBody(BaseModel):
    corrected_count: int = Field(ge=0)
    reason: str = Field(min_length=10)


class FloorPlanReconciliationBody(BaseModel):
    evidence_version_id: str
    plan_name: str
    declared_spaces: list[dict[str, Any]]
    identified_spaces: list[dict[str, Any]]


def create_phase_11_router(
    store: DomainStore, principal: Any, storage: ObjectStorage | None = None
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["phase_11_media_spatial"])

    # 1. Media Metadata Inspection & Frame Sampling
    @router.post("/evidence/{evidence_id}/media-analysis")
    def inspect_media_endpoint(
        evidence_id: str,
        body: InspectMediaBody,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            ev_row = conn.execute(
                select(t.evidence.c.institution_id).where(t.evidence.c.id == evidence_id)
            ).first()
            if not ev_row:
                raise NotFoundError("Evidence")
            institution_id = ev_row[0]
            _check_institution_access(conn, institution_id, write=True)

            if body.evidence_version_id != evidence_id:
                raise ApplicationError(
                    "VERSION_MISMATCH", "Analyze the admitted evidence version", 422
                )
            ev = (
                conn.execute(select(t.evidence).where(t.evidence.c.id == evidence_id))
                .mappings()
                .one()
            )
            if ev["status"] != "ACCEPTED":
                raise ApplicationError("EVIDENCE_NOT_ACCEPTED", "Admitted evidence required", 409)
            event_id = str(uuid4())
            conn.execute(
                t.outbox.insert().values(
                    id=event_id,
                    institution_id=institution_id,
                    application_id=ev["application_id"],
                    event_type="MediaAnalysisRequested",
                    payload={"evidence_id": evidence_id, "video_role": body.video_role},
                )
            )
            return {"event_id": event_id, "status": "QUEUED"}

    @router.get("/evidence/{evidence_id}/media-analysis")
    def get_media_analysis_endpoint(
        evidence_id: str,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            ev_row = conn.execute(
                select(t.evidence.c.institution_id).where(t.evidence.c.id == evidence_id)
            ).first()
            if not ev_row:
                raise NotFoundError("Evidence")
            institution_id = ev_row[0]
            _check_institution_access(conn, institution_id, write=False)

            meta_row = (
                conn.execute(
                    select(t.media_metadata).where(t.media_metadata.c.evidence_id == evidence_id)
                )
                .mappings()
                .first()
            )

            if not meta_row:
                raise NotFoundError("MediaMetadata")

            frames = (
                conn.execute(
                    select(t.media_sampled_frames).where(
                        t.media_sampled_frames.c.media_metadata_id == meta_row["id"]
                    )
                )
                .mappings()
                .all()
            )

            return {
                "metadata": dict(meta_row),
                "sampled_frames": [dict(f) for f in frames],
            }

    @router.get("/evidence/{evidence_id}/contact-sheet")
    def get_contact_sheet_endpoint(
        evidence_id: str,
        actor: Principal = Depends(principal),
    ) -> Response:
        with store.transaction(actor) as conn:
            ev_row = conn.execute(
                select(t.evidence.c.institution_id).where(t.evidence.c.id == evidence_id)
            ).first()
            if not ev_row:
                raise NotFoundError("Evidence")
            institution_id = ev_row[0]
            _check_institution_access(conn, institution_id, write=False)

            meta_row = (
                conn.execute(
                    select(t.media_metadata).where(t.media_metadata.c.evidence_id == evidence_id)
                )
                .mappings()
                .first()
            )
            if not meta_row:
                raise NotFoundError("MediaMetadata")

            derivative = (
                conn.execute(
                    select(t.derivatives).where(
                        t.derivatives.c.evidence_id == evidence_id,
                        t.derivatives.c.kind == "CONTACT_SHEET",
                    )
                )
                .mappings()
                .first()
            )
            if not derivative or storage is None:
                raise ApplicationError(
                    "MEDIA_NOT_READY", "No decoded contact sheet is available", 409
                )
            stream = storage.read(
                derivative["object_key"], derivative["object_version"], storage.clean
            )
            try:
                content = stream.read(derivative["size_bytes"] + 1)
            finally:
                stream.close()
            import hashlib

            if hashlib.sha256(content).hexdigest() != derivative["sha256"]:
                raise ApplicationError("HASH_MISMATCH", "Contact sheet integrity failure", 409)
            return Response(content=content, media_type="image/png")

    # 2. Similarity candidates
    @router.post("/evidence/{evidence_id}/similarity-check", response_model=list[SimilarityMatch])
    def check_similarity_endpoint(
        evidence_id: str,
        body: SimilarityCheckBody,
        actor: Principal = Depends(principal),
    ) -> list[SimilarityMatch]:
        with store.transaction(actor) as conn:
            ev_row = conn.execute(
                select(t.evidence.c.institution_id).where(t.evidence.c.id == evidence_id)
            ).first()
            if not ev_row:
                raise NotFoundError("Evidence")
            institution_id = ev_row[0]
            _check_institution_access(conn, institution_id, write=True)

            meta_row = (
                conn.execute(
                    select(t.media_metadata).where(t.media_metadata.c.evidence_id == evidence_id)
                )
                .mappings()
                .first()
            )
            if not meta_row:
                raise NotFoundError("MediaMetadata")

            service = MediaAnalysisService(conn)
            return service.detect_similarity_matches(
                institution_id=institution_id,
                source_evidence_version_id=meta_row["evidence_version_id"],
                target_evidence_version_id=body.target_evidence_version_id,
            )

    # 3. Equipment candidate detection
    @router.post(
        "/applications/{application_id}/equipment-detection",
        response_model=EquipmentDetectionRecord,
    )
    def run_equipment_detection_endpoint(
        application_id: str,
        body: DetectEquipmentBody,
        actor: Principal = Depends(principal),
    ) -> EquipmentDetectionRecord:
        with store.transaction(actor) as conn:
            app_row = conn.execute(
                select(t.applications.c.institution_id).where(t.applications.c.id == application_id)
            ).first()
            if not app_row:
                raise NotFoundError("Application")
            institution_id = app_row[0]
            _check_institution_access(
                conn, institution_id, application_id=application_id, write=True
            )

            img_bytes: bytes | None = None
            if body.image_bytes_base64:
                try:
                    img_bytes = base64.b64decode(body.image_bytes_base64)
                except Exception:
                    img_bytes = None

            service = MediaAnalysisService(conn)
            evidence = (
                conn.execute(
                    select(t.evidence).where(
                        t.evidence.c.id == body.evidence_version_id,
                        t.evidence.c.application_id == application_id,
                        t.evidence.c.institution_id == institution_id,
                        t.evidence.c.status == "ACCEPTED",
                    )
                )
                .mappings()
                .first()
            )
            if evidence is None:
                raise ApplicationError(
                    "EVIDENCE_NOT_ACCEPTED", "Admitted evidence from this application required", 422
                )
            return service.run_equipment_detection(
                institution_id=institution_id,
                application_id=application_id,
                evidence_version_id=body.evidence_version_id,
                room_identifier=body.room_identifier,
                declared_quantity=body.declared_quantity,
                equipment_category=body.equipment_category,
                model_mode=body.model_mode,
                image_bytes=img_bytes,
            )

    @router.get("/applications/{application_id}/equipment-detections")
    def list_equipment_detections_endpoint(
        application_id: str,
        room_identifier: str | None = None,
        actor: Principal = Depends(principal),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            app_row = conn.execute(
                select(t.applications.c.institution_id).where(t.applications.c.id == application_id)
            ).first()
            if not app_row:
                raise NotFoundError("Application")
            institution_id = app_row[0]
            _check_institution_access(
                conn, institution_id, application_id=application_id, write=False
            )

            stmt = select(t.equipment_detections).where(
                t.equipment_detections.c.application_id == application_id
            )
            if room_identifier:
                stmt = stmt.where(t.equipment_detections.c.room_identifier == room_identifier)

            rows = conn.execute(stmt).mappings().all()
            return [dict(r) for r in rows]

    @router.post("/equipment-detections/{detection_id}/corrections")
    def correct_equipment_count_endpoint(
        detection_id: str,
        body: CorrectEquipmentCountBody,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            det_row = (
                conn.execute(
                    select(t.equipment_detections).where(
                        t.equipment_detections.c.id == detection_id
                    )
                )
                .mappings()
                .first()
            )
            if not det_row:
                raise NotFoundError("EquipmentDetection")

            institution_id = det_row["institution_id"]
            app_id = det_row["application_id"]
            _check_institution_access(conn, institution_id, application_id=app_id, write=True)

            if not conn.scalar(
                text(
                    "SELECT wb.elevated() AND (wb.has_role('officer') OR wb.has_role('supervisor'))"
                )
            ):
                raise ApplicationError("ACCESS_DENIED", "Officer with fresh MFA required", 403)
            service = MediaAnalysisService(conn)
            result = service.record_human_count_correction(
                detection_id=detection_id,
                institution_id=institution_id,
                officer_id=actor.subject,
                corrected_count=body.corrected_count,
                reason=body.reason,
            )
            store.audit(
                conn,
                institution_id,
                app_id,
                "EquipmentCountCorrected",
                {"detection_id": detection_id, "count": body.corrected_count},
                str(uuid4()),
            )
            return result

    # 4. Spatial Floor Plan Reconciliation
    @router.post(
        "/applications/{application_id}/floor-plan-reconciliation",
        response_model=FloorPlanReconciliationRecord,
    )
    def reconcile_floor_plan_endpoint(
        application_id: str,
        body: FloorPlanReconciliationBody,
        actor: Principal = Depends(principal),
    ) -> FloorPlanReconciliationRecord:
        with store.transaction(actor) as conn:
            app_row = conn.execute(
                select(t.applications.c.institution_id).where(t.applications.c.id == application_id)
            ).first()
            if not app_row:
                raise NotFoundError("Application")
            institution_id = app_row[0]
            _check_institution_access(
                conn, institution_id, application_id=application_id, write=True
            )

            service = MediaAnalysisService(conn)
            return service.reconcile_floor_plan(
                institution_id=institution_id,
                application_id=application_id,
                evidence_version_id=body.evidence_version_id,
                plan_name=body.plan_name,
                declared_spaces=body.declared_spaces,
                identified_spaces=body.identified_spaces,
            )

    @router.get("/applications/{application_id}/floor-plan-reconciliations")
    def list_floor_plan_reconciliations_endpoint(
        application_id: str,
        actor: Principal = Depends(principal),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            app_row = conn.execute(
                select(t.applications.c.institution_id).where(t.applications.c.id == application_id)
            ).first()
            if not app_row:
                raise NotFoundError("Application")
            institution_id = app_row[0]
            _check_institution_access(
                conn, institution_id, application_id=application_id, write=False
            )

            rows = (
                conn.execute(
                    select(t.floor_plan_reconciliations).where(
                        t.floor_plan_reconciliations.c.application_id == application_id
                    )
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows]

    return router
