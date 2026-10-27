"""Phase 6 claims service: claim management, evidence links, and full provenance queries."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection, Engine

from workbench.adapters import tables as t
from workbench.modules.claims.models import ClaimStatus
from workbench.modules.claims.reconciliation import ClaimReconciler


class ClaimsService:
    """Manages institutional claims, evidence links, and provenance queries."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.reconciler = ClaimReconciler()

    @contextmanager
    def _connection(self, conn: Connection | None = None) -> Iterator[Connection]:
        if conn is not None:
            yield conn
        else:
            with self.engine.begin() as connection:
                yield connection

    def declare_claim(
        self,
        institution_id: str,
        application_id: str,
        subject: str,
        predicate: str,
        declared_value: dict[str, Any],
        period_start: str | None = None,
        period_end: str | None = None,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Record an institutional claim in the application."""
        claim_id = str(uuid4())
        with self._connection(conn) as db:
            db.execute(
                insert(t.claims).values(
                    id=claim_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    subject=subject,
                    predicate=predicate,
                    period_start=period_start,
                    period_end=period_end,
                    declared_value=declared_value,
                    reconciled_value=declared_value,
                    status=ClaimStatus.UNVERIFIED.value,
                )
            )

        return {
            "id": claim_id,
            "subject": subject,
            "predicate": predicate,
            "declared_value": declared_value,
            "status": ClaimStatus.UNVERIFIED.value,
        }

    def reconcile_application_claims(
        self, institution_id: str, application_id: str, conn: Connection | None = None
    ) -> list[dict[str, Any]]:
        """Reconcile all declared claims against the latest active extracted fields."""
        with self._connection(conn) as db:
            # 1. Fetch all claims
            claims = (
                db.execute(
                    select(t.claims).where(
                        t.claims.c.institution_id == institution_id,
                        t.claims.c.application_id == application_id,
                    )
                )
                .mappings()
                .all()
            )

            # 2. Fetch all current extracted fields
            fields = (
                db.execute(
                    select(t.extracted_fields).where(
                        t.extracted_fields.c.institution_id == institution_id,
                        t.extracted_fields.c.application_id == application_id,
                        t.extracted_fields.c.is_current.is_(True),
                    )
                )
                .mappings()
                .all()
            )

            fields_list = [dict(f) for f in fields]
            results: list[dict[str, Any]] = []

            for c in claims:
                claim_id = c["id"]
                status, reconciled_val, links = self.reconciler.reconcile(
                    subject=c["subject"],
                    predicate=c["predicate"],
                    declared_value=c["declared_value"] or {},
                    extracted_fields=fields_list,
                )

                # Update claim
                db.execute(
                    update(t.claims)
                    .where(t.claims.c.id == claim_id)
                    .values(status=status.value, reconciled_value=reconciled_val)
                )

                # Delete prior links and reinsert fresh
                db.execute(
                    delete(t.claim_evidence_links).where(
                        t.claim_evidence_links.c.claim_id == claim_id
                    )
                )

                for link in links:
                    db.execute(
                        insert(t.claim_evidence_links).values(
                            id=str(uuid4()),
                            claim_id=claim_id,
                            institution_id=institution_id,
                            application_id=application_id,
                            evidence_version_id=link["evidence_version_id"],
                            field_id=link["field_id"],
                            relationship=link["relationship"],
                            rationale=link["rationale"],
                        )
                    )

                results.append(
                    {
                        "claim_id": claim_id,
                        "subject": c["subject"],
                        "predicate": c["predicate"],
                        "status": status.value,
                        "reconciled_value": reconciled_val,
                        "links_count": len(links),
                    }
                )

            return results

    def get_claim_provenance(
        self, institution_id: str, claim_id: str, conn: Connection | None = None
    ) -> dict[str, Any] | None:
        """Fetch complete provenance for a claim: declared value, reconciled value,
        linked evidence versions, extracted fields, and bounding boxes."""
        with self._connection(conn) as db:
            claim = (
                db.execute(
                    select(t.claims).where(
                        t.claims.c.id == claim_id,
                        t.claims.c.institution_id == institution_id,
                    )
                )
                .mappings()
                .first()
            )

            if not claim:
                return None

            links = (
                db.execute(
                    select(t.claim_evidence_links).where(
                        t.claim_evidence_links.c.claim_id == claim_id
                    )
                )
                .mappings()
                .all()
            )

            provenance_links: list[dict[str, Any]] = []
            for lnk in links:
                link_dict = dict(lnk)
                if lnk["field_id"]:
                    field_rec = (
                        db.execute(
                            select(t.extracted_fields).where(
                                t.extracted_fields.c.id == lnk["field_id"]
                            )
                        )
                        .mappings()
                        .first()
                    )
                    link_dict["field"] = dict(field_rec) if field_rec else None
                provenance_links.append(link_dict)

            result = dict(claim)
            result["provenance_links"] = provenance_links
            return result
