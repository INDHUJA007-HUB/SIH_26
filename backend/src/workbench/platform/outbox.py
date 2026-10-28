"""Leased transactional outbox relay; repeated starts have stable workflow IDs."""

import asyncio
from contextlib import suppress
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select, update
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from workbench.adapters import tables as t
from workbench.adapters.domain_store import now, row
from workbench.platform.config import Settings
from workbench.platform.intake_metrics import increment, set_metric, start_worker_metrics
from workbench.platform.runtime_roles import build_runtime_engine
from workbench.platform.telemetry import configure_logging, log_event


async def dispatch_once(settings: Settings) -> int:
    engine = build_runtime_engine(settings.relay_database_url.get_secret_value(), "wb_relay")
    lease_owner = str(uuid4())
    with engine.begin() as connection:
        oldest = connection.scalar(
            select(func.min(t.outbox.c.created_at)).where(t.outbox.c.delivered_at.is_(None))
        )
        set_metric(
            "workbench_outbox_oldest_pending_seconds",
            (now() - oldest).total_seconds() if oldest else 0,
        )
        events = [
            row(item)
            for item in connection.execute(
                select(t.outbox)
                .where(
                    t.outbox.c.delivered_at.is_(None),
                    t.outbox.c.available_at <= now(),
                    (t.outbox.c.lease_until.is_(None)) | (t.outbox.c.lease_until < now()),
                )
                .order_by(t.outbox.c.created_at)
                .limit(20)
                .with_for_update(skip_locked=True)
            )
        ]
        for event in events:
            connection.execute(
                update(t.outbox)
                .where(t.outbox.c.id == event["id"])
                .values(
                    lease_owner=lease_owner,
                    lease_until=now() + timedelta(seconds=45),
                    attempts=event["attempts"] + 1,
                )
            )
    try:
        client = (
            await asyncio.wait_for(
                Client.connect(settings.temporal_address, namespace=settings.temporal_namespace),
                timeout=5,
            )
            if events
            else None
        )
        for event in events:
            try:
                workflow_name = (
                    "ScanEvidenceWorkflow"
                    if event["event_type"] == "EvidenceUploadCompleted"
                    else "IntakeReceiptWorkflow"
                )
                assert client is not None
                with suppress(WorkflowAlreadyStartedError):
                    await client.start_workflow(
                        workflow_name,
                        event["id"],
                        id="outbox-" + event["id"],
                        task_queue="intake",
                        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                    )
                with engine.begin() as connection:
                    connection.execute(
                        update(t.outbox)
                        .where(t.outbox.c.id == event["id"], t.outbox.c.lease_owner == lease_owner)
                        .values(delivered_at=now(), lease_until=None)
                    )
            except Exception:
                increment("workbench_outbox_dispatch_failures_total")
                with engine.begin() as connection:
                    connection.execute(
                        update(t.outbox)
                        .where(t.outbox.c.id == event["id"], t.outbox.c.lease_owner == lease_owner)
                        .values(
                            lease_until=None,
                            available_at=now()
                            + timedelta(seconds=min(300, 2 ** min(event["attempts"] + 1, 8))),
                        )
                    )
                log_event("outbox_dispatch_failed", error_code="OUTBOX_RETRY")
    finally:
        engine.dispose()
    return len(events)


async def main() -> None:
    settings = Settings()
    configure_logging()
    with suppress(Exception):
        start_worker_metrics()
    while True:
        try:
            await dispatch_once(settings)
        except Exception:
            log_event("outbox_unavailable", error_code="OUTBOX_UNAVAILABLE")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
