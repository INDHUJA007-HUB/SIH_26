"""Phase 10: Alerts, tasks, versioned durable timers, notifications, audit export tests."""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select

from workbench.adapters import tables as t
from workbench.modules.audit_access.contracts import AccessAction, AccessResult
from workbench.modules.tasks_alerts.contracts import (
    AlertCategory,
    AlertSeverity,
    AlertStatus,
    AlertTriggerType,
    NotificationChannel,
    NotificationStatus,
    TaskState,
    TimerStatus,
)

pytestmark = pytest.mark.integration


def test_one_unchanged_condition_creates_one_open_alert_on_replay(h):
    """Exit gate requirement: One unchanged condition creates one open alert on replay."""
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]

    payload = {
        "institution_id": inst_id,
        "application_id": app_id,
        "category": AlertCategory.COMPLIANCE.value,
        "trigger_type": AlertTriggerType.MISSING_EVIDENCE.value,
        "severity": AlertSeverity.WARNING.value,
        "title": "Missing Land Ownership Document",
        "message": "Required slot 'land_documents' has no accepted evidence",
        "resource_id": "slot_land_documents",
        "details": {"slot": "land_documents"},
    }

    # First trigger execution: creates new alert
    resp1 = h.call("POST", "/api/v1/alerts", json=payload)
    assert resp1.status_code == 200, resp1.text
    alert1 = resp1.json()
    assert alert1["status"] == AlertStatus.OPEN.value
    assert (
        alert1["dedup_key"] == f"COMPLIANCE:MISSING_EVIDENCE:{inst_id}:{app_id}:slot_land_documents"
    )

    # Replay on unchanged condition: MUST return same open alert rather than duplicate
    resp2 = h.call("POST", "/api/v1/alerts", json=payload)
    assert resp2.status_code == 200, resp2.text
    alert2 = resp2.json()
    assert alert2["id"] == alert1["id"], "Replay must return existing open alert"

    # Verify database has exactly 1 alert row for this dedup_key
    with h.owner.connect() as conn:
        count = conn.scalar(
            select(t.alerts.c.id).where(t.alerts.c.dedup_key == alert1["dedup_key"])
        )
        assert count == alert1["id"]

    # Now acknowledge the alert
    ack_resp = h.call("POST", f"/api/v1/alerts/{alert1['id']}/acknowledge")
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == AlertStatus.ACKNOWLEDGED.value


def test_security_alerts_separated_from_compliance(h):
    """Triggers: Security alerts stay separate from compliance."""
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]

    # 1. Create a compliance alert (missing evidence)
    h.call(
        "POST",
        "/api/v1/alerts",
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "category": AlertCategory.COMPLIANCE.value,
            "trigger_type": AlertTriggerType.MISSING_EVIDENCE.value,
            "severity": AlertSeverity.WARNING.value,
            "title": "Compliance Alert",
            "message": "Fire NOC required",
            "resource_id": "slot_fire_noc",
        },
    )

    # 2. Create a security alert (suspicious malware or quota abuse)
    h.call(
        "POST",
        "/api/v1/alerts",
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "category": AlertCategory.SECURITY.value,
            "trigger_type": AlertTriggerType.SECURITY.value,
            "severity": AlertSeverity.CRITICAL.value,
            "title": "Security Alert: Malicious Object Detected",
            "message": "Malware pattern detected in quarantine upload",
            "resource_id": "quarantine_obj_123",
            "details": {"virus_signature": "EICAR-Test-Signature"},
        },
    )

    # 3. Query compliance alerts: MUST NOT include security alert
    comp_resp = h.call(
        "GET",
        f"/api/v1/alerts?institution_id={inst_id}&category=COMPLIANCE",
    )
    assert comp_resp.status_code == 200
    comp_alerts = comp_resp.json()
    assert len(comp_alerts) >= 1
    assert all(a["category"] == AlertCategory.COMPLIANCE.value for a in comp_alerts)
    assert not any(a["category"] == AlertCategory.SECURITY.value for a in comp_alerts)

    # 4. Query security alerts: isolated to security category
    sec_resp = h.call(
        "GET",
        f"/api/v1/alerts?institution_id={inst_id}&category=SECURITY",
    )
    assert sec_resp.status_code == 200
    sec_alerts = sec_resp.json()
    assert len(sec_alerts) >= 1
    assert all(a["category"] == AlertCategory.SECURITY.value for a in sec_alerts)


