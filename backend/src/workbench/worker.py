"""Phase 1 development worker; production workflow operation is delivered later."""

import asyncio

from opentelemetry import trace
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from workbench.platform.config import Settings
from workbench.platform.telemetry import build_tracing, configure_logging, log_event
from workbench.workflows.foundation import FoundationWorkflow


@activity.defn(name="foundation_ping")
async def foundation_ping(reference: str) -> str:
    # Only opaque references belong in workflow history; do not log the input value.
    tracer = trace.get_tracer("workbench.activities")
    with tracer.start_as_current_span("activity.foundation_ping") as span:
        span.set_attribute("activity.type", "foundation_ping")
    log_event(
        "activity_completed",
        activity="foundation_ping",
        outcome="success",
        workflow_id=activity.info().workflow_id,
    )
    return "SYNTHETIC_PLATFORM_OK" if reference else "EMPTY_REFERENCE"


async def main() -> None:
    settings = Settings()
    configure_logging()
    provider = build_tracing(settings)
    trace.set_tracer_provider(provider)
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[FoundationWorkflow],
        activities=[foundation_ping],
    )
    try:
        await worker.run()
    finally:
        provider.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
