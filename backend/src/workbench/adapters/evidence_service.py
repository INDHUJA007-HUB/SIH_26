"""Quota-bound upload sessions and exact-version quarantine acceptance."""

import math
from datetime import timedelta
from typing import Any

from botocore.exceptions import ClientError
from sqlalchemy import insert, select, text, update

from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore, now, row, uid
from workbench.adapters.object_storage import ObjectStorage
from workbench.contracts.intake import Principal
from workbench.modules.applications.domain import require_draft
from workbench.modules.evidence.policy import safe_filename
from workbench.platform.config import Settings
from workbench.platform.errors import ApplicationError


class EvidenceService:
    def __init__(self, store: DomainStore, storage: ObjectStorage, settings: Settings) -> None:
        self.store, self.storage, self.settings = store, storage, settings

    def initiate(
        self, principal: Principal, app_id: str, payload: dict[str, Any], key: str, request: str
    ) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            application = self.store.application(connection, app_id, lock=True)
            self.store.institution_editor(connection, application["institution_id"])
            actor = self.store.actor(connection)
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:id,0))"),
                {"id": "quota:" + application["institution_id"]},
            )

            def operation() -> dict[str, Any]:
                require_draft(application["stage"])
                if payload["size_bytes"] > self.settings.max_upload_bytes:
                    raise ApplicationError(
                        "UPLOAD_LIMIT", "The file exceeds the configured size limit", 413
                    )
                slot = connection.execute(
                    select(t.slots.c.id).where(
                        t.slots.c.id == payload["slot_id"], t.slots.c.application_id == app_id
                    )
                ).first()
                if not slot:
                    raise ApplicationError("NOT_FOUND", "Evidence slot is not available", 404)
                parent = payload.get("parent_version_id")
                if (
                    parent
                    and not connection.execute(
                        select(t.evidence.c.id).where(
                            t.evidence.c.id == parent,
                            t.evidence.c.application_id == app_id,
                            t.evidence.c.slot_id == payload["slot_id"],
                        )
                    ).first()
                ):
                    raise ApplicationError(
                        "NOT_FOUND", "Parent version is not available in this slot", 404
                    )
                reserved = [
                    row(item)
                    for item in connection.execute(
                        select(t.uploads).where(
                            t.uploads.c.institution_id == application["institution_id"],
                            ((t.uploads.c.status == "PENDING") & (t.uploads.c.expires_at > now()))
                            | (t.uploads.c.status == "COMPLETED"),
                        )
                    )
                ]
                if (
                    sum(item["status"] == "PENDING" for item in reserved)
                    >= self.settings.max_pending_uploads
                ):
                    raise ApplicationError("UPLOAD_QUOTA", "Too many active uploads", 429)
                total = sum(item["expected_size"] for item in reserved)
                own = sum(
                    item["expected_size"] for item in reserved if item["actor_id"] == actor["id"]
                )
                if (
                    total + payload["size_bytes"] > self.settings.institution_quota_bytes
                    or own + payload["size_bytes"] > self.settings.actor_quota_bytes
                ):
                    raise ApplicationError(
                        "UPLOAD_QUOTA", "The storage reservation quota is exceeded", 429
                    )
                session_id = uid()
                object_key = f"quarantine/{application['institution_id']}/{app_id}/{session_id}"
                multipart_id = (
                    self.storage.initiate_multipart(object_key, payload["media_type"])
                    if payload["mode"] == "MULTIPART"
                    else None
                )
                connection.execute(
                    insert(t.uploads).values(
                        id=session_id,
                        institution_id=application["institution_id"],
                        application_id=app_id,
                        slot_id=payload["slot_id"],
                        actor_id=actor["id"],
                        filename=safe_filename(payload["filename"]),
                        media_type=payload["media_type"],
                        expected_size=payload["size_bytes"],
                        expected_sha256=payload["sha256"],
                        object_key=object_key,
                        mode=payload["mode"],
                        multipart_id=multipart_id,
                        part_size=self.settings.multipart_part_bytes,
                        status="PENDING",
                        expires_at=now() + timedelta(seconds=self.settings.upload_ttl_seconds),
                        parent_version_id=parent,
                    )
                )
                self.store.audit(
                    connection,
                    application["institution_id"],
                    app_id,
                    "UploadSessionCreated",
                    {
                        "upload_id": session_id,
                        "size_bytes": payload["size_bytes"],
                        "mode": payload["mode"],
                    },
                    request,
                )
                return {"id": session_id}

            result = self.store.command(
                connection, "initiate-upload:" + app_id, key, payload, operation
            )
        return self.describe(principal, result["id"], grant=True)

    def describe(
        self, principal: Principal, session_id: str, grant: bool = False
    ) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            upload = row(
                connection.execute(select(t.uploads).where(t.uploads.c.id == session_id)).first()
            )
            if not upload:
                raise ApplicationError("NOT_FOUND", "Upload session is not available", 404)
            result = {
                name: upload[name]
                for name in (
                    "id",
                    "application_id",
                    "slot_id",
                    "mode",
                    "status",
                    "expires_at",
                    "expected_size",
                )
            }
            if grant:
                self.store.institution_editor(connection, upload["institution_id"])
                if upload["status"] != "PENDING" or upload["expires_at"] <= now():
                    raise ApplicationError(
                        "UPLOAD_EXPIRED", "The upload grant is no longer active", 410
                    )
                if upload["mode"] == "SINGLE":
                    result["grant"] = self.storage.grant(
                        upload, max(1, int((upload["expires_at"] - now()).total_seconds()))
                    )
                else:
                    result["part_count"] = math.ceil(upload["expected_size"] / upload["part_size"])
                    result["part_size"] = upload["part_size"]
            return result

    def part_grant(self, principal: Principal, session_id: str, number: int) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            upload = row(
                connection.execute(select(t.uploads).where(t.uploads.c.id == session_id)).first()
            )
            if not upload:
                raise ApplicationError("NOT_FOUND", "Upload session is not available", 404)
            self.store.institution_editor(connection, upload["institution_id"])
            application = self.store.application(connection, upload["application_id"])
            require_draft(application["stage"])
            count = math.ceil(upload["expected_size"] / upload["part_size"])
            if upload["status"] != "PENDING" or upload["expires_at"] <= now():
                raise ApplicationError("UPLOAD_EXPIRED", "The upload session has expired", 410)
            if upload["mode"] != "MULTIPART" or not 1 <= number <= count:
                raise ApplicationError("INVALID_PART", "The requested part is not planned", 422)
            size = min(
                upload["part_size"], upload["expected_size"] - (number - 1) * upload["part_size"]
            )
            return self.storage.part_grant(
                upload, number, size, max(1, int((upload["expires_at"] - now()).total_seconds()))
            )

    def abort(self, principal: Principal, session_id: str, request: str) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            upload = row(
                connection.execute(
                    select(t.uploads).where(t.uploads.c.id == session_id).with_for_update()
                ).first()
            )
            if not upload:
                raise ApplicationError("NOT_FOUND", "Upload session is not available", 404)
            self.store.institution_editor(connection, upload["institution_id"])
            if upload["status"] in {"ABORTED", "EXPIRED"}:
                return {"id": session_id, "status": upload["status"]}
            if upload["status"] != "PENDING":
                raise ApplicationError(
                    "UPLOAD_FINALIZED", "Completed uploads cannot be aborted", 409
                )
            if upload["multipart_id"]:
                try:
                    self.storage.client.abort_multipart_upload(
                        Bucket=self.storage.quarantine,
                        Key=upload["object_key"],
                        UploadId=upload["multipart_id"],
                    )
                except ClientError as error:
                    if error.response["Error"]["Code"] != "NoSuchUpload":
                        raise
            connection.execute(
                update(t.uploads).where(t.uploads.c.id == session_id).values(status="ABORTED")
            )
            self.store.audit(
                connection,
                upload["institution_id"],
                upload["application_id"],
                "UploadAborted",
                {"upload_id": session_id},
                request,
            )
            return {"id": session_id, "status": "ABORTED"}

    def complete(
        self, principal: Principal, session_id: str, payload: dict[str, Any], key: str, request: str
    ) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            upload = row(
                connection.execute(
                    select(t.uploads).where(t.uploads.c.id == session_id).with_for_update()
                ).first()
            )
            if not upload:
                raise ApplicationError("NOT_FOUND", "Upload session is not available", 404)
            application = self.store.application(connection, upload["application_id"], lock=True)
            self.store.institution_editor(connection, upload["institution_id"])

            def operation() -> dict[str, Any]:
                existing = row(
                    connection.execute(
                        select(t.evidence).where(t.evidence.c.upload_id == session_id)
                    ).first()
                )
                if existing:
                    return {"id": existing["id"], "status": existing["status"]}
                require_draft(application["stage"])
                if upload["status"] != "PENDING" or upload["expires_at"] <= now():
                    raise ApplicationError(
                        "UPLOAD_EXPIRED", "The upload session is no longer active", 410
                    )
                version = payload.get("version_id")
                if upload["mode"] == "MULTIPART":
                    try:
                        parts = self.storage.parts(upload)
                        expected_count = math.ceil(upload["expected_size"] / upload["part_size"])
                        if len(parts) != expected_count or [p["PartNumber"] for p in parts] != list(
                            range(1, expected_count + 1)
                        ):
                            raise ApplicationError(
                                "INVALID_PARTS", "The multipart upload is incomplete", 409
                            )
                        for part in parts:
                            expected = min(
                                upload["part_size"],
                                upload["expected_size"]
                                - (part["PartNumber"] - 1) * upload["part_size"],
                            )
                            if part["Size"] != expected:
                                raise ApplicationError(
                                    "INVALID_PART_SIZE", "A part has an unexpected size", 409
                                )
                        version = self.storage.finish_multipart(upload, parts)
                    except ClientError as error:
                        if error.response["Error"]["Code"] != "NoSuchUpload":
                            raise
                        # Recover a provider completion committed before a database failure.
                        version = self.storage.head(upload["object_key"])["VersionId"]
                head = self.storage.head(upload["object_key"], version)
                if head["ContentLength"] != upload["expected_size"]:
                    raise ApplicationError(
                        "SIZE_MISMATCH", "The uploaded object has an unexpected size", 409
                    )
                if head.get("ContentType") != upload["media_type"]:
                    raise ApplicationError(
                        "TYPE_MISMATCH", "The uploaded object type does not match the grant", 409
                    )
                version = head.get("VersionId")
                if not version or version == "null":
                    raise ApplicationError(
                        "VERSIONING_REQUIRED", "Version-aware storage is required", 503
                    )
                evidence_id = uid()
                connection.execute(
                    insert(t.evidence).values(
                        id=evidence_id,
                        institution_id=upload["institution_id"],
                        application_id=upload["application_id"],
                        slot_id=upload["slot_id"],
                        upload_id=session_id,
                        parent_version_id=upload["parent_version_id"],
                        quarantine_key=upload["object_key"],
                        quarantine_version=version,
                        size_bytes=upload["expected_size"],
                        sha256=upload["expected_sha256"],
                        media_type=upload["media_type"],
                        filename=upload["filename"],
                        status="QUARANTINED",
                        metadata={},
                    )
                )
                connection.execute(
                    update(t.uploads)
                    .where(t.uploads.c.id == session_id)
                    .values(status="COMPLETED", object_version=version)
                )
                self.store.audit(
                    connection,
                    upload["institution_id"],
                    upload["application_id"],
                    "EvidenceQuarantined",
                    {"evidence_id": evidence_id, "upload_id": session_id},
                    request,
                )
                self.store.event(
                    connection, application, "EvidenceUploadCompleted", {"evidence_id": evidence_id}
                )
                return {"id": evidence_id, "status": "QUARANTINED"}

            return self.store.command(
                connection, "complete-upload:" + session_id, key, payload, operation
            )
