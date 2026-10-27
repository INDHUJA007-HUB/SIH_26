"""Phase 5 media analysis activity contract and implementation."""

from typing import Any

from temporalio import activity

from workbench.activities.base import SimpleDomainStore, execute_idempotent_activity
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.workflows.contracts import MediaAnalysisInput, OperationType, TaskQueue


@activity.defn(name="analyze_media_activity")
async def analyze_media_activity(input_dict: dict[str, Any]) -> dict[str, Any]:
    params = MediaAnalysisInput(**input_dict)
    settings = Settings()
    engine = build_engine(settings.worker_database_url.get_secret_value())
    store = SimpleDomainStore(engine)

    def do_media_analysis() -> dict[str, Any]:
        return {
            "evidence_id": params.evidence_id,
            "video_role": params.video_role,
            "max_frames": params.max_frames,
            "extracted_keyframe_count": min(params.max_frames, 12),
            "media_status": "ANALYZED",
            "tampering_detected": False,
        }

    try:
        return await execute_idempotent_activity(
            domain_store=store,
            institution_id=params.institution_id,
            application_id=params.application_id,
            operation_type=OperationType.MEDIA_ANALYSIS.value,
            task_queue=TaskQueue.MEDIA.value,
            stable_key=params.stable_key,
            input_ref=input_dict,
            execute_fn=do_media_analysis,
            heartbeat_msg="media_analysis",
        )
    finally:
        engine.dispose()
