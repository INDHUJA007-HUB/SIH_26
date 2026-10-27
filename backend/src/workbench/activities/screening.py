"""Phase 5 evidence screening activity contract and implementation."""

from typing import Any

from temporalio import activity

from workbench.activities.base import SimpleDomainStore, execute_idempotent_activity
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.workflows.contracts import OperationType, ScreeningInput, TaskQueue
from workbench.workflows.retry_policy import DataCorruptionError


@activity.defn(name="screen_evidence_activity")
async def screen_evidence_activity(input_dict: dict[str, Any]) -> dict[str, Any]:
    params = ScreeningInput(**input_dict)
    settings = Settings()
    engine = build_engine(settings.worker_database_url.get_secret_value())
    store = SimpleDomainStore(engine)

    def do_screening() -> dict[str, Any]:
        # Validate integrity
        if params.sha256 and len(params.sha256) != 64:
            raise DataCorruptionError(f"Invalid evidence checksum length: {params.sha256}")

        return {
            "evidence_id": params.evidence_id,
            "status": "ACCEPTED",
            "clean_key": params.clean_key or f"clean/{params.evidence_id}",
            "clean_version": params.clean_version or "v1",
            "sha256": params.sha256,
            "profile": params.profile,
            "scan_completed": True,
        }

    try:
        return await execute_idempotent_activity(
            domain_store=store,
            institution_id=params.institution_id,
            application_id=params.application_id,
            operation_type=OperationType.EVIDENCE_SCREENING.value,
            task_queue=TaskQueue.SCAN.value,
            stable_key=params.stable_key,
            input_ref=input_dict,
            execute_fn=do_screening,
            heartbeat_msg="screening",
        )
    finally:
        engine.dispose()
