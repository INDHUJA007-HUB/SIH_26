"""Contracts and schemas for Phase 11 media analysis and spatial discrepancy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class VideoRole(StrEnum):
    EVC_WALKTHROUGH = "EVC_WALKTHROUGH"
    WEBSITE_DISCLOSURE = "WEBSITE_DISCLOSURE"
    SUPPLEMENTARY_EVIDENCE = "SUPPLEMENTARY_EVIDENCE"
    NONE = "NONE"


class MediaStatus(StrEnum):
    VALID = "VALID"
    UNAVAILABLE_METADATA = "UNAVAILABLE_METADATA"
    INVALID_DURATION = "INVALID_DURATION"
    CORRUPTED = "CORRUPTED"


class EquipmentCategory(StrEnum):
    WORKSTATION = "WORKSTATION"
    MONITOR = "MONITOR"
    PRINTER = "PRINTER"
    SERVER = "SERVER"


class ModelMode(StrEnum):
    HEURISTIC_SIMULATED = "HEURISTIC_SIMULATED"
    INFERENCE_RUN = "INFERENCE_RUN"
    EXPRESS_MANUAL_FALLBACK = "EXPRESS_MANUAL_FALLBACK"


class EquipmentDetectionStatus(StrEnum):
    ADVISORY_PENDING_REVIEW = "ADVISORY_PENDING_REVIEW"
    OFFICER_CONFIRMED = "OFFICER_CONFIRMED"
    ADDITIONAL_EVIDENCE_REQUESTED = "ADDITIONAL_EVIDENCE_REQUESTED"


class FloorPlanStatus(StrEnum):
    RECONCILED = "RECONCILED"
    DISCREPANCIES_FLAGGED = "DISCREPANCIES_FLAGGED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


@dataclass(frozen=True)
class VideoRolePolicy:
    min_seconds: float
    max_seconds: float
    description: str

    @classmethod
    def get_policy(cls, role: VideoRole) -> VideoRolePolicy:
        if role == VideoRole.WEBSITE_DISCLOSURE:
            return cls(
                min_seconds=60.0,
                max_seconds=120.0,
                description="Mandatory 1 to 2 minute website disclosure video",
            )
        if role == VideoRole.EVC_WALKTHROUGH:
            return cls(
                min_seconds=180.0,
                max_seconds=1800.0,
                description="Contextual Expert Visiting Committee walkthrough recording",
            )
        if role == VideoRole.SUPPLEMENTARY_EVIDENCE:
            return cls(
                min_seconds=5.0,
                max_seconds=600.0,
                description="Supplementary facility or laboratory recording",
            )
        return cls(
            min_seconds=0.0,
            max_seconds=7200.0,
            description="General media recording",
        )


@dataclass
class GPSMetadata:
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    timestamp_utc: str | None = None


@dataclass
class SampledFrame:
    frame_index: int
    timestamp_seconds: float
    perceptual_hash: str
    difference_hash: str
    average_hash: str
    is_keyframe: bool = True
    storage_key: str | None = None


@dataclass
class SimilarityMatch:
    source_evidence_version_id: str
    target_evidence_version_id: str
    similarity_score: float
    hamming_distance: int
    match_type: str
    advisory_disposition: str
    scope: str = "INTRA_APPLICATION"
    source_frame_id: str | None = None
    target_frame_id: str | None = None


@dataclass
class DetectedBox:
    box: list[float]  # [ymin, xmin, ymax, xmax] normalized 0.0 - 1.0
    label: str
    confidence: float


@dataclass
class EquipmentDetectionRecord:
    id: str
    institution_id: str
    application_id: str
    evidence_version_id: str
    room_identifier: str
    equipment_category: str
    declared_quantity: int
    model_mode: str
    model_name: str
    model_version: str
    detected_candidate_count: int
    detected_boxes: list[dict[str, Any]]
    confidence_score: float
    coverage_assessment: dict[str, Any]
    advisory_finding: str
    status: str = EquipmentDetectionStatus.ADVISORY_PENDING_REVIEW.value
    human_correction: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DeclaredSpace:
    room_identifier: str
    room_type: str
    declared_area_sqm: float


@dataclass
class IdentifiedSpace:
    space_label: str
    measured_area_sqm: float
    coordinates: list[float] | None = None


@dataclass
class FloorPlanReconciliationRecord:
    id: str
    institution_id: str
    application_id: str
    evidence_version_id: str
    plan_name: str
    total_declared_area_sqm: float
    total_measured_area_sqm: float
    declared_spaces: list[dict[str, Any]]
    identified_spaces: list[dict[str, Any]]
    matched_spaces: list[dict[str, Any]]
    discrepancies: list[dict[str, Any]]
    reconciliation_status: str
    notes: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
