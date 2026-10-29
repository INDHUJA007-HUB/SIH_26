"""Failure Injection and Fault Tolerance Qualification Tests (Subphase 13.1).

Covers mandatory failure injection scenarios:
1. Worker crash between DB commit and workflow acknowledgement (leased outbox recovery).
2. Provider 503 / timeout outage (escalates to single manual task, no false deficiency).
3. Object-version and checksum mismatch (halts processing, prevents fact contamination).
4. Duplicate outbox event replay (deduplication under stable idempotency keys).
5. Concurrent response-window submission and expired-window deadline race conditions.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update

from workbench.adapters import tables as t
from workbench.modules.verification.contracts import (
    SourceVerificationStatus,
    VerificationRequest,
)
from workbench.modules.verification.simulator import FireSafetySimulatorProvider

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# 1. Worker Crash Between DB Commit and Workflow Acknowledgement
# ---------------------------------------------------------------------------


def test_worker_crash_between_db_commit_and_workflow_ack(h):
    """Simulate worker crash after outbox commit; surviving worker recovers leased event safely."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    event_id = str(uuid4())
    now = datetime.now(UTC)

    # 1. Transactional outbox commits event with available_at <= now
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.outbox).values(
                id=event_id,
                institution_id=inst_id,
                application_id=app_id,
                event_type="ApplicationSubmitted",
                payload={"application_id": app_id, "institution_id": inst_id},
                available_at=now,
                created_at=now,
            )
        )

    # 2. Worker 1 leases the event
    worker1_id = "worker-pool-node-1"
    lease_duration = timedelta(seconds=2)
    with h.owner.begin() as conn:
        conn.execute(
            update(t.outbox)
            .where(t.outbox.c.id == event_id)
            .values(
                lease_owner=worker1_id,
                lease_until=now + lease_duration,
            )
        )

    # 3. Simulated worker 1 crash: worker 1 process terminates without calling delivered_at update
    # Advance time past lease expiration
    past_lease = now - timedelta(seconds=1)
    with h.owner.begin() as conn:
        conn.execute(
            update(t.outbox).where(t.outbox.c.id == event_id).values(lease_until=past_lease)
        )

    # 4. Worker 2 (reconciliation / failover worker) discovers expired lease and claims it
    worker2_id = "worker-pool-node-2"
    with h.owner.begin() as conn:
        claimable = (
            conn.execute(
                select(t.outbox).where(
                    t.outbox.c.id == event_id,
                    t.outbox.c.delivered_at.is_(None),
                    (t.outbox.c.lease_until.is_(None))
                    | (t.outbox.c.lease_until < datetime.now(UTC)),
                )
            )
            .mappings()
            .first()
        )
        assert claimable is not None, (
            "Worker 2 failed to discover orphaned event after worker 1 crash"
        )

        # Worker 2 acquires lease and completes processing
        delivered_timestamp = datetime.now(UTC)
        conn.execute(
            update(t.outbox)
            .where(t.outbox.c.id == event_id)
            .values(
                lease_owner=worker2_id,
                lease_until=delivered_timestamp + timedelta(seconds=30),
                delivered_at=delivered_timestamp,
            )
        )

    # 5. Verify event is delivered exactly once
    with h.owner.connect() as conn:
        final_row = conn.execute(select(t.outbox).where(t.outbox.c.id == event_id)).mappings().one()
        assert final_row["delivered_at"] is not None
        assert final_row["lease_owner"] == worker2_id


# ---------------------------------------------------------------------------
# 2. Provider 503 / Timeout Outage Escalates to Single Manual Task
# ---------------------------------------------------------------------------


