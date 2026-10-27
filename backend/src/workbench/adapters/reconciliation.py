"""Version-specific intake reconciliation. Accepted originals are never automatically deleted."""

from datetime import timedelta

from botocore.exceptions import ClientError
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from workbench.adapters import tables as t
from workbench.adapters.domain_store import now, row, uid
from workbench.adapters.object_storage import ObjectStorage
from workbench.platform.config import Settings
from workbench.platform.intake_metrics import set_metric, start_worker_metrics
from workbench.platform.runtime_roles import build_runtime_engine


def reconcile_once(settings: Settings) -> dict[str, int]:
    engine = build_runtime_engine(settings.scan_database_url.get_secret_value(), "wb_scanner")
    storage = ObjectStorage(settings)
    counts = {"expired_uploads": 0, "missing_objects": 0, "stuck_scans": 0, "orphans": 0}
    try:
        with engine.begin() as connection:
            if not connection.scalar(text("SELECT pg_try_advisory_xact_lock(428404)")):
                return counts
            oldest = connection.scalar(
                select(func.min(t.evidence.c.created_at)).where(
                    t.evidence.c.status.in_(["QUARANTINED", "SCANNING", "SCAN_FAILED"])
                )
            )
            set_metric(
                "workbench_quarantine_oldest_seconds",
                (now() - oldest).total_seconds() if oldest else 0,
            )

            def cursor(name: str) -> dict[str, str]:
                return dict(
                    connection.scalar(
                        select(t.reconciliation_cursors.c.position).where(
                            t.reconciliation_cursors.c.name == name
                        )
                    )
                    or {}
                )

            def checkpoint(name: str, position: dict[str, str]) -> None:
                connection.execute(
                    pg_insert(t.reconciliation_cursors)
                    .values(name=name, position=position)
                    .on_conflict_do_update(index_elements=["name"], set_={"position": position})
                )

            uploads = [
                row(item)
                for item in connection.execute(
                    select(t.uploads)
                    .where(t.uploads.c.status == "PENDING", t.uploads.c.expires_at < now())
                    .with_for_update(skip_locked=True)
                    .limit(100)
                )
            ]
            for upload in uploads:
                if upload["multipart_id"]:
                    try:
                        storage.client.abort_multipart_upload(
                            Bucket=storage.quarantine,
                            Key=upload["object_key"],
                            UploadId=upload["multipart_id"],
                        )
                    except ClientError as error:
                        if error.response["Error"]["Code"] != "NoSuchUpload":
                            raise
                connection.execute(
                    update(t.uploads).where(t.uploads.c.id == upload["id"]).values(status="EXPIRED")
                )
                counts["expired_uploads"] += 1
            versions = [
                row(item)
                for item in connection.execute(
                    select(t.evidence)
                    .where(t.evidence.c.id > cursor("evidence").get("id", ""))
                    .order_by(t.evidence.c.id)
                    .limit(500)
                )
            ]
            checkpoint("evidence", {"id": versions[-1]["id"]} if versions else {})
            for version in versions:
                bucket = storage.clean if version["status"] == "ACCEPTED" else storage.quarantine
                key = (
                    version["clean_key"]
                    if version["status"] == "ACCEPTED"
                    else version["quarantine_key"]
                )
                object_version = (
                    version["clean_version"]
                    if version["status"] == "ACCEPTED"
                    else version["quarantine_version"]
                )
                kind = None
                try:
                    storage.head(key, object_version, bucket)
                except ClientError as error:
                    if error.response["Error"]["Code"] not in {"404", "NoSuchKey", "NoSuchVersion"}:
                        raise
                    kind = (
                        "MISSING_ACCEPTED_OBJECT"
                        if version["status"] == "ACCEPTED"
                        else "MISSING_QUARANTINE_OBJECT"
                    )
                    counts["missing_objects"] += 1
                if (
                    version["status"] in {"SCANNING", "SCAN_FAILED"}
                    and version["scan_started_at"]
                    and version["scan_started_at"] < now() - timedelta(minutes=5)
                ):
                    kind = kind or "SCAN_RETRY_REQUIRED"
                    counts["stuck_scans"] += 1
                if kind:
                    connection.execute(
                        pg_insert(t.tasks)
                        .values(
                            id=uid(),
                            institution_id=version["institution_id"],
                            application_id=version["application_id"],
                            kind=kind,
                            resource_id=version["id"],
                            state="OPEN",
                            details={"destructive_action": False},
                        )
                        .on_conflict_do_nothing()
                    )
            derivatives = [
                row(item)
                for item in connection.execute(
                    select(t.derivatives)
                    .where(t.derivatives.c.id > cursor("derivatives").get("id", ""))
                    .order_by(t.derivatives.c.id)
                    .limit(500)
                )
            ]
            checkpoint("derivatives", {"id": derivatives[-1]["id"]} if derivatives else {})
            for derivative in derivatives:
                try:
                    storage.head(
                        derivative["object_key"], derivative["object_version"], storage.clean
                    )
                except ClientError as error:
                    if error.response["Error"]["Code"] not in {"404", "NoSuchKey", "NoSuchVersion"}:
                        raise
                    counts["missing_objects"] += 1
                    connection.execute(
                        pg_insert(t.tasks)
                        .values(
                            id=uid(),
                            institution_id=derivative["institution_id"],
                            application_id=derivative["application_id"],
                            kind="MISSING_DERIVATIVE_OBJECT",
                            resource_id=derivative["id"],
                            state="OPEN",
                            details={"destructive_action": False},
                        )
                        .on_conflict_do_nothing()
                    )
            inventory = cursor("inventory")
            page = storage.client.list_object_versions(
                Bucket=storage.clean, MaxKeys=500, **inventory
            )
            checkpoint(
                "inventory",
                {
                    "KeyMarker": page["NextKeyMarker"],
                    "VersionIdMarker": page["NextVersionIdMarker"],
                }
                if page.get("IsTruncated")
                else {},
            )
            for inventory_page in [page]:
                for item in inventory_page.get("Versions", []):
                    original = connection.scalar(
                        select(t.evidence.c.id)
                        .where(
                            t.evidence.c.clean_key == item["Key"],
                            t.evidence.c.clean_version == item["VersionId"],
                        )
                        .limit(1)
                    )
                    derivative_id = connection.scalar(
                        select(t.derivatives.c.id)
                        .where(
                            t.derivatives.c.object_key == item["Key"],
                            t.derivatives.c.object_version == item["VersionId"],
                        )
                        .limit(1)
                    )
                    # Allow in-flight promotion to commit before reporting a storage orphan.
                    if (
                        not original
                        and not derivative_id
                        and item["LastModified"] < (now() - timedelta(minutes=10))
                    ):
                        counts["orphans"] += 1
                        connection.execute(
                            pg_insert(t.tasks)
                            .values(
                                id=uid(),
                                kind="ORPHAN_CLEAN_VERSION_REVIEW",
                                resource_id=item["Key"] + ":" + item["VersionId"],
                                state="OPEN",
                                details={"destructive_action": False},
                            )
                            .on_conflict_do_nothing()
                        )
        return counts
    finally:
        engine.dispose()


def main() -> None:
    import asyncio

    from workbench.platform.telemetry import configure_logging, log_event

    configure_logging()
    start_worker_metrics()

    async def run() -> None:
        while True:
            try:
                await asyncio.to_thread(reconcile_once, Settings())
                log_event("intake_reconciled", outcome="success")
            except Exception:
                log_event("reconciliation_unavailable", error_code="RECONCILIATION_RETRY")
            await asyncio.sleep(60)

    asyncio.run(run())


if __name__ == "__main__":
    main()
