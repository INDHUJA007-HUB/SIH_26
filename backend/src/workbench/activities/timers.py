"""Phase 5 response window timer activity contract and implementation."""

from typing import Any

from temporalio import activity

from workbench.activities.base import SimpleDomainStore, execute_idempotent_activity
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.workflows.contracts import OperationType, ResponseWindowTimerInput, TaskQueue


@activity.defn(name="wait_response_window_activity")
async def wait_response_window_activity(input_dict: dict[str, Any]) -> dict[str, Any]:
    params = ResponseWindowTimerInput(**input_dict)
    settings = Settings()
    engine = build_engine(settings.worker_database_url.get_secret_value())
    store = SimpleDomainStore(engine)

    def do_timer_check() -> dict[str, Any]:
        return {
            "window_id": params.window_id,
            "application_id": params.application_id,
            "deadline_iso": params.deadline_iso,
            "timer_generation": params.timer_generation,
            "expired": False,
            "status": "ARMED",
        }

    try:
        return await execute_idempotent_activity(
            domain_store=store,
            institution_id=params.institution_id,
            application_id=params.application_id,
            operation_type=OperationType.RESPONSE_WINDOW_TIMER.value,
            task_queue=TaskQueue.COORDINATION.value,
            stable_key=params.stable_key,
            input_ref=input_dict,
            execute_fn=do_timer_check,
            heartbeat_msg="response_timer",
        )
    finally:
        engine.dispose()
