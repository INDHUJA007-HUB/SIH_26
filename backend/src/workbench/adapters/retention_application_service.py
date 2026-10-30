"""Retention application service managing policies, legal holds, and approved purges."""

from __future__ import annotations

import contextlib
from datetime import timedelta

from sqlalchemy import Connection, delete, insert, select, text, update

from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore, now, row, uid
from workbench.adapters.object_storage import ObjectStorage
from workbench.contracts.intake import Principal
from workbench.modules.identity_access.policy import require_step_up
from workbench.modules.retention.contracts import (
    DataClass,
    LegalHoldCreate,
    LegalHoldRelease,
    LegalHoldResponse,
    PurgeCandidate,
    PurgeEligibilityResult,
    PurgeManifestResponse,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
    RetentionPurgeCompletedEvent,
)
from workbench.modules.retention.domain import (
    compute_manifest_digest,
    is_candidate_held,
    is_dependent_evidence,
    validate_retention_policy_rules,
)
from workbench.platform.errors import AccessDenied, ApplicationError, NotFoundError


class RetentionService:
    def __init__(self, store: DomainStore, storage: ObjectStorage | None = None) -> None:
        self.store = store
        self.storage = storage

    @staticmethod
    def _lock_retention(conn: Connection) -> None:
        # Hold placement/release and purge share a lock, including the no-holds-yet case.
        conn.execute(text("SELECT pg_advisory_xact_lock(78521315)"))

    def create_policy(
        self, principal: Principal, payload: RetentionPolicyCreate, request_id: str
    ) -> RetentionPolicyResponse:
        """Create a versioned retention policy (requires supervisor MFA)."""
        require_step_up(principal)
        validate_retention_policy_rules(payload)

        with self.store.transaction(principal) as conn:
            actor = self.store.actor(conn)
            if not any(m["role"] == "supervisor" for m in actor["memberships"]):
                raise AccessDenied()

            policy_id = uid()
            values = {
                "id": policy_id,
                "data_class": payload.data_class.value,
                "retention_basis": payload.retention_basis.value,
                "retention_period_days": payload.retention_period_days,
                "description": payload.description,
                "approved_by": actor["id"],
                "is_active": True,
            }
            conn.execute(insert(t.retention_policies).values(**values))

            self.store.audit(
                conn,
                None,
                None,
                "RetentionPolicyCreated",
                {
                    "policy_id": policy_id,
                    "data_class": payload.data_class.value,
                    "retention_period_days": payload.retention_period_days,
                },
                request_id,
            )

            created = row(
                conn.execute(
                    select(t.retention_policies).where(t.retention_policies.c.id == policy_id)
                ).first()
            )
            return RetentionPolicyResponse(**created)

    def list_policies(self, principal: Principal) -> list[RetentionPolicyResponse]:
        """List active retention policies."""
        with self.store.transaction(principal) as conn:
            rows = conn.execute(
                select(t.retention_policies)
                .where(t.retention_policies.c.is_active.is_(True))
                .order_by(t.retention_policies.c.created_at.desc())
            ).fetchall()
            return [RetentionPolicyResponse(**row(r)) for r in rows]

    def place_legal_hold(
        self, principal: Principal, payload: LegalHoldCreate, request_id: str
    ) -> LegalHoldResponse:
        """Place a legal hold on an institution, application, or slot (requires MFA)."""
        require_step_up(principal)

        with self.store.transaction(principal) as conn:
            self._lock_retention(conn)
            actor = self.store.actor(conn)
            if not any(m["role"] == "supervisor" for m in actor["memberships"]):
                raise AccessDenied()

            hold_id = uid()
            values = {
                "id": hold_id,
                "institution_id": payload.institution_id,
                "application_id": payload.application_id,
                "evidence_slot_id": payload.evidence_slot_id,
                "matter_reference": payload.matter_reference,
                "legal_basis": payload.legal_basis,
                "placed_by": actor["id"],
                "is_active": True,
            }
            conn.execute(insert(t.legal_holds).values(**values))

            self.store.audit(
                conn,
                payload.institution_id,
                payload.application_id,
                "LegalHoldPlaced",
                {
                    "hold_id": hold_id,
                    "matter_reference": payload.matter_reference,
                    "evidence_slot_id": payload.evidence_slot_id,
                },
                request_id,
            )

            created = row(
                conn.execute(select(t.legal_holds).where(t.legal_holds.c.id == hold_id)).first()
            )
            return LegalHoldResponse(**created)

    def release_legal_hold(
        self, principal: Principal, hold_id: str, payload: LegalHoldRelease, request_id: str
    ) -> LegalHoldResponse:
        """Release an existing active legal hold."""
        require_step_up(principal)

        with self.store.transaction(principal) as conn:
            self._lock_retention(conn)
            actor = self.store.actor(conn)
            if not any(m["role"] == "supervisor" for m in actor["memberships"]):
                raise AccessDenied()

            hold = row(
                conn.execute(
                    select(t.legal_holds).where(t.legal_holds.c.id == hold_id).with_for_update()
                ).first()
            )
            if not hold:
                raise NotFoundError("Legal hold not found")
            if not hold["is_active"]:
                raise ApplicationError("HOLD_INACTIVE", "Legal hold is already released", 409)

            now_ts = now()
            conn.execute(
                update(t.legal_holds)
                .where(t.legal_holds.c.id == hold_id)
                .values(
                    is_active=False,
                    released_by=actor["id"],
                    released_at=now_ts,
                    release_reason=payload.release_reason,
                )
            )

            self.store.audit(
                conn,
                hold["institution_id"],
                hold["application_id"],
                "LegalHoldReleased",
                {"hold_id": hold_id, "release_reason": payload.release_reason},
                request_id,
            )

            updated = row(
                conn.execute(select(t.legal_holds).where(t.legal_holds.c.id == hold_id)).first()
            )
            return LegalHoldResponse(**updated)

    def list_legal_holds(
        self, principal: Principal, active_only: bool = True, institution_id: str | None = None
    ) -> list[LegalHoldResponse]:
        """Query legal holds."""
        with self.store.transaction(principal) as conn:
            query = select(t.legal_holds)
            if active_only:
                query = query.where(t.legal_holds.c.is_active.is_(True))
            if institution_id:
                query = query.where(t.legal_holds.c.institution_id == institution_id)
            query = query.order_by(t.legal_holds.c.placed_at.desc())
            rows = conn.execute(query).fetchall()
            return [LegalHoldResponse(**row(r)) for r in rows]

    def evaluate_purge_eligibility(
        self,
        principal: Principal,
        policy_id: str,
        max_items: int = 100,
        connection: Connection | None = None,
    ) -> PurgeEligibilityResult:
        """Scan candidate items and partition into eligible, held, and active-dependency groups."""
        with (
            contextlib.nullcontext(connection)
            if connection is not None
            else self.store.transaction(principal)
        ) as conn:
            policy_row = row(
                conn.execute(
                    select(t.retention_policies).where(t.retention_policies.c.id == policy_id)
                ).first()
            )
            if not policy_row:
                raise NotFoundError(f"Retention policy '{policy_id}' not found")
            if not policy_row["is_active"]:
                raise ApplicationError("INACTIVE_POLICY", "Retention policy is inactive", 409)

            data_class = DataClass(policy_row["data_class"])
            cutoff = now() - timedelta(days=policy_row["retention_period_days"])

            # 1. Fetch active legal holds
            active_holds = [
                row(h)
                for h in conn.execute(
                    select(t.legal_holds).where(t.legal_holds.c.is_active.is_(True))
                ).fetchall()
            ]

            # 2. Fetch active non-terminal application IDs
            active_app_rows = conn.execute(
                select(t.applications.c.id).where(
                    t.applications.c.stage.notin_(["ARCHIVED", "CANCELLED", "DECIDED"])
                )
            ).fetchall()
            active_app_ids = {r[0] for r in active_app_rows}

            # Fetch evidence IDs referenced by evaluation runs / finalized manifests
            run_input_rows = conn.execute(
                select(t.run_inputs.c.input_id).where(t.run_inputs.c.input_type == "EVIDENCE")
            ).fetchall()
            manifest_evidence_ids = {r[0] for r in run_input_rows}
            for manifest in conn.execute(select(t.revisions.c.manifest)).scalars():
                manifest_evidence_ids.update(e["id"] for e in manifest.get("evidence", []))

            # Foreign-key dependents must be retained before any irreversible object delete.
            for table in t.metadata.tables.values():
                if table is t.derivatives:
                    continue
                for fk in table.foreign_keys:
                    if fk.column.table is t.evidence and fk.column.name == "id":
                        manifest_evidence_ids.update(
                            value for value in conn.execute(select(fk.parent)).scalars() if value
                        )

            candidates: list[PurgeCandidate] = []

            # 3. Discover candidates depending on data_class
            if data_class == DataClass.DERIVATIVES_CACHES:
                # Query evidence_derivatives older than cutoff
                d_rows = conn.execute(
                    select(t.derivatives)
                    .where(t.derivatives.c.created_at < cutoff)
                    .limit(max_items)
                ).fetchall()
                for d in d_rows:
                    dr = row(d)
                    slot_id = None
                    if dr.get("evidence_id"):
                        ev_row = row(
                            conn.execute(
                                select(t.evidence.c.slot_id).where(
                                    t.evidence.c.id == dr["evidence_id"]
                                )
                            ).first()
                        )
                        if ev_row:
                            slot_id = ev_row.get("slot_id")
                    candidates.append(
                        PurgeCandidate(
                            item_id=dr["id"],
                            data_class=data_class,
                            created_at=dr["created_at"],
                            age_days=(now() - dr["created_at"]).days,
                            institution_id=dr.get("institution_id"),
                            application_id=dr.get("application_id"),
                            evidence_slot_id=slot_id,
                            storage_key=dr.get("object_key"),
                            bytes_size=dr.get("size_bytes") or 1024,
                        )
                    )
            elif data_class == DataClass.ORIGINAL_EVIDENCE:
                # Query evidence_versions older than cutoff
                ev_rows = conn.execute(
                    select(t.evidence).where(t.evidence.c.created_at < cutoff).limit(max_items)
                ).fetchall()
                for ev in ev_rows:
                    evr = row(ev)
                    candidates.append(
                        PurgeCandidate(
                            item_id=evr["id"],
                            data_class=data_class,
                            created_at=evr["created_at"],
                            age_days=(now() - evr["created_at"]).days,
                            institution_id=evr.get("institution_id"),
                            application_id=evr.get("application_id"),
                            evidence_slot_id=evr.get("slot_id"),
                            storage_key=evr.get("clean_key") or evr.get("quarantine_key"),
                            bytes_size=evr.get("size_bytes") or 10240,
                        )
                    )

            eligible: list[str] = []
            held: list[str] = []
            dependencies: list[str] = []
            bytes_estimate = 0

            for cand in candidates:
                if is_candidate_held(cand, active_holds):
                    held.append(cand.item_id)
                elif is_dependent_evidence(cand, active_app_ids, manifest_evidence_ids):
                    dependencies.append(cand.item_id)
                else:
                    eligible.append(cand.item_id)
                    bytes_estimate += cand.bytes_size

            return PurgeEligibilityResult(
                policy_id=policy_id,
                data_class=data_class,
                retention_period_days=policy_row["retention_period_days"],
                candidate_count=len(candidates),
                eligible_count=len(eligible),
                skipped_held_count=len(held),
                skipped_dependency_count=len(dependencies),
                eligible_item_ids=eligible,
                held_item_ids=held,
                dependency_item_ids=dependencies,
                estimated_bytes_freed=bytes_estimate,
            )

    def execute_purge(
        self,
        principal: Principal,
        policy_id: str,
        dry_run: bool,
        max_items: int,
        request_id: str,
    ) -> PurgeManifestResponse:
        """Execute or dry-run an approved purge."""
        require_step_up(principal)
        with self.store.transaction(principal) as conn:
            self._lock_retention(conn)
            actor = self.store.actor(conn)
            if not any(m["role"] == "supervisor" for m in actor["memberships"]):
                raise AccessDenied()
            eligibility = self.evaluate_purge_eligibility(principal, policy_id, max_items, conn)
            if not dry_run and eligibility.eligible_count and self.storage is None:
                raise ApplicationError(
                    "STORAGE_REQUIRED", "Purge requires versioned object storage", 503
                )

            manifest_id = uid()
            now_ts = now()
            purged_ev_ids: list[str] = []
            purged_deriv_keys: list[str] = []
            bytes_freed = 0
            event_inst_id = None
            event_app_id = None

            if not dry_run and eligibility.eligible_count > 0:
                data_class = eligibility.data_class
                if data_class == DataClass.DERIVATIVES_CACHES:
                    for deriv_id in eligibility.eligible_item_ids:
                        d_row = row(
                            conn.execute(
                                select(t.derivatives).where(t.derivatives.c.id == deriv_id)
                            ).first()
                        )
                        if d_row:
                            if not event_inst_id:
                                event_inst_id = d_row.get("institution_id")
                                event_app_id = d_row.get("application_id")
                            storage_key = d_row.get("object_key")
                            if storage_key:
                                assert self.storage is not None
                                self.storage.delete(storage_key, version=d_row["object_version"])
                                purged_deriv_keys.append(storage_key)
                            bytes_freed += d_row["size_bytes"]
                            conn.execute(
                                delete(t.derivatives).where(t.derivatives.c.id == deriv_id)
                            )
                elif data_class == DataClass.ORIGINAL_EVIDENCE:
                    for ev_id in eligibility.eligible_item_ids:
                        ev_row = row(
                            conn.execute(select(t.evidence).where(t.evidence.c.id == ev_id)).first()
                        )
                        if ev_row:
                            if not event_inst_id:
                                event_inst_id = ev_row.get("institution_id")
                                event_app_id = ev_row.get("application_id")
                            purged_ev_ids.append(ev_id)
                            assert self.storage is not None
                            if ev_row.get("clean_key"):
                                self.storage.delete(
                                    ev_row["clean_key"], version=ev_row["clean_version"]
                                )
                            self.storage.delete(
                                ev_row["quarantine_key"],
                                bucket=self.storage.quarantine,
                                version=ev_row["quarantine_version"],
                            )
                            bytes_freed += ev_row["size_bytes"]
                            for child in conn.execute(
                                select(t.derivatives).where(t.derivatives.c.evidence_id == ev_id)
                            ).mappings():
                                self.storage.delete(
                                    child["object_key"], version=child["object_version"]
                                )
                                purged_deriv_keys.append(child["object_key"])
                                bytes_freed += child["size_bytes"]
                            # Delete derivative children first
                            conn.execute(
                                delete(t.derivatives).where(t.derivatives.c.evidence_id == ev_id)
                            )
                            conn.execute(delete(t.evidence).where(t.evidence.c.id == ev_id))
            else:
                # Dry run
                bytes_freed = 0

            sha256_digest = compute_manifest_digest(
                policy_id=policy_id,
                data_class=eligibility.data_class.value,
                purged_evidence_ids=purged_ev_ids,
                purged_derivative_keys=purged_deriv_keys,
                bytes_freed=bytes_freed,
                executed_at=now_ts,
            )

            manifest_values = {
                "id": manifest_id,
                "policy_id": policy_id,
                "data_class": eligibility.data_class.value,
                "candidate_count": eligibility.candidate_count,
                "purged_count": len(purged_ev_ids) + len(purged_deriv_keys) if not dry_run else 0,
                "skipped_held_count": eligibility.skipped_held_count,
                "skipped_dependency_count": eligibility.skipped_dependency_count,
                "purged_evidence_ids": purged_ev_ids,
                "purged_derivative_keys": purged_deriv_keys,
                "bytes_freed": bytes_freed,
                "executed_by": actor["id"],
                "executed_at": now_ts,
                "sha256_digest": sha256_digest,
            }

            conn.execute(insert(t.purge_manifests).values(**manifest_values))

            # Emit audit event
            self.store.audit(
                conn,
                None,
                None,
                "RetentionPurgeExecuted",
                {
                    "manifest_id": manifest_id,
                    "policy_id": policy_id,
                    "dry_run": dry_run,
                    "purged_count": manifest_values["purged_count"],
                    "bytes_freed": bytes_freed,
                    "sha256_digest": sha256_digest,
                },
                request_id,
            )

            # Queue outbox event if not dry run
            if not dry_run and event_inst_id and event_app_id:
                outbox_payload = RetentionPurgeCompletedEvent(
                    manifest_id=manifest_id,
                    policy_id=policy_id,
                    data_class=eligibility.data_class.value,
                    purged_count=manifest_values["purged_count"],
                    bytes_freed=bytes_freed,
                    sha256_digest=sha256_digest,
                    timestamp=now_ts,
                    executed_by=actor["id"],
                ).model_dump(mode="json")
                conn.execute(
                    insert(t.outbox).values(
                        id=uid(),
                        institution_id=event_inst_id,
                        application_id=event_app_id,
                        event_type="RetentionPurgeCompleted",
                        payload=outbox_payload,
                    )
                )

            return PurgeManifestResponse(
                id=manifest_id,
                policy_id=policy_id,
                data_class=eligibility.data_class,
                candidate_count=eligibility.candidate_count,
                purged_count=manifest_values["purged_count"],
                skipped_held_count=eligibility.skipped_held_count,
                skipped_dependency_count=eligibility.skipped_dependency_count,
                purged_evidence_ids=purged_ev_ids,
                purged_derivative_keys=purged_deriv_keys,
                bytes_freed=bytes_freed,
                executed_by=actor["id"],
                executed_at=now_ts,
                sha256_digest=sha256_digest,
                audit_event_id=None,
            )

    def get_purge_manifest(self, principal: Principal, manifest_id: str) -> PurgeManifestResponse:
        """Fetch an immutable purge manifest by ID."""
        with self.store.transaction(principal) as conn:
            mf_row = row(
                conn.execute(
                    select(t.purge_manifests).where(t.purge_manifests.c.id == manifest_id)
                ).first()
            )
            if not mf_row:
                raise NotFoundError(f"Purge manifest '{manifest_id}' not found")
            return PurgeManifestResponse(**mf_row)
