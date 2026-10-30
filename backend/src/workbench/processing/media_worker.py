"""Isolated worker entry point for bounded video and image processing."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from workbench.activities.media_processing import process_media
from workbench.platform.config import Settings
from workbench.workflows.lifecycle import MediaProcessingWorkflow


async def main() -> None:
    settings = Settings()
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    with ThreadPoolExecutor(max_workers=1) as executor:
        await Worker(
            client,
            task_queue="media-processing",
            workflows=[MediaProcessingWorkflow],
            activities=[process_media],
            activity_executor=executor,
        ).run()


if __name__ == "__main__":
    asyncio.run(main())
