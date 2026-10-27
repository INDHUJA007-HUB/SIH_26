"""Source verification durable workflow."""

from typing import Any

from temporalio import workflow

from workbench.workflows.contracts import TaskQueue
from workbench.workflows.retry_policy import (
    CONNECTOR_RETRY_POLICY,
    TIMEOUT_CONNECTOR,
    TIMEOUT_CONNECTOR_HEARTBEAT,
)


@workflow.defn(name="SourceVerificationWorkflow")
class SourceVerificationWorkflow:
    def __init__(self) -> None:
        self._status = "INITIALIZED"

    @workflow.run
    async def run(self, input_dict: dict[str, Any]) -> dict[str, Any]:
        self._status = "RUNNING"
        result = await workflow.execute_activity(
            "verify_source_records_activity",
            input_dict,
            task_queue=TaskQueue.CONNECTOR.value,
            start_to_close_timeout=TIMEOUT_CONNECTOR,
            heartbeat_timeout=TIMEOUT_CONNECTOR_HEARTBEAT,
            retry_policy=CONNECTOR_RETRY_POLICY,
        )
        self._status = "COMPLETED"
        return dict(result)

    @workflow.query
    def status(self) -> str:
        return self._status
