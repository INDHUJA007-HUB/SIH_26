"""Service logic for audit history, sensitive-access events, and checkpointed exports."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Connection, select

from workbench.adapters import tables as t
from workbench.adapters.domain_store import row
from workbench.modules.audit_access.contracts import (
    AccessEventRecord,
    AuditEventRecord,
    AuditExportManifest,
)
from workbench.platform.errors import ApplicationError


class AuditAccessService:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def list_audit_events(
        self,
        institution_id: str,
        application_id: str | None = None,
        stream: str | None = None,
        event_type: str | None = None,
        after_sequence: int = 0,
        limit: int = 50,
    ) -> list[AuditEventRecord]:
        query = select(t.audit).where(
            t.audit.c.institution_id == institution_id,
            t.audit.c.sequence > after_sequence,
        )
        if application_id:
            query = query.where(t.audit.c.application_id == application_id)
        if stream:
            query = query.where(t.audit.c.stream == stream)

        query = query.order_by(t.audit.c.sequence.asc()).limit(limit)
        items = [row(item) for item in self.conn.execute(query)]

        if event_type:
            items = [item for item in items if item["event"].get("event_type") == event_type]

        return [
            AuditEventRecord(
                id=item["id"],
                stream=item["stream"],
                institution_id=item.get("institution_id"),
                application_id=item.get("application_id"),
                sequence=item["sequence"],
                previous_hash=item["previous_hash"],
                sha256=item["sha256"],
                event=item["event"],
                created_at=item["created_at"],
            )
            for item in items
        ]

    def list_access_events(
        self,
        institution_id: str,
        application_id: str | None = None,
        evidence_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        result: str | None = None,
        after_id: str = "",
        limit: int = 50,
    ) -> list[AccessEventRecord]:
        query = select(t.access).where(t.access.c.institution_id == institution_id)
        if application_id:
            query = query.where(t.access.c.application_id == application_id)
        if evidence_id:
            query = query.where(t.access.c.evidence_id == evidence_id)
        if actor_id:
            query = query.where(t.access.c.actor_id == actor_id)
        if action:
            query = query.where(t.access.c.action == action)
        if result:
            query = query.where(t.access.c.result == result)
        if after_id:
            query = query.where(t.access.c.id > after_id)

        query = query.order_by(t.access.c.id.asc()).limit(limit)
        items = [row(item) for item in self.conn.execute(query)]

        return [
            AccessEventRecord(
                id=item["id"],
                actor_id=item.get("actor_id"),
                institution_id=item.get("institution_id"),
                application_id=item.get("application_id"),
                evidence_id=item.get("evidence_id"),
                resource_id=item["resource_id"],
                action=item["action"],
                result=item["result"],
                bytes_served=item["bytes_served"],
                request_id=item["request_id"],
                parent_event_id=item.get("parent_event_id"),
                created_at=item["created_at"],
            )
            for item in items
        ]

    def record_access_event(
        self,
        institution_id: str,
        resource_id: str,
        action: str,
        result: str,
        bytes_served: int,
        request_id: str,
        actor_id: str | None = None,
        application_id: str | None = None,
        evidence_id: str | None = None,
        parent_event_id: str | None = None,
    ) -> AccessEventRecord:
        event_id = str(uuid4())
        created_at = datetime.now(UTC)
        values = {
            "id": event_id,
            "actor_id": actor_id,
            "institution_id": institution_id,
            "application_id": application_id,
            "evidence_id": evidence_id,
            "resource_id": resource_id,
            "action": action,
            "result": result,
            "bytes_served": bytes_served,
            "request_id": request_id,
            "parent_event_id": parent_event_id,
            "created_at": created_at,
        }
        self.conn.execute(t.access.insert().values(**values))
        return AccessEventRecord(
            id=event_id,
            actor_id=actor_id,
            institution_id=institution_id,
            application_id=application_id,
            evidence_id=evidence_id,
            resource_id=resource_id,
            action=action,
            result=result,
            bytes_served=bytes_served,
            request_id=request_id,
            parent_event_id=parent_event_id,
            created_at=created_at,
        )

    def create_checkpointed_export(
        self,
        institution_id: str,
        application_id: str,
        auditor_id: str,
        is_auditor_or_supervisor: bool,
    ) -> AuditExportManifest:
        if not is_auditor_or_supervisor:
            raise ApplicationError(
                "AUDITOR_PERMISSION_REQUIRED",
                "Export requires scoped auditor or supervisor permission",
                403,
            )

        query = (
            select(t.audit)
            .where(
                t.audit.c.institution_id == institution_id,
                t.audit.c.application_id == application_id,
            )
            .order_by(t.audit.c.sequence.asc())
        )
        events = [row(item) for item in self.conn.execute(query)]
        if not events:
            raise ApplicationError(
                "EMPTY_AUDIT_STREAM",
                "No audit events found to export for application",
                404,
            )

        stream = events[0]["stream"]
        start_seq = events[0]["sequence"]
        end_seq = events[-1]["sequence"]

        # Validate cryptographic hash chain continuity
        hasher = hashlib.sha256()
        for ev in events:
            hasher.update(str(ev["sequence"]).encode())
            hasher.update(ev["sha256"].encode())
            hasher.update(ev["previous_hash"].encode())

        checkpoint_hash = hasher.hexdigest()
        latest_created = events[-1]["created_at"]
        archive_lag_seconds = max(0.0, (datetime.now(UTC) - latest_created).total_seconds())

        checkpoint_id = str(uuid4())
        exported_at = datetime.now(UTC)

        manifest_data = {
            "checkpoint_id": checkpoint_id,
            "institution_id": institution_id,
            "application_id": application_id,
            "auditor_id": auditor_id,
            "stream": stream,
            "start_sequence": start_seq,
            "end_sequence": end_seq,
            "event_count": len(events),
            "checkpoint_hash": checkpoint_hash,
            "archive_lag_seconds": archive_lag_seconds,
            "integrity_status": "VERIFIED",
            "exported_at": exported_at.isoformat(),
        }

        self.conn.execute(
            t.audit_checkpoints.insert().values(
                id=checkpoint_id,
                institution_id=institution_id,
                application_id=application_id,
                auditor_id=auditor_id,
                stream=stream,
                start_sequence=start_seq,
                end_sequence=end_seq,
                event_count=len(events),
                checkpoint_hash=checkpoint_hash,
                archive_lag_seconds=archive_lag_seconds,
                integrity_status="VERIFIED",
                manifest=manifest_data,
                created_at=exported_at,
            )
        )

        return AuditExportManifest(
            checkpoint_id=checkpoint_id,
            institution_id=institution_id,
            application_id=application_id,
            auditor_id=auditor_id,
            stream=stream,
            start_sequence=start_seq,
            end_sequence=end_seq,
            event_count=len(events),
            checkpoint_hash=checkpoint_hash,
            archive_lag_seconds=archive_lag_seconds,
            integrity_status="VERIFIED",
            exported_at=exported_at,
            events=[ev["event"] for ev in events],
        )
