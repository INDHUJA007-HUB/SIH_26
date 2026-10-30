"""Database-enforced audience isolation and server-controlled reassessment regressions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest

from workbench.adapters import tables as t

pytestmark = pytest.mark.integration


def test_applicant_cannot_generate_or_read_officer_report(h):
    app = h.create()
    run_id = str(uuid4())
    with h.owner.begin() as conn:
        conn.execute(
            t.evaluation_runs.insert().values(
                id=run_id,
                institution_id=h.institutions["a"],
                application_id=app["id"],
                manifest_hash="test",
                evaluation_as_of="2026-10-29",
            )
        )
    payload = {
        "institution_id": h.institutions["a"],
        "application_id": app["id"],
        "evaluation_run_id": run_id,
        "audience": "OFFICER",
    }
    assert h.call("POST", "/api/v1/reports/generate", json=payload).status_code == 403
    officer = h.call("POST", "/api/v1/reports/generate", json=payload, actor="supervisor", mfa=True)
    assert officer.status_code == 200, officer.text
    report_id = officer.json()["id"]
    assert h.call("GET", f"/api/v1/reports/{report_id}").status_code in {403, 404}
    assert h.call("GET", f"/api/v1/reports/{report_id}/pdf").status_code in {403, 404}
    reports = h.call("GET", f"/api/v1/reports?institution_id={h.institutions['a']}")
    assert reports.status_code == 200, reports.text
    assert all(r["audience"] == "APPLICANT" for r in reports.json())


def test_reassessment_rejects_client_findings(h):
    app = h.create()
    payload = {
        "institution_id": h.institutions["a"],
        "application_id": app["id"],
        "response_id": str(uuid4()),
        "baseline_run_id": str(uuid4()),
        "reassessed_findings": [{"semantic_key": "fabricated-pass"}],
    }
    assert h.call("POST", "/api/v1/rectification/reassess", json=payload).status_code == 403
    response = h.call(
        "POST", "/api/v1/rectification/reassess", json=payload, actor="supervisor", mfa=True
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "CLIENT_RESULTS_FORBIDDEN"


def test_durable_timer_fires_once_from_persisted_intent(h):
    from sqlalchemy import select

    from workbench.activities.lifecycle import fire_durable_timer, load_durable_timer

    app = h.create()
    scheduled = h.call(
        "POST",
        "/api/v1/timers",
        json={
            "institution_id": h.institutions["a"],
            "application_id": app["id"],
            "timer_type": "RESPONSE_DEADLINE",
            "generation": 1,
            "deadline": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        },
    )
    assert scheduled.status_code == 200, scheduled.text
    with h.owner.connect() as conn:
        event_id = conn.scalar(
            select(t.outbox.c.id).where(
                t.outbox.c.application_id == app["id"],
                t.outbox.c.event_type == "DurableTimerScheduled",
            )
        )
    assert load_durable_timer(event_id)["status"] == "SCHEDULED"
    assert fire_durable_timer(event_id)["status"] == "FIRED"
    assert fire_durable_timer(event_id)["status"] == "FIRED"
    with h.owner.connect() as conn:
        tasks = conn.execute(
            select(t.review_tasks).where(t.review_tasks.c.application_id == app["id"])
        ).all()
        assert len(tasks) == 1


def test_ambiguous_email_delivery_is_not_repeated(h):
    from sqlalchemy import select

    from workbench.activities.lifecycle import deliver_notification

    app = h.create()
    queued = h.call(
        "POST",
        "/api/v1/notifications/send",
        json={
            "institution_id": h.institutions["a"],
            "application_id": app["id"],
            "recipient": "synthetic@example.test",
            "channel": "EMAIL",
            "body": "Synthetic test",
        },
    )
    assert queued.status_code == 200, queued.text
    with h.owner.connect() as conn:
        event_id = conn.scalar(
            select(t.outbox.c.id).where(
                t.outbox.c.application_id == app["id"],
                t.outbox.c.event_type == "NotificationQueued",
            )
        )
    with patch(
        "workbench.activities.lifecycle.smtplib.SMTP", side_effect=OSError("Ambiguous timeout")
    ) as smtp:
        assert deliver_notification(event_id)["status"] == "UNKNOWN"
        assert deliver_notification(event_id)["status"] == "UNKNOWN"
        assert smtp.call_count == 1
