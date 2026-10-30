"""Domain services for Phase 11 media analysis, frame sampling,
equipment detection, and floor plan reconciliation.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from PIL import Image
from sqlalchemy import Connection, insert, select, update

from workbench.adapters import tables as t
from workbench.modules.media_analysis.contracts import (
    EquipmentCategory,
    EquipmentDetectionRecord,
    EquipmentDetectionStatus,
    FloorPlanReconciliationRecord,
    FloorPlanStatus,
    ModelMode,
    SampledFrame,
    SimilarityMatch,
)
from workbench.modules.media_analysis.service import (
    compute_average_hash,
    compute_difference_hash,
    extract_gps_and_exif,
    hamming_distance,
    validate_video_duration_policy,
)


class MediaAnalysisService:
    """Domain service for managing media analysis, equipment detection, and floor plans."""

    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def inspect_and_store_media(
        self,
        institution_id: str,
        evidence_id: str,
        evidence_version_id: str,
        media_type: str,
        video_role: str,
        duration_seconds: float,
        dimensions: dict[str, int] | None = None,
        codec: str = "h264",
        frame_rate: float = 30.0,
        bitrate_kbps: int = 2500,
        image_bytes: bytes | None = None,
        decoded_frames: list[tuple[float, bytes]] | None = None,
    ) -> dict[str, Any]:
        """Perform media inspection, role validation, and metadata persistence."""
        has_gps = False
        gps_meta: dict[str, Any] | None = None
        raw_exif: dict[str, Any] = {}

        # 1. Image metadata & EXIF extraction if image bytes provided
        if image_bytes and media_type in ("image/png", "image/jpeg"):
            try:
                img = Image.open(io.BytesIO(image_bytes))
                has_gps, gps_meta, raw_exif = extract_gps_and_exif(img)
                if not dimensions:
                    dimensions = {"width": img.width, "height": img.height}
            except Exception:  # noqa: S110
                pass

        # 2. Duration policy validation
        duration_policy = validate_video_duration_policy(video_role, duration_seconds)

        meta_id = str(uuid4())
        metadata_status = "VALID" if duration_policy["compliant"] else "INVALID_DURATION"

        self.conn.execute(
            insert(t.media_metadata).values(
                id=meta_id,
                institution_id=institution_id,
                evidence_id=evidence_id,
                evidence_version_id=evidence_version_id,
                media_type=media_type,
                video_role=video_role,
                duration_seconds=duration_seconds,
                dimensions=dimensions or {"width": 1920, "height": 1080},
                codec=codec,
                frame_rate=frame_rate,
                bitrate_kbps=bitrate_kbps,
                gps_metadata=gps_meta,
                has_gps=has_gps,
                metadata_status=metadata_status,
                duration_policy_result=duration_policy,
                exif_raw=raw_exif,
                created_at=datetime.now(UTC),
            )
        )

        # 3. Deterministic frame sampling for video or single frame for image
        sampled_frames_data: list[SampledFrame] = []
        if media_type == "video/mp4":
            if not decoded_frames:
                raise ValueError("Decoded video frames are required")
            for index, (timestamp, frame_bytes) in enumerate(decoded_frames):
                with Image.open(io.BytesIO(frame_bytes)) as image:
                    ahash = compute_average_hash(image)
                    dhash = compute_difference_hash(image)
                sampled_frames_data.append(
                    SampledFrame(
                        frame_index=index,
                        timestamp_seconds=timestamp,
                        perceptual_hash=dhash,
                        difference_hash=dhash,
                        average_hash=ahash,
                    )
                )
        elif image_bytes:
            try:
                img = Image.open(io.BytesIO(image_bytes))
                ahash = compute_average_hash(img)
                dhash = compute_difference_hash(img)
                sampled_frames_data.append(
                    SampledFrame(
                        frame_index=0,
                        timestamp_seconds=0.0,
                        perceptual_hash=dhash,
                        difference_hash=dhash,
                        average_hash=ahash,
                        is_keyframe=True,
                    )
                )
            except Exception:  # noqa: S110
                pass

        for sf in sampled_frames_data:
            self.conn.execute(
                insert(t.media_sampled_frames).values(
                    id=str(uuid4()),
                    institution_id=institution_id,
                    media_metadata_id=meta_id,
                    evidence_version_id=evidence_version_id,
                    frame_index=sf.frame_index,
                    timestamp_seconds=sf.timestamp_seconds,
                    perceptual_hash=sf.perceptual_hash,
                    difference_hash=sf.difference_hash,
                    average_hash=sf.average_hash,
                    is_keyframe=sf.is_keyframe,
                    created_at=datetime.now(UTC),
                )
            )

        return {
            "media_metadata_id": meta_id,
            "evidence_id": evidence_id,
            "evidence_version_id": evidence_version_id,
            "media_type": media_type,
            "video_role": video_role,
            "duration_seconds": duration_seconds,
            "duration_policy_result": duration_policy,
            "has_gps": has_gps,
            "gps_metadata": gps_meta,
            "metadata_status": metadata_status,
            "sampled_frame_count": len(sampled_frames_data),
        }

    def detect_similarity_matches(
        self,
        institution_id: str,
        source_evidence_version_id: str,
        target_evidence_version_id: str,
    ) -> list[SimilarityMatch]:
        """Detect near-duplicate frames between evidence versions using Hamming distance."""
        src_frames = (
            self.conn.execute(
                select(t.media_sampled_frames).where(
                    t.media_sampled_frames.c.evidence_version_id == source_evidence_version_id,
                    t.media_sampled_frames.c.institution_id == institution_id,
                )
            )
            .mappings()
            .all()
        )

        tgt_frames = (
            self.conn.execute(
                select(t.media_sampled_frames).where(
                    t.media_sampled_frames.c.evidence_version_id == target_evidence_version_id,
                    t.media_sampled_frames.c.institution_id == institution_id,
                )
            )
            .mappings()
            .all()
        )

        matches: list[SimilarityMatch] = []
        for sf in src_frames:
            for tf in tgt_frames:
                dist = hamming_distance(sf["perceptual_hash"], tf["perceptual_hash"])
                if dist <= 5:  # Hamming threshold <= 5 indicates near-duplicate (>= 92% similarity)
                    sim_score = round(1.0 - (dist / 64.0), 3)
                    match_type = "IDENTICAL_IMAGE" if dist == 0 else "NEAR_DUPLICATE_FRAME"
                    disposition = (
                        "IDENTICAL_FRAME_REUSED"
                        if dist == 0
                        else "POTENTIAL_REPEATED_SCENE_ADVISORY"
                    )
                    match_obj = SimilarityMatch(
                        source_evidence_version_id=source_evidence_version_id,
                        target_evidence_version_id=target_evidence_version_id,
                        similarity_score=sim_score,
                        hamming_distance=dist,
                        match_type=match_type,
                        advisory_disposition=disposition,
                        source_frame_id=sf["id"],
                        target_frame_id=tf["id"],
                    )
                    matches.append(match_obj)

                    self.conn.execute(
                        insert(t.media_similarity_matches).values(
                            id=str(uuid4()),
                            institution_id=institution_id,
                            source_evidence_version_id=source_evidence_version_id,
                            target_evidence_version_id=target_evidence_version_id,
                            source_frame_id=sf["id"],
                            target_frame_id=tf["id"],
                            similarity_score=sim_score,
                            hamming_distance=dist,
                            match_type=match_type,
                            advisory_disposition=disposition,
                            created_at=datetime.now(UTC),
                        )
                    )
        return matches

    def run_equipment_detection(
        self,
        institution_id: str,
        application_id: str,
        evidence_version_id: str,
        room_identifier: str,
        declared_quantity: int,
        equipment_category: str = EquipmentCategory.WORKSTATION.value,
        model_mode: str = ModelMode.HEURISTIC_SIMULATED.value,
        image_bytes: bytes | None = None,
    ) -> EquipmentDetectionRecord:
        """Run room-level visible equipment candidate detection.

        Emits calibrated advisory wording with count uncertainty and coverage assessment.
        Single-view photographs are NEVER treated as complete inventory!
        """
        detected_boxes: list[dict[str, Any]] = []

        # No approved detector is installed. Start an explicit human comparison task;
        # zero here means no automated candidates, never an observed inventory count.
        model_mode = ModelMode.EXPRESS_MANUAL_FALLBACK.value
        detected_count = 0
        advisory_finding = (
            "Manual comparison required. No automated equipment inference was performed. "
            "An authorized officer must inspect the evidence and record a count and rationale. "
            "Unobserved equipment is unknown; no shortage is inferred."
        )

        det_id = str(uuid4())
        coverage_assessment = {
            "coverage_percent": None,
            "count_known": False,
            "inference_performed": False,
            "notes": "Awaiting human inspection of the referenced evidence.",
        }

        self.conn.execute(
            insert(t.equipment_detections).values(
                id=det_id,
                institution_id=institution_id,
                application_id=application_id,
                evidence_version_id=evidence_version_id,
                room_identifier=room_identifier,
                equipment_category=equipment_category,
                declared_quantity=declared_quantity,
                model_mode=model_mode,
                model_name="manual-comparison",
                model_version="1",
                detected_candidate_count=detected_count,
                detected_boxes=detected_boxes,
                confidence_score=0.0,
                coverage_assessment=coverage_assessment,
                advisory_finding=advisory_finding,
                status=EquipmentDetectionStatus.ADVISORY_PENDING_REVIEW.value,
                created_at=datetime.now(UTC),
            )
        )

        return EquipmentDetectionRecord(
            id=det_id,
            institution_id=institution_id,
            application_id=application_id,
            evidence_version_id=evidence_version_id,
            room_identifier=room_identifier,
            equipment_category=equipment_category,
            declared_quantity=declared_quantity,
            model_mode=model_mode,
            model_name="manual-comparison",
            model_version="1",
            detected_candidate_count=detected_count,
            detected_boxes=detected_boxes,
            confidence_score=0.0,
            coverage_assessment=coverage_assessment,
            advisory_finding=advisory_finding,
            status=EquipmentDetectionStatus.ADVISORY_PENDING_REVIEW.value,
        )

    def record_human_count_correction(
        self,
        detection_id: str,
        institution_id: str,
        officer_id: str,
        corrected_count: int,
        reason: str,
    ) -> dict[str, Any]:
        """Record audited human correction without mutating raw model boxes."""
        row = (
            self.conn.execute(
                select(t.equipment_detections).where(
                    t.equipment_detections.c.id == detection_id,
                    t.equipment_detections.c.institution_id == institution_id,
                )
            )
            .mappings()
            .first()
        )

        if not row:
            raise ValueError(f"Equipment detection {detection_id} not found")

        correction_data = {
            "officer_id": officer_id,
            "corrected_count": corrected_count,
            "original_count": row["detected_candidate_count"],
            "reason": reason,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        self.conn.execute(
            update(t.equipment_detections)
            .where(t.equipment_detections.c.id == detection_id)
            .values(
                human_correction=correction_data,
                status=EquipmentDetectionStatus.OFFICER_CONFIRMED.value,
            )
        )

        return {
            "detection_id": detection_id,
            "status": EquipmentDetectionStatus.OFFICER_CONFIRMED.value,
            "human_correction": correction_data,
        }

    def reconcile_floor_plan(
        self,
        institution_id: str,
        application_id: str,
        evidence_version_id: str,
        plan_name: str,
        declared_spaces: list[dict[str, Any]],
        identified_spaces: list[dict[str, Any]],
    ) -> FloorPlanReconciliationRecord:
        """Reconcile declared building/room schedules against spatial floor plan drawings."""
        total_declared = sum(float(s.get("declared_area_sqm", 0)) for s in declared_spaces)
        total_measured = sum(float(s.get("measured_area_sqm", 0)) for s in identified_spaces)

        matched_spaces: list[dict[str, Any]] = []
        discrepancies: list[dict[str, Any]] = []

        identified_by_label = {s["space_label"].strip().lower(): s for s in identified_spaces}

        for dec in declared_spaces:
            label = dec["room_identifier"].strip().lower()
            dec_area = float(dec["declared_area_sqm"])
            if label in identified_by_label:
                ident = identified_by_label[label]
                meas_area = float(ident["measured_area_sqm"])
                # Area tolerance check: +/- 5%
                diff = abs(meas_area - dec_area)
                pct_diff = (diff / dec_area) * 100 if dec_area > 0 else 0
                if pct_diff <= 5.0:
                    matched_spaces.append(
                        {
                            "room_identifier": dec["room_identifier"],
                            "room_type": dec.get("room_type", "GENERIC"),
                            "declared_area_sqm": dec_area,
                            "measured_area_sqm": meas_area,
                            "status": "MATCHED",
                        }
                    )
                else:
                    discrepancies.append(
                        {
                            "type": "AREA_DISCREPANCY",
                            "room_identifier": dec["room_identifier"],
                            "declared_area_sqm": dec_area,
                            "measured_area_sqm": meas_area,
                            "deviation_percent": round(pct_diff, 2),
                            "note": f"Measured area differs by {pct_diff:.1f}% from declared area.",
                        }
                    )
            else:
                discrepancies.append(
                    {
                        "type": "MISSING_ON_PLAN",
                        "room_identifier": dec["room_identifier"],
                        "declared_area_sqm": dec_area,
                        "note": (
                            f"Declared space '{dec['room_identifier']}' "
                            "could not be identified on floor plan."
                        ),
                    }
                )

        rec_status = (
            FloorPlanStatus.RECONCILED.value
            if not discrepancies
            else FloorPlanStatus.DISCREPANCIES_FLAGGED.value
        )
        rec_id = str(uuid4())

        self.conn.execute(
            insert(t.floor_plan_reconciliations).values(
                id=rec_id,
                institution_id=institution_id,
                application_id=application_id,
                evidence_version_id=evidence_version_id,
                plan_name=plan_name,
                total_declared_area_sqm=round(total_declared, 2),
                total_measured_area_sqm=round(total_measured, 2),
                declared_spaces=declared_spaces,
                identified_spaces=identified_spaces,
                matched_spaces=matched_spaces,
                discrepancies=discrepancies,
                reconciliation_status=rec_status,
                notes=(
                    f"Floor plan '{plan_name}' reconciled: {len(matched_spaces)} spaces matched, "
                    f"{len(discrepancies)} discrepancies observed."
                ),
                created_at=datetime.now(UTC),
            )
        )

        return FloorPlanReconciliationRecord(
            id=rec_id,
            institution_id=institution_id,
            application_id=application_id,
            evidence_version_id=evidence_version_id,
            plan_name=plan_name,
            total_declared_area_sqm=round(total_declared, 2),
            total_measured_area_sqm=round(total_measured, 2),
            declared_spaces=declared_spaces,
            identified_spaces=identified_spaces,
            matched_spaces=matched_spaces,
            discrepancies=discrepancies,
            reconciliation_status=rec_status,
            notes=f"Reconciled {len(matched_spaces)} spaces; {len(discrepancies)} discrepancies.",
        )
