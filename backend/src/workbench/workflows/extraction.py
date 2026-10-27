"""Document extraction durable workflow."""

from typing import Any

from temporalio import workflow

from workbench.workflows.contracts import TaskQueue
from workbench.workflows.retry_policy import (
    DOCUMENT_RETRY_POLICY,
    TIMEOUT_DOCUMENT,
    TIMEOUT_DOCUMENT_HEARTBEAT,
)


@workflow.defn(name="DocumentExtractionWorkflow")
class DocumentExtractionWorkflow:
    def __init__(self) -> None:
        self._status = "INITIALIZED"

    @workflow.run
    async def run(self, input_dict: dict[str, Any]) -> dict[str, Any]:
        self._status = "RUNNING"
        result = await workflow.execute_activity(
            "extract_facts_activity",
            input_dict,
            task_queue=TaskQueue.DOCUMENT.value,
            start_to_close_timeout=TIMEOUT_DOCUMENT,
            heartbeat_timeout=TIMEOUT_DOCUMENT_HEARTBEAT,
            retry_policy=DOCUMENT_RETRY_POLICY,
        )
        self._status = "COMPLETED"
        return dict(result)

    @workflow.query
    def status(self) -> str:
        return self._status
