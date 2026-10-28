"""Contracts and value objects for Phase 10 tasks, alerts, timers, and notifications."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AlertCategory(StrEnum):
    COMPLIANCE = "COMPLIANCE"
    SECURITY = "SECURITY"
    OPERATIONS = "OPERATIONS"


class AlertTriggerType(StrEnum):
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    EXPIRY_WARNING = "EXPIRY_WARNING"
    UNAVAILABLE_SOURCE = "UNAVAILABLE_SOURCE"
    INCONSISTENCY_REVIEW = "INCONSISTENCY_REVIEW"
    RESPONSE_DEADLINE = "RESPONSE_DEADLINE"
    SECURITY = "SECURITY"


class AlertSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class TaskState(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"
    ESCALATED = "ESCALATED"


class TimerStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    FIRED = "FIRED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"


class NotificationStatus(StrEnum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class AlertRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str | None = None
    category: AlertCategory
    trigger_type: AlertTriggerType
    dedup_key: str
    severity: AlertSeverity
    title: str
    message: str
    status: AlertStatus
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    acknowledged_by: str | None = None


class CreateAlertRequest(BaseModel):
    institution_id: str
    application_id: str | None = None
    category: AlertCategory
    trigger_type: AlertTriggerType
    severity: AlertSeverity = AlertSeverity.WARNING
    title: str
    message: str
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class TaskRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str | None = None
    task_type: str
    dedup_key: str
    state: TaskState
    assigned_to: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class CreateTaskRequest(BaseModel):
    institution_id: str
    application_id: str | None = None
    task_type: str
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    assigned_to: str | None = None


class UpdateTaskStateRequest(BaseModel):
    new_state: TaskState
    details: dict[str, Any] = Field(default_factory=dict)


class DurableTimerRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str
    slot_id: str | None = None
    timer_type: str
    generation: int
    deadline: datetime
    status: TimerStatus
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    cancelled_at: datetime | None = None
    fired_at: datetime | None = None


class ScheduleTimerRequest(BaseModel):
    institution_id: str
    application_id: str
    slot_id: str | None = None
    timer_type: str
    deadline: datetime
    generation: int = 1
    details: dict[str, Any] = Field(default_factory=dict)


class NotificationRecord(BaseModel):
    id: str
    institution_id: str
    application_id: str | None = None
    alert_id: str | None = None
    task_id: str | None = None
    recipient: str
    channel: NotificationChannel
    status: NotificationStatus
    provider_reference: str | None = None
    subject: str | None = None
    body: str
    retry_count: int = 0
    retry_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None


class SendNotificationRequest(BaseModel):
    institution_id: str
    application_id: str | None = None
    recipient: str
    channel: NotificationChannel
    subject: str | None = None
    body: str
    alert_id: str | None = None
    task_id: str | None = None
