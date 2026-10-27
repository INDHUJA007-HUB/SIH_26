"""Report generation durable workflow."""

from typing import Any

from temporalio import workflow

from workbench.workflows.contracts import TaskQueue
from workbench.workflows.retry_policy import TIMEOUT_REPORT


@workflow.defn(name="ReportGenerationWorkflow")
class ReportGenerationWorkflow:
    def __init__(self) -> None:
        self._status = "INITIALIZED"

    @workflow.run
    async def run(self, input_dict: dict[str, Any]) -> dict[str, Any]:
        self._status = "RUNNING"
        result = await workflow.execute_activity(
            "generate_report_activity",
            input_dict,
            task_queue=TaskQueue.REPORTING.value,
            start_to_close_timeout=TIMEOUT_REPORT,
        )
        self._status = "COMPLETED"
        return dict(result)

    @workflow.query
    def status(self) -> str:
        return self._status
