"""Durable policy reminder waits; approval decisions are never automated here."""

from datetime import datetime, timedelta
from typing import Any

from temporalio import workflow


@workflow.defn
class NiyamDeadlineWorkflow:
    @workflow.run
    async def run(self, event_id: str) -> dict[str, Any]:
        plan = await workflow.execute_activity(
            "load_niyam_deadline", event_id, start_to_close_timeout=timedelta(seconds=30)
        )
        for trigger in plan["triggers"]:
            wait = datetime.fromisoformat(trigger["at"]) - workflow.now()
            if wait.total_seconds() > 0:
                await workflow.sleep(wait)
            await workflow.execute_activity(
                "fire_niyam_deadline",
                {"event_id": event_id, "key": trigger["key"]},
                start_to_close_timeout=timedelta(seconds=30),
            )
        return {"evaluated": len(plan["triggers"])}
