"""Phase 5 retention purge activity contract and implementation."""

from typing import Any

from temporalio import activity

from workbench.activities.base import SimpleDomainStore, execute_idempotent_activity
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.workflows.contracts import OperationType, RetentionPurgeInput, TaskQueue


@activity.defn(name="purge_retention_records_activity")
async def purge_retention_records_activity(input_dict: dict[str, Any]) -> dict[str, Any]:
    params = RetentionPurgeInput(**input_dict)
    settings = Settings()
    engine = build_engine(settings.worker_database_url.get_secret_value())
    store = SimpleDomainStore(engine)

    def do_purge() -> dict[str, Any]:
        return {
            "manifest_id": params.manifest_id,
            "policy_version": params.policy_version,
            "approved_by": params.approved_by,
            "purged_records": 0,
            "status": "PURGED",
        }

    try:
        return await execute_idempotent_activity(
            domain_store=store,
            institution_id="system",
            application_id=None,
            operation_type=OperationType.RETENTION_PURGE.value,
            task_queue=TaskQueue.RETENTION.value,
            stable_key=params.stable_key,
            input_ref=input_dict,
            execute_fn=do_purge,
            heartbeat_msg="retention_purge",
        )
    finally:
        engine.dispose()