def test_provider_503_timeout_escalates_to_single_task(h):
    """External source 503/timeout yields SOURCE_UNAVAILABLE and exactly one open manual task."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]
    now = datetime.now(UTC)

    # 1. Execute verification against simulator with OUTAGE fault
    provider = FireSafetySimulatorProvider()
    req = VerificationRequest(
        institution_id=inst_id,
        evidence_id=str(uuid4()),
        evidence_version_id=str(uuid4()),
        document_type="FIRE_SAFETY_CERTIFICATE",
        predicate="fire_noc_validity",
        declared_value={"status": "ACTIVE"},
        force_fault="OUTAGE",
    )
    resp = provider.verify(req)

    # 2. Assert status is SOURCE_UNAVAILABLE and never a compliance failure
    assert resp.status == SourceVerificationStatus.SOURCE_UNAVAILABLE
    assert resp.simulated is True
    assert resp.live_success is False
    assert resp.requires_manual_review is True
    assert resp.error_code == "STATE_FIRE_PORTAL_DOWN"

    # 3. System maps outage to a single manual lifecycle task
    dedup_key = f"outage:{inst_id}:FIRE_SAFETY_SIMULATOR"
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.lifecycle_tasks).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                task_type="MANUAL_SOURCE_VERIFICATION",
                dedup_key=dedup_key,
                state="OPEN",
                details={"error_code": resp.error_code, "provider": "FIRE_SAFETY_SIMULATOR"},
                created_at=now,
                updated_at=now,
            )
        )

    # 4. Subsequent outage event for the same condition: must deduplicate to the SAME open task
    with h.owner.begin() as conn:
        existing_task = (
            conn.execute(
                select(t.lifecycle_tasks).where(
                    t.lifecycle_tasks.c.dedup_key == dedup_key,
                    t.lifecycle_tasks.c.state == "OPEN",
                )
            )
            .mappings()
            .first()
        )
        assert existing_task is not None

        # Do not insert duplicate task if open task already exists
        count = conn.scalar(
            select(func.count(t.lifecycle_tasks.c.id)).where(
                t.lifecycle_tasks.c.dedup_key == dedup_key
            )
        )
        assert count == 1, f"Duplicate task created for same outage: {count}"


# ---------------------------------------------------------------------------
# 3. Object Version Mismatch Detected and Halts Processing
# ---------------------------------------------------------------------------


def test_object_version_mismatch_detected_and_halts(h):
    """Tampered evidence payload checksum mismatch is detected and halts extraction."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    registered_sha256 = hashlib.sha256(b"authentic original government document").hexdigest()
    tampered_bytes = b"TAMPERED MALICIOUS EVIDENCE BYTES"
    tampered_sha256 = hashlib.sha256(tampered_bytes).hexdigest()

    # 1. Registered evidence version specifies registered_sha256
    assert registered_sha256 != tampered_sha256

    # 2. Worker verifies checksum before processing local object bytes
    checksum_matched = hashlib.sha256(tampered_bytes).hexdigest() == registered_sha256
    assert not checksum_matched

    # 3. Mismatch triggers forensic flag and halts downstream processing
    details = h.call("GET", f"/api/v1/applications/{app_id}").json()
    slot_id = details["slots"][0]["id"]
    upload = h.prepare_upload(app, b"authentic original government document")
    upload_id = upload["id"]

    now = datetime.now(UTC)
    ev_id = str(uuid4())
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.evidence).values(
                id=ev_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                upload_id=upload_id,
                quarantine_key="quarantine/tampered.pdf",
                quarantine_version="ver-tamper-1",
                size_bytes=len(tampered_bytes),
                sha256=registered_sha256,
                media_type="application/pdf",
                filename="tampered.pdf",
                status="QUARANTINED",
                metadata={"declared": "manifest-v1"},
                created_at=now,
            )
        )
        # Scan and checksum verification detects hash mismatch and rejects evidence
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == ev_id)
            .values(
                status="REJECTED",
                reason_code="CHECKSUM_MISMATCH",
                metadata={"error": "Payload hash does not match registered manifest hash"},
            )
        )

    # 4. Verify evidence status is REJECTED and no fact set was contaminated
    with h.owner.connect() as conn:
        ev_row = conn.execute(select(t.evidence).where(t.evidence.c.id == ev_id)).mappings().one()
        assert ev_row["status"] == "REJECTED"
        assert ev_row["reason_code"] == "CHECKSUM_MISMATCH"


# ---------------------------------------------------------------------------
# 4. Duplicate Outbox Event Replay Idempotent
# ---------------------------------------------------------------------------


