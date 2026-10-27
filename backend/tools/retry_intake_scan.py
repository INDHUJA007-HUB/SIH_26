"""Local operator retry after repairing an exhausted scan; never bypasses inspection."""

import argparse
import asyncio
from uuid import UUID, uuid4

from sqlalchemy import select
from temporalio.client import Client, WorkflowExecutionStatus

from workbench.adapters import tables as t
from workbench.platform.config import Settings
from workbench.platform.runtime_roles import build_runtime_engine

parser = argparse.ArgumentParser()
parser.add_argument("evidence_id", type=UUID)
arguments = parser.parse_args()
settings = Settings()
if settings.environment not in {"local", "test"}:
    raise SystemExit("Use reviewed organizational job operations in deployed environments")
engine = build_runtime_engine(settings.scan_database_url.get_secret_value(), "wb_scanner")
try:
    with engine.connect() as connection:
        evidence = connection.execute(
            select(t.evidence).where(t.evidence.c.id == str(arguments.evidence_id))
        ).first()
        if evidence is None or evidence.status != "SCAN_FAILED":
            raise SystemExit("Only failed, quarantined scans can be retried")
        events = connection.execute(
            select(t.outbox).where(
                t.outbox.c.application_id == evidence.application_id,
                t.outbox.c.event_type == "EvidenceUploadCompleted",
            )
        )
        event = next((row for row in events if row.payload["evidence_id"] == evidence.id), None)
        if event is None:
            raise SystemExit("The committed scan event is unavailable")
finally:
    engine.dispose()


async def retry() -> None:
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    state = await client.get_workflow_handle("outbox-" + event.id).describe()
    if state.status == WorkflowExecutionStatus.RUNNING:
        print("An automatic scan retry is still running")
        return
    if state.status not in {
        WorkflowExecutionStatus.FAILED,
        WorkflowExecutionStatus.CANCELED,
        WorkflowExecutionStatus.TERMINATED,
        WorkflowExecutionStatus.TIMED_OUT,
    }:
        raise SystemExit("Review the completed workflow before creating a retry")
    workflow_id = "scan-retry-" + evidence.id + "-" + uuid4().hex
    await client.start_workflow(
        "ScanEvidenceWorkflow", event.id, id=workflow_id, task_queue="intake"
    )
    print("Queued a complete checksum, malware and parser inspection:", workflow_id)


asyncio.run(retry())
