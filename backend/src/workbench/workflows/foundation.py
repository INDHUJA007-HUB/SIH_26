"""Minimal deterministic workflow used to verify the Phase 1 platform."""

from datetime import timedelta

from temporalio import workflow


@workflow.defn
class FoundationWorkflow:
    @workflow.run
    async def run(self, reference: str) -> str:
        result = await workflow.execute_activity(
            "foundation_ping",
            reference,
            start_to_close_timeout=timedelta(seconds=10),
            result_type=str,
        )
        if not isinstance(result, str):
            raise TypeError("Foundation activity must return a string")
        return result
