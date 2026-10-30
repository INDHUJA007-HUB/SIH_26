"""Response window timer durable workflow with pause/cancel/extend support."""

from datetime import timedelta
from typing import Any

from temporalio import workflow

from workbench.workflows.contracts import TaskQueue
from workbench.workflows.retry_policy import TIMEOUT_COORDINATION


@workflow.defn(name="ResponseWindowTimerWorkflow")
class ResponseWindowTimerWorkflow:
    def __init__(self) -> None:
        self._status = "ACTIVE"
        self._cancelled = False
        self._extended_seconds = 0
        self._generation = 0

    @workflow.run
    async def run(self, input_dict: dict[str, Any]) -> dict[str, Any]:
        # Record initial timer check activity
        activity_res = await workflow.execute_activity(
            "wait_response_window_activity",
            input_dict,
            task_queue=TaskQueue.COORDINATION.value,
            start_to_close_timeout=TIMEOUT_COORDINATION,
        )

        duration = input_dict.get("duration_seconds", 3600)
        deadline = workflow.now() + timedelta(seconds=duration)
        while not self._cancelled:
            generation = self._generation
            remaining = deadline - workflow.now()
            if remaining.total_seconds() <= 0:
                break

            def changed(expected: int = generation) -> bool:
                return self._cancelled or self._generation != expected

            try:
                await workflow.wait_condition(
                    changed,
                    timeout=remaining,
                )
            except TimeoutError:
                break
            deadline += timedelta(seconds=self._extended_seconds)
            self._extended_seconds = 0

        if self._cancelled:
            self._status = "CANCELLED"
        else:
            self._status = "EXPIRED"

        return {
            "window_id": input_dict.get("window_id"),
            "status": self._status,
            "activity_result": activity_res,
        }

    @workflow.signal
    def cancel_timer(self) -> None:
        self._cancelled = True

    @workflow.signal
    def extend_timer(self, seconds: int) -> None:
        if seconds > 0:
            self._extended_seconds += seconds
            self._generation += 1

    @workflow.query
    def status(self) -> str:
        return self._status
