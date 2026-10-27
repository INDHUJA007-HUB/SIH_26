"""Authorized original/derivative streaming with durable attempt and completion records."""

from collections.abc import Iterator
from typing import Any

from sqlalchemy import select, text

from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore, row, uid
from workbench.adapters.object_storage import ObjectStorage
from workbench.contracts.intake import Principal
from workbench.modules.evidence.policy import byte_range, safe_filename
from workbench.platform.errors import ApplicationError
from workbench.platform.intake_metrics import increment
from workbench.platform.telemetry import log_event


class DeliveryService:
    def __init__(self, store: DomainStore, storage: ObjectStorage) -> None:
        self.store, self.storage = store, storage

    def history(
        self, principal: Principal, application_id: str, after: str, limit: int
    ) -> list[dict[str, Any]]:
        with self.store.transaction(principal) as connection:
            self.store.application(connection, application_id)
            return [
                {
                    key: value
                    for key, value in row(item).items()
                    if key
                    not in {"quarantine_key", "quarantine_version", "clean_key", "clean_version"}
                }
                for item in connection.execute(
                    select(t.evidence)
                    .where(t.evidence.c.application_id == application_id, t.evidence.c.id > after)
                    .order_by(t.evidence.c.id)
                    .limit(limit)
                )
            ]

    def metadata(self, principal: Principal, evidence_id: str) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            result = row(
                connection.execute(select(t.evidence).where(t.evidence.c.id == evidence_id)).first()
            )
            if not result:
                raise ApplicationError("NOT_FOUND", "Evidence is not available", 404)
            return {
                key: value
                for key, value in result.items()
                if key not in {"quarantine_key", "quarantine_version", "clean_key", "clean_version"}
            }

    def prepare(
        self,
        principal: Principal,
        evidence_id: str,
        page: int | None,
        range_header: str | None,
        request: str,
        *,
        head_only: bool = False,
    ) -> tuple[Iterator[bytes], dict[str, str], int]:
        attempt_id = uid()
        error: ApplicationError | None = None
        with self.store.transaction(principal, delivery=True) as connection:
            evidence = row(
                connection.execute(select(t.evidence).where(t.evidence.c.id == evidence_id)).first()
            )
            if not evidence:
                error = ApplicationError("NOT_FOUND", "Evidence is not available", 404)
            elif evidence["status"] != "ACCEPTED":
                error = ApplicationError(
                    "EVIDENCE_QUARANTINED", "Evidence is not accepted for delivery", 409
                )
            resource = evidence
            if not error and page is not None:
                resource = row(
                    connection.execute(
                        select(t.derivatives).where(
                            t.derivatives.c.evidence_id == evidence_id, t.derivatives.c.page == page
                        )
                    ).first()
                )
                if not resource:
                    error = ApplicationError("NOT_FOUND", "The derivative is not available", 404)
            if not error:
                try:
                    start, end, status = byte_range(range_header, resource["size_bytes"])
                except ApplicationError as caught:
                    if caught.status == 416:
                        caught.headers = {"Content-Range": f"bytes */{resource['size_bytes']}"}
                    error = caught
            connection.execute(
                text(
                    "SELECT wb.access_attempt("
                    ":id,:inst,:app,:ev,:resource,:action,:request,:allowed)"
                ),
                {
                    "id": attempt_id,
                    "inst": evidence.get("institution_id"),
                    "app": evidence.get("application_id"),
                    "ev": evidence_id,
                    "resource": evidence_id + (f":page:{page}" if page else ":original"),
                    "action": "HEAD" if head_only else "PREVIEW" if page else "DOWNLOAD",
                    "request": request,
                    "allowed": error is None,
                },
            )
        if error:
            raise error
        key, version = (
            (resource["object_key"], resource["object_version"])
            if page is not None
            else (evidence["clean_key"], evidence["clean_version"])
        )
        body = None
        if not head_only:
            try:
                body = self.storage.read(key, version, self.storage.clean, start, end)
            except Exception:
                self.finish(attempt_id, 0, "FAILED")
                raise ApplicationError(
                    "STORAGE_UNAVAILABLE", "Evidence storage is temporarily unavailable", 503
                ) from None
        headers = {
            "Content-Length": str(end - start + 1),
            "Accept-Ranges": "bytes",
            "ETag": '"' + resource["sha256"] + '"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Content-Type": resource["media_type"],
            "Content-Disposition": 'inline; filename="preview.png"'
            if page is not None
            else 'attachment; filename="' + safe_filename(evidence["filename"]) + '"',
        }
        if status == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{resource['size_bytes']}"
        if head_only:
            self.finish(attempt_id, 0, "COMPLETED")

        return DeliveryStream(self, body, attempt_id, end - start + 1, head_only), headers, status

    def finish(self, attempt_id: str, served: int, result: str) -> None:
        try:
            with self.store.delivery_engine.begin() as connection:
                connection.execute(
                    text("SELECT wb.access_finish(:id,:attempt,:bytes,:result)"),
                    {"id": uid(), "attempt": attempt_id, "bytes": served, "result": result},
                )
        except Exception:
            increment("workbench_access_completion_failures_total")
            log_event("access_completion_failed", error_code="ACCESS_COMPLETION_FAILURE")


class DeliveryStream(Iterator[bytes]):
    """Close also records cancellation when the consumer never requests its first byte."""

    def __init__(
        self, service: DeliveryService, body: Any, attempt: str, remaining: int, head_only: bool
    ) -> None:
        self.service, self.body, self.attempt = service, body, attempt
        self.remaining, self.served = remaining, 0
        self.closed = head_only

    def __iter__(self) -> "DeliveryStream":
        return self

    def __next__(self) -> bytes:
        if self.closed:
            raise StopIteration
        if self.remaining == 0:
            self.close("COMPLETED")
            raise StopIteration
        try:
            chunk: bytes = self.body.read(min(64 * 1024, self.remaining))
            if not chunk:
                raise OSError("Object stream ended early")
        except Exception:
            self.close("FAILED")
            raise
        self.served += len(chunk)
        self.remaining -= len(chunk)
        return chunk

    def close(self, result: str = "ABORTED") -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.body.close()
        finally:
            self.service.finish(self.attempt, self.served, result)
