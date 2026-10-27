"""Restricted scan worker: pinned object -> ClamAV -> networkless parser -> acceptance."""

import asyncio
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from workbench.adapters import tables as t
from workbench.adapters.domain_store import now, row, uid
from workbench.adapters.malware import MalwareScanner
from workbench.adapters.object_storage import ObjectStorage
from workbench.platform.config import Settings
from workbench.platform.intake_metrics import increment, start_worker_metrics
from workbench.platform.runtime_roles import build_runtime_engine
from workbench.platform.telemetry import configure_logging, log_event


def cleanup_job(settings: Settings, evidence_id: str) -> None:
    """Remove only a terminal job's transient files; originals remain versioned in S3."""
    job = str(UUID(evidence_id))
    try:
        for name in [job + ".json", job + ".bin", job + ".tmp"]:
            (settings.scan_input_directory / name).unlink(missing_ok=True)
        marker = settings.scan_input_directory / (job + ".cleanup")
        marker.touch()
        deadline = time.monotonic() + 2
        while (settings.scan_output_directory / (job + ".result.json")).exists():
            if time.monotonic() > deadline:
                return
            time.sleep(0.1)
        marker.unlink(missing_ok=True)
    except OSError:
        log_event("scan_scratch_cleanup_pending", error_code="SCRATCH_CLEANUP_PENDING")


