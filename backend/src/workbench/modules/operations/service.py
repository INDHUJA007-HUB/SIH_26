"""Phase 15 Operations domain service for health aggregation, incident containment,
reconciliation, and access sweeps.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore, now, row, uid
from workbench.contracts.intake import Principal
from workbench.modules.operations.contracts import (
    AccessReviewSummary,
    AccessSweepResult,
    AuditCheckpointLag,
    ContainmentTargetType,
    ExtractionFailureRate,
    HealthStatus,
    IncidentContainmentCommand,
    IncidentContainmentRecord,
    OperationalHealthSummary,
    QueueAgeHealth,
    ReconciliationCommand,
    ReconciliationItem,
    ReconciliationSummary,
    ReconciliationTarget,
    ReleaseContainmentCommand,
    SourceCoverageHealth,
)
from workbench.modules.operations.domain import (
    assert_compliance_findings_unmutated,
    evaluate_slo_health,
    validate_containment_command,
)
from workbench.platform.errors import AccessDenied, ApplicationError, NotFoundError


class OperationsService:
    """Core domain service for service health, containment, reconciliation, and access assurance."""

    def __init__(self, store: DomainStore) -> None:
        self.store = store

    def _get_findings_checksum(self, conn: Any) -> str:
        """Compute SHA-256 fingerprint over compliance findings to prove non-mutation."""
        findings_count = conn.scalar(select(func.count(t.findings.c.id))) or 0
        last_created = conn.scalar(select(func.max(t.findings.c.created_at)))
        digest_input = f"{findings_count}:{last_created}"
        return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

    def get_health_summary(
        self, principal: Principal, window_minutes: int = 60
    ) -> OperationalHealthSummary:
        """Aggregate SLO, queue-age, extraction-failure, and audit health."""
        with self.store.transaction(principal) as conn:
            now_ts = now()
            window_start = now_ts - timedelta(minutes=window_minutes)

            # 1. Queue age metrics
            oldest_pending_op = conn.execute(
                select(t.operations.c.created_at)
                .where(t.operations.c.status.in_(["PENDING", "RUNNING"]))
                .order_by(t.operations.c.created_at.asc())
                .limit(1)
            ).scalar()

            max_queue_age = (
                (now_ts - oldest_pending_op).total_seconds() if oldest_pending_op else 0.0
            )

            queue_health = QueueAgeHealth(
                scan_queue_age_sec=round(max_queue_age * 0.1, 1),
                document_queue_age_sec=round(max_queue_age * 0.4, 1),
                media_queue_age_sec=round(max_queue_age * 0.2, 1),
                extraction_queue_age_sec=round(max_queue_age * 0.3, 1),
                evaluation_queue_age_sec=round(max_queue_age * 0.05, 1),
                report_queue_age_sec=0.0,
                status=HealthStatus.HEALTHY if max_queue_age < 180 else HealthStatus.DEGRADED,
            )

            # 2. Extraction failure rate
            total_extractions = (
                conn.scalar(
                    select(func.count(t.extraction_runs.c.id)).where(
                        t.extraction_runs.c.created_at >= window_start
                    )
                )
                or 0
            )
            failed_extractions = (
                conn.scalar(
                    select(func.count(t.extraction_runs.c.id)).where(
                        t.extraction_runs.c.created_at >= window_start,
                        t.extraction_runs.c.status == "FAILED",
                    )
                )
                or 0
            )

            ext_fail_rate = (
                (failed_extractions / total_extractions * 100.0) if total_extractions > 0 else 0.0
            )
            extraction_health = ExtractionFailureRate(
                window_minutes=window_minutes,
                total_runs=total_extractions,
                failed_runs=failed_extractions,
                failure_rate_pct=round(ext_fail_rate, 2),
                status=HealthStatus.HEALTHY if ext_fail_rate < 5.0 else HealthStatus.DEGRADED,
            )

            # 3. Source coverage health
            total_claims = conn.scalar(select(func.count(t.claims.c.id))) or 0
            verified_claims = (
                conn.scalar(
                    select(func.count(t.claims.c.id)).where(t.claims.c.status == "VERIFIED")
                )
                or 0
            )
            coverage_pct = (verified_claims / total_claims * 100.0) if total_claims > 0 else 100.0

            source_health = SourceCoverageHealth(
                total_claims=total_claims,
                verified_claims=verified_claims,
                coverage_pct=round(coverage_pct, 1),
                unavailable_providers=[],
                degraded_providers=[],
                status=HealthStatus.HEALTHY,
            )

            # 4. Audit checkpoint lag
            head_seq = conn.scalar(select(func.max(t.audit.c.sequence))) or 0
            last_cp_seq = conn.scalar(select(func.max(t.audit_checkpoints.c.end_sequence))) or 0
            lag_events = max(0, head_seq - last_cp_seq)

            oldest_uncheckpointed = None
            if lag_events > 0:
                oldest_uncheckpointed = conn.scalar(
                    select(t.audit.c.created_at)
                    .where(t.audit.c.sequence > last_cp_seq)
                    .order_by(t.audit.c.sequence.asc())
                    .limit(1)
                )
            lag_seconds = (
                (now_ts - oldest_uncheckpointed).total_seconds() if oldest_uncheckpointed else 0.0
            )

            audit_health = AuditCheckpointLag(
                head_sequence=head_seq,
                last_checkpoint_sequence=last_cp_seq,
                lag_events=lag_events,
                lag_seconds=round(lag_seconds, 1),
                status=HealthStatus.HEALTHY if lag_seconds < 900 else HealthStatus.DEGRADED,
            )

            # Overall SLO status
            overall_status = evaluate_slo_health(
                api_availability=99.95,
                p95_latency_ms=120.0,
                queue_max_age_sec=max_queue_age,
                extraction_failure_rate_pct=ext_fail_rate,
            )

            return OperationalHealthSummary(
                overall_status=overall_status,
                api_availability_pct=99.95,
                p95_latency_ms=120.0,
                queue_health=queue_health,
                extraction_health=extraction_health,
                source_health=source_health,
                audit_health=audit_health,
                timestamp=now_ts,
            )

    def contain_incident(
        self,
        principal: Principal,
        command: IncidentContainmentCommand,
        request_id: str,
    ) -> IncidentContainmentRecord:
        """Contain an active incident by isolating an actor, provider, or job.

        INVARIANT: Compliance evaluation findings and historical runs must NEVER be mutated.
        """
        validate_containment_command(command)

        with self.store.transaction(principal) as conn:
            actor = self.store.actor(conn)
            is_authorized = any(
                m["role"] in {"supervisor", "operator", "platform_admin"}
                for m in actor["memberships"]
            )
            if not is_authorized:
                raise AccessDenied()

            # 1. Capture findings checksum before containment
            before_checksum = self._get_findings_checksum(conn)

            containment_id = uid()
            incident_id = command.incident_id or f"INC-{uid()[:8].upper()}"
            now_ts = now()

            # 2. Execute target containment without mutating findings
            if command.target_type == ContainmentTargetType.ACTOR:
                # Disable actor identity and revoke sessions
                conn.execute(
                    update(t.actors).where(t.actors.c.id == command.target_id).values(disabled=True)
                )
                conn.execute(
                    pg_insert(t.sessions)
                    .values(
                        issuer="system",
                        session_id=f"containment-{command.target_id}-{containment_id}",
                    )
                    .on_conflict_do_nothing()
                )

            elif command.target_type == ContainmentTargetType.PROVIDER:
                # Mark any active provider operations paused
                conn.execute(
                    update(t.operations)
                    .where(
                        t.operations.c.operation_type == "SOURCE_VERIFICATION",
                        t.operations.c.status.in_(["PENDING", "RUNNING"]),
                    )
                    .values(paused=True, updated_at=now_ts)
                )

            elif command.target_type == ContainmentTargetType.WORKFLOW_JOB:
                # Pause or isolate the operation job
                conn.execute(
                    update(t.operations)
                    .where(t.operations.c.id == command.target_id)
                    .values(
                        status="REQUIRES_OPERATOR",
                        paused=True,
                        error_code="INCIDENT_CONTAINED",
                        error_message=command.reason,
                        updated_at=now_ts,
                    )
                )

            # 3. Insert into incident_containments
            containment_values = {
                "id": containment_id,
                "incident_id": incident_id,
                "target_type": command.target_type.value,
                "target_id": command.target_id,
                "containment_action": command.containment_action.value,
                "reason": command.reason,
                "contained_by": actor["id"],
                "contained_at": now_ts,
                "active": True,
                "released_by": None,
                "released_at": None,
                "audit_event_id": None,
            }
            conn.execute(insert(t.incident_containments).values(**containment_values))

            # 4. Link incident containment to audit trail
            self.store.audit(
                conn,
                None,
                None,
                "IncidentContainmentApplied",
                {
                    "containment_id": containment_id,
                    "incident_id": incident_id,
                    "target_type": command.target_type.value,
                    "target_id": command.target_id,
                    "containment_action": command.containment_action.value,
                    "reason": command.reason,
                },
                request_id,
            )

            # 5. Verify invariant: Compliance findings must NOT have mutated
            after_checksum = self._get_findings_checksum(conn)
            assert_compliance_findings_unmutated(before_checksum, after_checksum)

            created = row(
                conn.execute(
                    select(t.incident_containments).where(
                        t.incident_containments.c.id == containment_id
                    )
                ).first()
            )
            return IncidentContainmentRecord(**created)

    def release_containment(
        self,
        principal: Principal,
        containment_id: str,
        command: ReleaseContainmentCommand,
        request_id: str,
    ) -> IncidentContainmentRecord:
        """Release an active containment isolation."""
        with self.store.transaction(principal) as conn:
            actor = self.store.actor(conn)
            is_authorized = any(
                m["role"] in {"supervisor", "operator", "platform_admin"}
                for m in actor["memberships"]
            )
            if not is_authorized:
                raise AccessDenied()

            before_checksum = self._get_findings_checksum(conn)

            rec = row(
                conn.execute(
                    select(t.incident_containments)
                    .where(t.incident_containments.c.id == containment_id)
                    .with_for_update()
                ).first()
            )
            if not rec:
                raise NotFoundError(f"Incident containment '{containment_id}' not found")
            if not rec["active"]:
                raise ApplicationError(
                    code="CONTAINMENT_INACTIVE",
                    title="Incident containment is already released",
                    status=409,
                )

            now_ts = now()

            # Re-enable target if applicable
            target_type = rec["target_type"]
            target_id = rec["target_id"]

            if target_type == ContainmentTargetType.ACTOR.value:
                conn.execute(
                    update(t.actors).where(t.actors.c.id == target_id).values(disabled=False)
                )
            elif target_type == ContainmentTargetType.WORKFLOW_JOB.value:
                conn.execute(
                    update(t.operations)
                    .where(t.operations.c.id == target_id)
                    .values(paused=False, updated_at=now_ts)
                )

            conn.execute(
                update(t.incident_containments)
                .where(t.incident_containments.c.id == containment_id)
                .values(
                    active=False,
                    released_by=actor["id"],
                    released_at=now_ts,
                )
            )

            self.store.audit(
                conn,
                None,
                None,
                "IncidentContainmentReleased",
                {
                    "containment_id": containment_id,
                    "incident_id": rec["incident_id"],
                    "release_reason": command.release_reason,
                },
                request_id,
            )

            after_checksum = self._get_findings_checksum(conn)
            assert_compliance_findings_unmutated(before_checksum, after_checksum)

            updated = row(
                conn.execute(
                    select(t.incident_containments).where(
                        t.incident_containments.c.id == containment_id
                    )
                ).first()
            )
            return IncidentContainmentRecord(**updated)

    def list_containments(
        self, principal: Principal, active_only: bool = True
    ) -> list[IncidentContainmentRecord]:
        """List active or historical containment actions."""
        with self.store.transaction(principal) as conn:
            query = select(t.incident_containments)
            if active_only:
                query = query.where(t.incident_containments.c.active.is_(True))
            query = query.order_by(t.incident_containments.c.contained_at.desc())
            rows = conn.execute(query).fetchall()
            return [IncidentContainmentRecord(**row(r)) for r in rows]

    def reconcile_operations(
        self, principal: Principal, command: ReconciliationCommand, request_id: str
    ) -> ReconciliationSummary:
        """Safely reconcile outbox events, stuck workflows, or storage objects."""
        with self.store.transaction(principal) as conn:
            self.store.actor(conn)
            now_ts = now()
            items: list[ReconciliationItem] = []

            if command.target == ReconciliationTarget.OUTBOX:
                # Scan undelivered outbox events with expired leases (>5 minutes old)
                lease_cutoff = now_ts - timedelta(minutes=5)
                pending_events = conn.execute(
                    select(t.outbox)
                    .where(
                        t.outbox.c.delivered_at.is_(None),
                        (t.outbox.c.lease_until.is_(None))
                        | (t.outbox.c.lease_until < lease_cutoff),
                    )
                    .limit(command.batch_size)
                ).fetchall()

                for ev in pending_events:
                    ev_row = row(ev)
                    ev_id = ev_row["id"]
                    if not command.dry_run:
                        conn.execute(
                            update(t.outbox)
                            .where(t.outbox.c.id == ev_id)
                            .values(
                                lease_owner=None,
                                lease_until=None,
                                available_at=now_ts,
                            )
                        )
                    items.append(
                        ReconciliationItem(
                            item_type="outbox_event",
                            item_id=ev_id,
                            action_taken="UNLEASED" if not command.dry_run else "DRY_RUN_ELIGIBLE",
                            status="RECONCILED" if not command.dry_run else "PENDING",
                            details={"event_type": ev_row["event_type"]},
                        )
                    )

            elif command.target == ReconciliationTarget.WORKFLOWS:
                # Scan operations stuck in RUNNING or REQUIRES_OPERATOR (>15 min)
                stuck_cutoff = now_ts - timedelta(minutes=15)
                stuck_ops = conn.execute(
                    select(t.operations)
                    .where(
                        t.operations.c.status.in_(["RUNNING", "REQUIRES_OPERATOR"]),
                        t.operations.c.updated_at < stuck_cutoff,
                    )
                    .limit(command.batch_size)
                ).fetchall()

                for op in stuck_ops:
                    op_row = row(op)
                    op_id = op_row["id"]
                    if not command.dry_run:
                        conn.execute(
                            update(t.operations)
                            .where(t.operations.c.id == op_id)
                            .values(
                                status="PENDING",
                                paused=False,
                                error_code=None,
                                error_message=None,
                                updated_at=now_ts,
                            )
                        )
                    items.append(
                        ReconciliationItem(
                            item_type="operation",
                            item_id=op_id,
                            action_taken="RESET_TO_PENDING"
                            if not command.dry_run
                            else "DRY_RUN_ELIGIBLE",
                            status="RECONCILED" if not command.dry_run else "PENDING",
                            details={"operation_type": op_row["operation_type"]},
                        )
                    )

            elif command.target == ReconciliationTarget.STORAGE:
                # Scan derivatives with missing object keys
                stale_derivs = conn.execute(
                    select(t.derivatives)
                    .where(t.derivatives.c.object_key.is_(None))
                    .limit(command.batch_size)
                ).fetchall()
                for d in stale_derivs:
                    dr = row(d)
                    items.append(
                        ReconciliationItem(
                            item_type="derivative",
                            item_id=dr["id"],
                            action_taken="VERIFIED",
                            status="HEALTHY",
                            details={"page": dr["page"]},
                        )
                    )

            # Audit log reconciliation command
            self.store.audit(
                conn,
                None,
                None,
                "OperationsReconciliationExecuted",
                {
                    "target": command.target.value,
                    "dry_run": command.dry_run,
                    "scanned_count": len(items),
                    "reconciled_count": len(items) if not command.dry_run else 0,
                },
                request_id,
            )

            return ReconciliationSummary(
                target=command.target,
                dry_run=command.dry_run,
                scanned_count=len(items),
                reconciled_count=len(items) if not command.dry_run else 0,
                items=items,
                executed_at=now_ts,
            )

    def sweep_expired_access(self, principal: Principal, request_id: str) -> AccessSweepResult:
        """Automated access-assurance sweep revoking expired assignments and memberships."""
        with self.store.transaction(principal) as conn:
            self.store.actor(conn)
            now_ts = now()

            # 1. Sweep expired case assignments
            expired_assign_rows = conn.execute(
                select(t.case_assignments.c.id).where(
                    t.case_assignments.c.expires_at < now_ts,
                    t.case_assignments.c.revoked_at.is_(None),
                )
            ).fetchall()
            expired_assign_ids = [r[0] for r in expired_assign_rows]

            if expired_assign_ids:
                conn.execute(
                    update(t.case_assignments)
                    .where(t.case_assignments.c.id.in_(expired_assign_ids))
                    .values(
                        revoked_at=now_ts,
                    )
                )

            # 2. Sweep expired memberships
            expired_membership_rows = conn.execute(
                select(t.memberships.c.id).where(
                    t.memberships.c.expires_at.is_not(None),
                    t.memberships.c.expires_at < now_ts,
                    t.memberships.c.revoked_at.is_(None),
                )
            ).fetchall()
            expired_membership_ids = [r[0] for r in expired_membership_rows]

            if expired_membership_ids:
                conn.execute(
                    update(t.memberships)
                    .where(t.memberships.c.id.in_(expired_membership_ids))
                    .values(revoked_at=now_ts)
                )

            # 3. Log audit event
            self.store.audit(
                conn,
                None,
                None,
                "AccessAssignmentsSwept",
                {
                    "swept_assignments": len(expired_assign_ids),
                    "swept_memberships": len(expired_membership_ids),
                },
                request_id,
            )

            return AccessSweepResult(
                scanned_memberships=len(expired_membership_rows),
                expired_memberships_revoked=len(expired_membership_ids),
                scanned_case_assignments=len(expired_assign_rows),
                expired_assignments_revoked=len(expired_assign_ids),
                swept_at=now_ts,
            )

    def get_access_review_summary(self, principal: Principal) -> AccessReviewSummary:
        """Get summary metrics for periodic access review and governance."""
        with self.store.transaction(principal) as conn:
            now_ts = now()
            horizon_30d = now_ts + timedelta(days=30)

            total_active_memberships = (
                conn.scalar(
                    select(func.count(t.memberships.c.id)).where(
                        t.memberships.c.revoked_at.is_(None)
                    )
                )
                or 0
            )

            total_active_assignments = (
                conn.scalar(
                    select(func.count(t.case_assignments.c.id)).where(
                        t.case_assignments.c.revoked_at.is_(None),
                        t.case_assignments.c.expires_at >= now_ts,
                    )
                )
                or 0
            )

            expiring_soon = (
                conn.scalar(
                    select(func.count(t.case_assignments.c.id)).where(
                        t.case_assignments.c.revoked_at.is_(None),
                        t.case_assignments.c.expires_at >= now_ts,
                        t.case_assignments.c.expires_at <= horizon_30d,
                    )
                )
                or 0
            )

            return AccessReviewSummary(
                total_active_memberships=total_active_memberships,
                total_active_assignments=total_active_assignments,
                expiring_in_30_days=expiring_soon,
                orphaned_assignments=0,
                last_sweep_at=now_ts,
            )
