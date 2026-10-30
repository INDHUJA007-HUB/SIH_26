"""Service for importing and reconciling historical AICTE institutional records (Phase 8.2)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, Engine, insert, select

from workbench.adapters import tables as t
from workbench.platform.errors import ApplicationError


class HistoricalRecordService:
    """Manages versioned external AICTE records (EoA, intake, accreditation, deficiencies)."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _connection(self, conn: Connection | None = None) -> Iterator[Connection]:
        if conn is not None:
            yield conn
        else:
            with self.engine.begin() as connection:
                yield connection

    def import_record(
        self,
        institution_id: str,
        source: str,
        record_type: str,
        academic_cycle: int,
        payload: dict[str, Any],
        external_reference: str,
        valid_from: datetime,
        valid_to: datetime | None = None,
        imported_by: str = "system_import",
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Import a versioned historical institutional record with lineage and SHA-256 hash."""
        if not institution_id:
            raise ApplicationError("INVALID_INPUT", "Institution ID is required", 400)
        if academic_cycle < 1987 or academic_cycle > 2100:
            raise ApplicationError(
                "INVALID_INPUT", f"Invalid academic cycle: {academic_cycle}", 400
            )

        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload_hash = hashlib.sha256(canonical_bytes).hexdigest()

        record_id = str(uuid.uuid4())
        lineage = {
            "batch_id": str(uuid.uuid4()),
            "imported_by": imported_by,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        with self._connection(conn) as c:
            c.execute(
                insert(t.historical_records).values(
                    id=record_id,
                    institution_id=institution_id,
                    source=source,
                    record_type=record_type,
                    academic_cycle=academic_cycle,
                    payload=payload,
                    payload_sha256=payload_hash,
                    external_reference=external_reference,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    simulated=True,
                    import_lineage=lineage,
                )
            )

        return {
            "id": record_id,
            "institution_id": institution_id,
            "source": source,
            "record_type": record_type,
            "academic_cycle": academic_cycle,
            "payload_sha256": payload_hash,
            "external_reference": external_reference,
            "simulated": True,
            "import_lineage": lineage,
        }

    def list_records(
        self,
        institution_id: str,
        record_type: str | None = None,
        academic_cycle: int | None = None,
        conn: Connection | None = None,
    ) -> list[dict[str, Any]]:
        """List historical records for an institution, optionally filtered by cycle or type."""
        query = select(t.historical_records).where(
            t.historical_records.c.institution_id == institution_id
        )
        if record_type:
            query = query.where(t.historical_records.c.record_type == record_type)
        if academic_cycle:
            query = query.where(t.historical_records.c.academic_cycle == academic_cycle)

        query = query.order_by(
            t.historical_records.c.academic_cycle.desc(), t.historical_records.c.created_at.desc()
        )

        with self._connection(conn) as c:
            rows = c.execute(query).fetchall()
            return [
                {
                    "id": r.id,
                    "institution_id": r.institution_id,
                    "source": r.source,
                    "record_type": r.record_type,
                    "academic_cycle": r.academic_cycle,
                    "payload": r.payload,
                    "payload_sha256": r.payload_sha256,
                    "external_reference": r.external_reference,
                    "valid_from": r.valid_from.isoformat() if r.valid_from else None,
                    "valid_to": r.valid_to.isoformat() if r.valid_to else None,
                    "simulated": r.simulated,
                    "import_lineage": r.import_lineage,
                }
                for r in rows
            ]

    def reconcile_claims(
        self,
        institution_id: str,
        declared_facts: dict[str, Any],
        academic_cycle: int,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Reconcile declared application facts against historical portal records."""
        history = self.list_records(institution_id, academic_cycle=academic_cycle, conn=conn)
        reconciliation: dict[str, Any] = {
            "institution_id": institution_id,
            "academic_cycle": academic_cycle,
            "historical_records_found": len(history),
            "simulated": True,
            "matches": [],
            "discrepancies": [],
        }

        # Example: check intake claim vs historical intake record
        intake_records = [r for r in history if r["record_type"] == "INTAKE"]
        if intake_records and "approved_intake" in declared_facts:
            historical_intake = intake_records[0]["payload"].get("approved_intake")
            declared_intake = declared_facts.get("approved_intake")
            if historical_intake is not None and declared_intake is not None:
                if historical_intake == declared_intake:
                    reconciliation["matches"].append(
                        {
                            "field": "approved_intake",
                            "declared": declared_intake,
                            "historical": historical_intake,
                        }
                    )
                else:
                    reconciliation["discrepancies"].append(
                        {
                            "field": "approved_intake",
                            "declared": declared_intake,
                            "historical": historical_intake,
                            "diff": declared_intake - historical_intake,
                            "reason": "Declared intake differs from historical portal baseline",
                        }
                    )

        return reconciliation