def scan_event(settings: Settings, event_id: str) -> str:
    engine = build_runtime_engine(settings.scan_database_url.get_secret_value(), "wb_scanner")
    storage = ObjectStorage(settings)
    try:
        with engine.begin() as connection:
            event = row(
                connection.execute(select(t.outbox).where(t.outbox.c.id == event_id)).first()
            )
            if not event or event["event_type"] != "EvidenceUploadCompleted":
                raise ValueError("Unsupported scan event")
            evidence = row(
                connection.execute(
                    select(t.evidence)
                    .where(t.evidence.c.id == event["payload"]["evidence_id"])
                    .with_for_update()
                ).first()
            )
            if evidence["status"] in {"ACCEPTED", "REJECTED"}:
                cleanup_job(settings, evidence["id"])
                return str(evidence["status"])
            connection.execute(
                update(t.evidence)
                .where(t.evidence.c.id == evidence["id"])
                .values(status="SCANNING", scan_started_at=now())
            )
        settings.scan_input_directory.mkdir(exist_ok=True, parents=True)
        settings.scan_output_directory.mkdir(exist_ok=True, parents=True)
        source = settings.scan_input_directory / (evidence["id"] + ".bin")
        body = storage.read(
            evidence["quarantine_key"], evidence["quarantine_version"], storage.quarantine
        )
        checksum, size = hashlib.sha256(), 0
        try:
            with source.open("wb") as file:
                while chunk := body.read(64 * 1024):
                    size += len(chunk)
                    if size > evidence["size_bytes"] or size > settings.max_upload_bytes:
                        raise ValueError("SIZE_MISMATCH")
                    checksum.update(chunk)
                    file.write(chunk)
        finally:
            body.close()
        if size != evidence["size_bytes"] or checksum.hexdigest() != evidence["sha256"]:
            inspection: dict[str, Any] = {"status": "REJECTED", "reason": "CHECKSUM_MISMATCH"}
        else:
            malware = MalwareScanner(
                settings.scanner_host,
                settings.scanner_port,
                settings.scanner_max_signature_age_hours,
            ).scan(source)
            if malware["status"] == "REJECTED":
                inspection = malware
            else:
                request = settings.scan_input_directory / (evidence["id"] + ".json")
                if not request.exists():
                    temporary = request.with_suffix(".tmp")
                    temporary.write_text(
                        json.dumps(
                            {
                                "size": size,
                                "sha256": evidence["sha256"],
                                "media_type": evidence["media_type"],
                                "max_pdf_pages": settings.max_pdf_pages,
                                "max_video_seconds": settings.max_video_seconds,
                            }
                        ),
                        encoding="utf-8",
                    )
                    os.replace(temporary, request)
                result = settings.scan_output_directory / (evidence["id"] + ".result.json")
                deadline = time.monotonic() + settings.parser_timeout_seconds
                while not result.exists():
                    if time.monotonic() > deadline:
                        raise RuntimeError("PARSER_SERVICE_UNAVAILABLE")
                    time.sleep(0.2)
                inspection = json.loads(result.read_text(encoding="utf-8"))
                inspection["engine"] = malware["engine"]
        clean_key = clean_version = None
        derivative_values = []
        if inspection["status"] == "ACCEPTED":
            if inspection.get("sha256") != evidence["sha256"]:
                raise RuntimeError("PARSER_RESULT_BINDING_FAILED")
            clean_key = (
                f"original/{evidence['institution_id']}/{evidence['application_id']}/"
                f"{evidence['id']}/{evidence['sha256']}"
            )
            clean_version = storage.copy_clean(evidence, clean_key)
            for item in inspection.get("derivatives", []):
                if Path(item["filename"]).name != item["filename"] or not item["filename"].endswith(
                    ".png"
                ):
                    raise RuntimeError("INVALID_DERIVATIVE_REFERENCE")
                path = settings.scan_output_directory / evidence["id"] / item["filename"]
                data = path.read_bytes()
                if (
                    not data.startswith(b"\x89PNG\r\n\x1a\n")
                    or len(data) > 8 * 1024 * 1024
                    or hashlib.sha256(data).hexdigest() != item["sha256"]
                ):
                    raise RuntimeError("INVALID_DERIVATIVE_CONTENT")
                key = f"derivative/{evidence['id']}/{item['page']}/{item['sha256']}.png"
                result = storage.client.put_object(
                    Bucket=storage.clean,
                    Key=key,
                    Body=data,
                    ContentType="image/png",
                    ServerSideEncryption="AES256",
                    Metadata={"sha256": item["sha256"]},
                )
                derivative_values.append(
                    {
                        "id": uid(),
                        "institution_id": evidence["institution_id"],
                        "application_id": evidence["application_id"],
                        "evidence_id": evidence["id"],
                        "kind": item["kind"],
                        "page": item["page"],
                        "object_key": key,
                        "object_version": result["VersionId"],
                        "sha256": item["sha256"],
                        "size_bytes": len(data),
                        "media_type": "image/png",
                        "metadata": {**item["metadata"], "generator": "networkless-inspection-v1"},
                    }
                )
        with engine.begin() as connection:
            current = row(
                connection.execute(
                    select(t.evidence).where(t.evidence.c.id == evidence["id"]).with_for_update()
                ).first()
            )
            if current["status"] in {"ACCEPTED", "REJECTED"}:
                return str(current["status"])
            for value in derivative_values:
                connection.execute(
                    pg_insert(t.derivatives).values(**value).on_conflict_do_nothing()
                )
            status = "ACCEPTED" if inspection["status"] == "ACCEPTED" else "REJECTED"
            metadata = {
                **inspection.get("metadata", {}),
                "scanner": inspection.get("engine", ""),
                "inspection_profile": "networkless-inspection-v1",
            }
            connection.execute(
                update(t.evidence)
                .where(t.evidence.c.id == evidence["id"])
                .values(
                    status=status,
                    reason_code=inspection.get("reason"),
                    clean_key=clean_key,
                    clean_version=clean_version,
                    metadata=metadata,
                )
            )
            connection.execute(
                pg_insert(t.receipts).values(event_id=event_id).on_conflict_do_nothing()
            )
            connection.execute(
                update(t.tasks)
                .where(
                    t.tasks.c.resource_id == evidence["id"],
                    t.tasks.c.kind == "SCAN_RETRY_REQUIRED",
                    t.tasks.c.state == "OPEN",
                )
                .values(state="RESOLVED")
            )
            connection.execute(
                text(
                    "SELECT wb.append_audit(:id,:inst,:app,:kind,CAST(:payload AS jsonb),:request)"
                ),
                {
                    "id": uid(),
                    "inst": evidence["institution_id"],
                    "app": evidence["application_id"],
                    "kind": "EvidenceAccepted" if status == "ACCEPTED" else "EvidenceRejected",
                    "payload": json.dumps(
                        {
                            "evidence_id": evidence["id"],
                            "reason": inspection.get("reason"),
                            "sha256": evidence["sha256"],
                        }
                    ),
                    "request": event_id,
                },
            )
        cleanup_job(settings, evidence["id"])
        return status
    except Exception:
        increment("workbench_scan_failures_total")
        if "evidence" in locals() and evidence:
            with engine.begin() as connection:
                connection.execute(
                    update(t.evidence)
                    .where(
                        t.evidence.c.id == evidence["id"],
                        t.evidence.c.status.notin_(["ACCEPTED", "REJECTED"]),
                    )
                    .values(status="SCAN_FAILED", reason_code="SCANNER_UNAVAILABLE")
                )
                connection.execute(
                    pg_insert(t.tasks)
                    .values(
                        id=uid(),
                        institution_id=evidence["institution_id"],
                        application_id=evidence["application_id"],
                        kind="SCAN_RETRY_REQUIRED",
                        resource_id=evidence["id"],
                        state="OPEN",
                        details={"event_id": event_id},
                    )
                    .on_conflict_do_nothing()
                )
        raise
    finally:
        engine.dispose()


@activity.defn(name="scan_evidence")
def scan_evidence(event_id: str) -> str:
    return scan_event(Settings(), event_id)


async def main() -> None:
    settings = Settings()
    configure_logging()
    start_worker_metrics()
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    with ThreadPoolExecutor(max_workers=1) as executor:
        worker = Worker(
            client,
            task_queue="evidence-scan",
            activities=[scan_evidence],
            activity_executor=executor,
            max_concurrent_activities=1,
        )
        log_event("scan_worker_started", service="workbench-scanner")
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
