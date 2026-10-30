"""Transactional timer transitions and conservative, persisted notification delivery."""

import email.message
import smtplib
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from temporalio import activity

from workbench.adapters import tables as t
from workbench.adapters.domain_store import now
from workbench.platform.config import Settings
from workbench.platform.runtime_roles import build_runtime_engine


def _engine() -> Any:
    return build_runtime_engine(Settings().worker_database_url.get_secret_value(), "wb_worker")


@activity.defn
def load_durable_timer(event_id: str) -> dict[str, Any]:
    engine = _engine()
    try:
        with engine.begin() as conn:
            event = conn.execute(select(t.outbox).where(t.outbox.c.id == event_id)).mappings().one()
            timer = (
                conn.execute(
                    select(t.durable_timers).where(
                        t.durable_timers.c.id == event["payload"]["timer_id"]
                    )
                )
                .mappings()
                .one()
            )
            return {"status": timer["status"], "deadline": timer["deadline"].isoformat()}
    finally:
        engine.dispose()


@activity.defn
def fire_durable_timer(event_id: str) -> dict[str, Any]:
    engine = _engine()
    try:
        with engine.begin() as conn:
            event = conn.execute(select(t.outbox).where(t.outbox.c.id == event_id)).mappings().one()
            timer = (
                conn.execute(
                    select(t.durable_timers)
                    .where(t.durable_timers.c.id == event["payload"]["timer_id"])
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            if timer["status"] != "SCHEDULED" or timer["deadline"] > now():
                return {"status": timer["status"]}
            newer = conn.scalar(
                select(t.durable_timers.c.id)
                .where(
                    t.durable_timers.c.application_id == timer["application_id"],
                    t.durable_timers.c.slot_id.is_not_distinct_from(timer["slot_id"]),
                    t.durable_timers.c.timer_type == timer["timer_type"],
                    t.durable_timers.c.generation > timer["generation"],
                )
                .limit(1)
            )
            state = "SUPERSEDED" if newer else "FIRED"
            conn.execute(
                update(t.durable_timers)
                .where(t.durable_timers.c.id == timer["id"])
                .values(
                    status=state,
                    fired_at=now() if not newer else None,
                )
            )
            if not newer:
                conn.execute(
                    t.review_tasks.insert().values(
                        id=str(uuid4()),
                        institution_id=timer["institution_id"],
                        application_id=timer["application_id"],
                        task_type=timer["timer_type"],
                        waiting_on="OFFICER",
                        status="PENDING",
                        details={"timer_id": timer["id"], "generation": timer["generation"]},
                    )
                )
                window_id = (timer["details"] or {}).get("window_id")
                if window_id:
                    conn.execute(
                        update(t.response_windows)
                        .where(
                            t.response_windows.c.id == window_id,
                            t.response_windows.c.status == "OPEN",
                            t.response_windows.c.deadline <= now(),
                        )
                        .values(status="EXPIRED", closed_at=now())
                    )
            return {"status": state}
    finally:
        engine.dispose()


@activity.defn
def deliver_notification(event_id: str) -> dict[str, Any]:
    engine = _engine()
    try:
        with engine.begin() as conn:
            event = conn.execute(select(t.outbox).where(t.outbox.c.id == event_id)).mappings().one()
            notification = (
                conn.execute(
                    select(t.notifications)
                    .where(t.notifications.c.id == event["payload"]["notification_id"])
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            if notification["status"] != "QUEUED":
                return {"status": notification["status"]}
            # Persist uncertainty before side effect. Retry after a crash never duplicates mail.
            conn.execute(
                update(t.notifications)
                .where(t.notifications.c.id == notification["id"])
                .values(status="UNKNOWN")
            )
            data = dict(notification)
        message = email.message.EmailMessage()
        message["Message-ID"] = f"<{data['id']}@workbench.local>"
        message["Subject"] = data["subject"] or "Workbench notification"
        message["From"] = "workbench@aicte.local"
        message["To"] = data["recipient"]
        message.set_content(data["body"])
        state = "SENT"
        try:
            with smtplib.SMTP("mailpit", 1025, timeout=5) as server:
                server.send_message(message)
        except (OSError, smtplib.SMTPException):
            state = "UNKNOWN"
        with engine.begin() as conn:
            conn.execute(
                update(t.notifications)
                .where(t.notifications.c.id == data["id"])
                .values(
                    status=state,
                    provider_reference=str(message["Message-ID"]),
                    sent_at=now() if state == "SENT" else None,
                    retry_count=1,
                    retry_history=[{"status": state, "at": now().isoformat()}],
                )
            )
        return {"status": state}
    finally:
        engine.dispose()
