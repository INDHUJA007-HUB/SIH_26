"""Media analysis and spatial floor plan reconciliation module."""

from workbench.modules.media_analysis.contracts import (
    EquipmentCategory,
    EquipmentDetectionRecord,
    EquipmentDetectionStatus,
    FloorPlanReconciliationRecord,
    FloorPlanStatus,
    ModelMode,
    SampledFrame,
    SimilarityMatch,
    VideoRole,
    VideoRolePolicy,
)
from workbench.modules.media_analysis.service import (
    compute_average_hash,
    compute_difference_hash,
    extract_gps_and_exif,
    generate_contact_sheet,
    hamming_distance,
    sample_video_frames,
    validate_video_duration_policy,
)

__all__ = [
    "EquipmentCategory",
    "EquipmentDetectionRecord",
    "EquipmentDetectionStatus",
    "FloorPlanReconciliationRecord",
    "FloorPlanStatus",
    "ModelMode",
    "SampledFrame",
    "SimilarityMatch",
    "VideoRole",
    "VideoRolePolicy",
    "compute_average_hash",
    "compute_difference_hash",
    "extract_gps_and_exif",
    "generate_contact_sheet",
    "hamming_distance",
    "sample_video_frames",
    "validate_video_duration_policy",
]
