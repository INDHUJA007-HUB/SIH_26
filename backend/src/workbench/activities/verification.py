"""Phase 5 external source verification activity contract and implementation."""

from typing import Any

from temporalio import activity

from workbench.activities.base import SimpleDomainStore, execute_idempotent_activity
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.workflows.contracts import OperationType, TaskQueue, VerificationInput


@activity.defn(name="verify_source_records_activity")
async def verify_source_records_activity(input_dict: dict[str, Any]) -> dict[str, Any]:
    params = VerificationInput(**input_dict)
    settings = Settings()
    engine = build_engine(settings.worker_database_url.get_secret_value())
    store = SimpleDomainStore(engine)

    def do_verification() -> dict[str, Any]:
        return {
            "claim_id": params.claim_id,
            "provider_id": params.provider_id,
            "request_fingerprint": params.request_fingerprint,
            "freshness_generation": params.freshness_generation,
            "verified": True,
            "verification_status": "VERIFIED",
            "simulated": True,
            "live_success": False,
            "record_id": f"rec_{params.claim_id}_{params.provider_id}",
        }

    try:
        return await execute_idempotent_activity(
            domain_store=store,
            institution_id=params.institution_id,
            application_id=None,
            operation_type=OperationType.SOURCE_VERIFICATION.value,
            task_queue=TaskQueue.CONNECTOR.value,
            stable_key=params.stable_key,
            input_ref=input_dict,
            execute_fn=do_verification,
            heartbeat_msg="source_verification",
        )
    finally:
        engine.dispose()
