"""Worker for persisted timer and notification intents."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from workbench.activities.lifecycle import (
    deliver_notification,
    fire_durable_timer,
    load_durable_timer,
)
from workbench.activities.niyamflow import fire_niyam_deadline, load_niyam_deadline
from workbench.activities.reassessment import reassess_response
from workbench.platform.config import Settings
from workbench.workflows.lifecycle import (
    DurableTimerWorkflow,
    NotificationDeliveryWorkflow,
    RectificationWorkflow,
)
from workbench.workflows.niyamflow import NiyamDeadlineWorkflow


async def main() -> None:
    settings = Settings()
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    with ThreadPoolExecutor(max_workers=4) as executor:
        await Worker(
            client,
            task_queue="lifecycle",
            workflows=[
                DurableTimerWorkflow,
                NotificationDeliveryWorkflow,
                RectificationWorkflow,
                NiyamDeadlineWorkflow,
            ],
            activities=[
                deliver_notification,
                fire_durable_timer,
                load_durable_timer,
                reassess_response,
                load_niyam_deadline,
                fire_niyam_deadline,
            ],
            activity_executor=executor,
        ).run()


if __name__ == "__main__":
    asyncio.run(main())