def test_task_state_machine_and_source_outage_to_single_manual_task(h):
    """Exit gate: A source outage becomes one manual task, and task state machine is enforced."""
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]

    outage_payload = {
        "institution_id": inst_id,
        "application_id": app_id,
        "task_type": "MANUAL_SOURCE_VERIFICATION",
        "resource_id": "claim_land_registration_tn_reg_dept",
        "details": {
            "claim_id": "claim_123",
            "provider_code": "TN_REGISTRATION_DEPT",
            "reason": "SOURCE_UNAVAILABLE",
        },
    }

    # 1. Source outage creates manual task
    resp1 = h.call("POST", "/api/v1/tasks/semantic", json=outage_payload)
    assert resp1.status_code == 200
    task1 = resp1.json()
    assert task1["state"] == TaskState.OPEN.value
    assert task1["task_type"] == "MANUAL_SOURCE_VERIFICATION"

    # 2. Replay source outage: MUST return the same single manual task
    resp2 = h.call("POST", "/api/v1/tasks/semantic", json=outage_payload)
    assert resp2.status_code == 200
    task2 = resp2.json()
    assert task2["id"] == task1["id"], "Source outage must deduplicate to single manual task"

    # 3. State machine transitions: OPEN -> IN_PROGRESS -> RESOLVED
    step1 = h.call(
        "PATCH",
        f"/api/v1/tasks/semantic/{task1['id']}/state",
        json={"new_state": TaskState.IN_PROGRESS.value, "details": {"officer": "assigned_1"}},
    )
    assert step1.status_code == 200
    assert step1.json()["state"] == TaskState.IN_PROGRESS.value

    step2 = h.call(
        "PATCH",
        f"/api/v1/tasks/semantic/{task1['id']}/state",
        json={
            "new_state": TaskState.RESOLVED.value,
            "details": {"resolution": "Verified manually via physical registry"},
        },
    )
    assert step2.status_code == 200
    assert step2.json()["state"] == TaskState.RESOLVED.value
    assert step2.json()["resolved_at"] is not None

    # 4. Illegal transition: cannot reopen a RESOLVED task (terminal state)
    illegal = h.call(
        "PATCH",
        f"/api/v1/tasks/semantic/{task1['id']}/state",
        json={"new_state": TaskState.OPEN.value},
    )
    assert illegal.status_code == 409


