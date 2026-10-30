"""Phase 9 service for recording officer review dispositions and managing pending tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, Engine, desc, insert, select, update

from workbench.adapters import tables as t
from workbench.modules.review.contracts import (
    ReviewDispositionType,
    TaskStatus,
    WaitingOn,
)
from workbench.platform.errors import ApplicationError


class ReviewService:
    def __init__(self, engine: Engine):
        self.engine = engine

    def record_disposition(
        self,
        *,
        institution_id: str,
        application_id: str,
        finding_id: str,
        evaluation_run_id: str,
        officer_id: str,
        disposition: ReviewDispositionType | str,
        rationale: str,
        metadata: dict[str, Any] | None = None,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Record human officer disposition for a machine finding.

        Machine findings in `findings` table remain immutable and stored separately.
        """
        if not rationale or len(rationale.strip()) < 5:
            raise ApplicationError(
                "INVALID_RATIONALE",
                "A substantiated rationale is required for every review disposition",
                400,
            )

        disp_value = (
            disposition.value
            if isinstance(disposition, ReviewDispositionType)
            else ReviewDispositionType(disposition).value
        )

        def _execute(c: Connection) -> dict[str, Any]:
            # Verify machine finding exists
            finding = (
                c.execute(select(t.findings).where(t.findings.c.id == finding_id))
                .mappings()
                .first()
            )
            if not finding:
                raise ApplicationError("NOT_FOUND", f"Finding {finding_id} not found", 404)

            # Insert human disposition record (machine findings remain untouched)
            disp_id = str(uuid4())
            now = datetime.now(UTC)
            c.execute(
                insert(t.review_dispositions).values(
                    id=disp_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    finding_id=finding_id,
                    evaluation_run_id=evaluation_run_id,
                    officer_id=officer_id,
                    disposition=disp_value,
                    rationale=rationale,
                    metadata=metadata or {},
                    created_at=now,
                    updated_at=now,
                )
            )

            # Auto-create or transition pending task if rectification requested
            if disp_value == ReviewDispositionType.RECTIFICATION_REQUESTED.value:
                task_id = str(uuid4())
                c.execute(
                    insert(t.review_tasks).values(
                        id=task_id,
                        institution_id=institution_id,
                        application_id=application_id,
                        task_type="DEFICIENCY_RECTIFICATION_REQUIRED",
                        waiting_on=WaitingOn.OFFICER.value,
                        status=TaskStatus.PENDING.value,
                        assigned_to=officer_id,
                        details={
                            "finding_id": finding_id,
                            "disposition": disp_value,
                            "rationale": rationale,
                        },
                        created_at=now,
                    )
                )

            return {
                "id": disp_id,
                "institution_id": institution_id,
                "application_id": application_id,
                "finding_id": finding_id,
                "evaluation_run_id": evaluation_run_id,
                "officer_id": officer_id,
                "disposition": disp_value,
                "rationale": rationale,
                "metadata": metadata or {},
                "created_at": now.isoformat(),
            }

        if conn is not None:
            return _execute(conn)
        with self.engine.begin() as c:
            return _execute(c)

    def list_dispositions(
        self,
        *,
        institution_id: str,
        application_id: str | None = None,
        finding_id: str | None = None,
        evaluation_run_id: str | None = None,
        conn: Connection | None = None,
    ) -> list[dict[str, Any]]:
        def _execute(c: Connection) -> list[dict[str, Any]]:
            query = select(t.review_dispositions).where(
                t.review_dispositions.c.institution_id == institution_id
            )
            if application_id:
                query = query.where(t.review_dispositions.c.application_id == application_id)
            if finding_id:
                query = query.where(t.review_dispositions.c.finding_id == finding_id)
            if evaluation_run_id:
                query = query.where(t.review_dispositions.c.evaluation_run_id == evaluation_run_id)
            query = query.order_by(desc(t.review_dispositions.c.created_at))
            rows = c.execute(query).mappings().all()
            return [dict(r) for r in rows]

        if conn is not None:
            return _execute(conn)
        with self.engine.connect() as c:
            return _execute(c)

    def create_or_update_task(
        self,
        *,
        institution_id: str,
        application_id: str,
        task_type: str,
        waiting_on: WaitingOn | str,
        status: TaskStatus | str = TaskStatus.PENDING,
        assigned_to: str | None = None,
        details: dict[str, Any] | None = None,
        deadline: datetime | None = None,
        task_id: str | None = None,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        waiting_val = (
            waiting_on.value if isinstance(waiting_on, WaitingOn) else WaitingOn(waiting_on).value
        )
        status_val = status.value if isinstance(status, TaskStatus) else TaskStatus(status).value

        def _execute(c: Connection) -> dict[str, Any]:
            now = datetime.now(UTC)
            tid = task_id or str(uuid4())
            if task_id:
                c.execute(
                    update(t.review_tasks)
                    .where(t.review_tasks.c.id == tid)
                    .values(
                        waiting_on=waiting_val,
                        status=status_val,
                        assigned_to=assigned_to,
                        details=details or {},
                        deadline=deadline,
                        resolved_at=now
                        if status_val in {TaskStatus.RESOLVED.value, TaskStatus.CANCELLED.value}
                        else None,
                    )
                )
            else:
                c.execute(
                    insert(t.review_tasks).values(
                        id=tid,
                        institution_id=institution_id,
                        application_id=application_id,
                        task_type=task_type,
                        waiting_on=waiting_val,
                        status=status_val,
                        assigned_to=assigned_to,
                        details=details or {},
                        deadline=deadline,
                        created_at=now,
                        resolved_at=now
                        if status_val in {TaskStatus.RESOLVED.value, TaskStatus.CANCELLED.value}
                        else None,
                    )
                )
            return {
                "id": tid,
                "institution_id": institution_id,
                "application_id": application_id,
                "task_type": task_type,
                "waiting_on": waiting_val,
                "status": status_val,
                "assigned_to": assigned_to,
                "details": details or {},
                "deadline": deadline.isoformat() if deadline else None,
                "created_at": now.isoformat(),
            }

        if conn is not None:
            return _execute(conn)
        with self.engine.begin() as c:
            return _execute(c)

    def list_tasks(
        self,
        *,
        institution_id: str,
        application_id: str | None = None,
        waiting_on: str | None = None,
        status: str | None = None,
        conn: Connection | None = None,
    ) -> list[dict[str, Any]]:
        def _execute(c: Connection) -> list[dict[str, Any]]:
            query = select(t.review_tasks).where(t.review_tasks.c.institution_id == institution_id)
            if application_id:
                query = query.where(t.review_tasks.c.application_id == application_id)
            if waiting_on:
                query = query.where(t.review_tasks.c.waiting_on == waiting_on)
            if status:
                query = query.where(t.review_tasks.c.status == status)
            query = query.order_by(desc(t.review_tasks.c.created_at))
            rows = c.execute(query).mappings().all()
            return [dict(r) for r in rows]

        if conn is not None:
            return _execute(conn)
        with self.engine.connect() as c:
            return _execute(c)

    def get_pending_action_summary(
        self,
        *,
        institution_id: str,
        application_id: str | None = None,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        tasks = self.list_tasks(
            institution_id=institution_id,
            application_id=application_id,
            status=TaskStatus.PENDING.value,
            conn=conn,
        )
        counts = {
            "OFFICER": 0,
            "APPLICANT": 0,
            "SOURCE": 0,
            "INTERPRETATION": 0,
        }
        for task in tasks:
            w = task.get("waiting_on")
            if w in counts:
                counts[w] += 1
        return {
            "institution_id": institution_id,
            "application_id": application_id,
            "total_pending": len(tasks),
            "waiting_on_counts": counts,
            "tasks": tasks,
        }