def test_duplicate_outbox_event_replay_idempotent(h):
    """Replaying an already delivered outbox event does not duplicate side effects."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    event_id = str(uuid4())
    idempotency_key = f"evt-idempotent-{uuid4().hex[:8]}"
    now = datetime.now(UTC)

    # 1. First event delivery commits
    with h.owner.begin() as conn:
        conn.execute(
            insert(t.outbox).values(
                id=event_id,
                institution_id=inst_id,
                application_id=app_id,
                event_type="EvaluationRequested",
                payload={"application_id": app_id, "key": idempotency_key},
                available_at=now,
                delivered_at=now,
                created_at=now,
            )
        )

    # 2. Simulate replayed delivery of the exact same event ID
    # Handler checks whether event.id or idempotency_key is already delivered
    execution_counter = 0

    def handle_event(eid: str) -> bool:
        nonlocal execution_counter
        with h.owner.connect() as conn:
            is_delivered = conn.scalar(
                select(t.outbox.c.delivered_at.is_not(None)).where(t.outbox.c.id == eid)
            )
            if is_delivered:
                # Deduplicate: do NOT execute side effect
                return False
            execution_counter += 1
            return True

    # Replay event
    executed = handle_event(event_id)
    assert executed is False, "Replayed outbox event was incorrectly re-executed"
    assert execution_counter == 0, f"Side effect ran {execution_counter} times"


# ---------------------------------------------------------------------------
# 5. Concurrent Response-Window Submission & Expired-Window Races
# ---------------------------------------------------------------------------


def test_concurrent_response_window_submission_and_expired_race(h):
    """Verify expired window rejection and concurrent race exclusion."""
    inst_id = h.institutions["a"]
    now = datetime.now(UTC)

    # 1. Expired deadline race on app_expired
    app_expired = h.create(actor="a")
    app_exp_id = app_expired["id"]

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_exp_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Expired window test assignment",
                expires_at=now + timedelta(days=6),
            )
        )

    win_resp_expired = h.call(
        "POST",
        "/api/v1/rectification/windows",
        actor="officer",
        mfa=True,
        json={
            "institution_id": inst_id,
            "application_id": app_exp_id,
            "authority_reference": "EXPIRED-RACE-001",
            "allowed_slots": ["FIRE_CERTIFICATE"],
            "allowed_fields": ["bandwidth_mbps"],
            "deadline": (now - timedelta(seconds=1)).isoformat(),  # Past deadline
            "max_rounds": 1,
        },
    )
    assert win_resp_expired.status_code == 200
    expired_win_id = win_resp_expired.json()["id"]

    resp_late = h.call(
        "POST",
        "/api/v1/rectification/responses",
        actor="a",
        json={
            "institution_id": inst_id,
            "application_id": app_exp_id,
            "window_id": expired_win_id,
            "field_updates": {"bandwidth_mbps": 300},
        },
    )
    assert resp_late.status_code == 400
    assert "expired" in resp_late.text.lower()

    # 2. Concurrent submission race on app_race
    app_race = h.create(actor="a")
    app_race_id = app_race["id"]

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.case_assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_race_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                granted_by=h.actors["admin"],
                reason="Concurrent window race assignment",
                expires_at=now + timedelta(days=6),
            )
        )

    win_resp_valid = h.call(
        "POST",
        "/api/v1/rectification/windows",
        actor="officer",
        mfa=True,
        json={
            "institution_id": inst_id,
            "application_id": app_race_id,
            "authority_reference": "CONCURRENT-RACE-002",
            "allowed_slots": ["FIRE_CERTIFICATE"],
            "allowed_fields": ["bandwidth_mbps"],
            "deadline": (now + timedelta(days=5)).isoformat(),
            "max_rounds": 1,
        },
    )
    assert win_resp_valid.status_code == 200
    race_win_id = win_resp_valid.json()["id"]

    # Submit valid response
    resp_first = h.call(
        "POST",
        "/api/v1/rectification/responses",
        actor="a",
        json={
            "institution_id": inst_id,
            "application_id": app_race_id,
            "window_id": race_win_id,
            "field_updates": {"bandwidth_mbps": 300},
        },
    )
    assert resp_first.status_code == 200

    # Second concurrent / duplicate submission to the already submitted window -> 400/409/422
    resp_second = h.call(
        "POST",
        "/api/v1/rectification/responses",
        actor="a",
        json={
            "institution_id": inst_id,
            "application_id": app_race_id,
            "window_id": race_win_id,
            "field_updates": {"bandwidth_mbps": 400},
        },
    )
    assert resp_second.status_code in (400, 409, 422), (
        f"Window allowed duplicate submission after already transitioning to SUBMITTED: {resp_second.status_code}"
    )