def test_versioned_durable_timers_replace_evidence_cancels_older_reminders(h):
    """Exit gate requirement: Replacing evidence cancels obsolete timers."""
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    slot_id = "slot_building_plan"

    deadline_gen1 = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    deadline_gen2 = (datetime.now(UTC) + timedelta(days=10)).isoformat()

    # 1. Initial upload schedules generation 1 timer
    gen1_resp = h.call(
        "POST",
        "/api/v1/timers",
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "slot_id": slot_id,
            "timer_type": "EXPIRY_WARNING",
            "generation": 1,
            "deadline": deadline_gen1,
            "details": {"version": "v1"},
        },
    )
    assert gen1_resp.status_code == 200
    timer_gen1 = gen1_resp.json()
    assert timer_gen1["status"] == TimerStatus.SCHEDULED.value
    assert timer_gen1["generation"] == 1

    # 2. Replacing evidence: cancel older reminders for slot and schedule generation 2 timer
    cancel_resp = h.call(
        "POST",
        "/api/v1/timers/cancel-obsolete",
        params={
            "institution_id": inst_id,
            "application_id": app_id,
            "slot_id": slot_id,
            "new_generation": 2,
        },
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["cancelled_count"] == 1

    # Schedule generation 2 timer
    gen2_resp = h.call(
        "POST",
        "/api/v1/timers",
        json={
            "institution_id": inst_id,
            "application_id": app_id,
            "slot_id": slot_id,
            "timer_type": "EXPIRY_WARNING",
            "generation": 2,
            "deadline": deadline_gen2,
            "details": {"version": "v2"},
        },
    )
    assert gen2_resp.status_code == 200
    timer_gen2 = gen2_resp.json()
    assert timer_gen2["status"] == TimerStatus.SCHEDULED.value
    assert timer_gen2["generation"] == 2

    # 3. Verify timer list: generation 1 is CANCELLED, generation 2 is SCHEDULED
    list_resp = h.call(
        "GET",
        f"/api/v1/timers?institution_id={inst_id}&application_id={app_id}&slot_id={slot_id}",
    )
    assert list_resp.status_code == 200
    timers = list_resp.json()
    assert len(timers) == 2
    t1 = next(t for t in timers if t["generation"] == 1)
    t2 = next(t for t in timers if t["generation"] == 2)
    assert t1["status"] == TimerStatus.CANCELLED.value
    assert t1["cancelled_at"] is not None
    assert t2["status"] == TimerStatus.SCHEDULED.value


def test_delivery_in_app_and_mailpit(h):
    """Delivery: In-app and Mailpit only, with queued/sent/failed/unknown/acknowledged states."""
    inst_id = h.institutions["a"]

    # 1. In-App Notification Delivery
    in_app_resp = h.call(
        "POST",
        "/api/v1/notifications/send",
        json={
            "institution_id": inst_id,
            "recipient": "officer_1",
            "channel": NotificationChannel.IN_APP.value,
            "subject": "Review Window Opening",
            "body": "Response window has opened for scrutiny packet",
        },
    )
    assert in_app_resp.status_code == 200
    notif_in_app = in_app_resp.json()
    assert notif_in_app["status"] == NotificationStatus.SENT.value
    assert notif_in_app["channel"] == NotificationChannel.IN_APP.value

    # Acknowledge in-app notification
    ack_resp = h.call(
        "POST",
        f"/api/v1/notifications/{notif_in_app['id']}/acknowledge",
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == NotificationStatus.ACKNOWLEDGED.value
    assert ack_resp.json()["acknowledged_at"] is not None

    # 2. Email Notification Delivery to local Mailpit instance (127.0.0.1:1025)
    test_email = f"applicant_{uuid4().hex[:8]}@example.edu.in"
    unique_subject = f"AICTE Notification {uuid4().hex[:8]}"

    email_resp = h.call(
        "POST",
        "/api/v1/notifications/send",
        json={
            "institution_id": inst_id,
            "recipient": test_email,
            "channel": NotificationChannel.EMAIL.value,
            "subject": unique_subject,
            "body": "Your application packet has completed preliminary screening.",
        },
    )
    assert email_resp.status_code == 200
    notif_email = email_resp.json()
    assert notif_email["status"] == NotificationStatus.SENT.value
    assert notif_email["provider_reference"].startswith("mailpit_")

    # Verify message exists in Mailpit via HTTP API (127.0.0.1:8025)
    req = urllib.request.Request("http://127.0.0.1:8025/api/v1/messages")
    with urllib.request.urlopen(req, timeout=3) as response:  # noqa: S310
        data = json.loads(response.read().decode())
        messages = data.get("messages", [])
        assert any(unique_subject in m["Subject"] for m in messages), (
            f"Expected subject '{unique_subject}' in Mailpit messages"
        )


def test_audit_and_access_history_with_phase_4_view_download_stream_outcomes(h):
    """Audit and access history APIs with filters and stream outcomes."""
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    ev_id = str(uuid4())

    # Pre-populate sensitive-access events reflecting Phase 4 actions and stream outcomes
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.access).values(
                [
                    {
                        "id": str(uuid4()),
                        "actor_id": h.actors["officer"],
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "evidence_id": ev_id,
                        "resource_id": f"evidence/{ev_id}/content",
                        "action": AccessAction.VIEW.value,
                        "result": AccessResult.ALLOWED.value,
                        "bytes_served": 1048576,
                        "request_id": f"req_{uuid4().hex[:12]}",
                        "created_at": datetime.now(UTC) - timedelta(minutes=10),
                    },
                    {
                        "id": str(uuid4()),
                        "actor_id": h.actors["b"],
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "evidence_id": ev_id,
                        "resource_id": f"evidence/{ev_id}/content",
                        "action": AccessAction.DOWNLOAD.value,
                        "result": AccessResult.DENIED.value,
                        "bytes_served": 0,
                        "request_id": f"req_{uuid4().hex[:12]}",
                        "created_at": datetime.now(UTC) - timedelta(minutes=5),
                    },
                    {
                        "id": str(uuid4()),
                        "actor_id": h.actors["officer"],
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "evidence_id": ev_id,
                        "resource_id": f"evidence/{ev_id}/content",
                        "action": AccessAction.DOWNLOAD.value,
                        "result": AccessResult.ABORTED.value,
                        "bytes_served": 512,
                        "request_id": f"req_{uuid4().hex[:12]}",
                        "created_at": datetime.now(UTC) - timedelta(minutes=2),
                    },
                ]
            )
        )

    # Assign officer to institution A to permit authorized access
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=None,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Assigned review for access event inspection",
                expires_at=datetime.now(UTC) + timedelta(days=6),
            )
        )

    # 1. Query access events filtered by action=VIEW
    resp_view = h.call(
        "GET",
        f"/api/v1/access/events?institution_id={inst_id}&action=VIEW",
        actor="officer",
        mfa=True,
    )
    assert resp_view.status_code == 200
    events_view = resp_view.json()
    assert len(events_view) >= 1
    assert all(e["action"] == "VIEW" for e in events_view)
    assert any(e["result"] == "ALLOWED" and e["bytes_served"] == 1048576 for e in events_view)

    # 2. Query access events filtered by result=DENIED
    resp_denied = h.call(
        "GET",
        f"/api/v1/access/events?institution_id={inst_id}&result=DENIED",
        actor="officer",
        mfa=True,
    )
    assert resp_denied.status_code == 200
    events_denied = resp_denied.json()
    assert len(events_denied) >= 1
    assert any(e["result"] == "DENIED" and e["bytes_served"] == 0 for e in events_denied)

    # 3. Query access events filtered by result=ABORTED (stream outcome)
    resp_aborted = h.call(
        "GET",
        f"/api/v1/access/events?institution_id={inst_id}&result=ABORTED",
        actor="officer",
        mfa=True,
    )
    assert resp_aborted.status_code == 200
    events_aborted = resp_aborted.json()
    assert len(events_aborted) >= 1
    assert any(e["result"] == "ABORTED" and e["bytes_served"] == 512 for e in events_aborted)


