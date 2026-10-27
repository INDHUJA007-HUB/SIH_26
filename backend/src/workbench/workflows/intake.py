"""Reference-only intake coordination. Scanning is on a separate restricted task queue."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class ScanEvidenceWorkflow:
    @workflow.run
    async def run(self, event_id: str) -> str:
        result = await workflow.execute_activity(
            "scan_evidence",
            event_id,
            task_queue="evidence-scan",
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=3),
            result_type=str,
        )
        return str(result)


@workflow.defn
class IntakeReceiptWorkflow:
    @workflow.run
    async def run(self, event_id: str) -> str:
        result = await workflow.execute_activity(
            "record_intake_receipt",
            event_id,
            start_to_close_timeout=timedelta(seconds=15),
            result_type=str,
        )
        return str(result)
