"""Base helper for idempotent Temporal activities with stable business keys
and cancellation checks.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from temporalio import activity

from workbench.adapters.operations_service import OperationsService
from workbench.workflows.contracts import OperationStatus
from workbench.workflows.retry_policy import (
    NonRetryableError,
    OperationCancelledError,
)


class SimpleDomainStore:
    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def system_transaction(self) -> Any:
        return self.engine.begin()


async def execute_idempotent_activity(
    *,
    domain_store: Any,
    institution_id: str,
    application_id: str | None,
    operation_type: str,
    task_queue: str,
    stable_key: str,
    input_ref: dict[str, Any],
    execute_fn: Callable[[], Any],
    heartbeat_msg: str = "running",
) -> dict[str, Any]:
    """Execute an activity idempotently under its stable business key."""
    # Check Temporal cancellation
    if activity.is_cancelled():
        raise OperationCancelledError()

    activity.heartbeat(f"{heartbeat_msg}_init")

    # 1. Check if previously executed and committed under stable business key
    with domain_store.system_transaction() as conn:
        op = OperationsService.create_or_get_operation(
            conn,
            institution_id=institution_id,
            application_id=application_id,
            operation_type=operation_type,
            task_queue=task_queue,
            stable_key=stable_key,
            input_ref=input_ref,
            workflow_id=activity.info().workflow_id,
        )
        if op["status"] == OperationStatus.SUCCEEDED.value and op["result"] is not None:
            # Re-read stored output without repeating side effects
            return {
                "status": OperationStatus.SUCCEEDED.value,
                "stable_key": stable_key,
                "output": op["result"],
                "replayed": True,
            }

        # Record running attempt
        OperationsService.record_running(conn, op["id"], activity.info().workflow_id)

    activity.heartbeat(f"{heartbeat_msg}_processing")

    try:
        if asyncio.iscoroutinefunction(execute_fn):
            output = await execute_fn()
        else:
            output = execute_fn()

        activity.heartbeat(f"{heartbeat_msg}_completed")

        # 2. Record success atomically
        with domain_store.system_transaction() as conn:
            OperationsService.record_success(conn, op["id"], output)

        return {
            "status": OperationStatus.SUCCEEDED.value,
            "stable_key": stable_key,
            "output": output,
            "replayed": False,
        }

    except asyncio.CancelledError as exc:
        with domain_store.system_transaction() as conn:
            OperationsService.record_cancellation(conn, op["id"], "Temporal activity cancelled")
        raise OperationCancelledError() from exc

    except NonRetryableError as exc:
        with domain_store.system_transaction() as conn:
            OperationsService.record_failure(
                conn, op["id"], exc.error_code, str(exc), requires_operator=False
            )
        raise

    except Exception as exc:
        with domain_store.system_transaction() as conn:
            OperationsService.record_failure(
                conn, op["id"], "ACTIVITY_ERROR", str(exc), requires_operator=False
            )
        raise