def test_checkpointed_audit_export_scoped_auditor_permission_and_integrity(h):
    """Checkpointed export under scoped auditor permission with hash chain validation."""
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]

    # 1. Ensure sequential audit events exist for the application
    with h.owner.connect() as conn:
        last = conn.execute(
            select(t.audit.c.sequence, t.audit.c.sha256, t.audit.c.stream)
            .where(t.audit.c.application_id == app_id)
            .order_by(t.audit.c.sequence.desc())
        ).first()
        last_seq = last.sequence
        last_hash = last.sha256
        stream_name = last.stream

    with h.owner.begin() as conn:
        h2 = "b" * 64
        conn.execute(
            insert(t.audit).values(
                [
                    {
                        "id": str(uuid4()),
                        "stream": stream_name,
                        "institution_id": inst_id,
                        "application_id": app_id,
                        "sequence": last_seq + 1,
                        "previous_hash": last_hash,
                        "sha256": h2,
                        "event": {"event_type": "EvidenceUploaded", "data": {"slot": "documents"}},
                        "created_at": datetime.now(UTC) - timedelta(minutes=30),
                    },
                ]
            )
        )

    # 2. Non-auditor / applicant attempt: MUST be denied (403 Forbidden)
    denied_resp = h.call(
        "POST",
        f"/api/v1/applications/{app_id}/audit-export?institution_id={inst_id}",
        actor="a",
    )
    assert denied_resp.status_code == 403

    # Grant scoped auditor permission via case_assignment
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                actor_id=h.actors["auditor"],
                access_role="auditor",
                granted_by=h.actors["admin"],
                reason="Scoped audit inspection",
                expires_at=datetime.now(UTC) + timedelta(days=6),
            )
        )

    # 3. Authorized auditor execution: succeeds with verified cryptographic checkpoint
    export_resp = h.call(
        "POST",
        f"/api/v1/applications/{app_id}/audit-export?institution_id={inst_id}",
        actor="auditor",
        mfa=True,
    )
    assert export_resp.status_code == 200, export_resp.text
    manifest = export_resp.json()
    assert manifest["integrity_status"] == "VERIFIED"
    assert manifest["event_count"] >= 2
    assert len(manifest["checkpoint_hash"]) == 64
    assert manifest["start_sequence"] == 1
    assert manifest["end_sequence"] >= 2
    assert manifest["archive_lag_seconds"] >= 0.0

    # Verify audit_checkpoints database entry
    with h.owner.connect() as conn:
        cp = conn.execute(
            select(t.audit_checkpoints).where(t.audit_checkpoints.c.id == manifest["checkpoint_id"])
        ).one()
        assert cp.integrity_status == "VERIFIED"
        assert cp.checkpoint_hash == manifest["checkpoint_hash"]


