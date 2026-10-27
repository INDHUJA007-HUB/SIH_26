"""Media analysis durable workflow."""

from typing import Any

from temporalio import workflow

from workbench.workflows.contracts import TaskQueue
from workbench.workflows.retry_policy import (
    TIMEOUT_MEDIA,
    TIMEOUT_MEDIA_HEARTBEAT,
)


@workflow.defn(name="MediaAnalysisWorkflow")
class MediaAnalysisWorkflow:
    def __init__(self) -> None:
        self._status = "INITIALIZED"

    @workflow.run
    async def run(self, input_dict: dict[str, Any]) -> dict[str, Any]:
        self._status = "RUNNING"
        result = await workflow.execute_activity(
            "analyze_media_activity",
            input_dict,
            task_queue=TaskQueue.MEDIA.value,
            start_to_close_timeout=TIMEOUT_MEDIA,
            heartbeat_timeout=TIMEOUT_MEDIA_HEARTBEAT,
        )
        self._status = "COMPLETED"
        return dict(result)

    @workflow.query
    def status(self) -> str:
        return self._status
