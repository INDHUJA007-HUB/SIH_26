"""Rule evaluation durable workflow."""

from typing import Any

from temporalio import workflow

from workbench.workflows.contracts import TaskQueue
from workbench.workflows.retry_policy import (
    EVALUATION_RETRY_POLICY,
    TIMEOUT_EVALUATION,
)


@workflow.defn(name="RuleEvaluationWorkflow")
class RuleEvaluationWorkflow:
    def __init__(self) -> None:
        self._status = "INITIALIZED"

    @workflow.run
    async def run(self, input_dict: dict[str, Any]) -> dict[str, Any]:
        self._status = "RUNNING"
        result = await workflow.execute_activity(
            "evaluate_rules_activity",
            input_dict,
            task_queue=TaskQueue.EVALUATION.value,
            start_to_close_timeout=TIMEOUT_EVALUATION,
            retry_policy=EVALUATION_RETRY_POLICY,
        )
        self._status = "COMPLETED"
        return dict(result)

    @workflow.query
    def status(self) -> str:
        return self._status