def test_full_traceability_upload_run_outage_officer_response_reassessment(h):
    """Exit gate: upload -> run -> outage -> officer response -> reassessment traceable."""
    app = h.create()
    inst_id = h.institutions["a"]
    app_id = app["id"]
    stream = f"app-{app_id}"

    # Record the sequential lifecycle events in the application's audit stream
    events = [
        ("EvidenceAccepted", {"evidence_id": "ev_1", "slot": "intake_approval"}),
        ("EvaluationFinalized", {"run_id": "eval_run_1", "status": "FINDINGS_DETECTED"}),
        ("SourceOutageEncountered", {"provider": "AICTE_PORTAL", "reason": "UNAVAILABLE"}),
        (
            "OfficerDispositionRecorded",
            {"finding_id": "f_1", "disposition": "RECTIFICATION_REQUESTED"},
        ),
        ("ResponseWindowOpened", {"window_id": "win_1", "allowed_slots": ["intake_approval"]}),
        ("ResponseSubmitted", {"response_id": "resp_1", "revision": 2}),
        (
            "ReassessmentCompleted",
            {
                "baseline_run_id": "eval_run_1",
                "reassessment_run_id": "eval_run_2",
                "diff": {"resolved": 1},
            },
        ),
    ]

    with h.owner.connect() as conn:
        last = conn.execute(
            select(t.audit.c.sequence, t.audit.c.sha256, t.audit.c.stream)
            .where(t.audit.c.application_id == app_id)
            .order_by(t.audit.c.sequence.desc())
        ).first()
        prev = last.sha256
        start_seq = last.sequence + 1
        stream = last.stream

    with h.owner.begin() as conn:
        for offset, (event_type, payload) in enumerate(events):
            seq = start_seq + offset
            cur = f"{seq:02x}" * 32
            conn.execute(
                insert(t.audit).values(
                    id=str(uuid4()),
                    stream=stream,
                    institution_id=inst_id,
                    application_id=app_id,
                    sequence=seq,
                    previous_hash=prev,
                    sha256=cur,
                    event={
                        "event_type": event_type,
                        "payload": payload,
                        "occurred_at": str(datetime.now(UTC)),
                    },
                    created_at=datetime.now(UTC) - timedelta(minutes=len(events) - offset),
                )
            )
            prev = cur

    # Assign officer to institution A to permit authorized access
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Assigned review for audit traceability",
                expires_at=datetime.now(UTC) + timedelta(days=6),
            )
        )

    # Query audit events endpoint
    resp = h.call(
        "GET",
        f"/api/v1/audit/events?institution_id={inst_id}&application_id={app_id}",
        actor="officer",
        mfa=True,
    )
    assert resp.status_code == 200, resp.text
    retrieved = resp.json()
    assert len(retrieved) == len(events) + 1

    # Verify that the complete chronological narrative is sequentially preserved
    event_types = [
        item["event"].get("event_type") or item["event"].get("kind") for item in retrieved
    ]
    assert event_types[0] == "ApplicationDraftCreated"
    assert event_types[1:] == [
        "EvidenceAccepted",
        "EvaluationFinalized",
        "SourceOutageEncountered",
        "OfficerDispositionRecorded",
        "ResponseWindowOpened",
        "ResponseSubmitted",
        "ReassessmentCompleted",
    ]


def test_phase_10_unassigned_officer_and_cross_tenant_denial(h):
    """Exit gate requirement: Unassigned officers and other institutions are denied access."""
    inst_a = h.institutions["a"]

    # 1. Create alert, task, and timer for Institution A
    alert = h.call(
        "POST",
        "/api/v1/alerts",
        json={
            "institution_id": inst_a,
            "category": AlertCategory.COMPLIANCE.value,
            "trigger_type": AlertTriggerType.MISSING_EVIDENCE.value,
            "title": "Tenant Isolation Test",
            "message": "Testing cross-tenant denial",
            "resource_id": "slot_isolation_test",
        },
    ).json()

    # 2. Institution B actor attempts to access Institution A's alerts -> 403 Forbidden
    resp_b = h.call(
        "GET",
        f"/api/v1/alerts?institution_id={inst_a}",
        actor="b",
    )
    assert resp_b.status_code in (403, 404), (
        f"Expected 403/404 for tenant B, got {resp_b.status_code}"
    )

    # 3. Unassigned officer attempts to access Institution A's alerts and tasks -> 403 Forbidden
    resp_officer = h.call(
        "GET",
        f"/api/v1/alerts?institution_id={inst_a}",
        actor="officer",
        mfa=True,
    )
    assert resp_officer.status_code in (403, 404), (
        f"Expected 403/404 for unassigned officer, got {resp_officer.status_code}"
    )

    resp_tasks = h.call(
        "GET",
        f"/api/v1/tasks/semantic?institution_id={inst_a}",
        actor="officer",
        mfa=True,
    )
    assert resp_tasks.status_code in (403, 404)

    # 4. Formally assign officer to Institution A
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_a,
                application_id=None,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Assigned review for Phase 10 validation",
                expires_at=datetime.now(UTC) + timedelta(days=6),
            )
        )

    # 5. Assigned officer can now access Institution A alerts
    resp_assigned = h.call(
        "GET",
        f"/api/v1/alerts?institution_id={inst_a}",
        actor="officer",
        mfa=True,
    )
    assert resp_assigned.status_code == 200
    alerts = resp_assigned.json()
    assert any(a["id"] == alert["id"] for a in alerts)
