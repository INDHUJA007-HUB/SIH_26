"""Phase 10 API endpoints: alerts, semantic tasks, timers, notifications, and audit export."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection, text

from workbench.adapters.audit_access_application_service import AuditAccessService
from workbench.adapters.domain_store import DomainStore
from workbench.adapters.tasks_alerts_application_service import TasksAlertsService
from workbench.contracts.intake import Principal
from workbench.modules.audit_access import AccessEventRecord, AuditEventRecord, AuditExportManifest
from workbench.modules.tasks_alerts import (
    AlertCategory,
    AlertRecord,
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


def _check_institution_access(conn: Connection, actor: Principal, institution_id: str) -> None:
    allowed = conn.scalar(
        text("SELECT (wb.can_access(:inst, NULL, false) OR wb.manages(:inst))"),
        {"inst": institution_id},
    )
    if allowed:
        return
    is_elevated = conn.scalar(
        text("SELECT wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('auditor'))")
    )
    if not is_elevated:
        raise ApplicationError("ACCESS_DENIED", "Access to institution is denied", 403)


def create_phase_10_router(store: DomainStore, principal: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["phase_10"])

    # --- Alerts ---

    @router.post("/alerts", response_model=AlertRecord)
    def create_or_dedup_alert(
        req: CreateAlertRequest, actor: Principal = Depends(principal)
    ) -> AlertRecord:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, req.institution_id)
            service = TasksAlertsService(conn)
            return service.create_or_dedup_alert(req)

    @router.get("/alerts", response_model=list[AlertRecord])
    def list_alerts(
        institution_id: str,
        application_id: str | None = None,
        category: AlertCategory | None = None,
        trigger_type: AlertTriggerType | None = None,
        status: AlertStatus | None = None,
        actor: Principal = Depends(principal),
    ) -> list[AlertRecord]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, institution_id)
            service = TasksAlertsService(conn)
            return service.list_alerts(
                institution_id=institution_id,
                application_id=application_id,
                category=category,
                trigger_type=trigger_type,
                status=status,
            )

    @router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRecord)
    def acknowledge_alert(alert_id: str, actor: Principal = Depends(principal)) -> AlertRecord:
        with store.transaction(actor) as conn:
            service = TasksAlertsService(conn)
            return service.acknowledge_alert(alert_id, actor.subject)

    @router.post("/alerts/{alert_id}/resolve", response_model=AlertRecord)
    def resolve_alert(alert_id: str, actor: Principal = Depends(principal)) -> AlertRecord:
        with store.transaction(actor) as conn:
            service = TasksAlertsService(conn)
            return service.resolve_alert(alert_id)

    # --- Semantic Lifecycle Tasks ---

    @router.post("/tasks/semantic", response_model=TaskRecord)
    def create_or_dedup_task(
        req: CreateTaskRequest, actor: Principal = Depends(principal)
    ) -> TaskRecord:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, req.institution_id)
            service = TasksAlertsService(conn)
            return service.create_or_dedup_task(req)

    @router.get("/tasks/semantic", response_model=list[TaskRecord])
    def list_tasks(
        institution_id: str,
        application_id: str | None = None,
        task_type: str | None = None,
        state: TaskState | None = None,
        actor: Principal = Depends(principal),
    ) -> list[TaskRecord]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, institution_id)
            service = TasksAlertsService(conn)
            return service.list_tasks(
                institution_id=institution_id,
                application_id=application_id,
                task_type=task_type,
                state=state,
            )

    @router.patch("/tasks/semantic/{task_id}/state", response_model=TaskRecord)
    def update_task_state(
        task_id: str,
        req: UpdateTaskStateRequest,
        actor: Principal = Depends(principal),
    ) -> TaskRecord:
        with store.transaction(actor) as conn:
            service = TasksAlertsService(conn)
            return service.transition_task_state(task_id, req)

    # --- Versioned Durable Timers ---

    @router.post("/timers", response_model=DurableTimerRecord)
    def schedule_timer(
        req: ScheduleTimerRequest, actor: Principal = Depends(principal)
    ) -> DurableTimerRecord:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, req.institution_id)
            service = TasksAlertsService(conn)
            return service.schedule_timer(req)

    @router.get("/timers", response_model=list[DurableTimerRecord])
    def list_timers(
        institution_id: str,
        application_id: str | None = None,
        slot_id: str | None = None,
        status: TimerStatus | None = None,
        actor: Principal = Depends(principal),
    ) -> list[DurableTimerRecord]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, institution_id)
            service = TasksAlertsService(conn)
            return service.list_timers(
                institution_id=institution_id,
                application_id=application_id,
                slot_id=slot_id,
                status=status,
            )

    @router.post("/timers/cancel-obsolete")
    def cancel_obsolete_timers(
        institution_id: str,
        application_id: str,
        slot_id: str,
        new_generation: int,
        actor: Principal = Depends(principal),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, institution_id)
            service = TasksAlertsService(conn)
            cancelled = service.cancel_obsolete_timers(
                institution_id=institution_id,
                application_id=application_id,
                slot_id=slot_id,
                new_generation=new_generation,
            )
            return {"cancelled_count": cancelled}

    # --- Notifications ---

    @router.post("/notifications/send", response_model=NotificationRecord)
    def send_notification(
        req: SendNotificationRequest, actor: Principal = Depends(principal)
    ) -> NotificationRecord:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, req.institution_id)
            service = TasksAlertsService(conn)
            return service.send_notification(req)

    @router.get("/notifications", response_model=list[NotificationRecord])
    def list_notifications(
        institution_id: str,
        channel: NotificationChannel | None = None,
        status: NotificationStatus | None = None,
        actor: Principal = Depends(principal),
    ) -> list[NotificationRecord]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, institution_id)
            service = TasksAlertsService(conn)
            return service.list_notifications(
                institution_id=institution_id, channel=channel, status=status
            )

    @router.post("/notifications/{notification_id}/acknowledge", response_model=NotificationRecord)
    def acknowledge_notification(
        notification_id: str, actor: Principal = Depends(principal)
    ) -> NotificationRecord:
        with store.transaction(actor) as conn:
            service = TasksAlertsService(conn)
            return service.acknowledge_notification(notification_id)

    # --- Audit & Access History ---

    @router.get("/audit/events", response_model=list[AuditEventRecord])
    def list_audit_events(
        institution_id: str,
        application_id: str | None = None,
        stream: str | None = None,
        event_type: str | None = None,
        after_sequence: int = 0,
        limit: int = Query(default=50, ge=1, le=100),
        actor: Principal = Depends(principal),
    ) -> list[AuditEventRecord]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, institution_id)
            service = AuditAccessService(conn)
            return service.list_audit_events(
                institution_id=institution_id,
                application_id=application_id,
                stream=stream,
                event_type=event_type,
                after_sequence=after_sequence,
                limit=limit,
            )

    @router.get("/access/events", response_model=list[AccessEventRecord])
    def list_access_events(
        institution_id: str,
        application_id: str | None = None,
        evidence_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        result: str | None = None,
        after_id: str = "",
        limit: int = Query(default=50, ge=1, le=100),
        actor: Principal = Depends(principal),
    ) -> list[AccessEventRecord]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, institution_id)
            service = AuditAccessService(conn)
            return service.list_access_events(
                institution_id=institution_id,
                application_id=application_id,
                evidence_id=evidence_id,
                actor_id=actor_id,
                action=action,
                result=result,
                after_id=after_id,
                limit=limit,
            )

    @router.post(
        "/applications/{application_id}/audit-export",
        response_model=AuditExportManifest,
    )
    def export_audit_checkpoint(
        application_id: str,
        institution_id: str,
        actor: Principal = Depends(principal),
    ) -> AuditExportManifest:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, actor, institution_id)
            is_auditor = bool(
                conn.scalar(
                    text(
                        "SELECT wb.elevated() AND ("
                        "wb.has_role('supervisor') OR wb.has_role('auditor'))"
                    )
                )
            )
            service = AuditAccessService(conn)
            return service.create_checkpointed_export(
                institution_id=institution_id,
                application_id=application_id,
                auditor_id=actor.subject,
                is_auditor_or_supervisor=is_auditor,
            )

    return router
