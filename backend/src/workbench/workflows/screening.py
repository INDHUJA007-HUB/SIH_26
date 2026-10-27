"""Evidence screening durable workflow."""

from typing import Any

from temporalio import workflow

from workbench.workflows.contracts import TaskQueue
from workbench.workflows.retry_policy import (
    SCAN_RETRY_POLICY,
    TIMEOUT_SCAN,
    TIMEOUT_SCAN_HEARTBEAT,
)


@workflow.defn(name="EvidenceScreeningWorkflow")
class EvidenceScreeningWorkflow:
    def __init__(self) -> None:
        self._status = "INITIALIZED"

    @workflow.run
    async def run(self, input_dict: dict[str, Any]) -> dict[str, Any]:
        self._status = "RUNNING"
        result = await workflow.execute_activity(
            "screen_evidence_activity",
            input_dict,
            task_queue=TaskQueue.SCAN.value,
            start_to_close_timeout=TIMEOUT_SCAN,
            heartbeat_timeout=TIMEOUT_SCAN_HEARTBEAT,
            retry_policy=SCAN_RETRY_POLICY,
        )
        self._status = "COMPLETED"
        return dict(result)

    @workflow.query
    def status(self) -> str:
        return self._status
