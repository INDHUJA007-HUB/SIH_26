"""Service logic for tasks, alerts, versioned durable timers, and notifications."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, select, update

from workbench.adapters import tables as t
from workbench.adapters.domain_store import row
from workbench.modules.tasks_alerts.contracts import (
    AlertCategory,
    AlertRecord,
    AlertSeverity,
    AlertStatus,
    AlertTriggerType,
    CreateAlertRequest,
    CreateTaskRequest,
    DurableTimerRecord,
    NotificationChannel,
    NotificationRecord,
    NotificationStatus,
    ScheduleTimerRequest,
    SendNotificationRequest,
    TaskRecord,
    TaskState,
    TimerStatus,
    UpdateTaskStateRequest,
)
from workbench.platform.errors import ApplicationError


class TasksAlertsService:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def create_or_dedup_alert(self, req: CreateAlertRequest) -> AlertRecord:
        dedup_key = (
            f"{req.category.value}:{req.trigger_type.value}:{req.institution_id}:"
            f"{req.application_id or '*'}:{req.resource_id}"
        )
        existing = self.conn.execute(
            select(t.alerts).where(
                t.alerts.c.dedup_key == dedup_key,
                t.alerts.c.status == AlertStatus.OPEN.value,
            )
        ).first()

        if existing:
            return self._to_alert_record(row(existing))

        alert_id = str(uuid4())
        created_at = datetime.now(UTC)
        values = {
            "id": alert_id,
            "institution_id": req.institution_id,
            "application_id": req.application_id,
            "category": req.category.value,
            "trigger_type": req.trigger_type.value,
            "dedup_key": dedup_key,
            "severity": req.severity.value,
            "title": req.title,
            "message": req.message,
            "status": AlertStatus.OPEN.value,
            "details": req.details,
            "created_at": created_at,
        }
        self.conn.execute(t.alerts.insert().values(**values))
        return self._to_alert_record(values)

    def acknowledge_alert(self, alert_id: str, actor_id: str) -> AlertRecord:
        existing = self.conn.execute(select(t.alerts).where(t.alerts.c.id == alert_id)).first()
        if not existing:
            raise ApplicationError("ALERT_NOT_FOUND", "Alert not found", 404)

        current = row(existing)
        if current["status"] in {AlertStatus.RESOLVED.value, AlertStatus.DISMISSED.value}:
            raise ApplicationError("INVALID_STATE", "Alert is already closed", 409)

        ack_at = datetime.now(UTC)
        self.conn.execute(
            update(t.alerts)
            .where(t.alerts.c.id == alert_id)
            .values(
                status=AlertStatus.ACKNOWLEDGED.value,
                acknowledged_at=ack_at,
                acknowledged_by=actor_id,
            )
        )
        current["status"] = AlertStatus.ACKNOWLEDGED.value
        current["acknowledged_at"] = ack_at
        current["acknowledged_by"] = actor_id
        return self._to_alert_record(current)

    def resolve_alert(self, alert_id: str) -> AlertRecord:
        existing = self.conn.execute(select(t.alerts).where(t.alerts.c.id == alert_id)).first()
        if not existing:
            raise ApplicationError("ALERT_NOT_FOUND", "Alert not found", 404)

        current = row(existing)
        resolved_at = datetime.now(UTC)
        self.conn.execute(
            update(t.alerts)
            .where(t.alerts.c.id == alert_id)
            .values(
                status=AlertStatus.RESOLVED.value,
                resolved_at=resolved_at,
            )
        )
        current["status"] = AlertStatus.RESOLVED.value
        current["resolved_at"] = resolved_at
        return self._to_alert_record(current)

    def list_alerts(
        self,
        institution_id: str,
        application_id: str | None = None,
        category: AlertCategory | None = None,
        trigger_type: AlertTriggerType | None = None,
        status: AlertStatus | None = None,
    ) -> list[AlertRecord]:
        query = select(t.alerts).where(t.alerts.c.institution_id == institution_id)
        if application_id:
            query = query.where(t.alerts.c.application_id == application_id)
        if category:
            query = query.where(t.alerts.c.category == category.value)
        if trigger_type:
            query = query.where(t.alerts.c.trigger_type == trigger_type.value)
        if status:
            query = query.where(t.alerts.c.status == status.value)

        query = query.order_by(t.alerts.c.created_at.desc())
        results = [row(item) for item in self.conn.execute(query)]
        return [self._to_alert_record(item) for item in results]

    # --- Tasks & Task State Machine ---

    def create_or_dedup_task(self, req: CreateTaskRequest) -> TaskRecord:
        dedup_key = (
            f"{req.task_type}:{req.institution_id}:{req.application_id or '*'}:{req.resource_id}"
        )
        existing = self.conn.execute(
            select(t.lifecycle_tasks).where(
                t.lifecycle_tasks.c.dedup_key == dedup_key,
                t.lifecycle_tasks.c.state.in_([TaskState.OPEN.value, TaskState.IN_PROGRESS.value]),
            )
        ).first()

        if existing:
            return self._to_task_record(row(existing))

        task_id = str(uuid4())
        created_at = datetime.now(UTC)
        values = {
            "id": task_id,
            "institution_id": req.institution_id,
            "application_id": req.application_id,
            "task_type": req.task_type,
            "dedup_key": dedup_key,
            "state": TaskState.OPEN.value,
            "assigned_to": req.assigned_to,
            "details": req.details,
            "created_at": created_at,
            "updated_at": created_at,
        }
        self.conn.execute(t.lifecycle_tasks.insert().values(**values))
        return self._to_task_record(values)

    def transition_task_state(self, task_id: str, req: UpdateTaskStateRequest) -> TaskRecord:
        existing = self.conn.execute(
            select(t.lifecycle_tasks).where(t.lifecycle_tasks.c.id == task_id)
        ).first()
        if not existing:
            raise ApplicationError("TASK_NOT_FOUND", "Task not found", 404)

        current = row(existing)
        current_state = TaskState(current["state"])
        target_state = req.new_state

        valid_transitions: dict[TaskState, set[TaskState]] = {
            TaskState.OPEN: {
                TaskState.IN_PROGRESS,
                TaskState.ESCALATED,
                TaskState.RESOLVED,
                TaskState.CANCELLED,
            },
            TaskState.IN_PROGRESS: {
                TaskState.RESOLVED,
                TaskState.CANCELLED,
                TaskState.ESCALATED,
            },
            TaskState.ESCALATED: {
                TaskState.IN_PROGRESS,
                TaskState.RESOLVED,
                TaskState.CANCELLED,
            },
            TaskState.RESOLVED: set(),
            TaskState.CANCELLED: set(),
        }

        if target_state not in valid_transitions.get(current_state, set()):
            raise ApplicationError(
                "ILLEGAL_STATE_TRANSITION",
                f"Cannot transition task from {current_state.value} to {target_state.value}",
                409,
            )

        updated_at = datetime.now(UTC)
        resolved_at = (
            updated_at if target_state in {TaskState.RESOLVED, TaskState.CANCELLED} else None
        )
        merged_details = {**(current.get("details") or {}), **req.details}

        self.conn.execute(
            update(t.lifecycle_tasks)
            .where(t.lifecycle_tasks.c.id == task_id)
            .values(
                state=target_state.value,
                updated_at=updated_at,
                resolved_at=resolved_at,
                details=merged_details,
            )
        )
        current["state"] = target_state.value
        current["updated_at"] = updated_at
        current["resolved_at"] = resolved_at
        current["details"] = merged_details
        return self._to_task_record(current)

    def list_tasks(
        self,
        institution_id: str,
        application_id: str | None = None,
        task_type: str | None = None,
        state: TaskState | None = None,
    ) -> list[TaskRecord]:
        query = select(t.lifecycle_tasks).where(
            t.lifecycle_tasks.c.institution_id == institution_id
        )
        if application_id:
            query = query.where(t.lifecycle_tasks.c.application_id == application_id)
        if task_type:
            query = query.where(t.lifecycle_tasks.c.task_type == task_type)
        if state:
            query = query.where(t.lifecycle_tasks.c.state == state.value)

        query = query.order_by(t.lifecycle_tasks.c.created_at.desc())
        results = [row(item) for item in self.conn.execute(query)]
        return [self._to_task_record(item) for item in results]

    # --- Versioned Durable Timers ---

    def schedule_timer(self, req: ScheduleTimerRequest) -> DurableTimerRecord:
        timer_id = str(uuid4())
        created_at = datetime.now(UTC)
        values = {
            "id": timer_id,
            "institution_id": req.institution_id,
            "application_id": req.application_id,
            "slot_id": req.slot_id,
            "timer_type": req.timer_type,
            "generation": req.generation,
            "deadline": req.deadline,
            "status": TimerStatus.SCHEDULED.value,
            "details": req.details,
            "created_at": created_at,
        }
        self.conn.execute(t.durable_timers.insert().values(**values))
        self.conn.execute(
            t.outbox.insert().values(
                id=str(uuid4()),
                institution_id=req.institution_id,
                application_id=req.application_id,
                event_type="DurableTimerScheduled",
                payload={"timer_id": timer_id},
            )
        )
        return self._to_timer_record(values)

    def cancel_obsolete_timers(
        self,
        institution_id: str,
        application_id: str,
        slot_id: str,
        new_generation: int,
    ) -> int:
        cancelled_at = datetime.now(UTC)
        stmt = (
            update(t.durable_timers)
            .where(
                t.durable_timers.c.institution_id == institution_id,
                t.durable_timers.c.application_id == application_id,
                t.durable_timers.c.slot_id == slot_id,
                t.durable_timers.c.generation < new_generation,
                t.durable_timers.c.status == TimerStatus.SCHEDULED.value,
            )
            .values(
                status=TimerStatus.CANCELLED.value,
                cancelled_at=cancelled_at,
            )
        )
        result = self.conn.execute(stmt)
        return result.rowcount or 0

    def list_timers(
        self,
        institution_id: str,
        application_id: str | None = None,
        slot_id: str | None = None,
        status: TimerStatus | None = None,
    ) -> list[DurableTimerRecord]:
        query = select(t.durable_timers).where(t.durable_timers.c.institution_id == institution_id)
        if application_id:
            query = query.where(t.durable_timers.c.application_id == application_id)
        if slot_id:
            query = query.where(t.durable_timers.c.slot_id == slot_id)
        if status:
            query = query.where(t.durable_timers.c.status == status.value)

        query = query.order_by(t.durable_timers.c.created_at.desc())
        results = [row(item) for item in self.conn.execute(query)]
        return [self._to_timer_record(item) for item in results]

    # --- Notifications & Delivery ---

    def send_notification(self, req: SendNotificationRequest) -> NotificationRecord:
        notification_id = str(uuid4())
        created_at = datetime.now(UTC)
        status = NotificationStatus.QUEUED
        provider_ref = None
        sent_at = None
        retries: list[dict[str, Any]] = []

        if req.channel == NotificationChannel.IN_APP:
            status = NotificationStatus.SENT
            provider_ref = f"in_app_{uuid4().hex[:12]}"
            sent_at = datetime.now(UTC)
        elif req.channel == NotificationChannel.EMAIL:
            if not req.application_id:
                raise ApplicationError(
                    "APPLICATION_REQUIRED", "Email delivery requires an application scope", 422
                )

        values = {
            "id": notification_id,
            "institution_id": req.institution_id,
            "application_id": req.application_id,
            "alert_id": req.alert_id,
            "task_id": req.task_id,
            "recipient": req.recipient,
            "channel": req.channel.value,
            "status": status.value,
            "provider_reference": provider_ref,
            "subject": req.subject,
            "body": req.body,
            "retry_count": len(retries),
            "retry_history": retries,
            "created_at": created_at,
            "sent_at": sent_at,
        }
        self.conn.execute(t.notifications.insert().values(**values))
        if req.channel == NotificationChannel.EMAIL:
            self.conn.execute(
                t.outbox.insert().values(
                    id=str(uuid4()),
                    institution_id=req.institution_id,
                    application_id=req.application_id,
                    event_type="NotificationQueued",
                    payload={"notification_id": notification_id},
                )
            )
        return self._to_notification_record(values)

    def acknowledge_notification(self, notification_id: str) -> NotificationRecord:
        existing = self.conn.execute(
            select(t.notifications).where(t.notifications.c.id == notification_id)
        ).first()
        if not existing:
            raise ApplicationError("NOTIFICATION_NOT_FOUND", "Notification not found", 404)

        current = row(existing)
        ack_at = datetime.now(UTC)
        self.conn.execute(
            update(t.notifications)
            .where(t.notifications.c.id == notification_id)
            .values(
                status=NotificationStatus.ACKNOWLEDGED.value,
                acknowledged_at=ack_at,
            )
        )
        current["status"] = NotificationStatus.ACKNOWLEDGED.value
        current["acknowledged_at"] = ack_at
        return self._to_notification_record(current)

    def list_notifications(
        self,
        institution_id: str,
        channel: NotificationChannel | None = None,
        status: NotificationStatus | None = None,
    ) -> list[NotificationRecord]:
        query = select(t.notifications).where(t.notifications.c.institution_id == institution_id)
        if channel:
            query = query.where(t.notifications.c.channel == channel.value)
        if status:
            query = query.where(t.notifications.c.status == status.value)

        query = query.order_by(t.notifications.c.created_at.desc())
        results = [row(item) for item in self.conn.execute(query)]
        return [self._to_notification_record(item) for item in results]

    # --- Helpers ---

    def _to_alert_record(self, data: dict[str, Any]) -> AlertRecord:
        return AlertRecord(
            id=data["id"],
            institution_id=data["institution_id"],
            application_id=data.get("application_id"),
            category=AlertCategory(data["category"]),
            trigger_type=AlertTriggerType(data["trigger_type"]),
            dedup_key=data["dedup_key"],
            severity=AlertSeverity(data["severity"]),
            title=data["title"],
            message=data["message"],
            status=AlertStatus(data["status"]),
            details=data.get("details") or {},
            created_at=data["created_at"],
            acknowledged_at=data.get("acknowledged_at"),
            resolved_at=data.get("resolved_at"),
            acknowledged_by=data.get("acknowledged_by"),
        )

    def _to_task_record(self, data: dict[str, Any]) -> TaskRecord:
        return TaskRecord(
            id=data["id"],
            institution_id=data["institution_id"],
            application_id=data.get("application_id"),
            task_type=data["task_type"],
            dedup_key=data["dedup_key"],
            state=TaskState(data["state"]),
            assigned_to=data.get("assigned_to"),
            details=data.get("details") or {},
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            resolved_at=data.get("resolved_at"),
        )

    def _to_timer_record(self, data: dict[str, Any]) -> DurableTimerRecord:
        return DurableTimerRecord(
            id=data["id"],
            institution_id=data["institution_id"],
            application_id=data["application_id"],
            slot_id=data.get("slot_id"),
            timer_type=data["timer_type"],
            generation=data["generation"],
            deadline=data["deadline"],
            status=TimerStatus(data["status"]),
            details=data.get("details") or {},
            created_at=data["created_at"],
            cancelled_at=data.get("cancelled_at"),
            fired_at=data.get("fired_at"),
        )

    def _to_notification_record(self, data: dict[str, Any]) -> NotificationRecord:
        return NotificationRecord(
            id=data["id"],
            institution_id=data["institution_id"],
            application_id=data.get("application_id"),
            alert_id=data.get("alert_id"),
            task_id=data.get("task_id"),
            recipient=data["recipient"],
            channel=NotificationChannel(data["channel"]),
            status=NotificationStatus(data["status"]),
            provider_reference=data.get("provider_reference"),
            subject=data.get("subject"),
            body=data["body"],
            retry_count=data.get("retry_count", 0),
            retry_history=data.get("retry_history") or [],
            created_at=data["created_at"],
            sent_at=data.get("sent_at"),
            acknowledged_at=data.get("acknowledged_at"),
        )
