"""Outbox-backed timer and notification workflows. Histories contain opaque IDs only."""

from datetime import datetime, timedelta
from typing import Any

from temporalio import workflow


@workflow.defn
class DurableTimerWorkflow:
    @workflow.run
    async def run(self, event_id: str) -> dict[str, Any]:
        timer = await workflow.execute_activity(
            "load_durable_timer", event_id, start_to_close_timeout=timedelta(seconds=30)
        )
        if timer["status"] != "SCHEDULED":
            return dict(timer)
        remaining = datetime.fromisoformat(timer["deadline"]) - workflow.now()
        if remaining.total_seconds() > 0:
            await workflow.sleep(remaining)
        result = await workflow.execute_activity(
            "fire_durable_timer", event_id, start_to_close_timeout=timedelta(seconds=30)
        )
        return dict(result)


@workflow.defn
class NotificationDeliveryWorkflow:
    @workflow.run
    async def run(self, event_id: str) -> dict[str, Any]:
        result = await workflow.execute_activity(
            "deliver_notification", event_id, start_to_close_timeout=timedelta(seconds=30)
        )
        return dict(result)


@workflow.defn
class RectificationWorkflow:
    @workflow.run
    async def run(self, event_id: str) -> dict[str, Any]:
        result = await workflow.execute_activity(
            "reassess_response", event_id, start_to_close_timeout=timedelta(minutes=10)
        )
        return dict(result)


@workflow.defn
class MediaProcessingWorkflow:
    @workflow.run
    async def run(self, event_id: str) -> dict[str, Any]:
        result = await workflow.execute_activity(
            "process_media", event_id, start_to_close_timeout=timedelta(minutes=5)
        )
        return dict(result)
