"""Intake coordinator and idempotent submission receipt activity."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from workbench.adapters import tables as t
from workbench.adapters.domain_store import row, uid
from workbench.platform.config import Settings
from workbench.platform.runtime_roles import build_runtime_engine
from workbench.workflows.intake import IntakeReceiptWorkflow, ScanEvidenceWorkflow


@activity.defn(name="record_intake_receipt")
def record_intake_receipt(event_id: str) -> str:
    engine = build_runtime_engine(Settings().worker_database_url.get_secret_value(), "wb_worker")
    try:
        with engine.begin() as connection:
            event = row(
                connection.execute(select(t.outbox).where(t.outbox.c.id == event_id)).first()
            )
            if not event:
                raise ValueError("Unknown intake event")
            connection.execute(
                pg_insert(t.receipts).values(event_id=event_id).on_conflict_do_nothing()
            )
            connection.execute(
                pg_insert(t.tasks)
                .values(
                    id=uid(),
                    institution_id=event["institution_id"],
                    application_id=event["application_id"],
                    kind="SCREENING_PENDING_PHASE_5",
                    resource_id=event_id,
                    state="OPEN",
                    details={"event_type": event["event_type"]},
                )
                .on_conflict_do_nothing()
            )
        return "RECEIPT_RECORDED"
    finally:
        engine.dispose()


async def main() -> None:
    settings = Settings()
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    with ThreadPoolExecutor(max_workers=2) as executor:
        await Worker(
            client,
            task_queue="intake",
            workflows=[ScanEvidenceWorkflow, IntakeReceiptWorkflow],
            activities=[record_intake_receipt],
            activity_executor=executor,
        ).run()


if __name__ == "__main__":
    asyncio.run(main())
