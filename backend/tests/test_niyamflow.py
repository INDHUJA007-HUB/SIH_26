"""SIH26262 acceptance: real RLS, human closure and concurrent booking."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import insert, select, update

from workbench.adapters import niyam_tables as n
from workbench.adapters import tables as t
from workbench.modules.approval_workflow import ProcessPack, clock


def demo_pack():
    return {
        "name": "Illustrative SIH prototype pack",
        "source_reference": "DEMO - not statutory AICTE policy",
        "academic_cycle": 2026,
        "demo_only": True,
        "pause_authorized": True,
        "routes": {"ONLY_SCRUTINY": "SCRUTINY", "ONLY_EVC": "EVC"},
        "selectors": [
            {"category": "EOA", "route": "ONLY_SCRUTINY"},
            {"category": "NEW", "route": "ONLY_EVC"},
        ],
        "stages": [
            {
                "key": "SCRUTINY",
                "actor_role": "OFFICER",
                "next": {"CLEAR": "DECISION", "RETURN": "RE_SCRUTINY"},
                "target_seconds": 3600,
            },
            {"key": "RE_SCRUTINY", "actor_role": "OFFICER", "next": {"CLEAR": "DECISION"}},
            {
                "key": "EVC",
                "actor_role": "OFFICER",
                "evc_queue": True,
                "requires_evc_report": True,
                "next": {"CLEAR": "DECISION"},
            },
            {
                "key": "DECISION",
                "actor_role": "AUTHORITY",
                "decision": True,
                "next": {"APPROVE": "APPROVED"},
            },
            {"key": "APPROVED", "actor_role": "AUTHORITY", "terminal": True},
        ],
        "reminders": [{"key": "DUE", "offset_seconds": 0, "recipient_role": "INSTITUTION"}],
        "evc_scheduling_seconds": 3600,
        "evc_report_seconds": 3600,
    }


def test_policy_rejects_ambiguous_routes_and_unprivileged_decisions():
    data = demo_pack()
    ProcessPack.model_validate(data)
    data["selectors"].append(data["selectors"][0])
    with pytest.raises(ValueError):
        ProcessPack.model_validate(data)
    data = demo_pack()
    data["stages"][3]["actor_role"] = "OFFICER"
    with pytest.raises(ValueError):
        ProcessPack.model_validate(data)


def test_clock_keeps_total_and_excludes_only_recorded_interval():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    pauses = [
        {
            "start": (start + timedelta(seconds=10)).isoformat(),
            "end": (start + timedelta(seconds=25)).isoformat(),
        }
    ]
    assert clock(start, pauses, start + timedelta(seconds=60)) == {
        "total_elapsed_seconds": 60,
        "excluded_seconds": 15,
        "accountable_seconds": 45,
    }


def ok(response, code=200):
    assert response.status_code == code, response.text
    return response.json()


def setup_case(h, category="EOA", actor="a", content=None):
    pack = ok(
        h.call(
            "POST", "/api/v1/process-packs", actor="author", mfa=True, json=content or demo_pack()
        ),
        201,
    )
    ok(
        h.call(
            "POST",
            f"/api/v1/process-packs/{pack['id']}/publish",
            actor="approver",
            mfa=True,
            json={"source_review": "Reviewed illustrative fixture, not a production pack"},
        )
    )
    app = h.create(actor=actor, category=category, slots=[{"code": "RENEWAL", "required": False}])
    ok(
        h.call(
            "POST",
            f"/api/v1/applications/{app['id']}/submit",
            actor=actor,
            json={"expected_revision": app["revision"]},
        )
    )
    case = ok(
        h.call(
            "POST",
            "/api/v1/approval-cases",
            actor="supervisor",
            mfa=True,
            json={"application_id": app["id"], "pack_id": pack["id"]},
        ),
        201,
    )
    app["institution_id"] = h.institutions[actor]
    return pack, app, case


def obligation(h, app, case, kind="UNDERTAKING", overdue=False):
    return ok(
        h.call(
            "POST",
            "/api/v1/obligations",
            actor="supervisor",
            mfa=True,
            json={
                "institution_id": app["institution_id"],
                "application_id": app["id"],
                "case_id": case["id"],
                "pack_id": case["pack_id"],
                "kind": kind,
                "code": "REQUIRED_CONDITION",
                "title": "Demonstration condition",
                "source_reference": "DEMO approval order page 1",
                "due_at": (datetime.now(UTC) + timedelta(days=-1 if overdue else 1)).isoformat(),
            },
        ),
        201,
    )


def clean_evidence(h, app):
    # Owner-only fixture constructs a scanned/accepted object; no S3/ClamAV success is inferred.
    ev_id, upload_id = str(uuid4()), str(uuid4())
    with h.owner.begin() as conn:
        slot_id = conn.scalar(select(t.slots.c.id).where(t.slots.c.application_id == app["id"]))
        conn.execute(
            insert(t.uploads).values(
                id=upload_id,
                institution_id=app["institution_id"],
                application_id=app["id"],
                slot_id=slot_id,
                actor_id=conn.scalar(
                    select(t.actors.c.id).where(
                        t.actors.c.issuer == h.issuer, t.actors.c.subject == h.actors["a"]
                    )
                ),
                status="COMPLETED",
                filename="fixture.pdf",
                media_type="application/pdf",
                expected_size=1,
                expected_sha256="a" * 64,
                object_key="fixture",
                mode="SINGLE",
                part_size=1,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        conn.execute(
            insert(t.evidence).values(
                id=ev_id,
                institution_id=app["institution_id"],
                application_id=app["id"],
                slot_id=slot_id,
                upload_id=upload_id,
                quarantine_key="fixture",
                quarantine_version="1",
                size_bytes=1,
                sha256="a" * 64,
                media_type="application/pdf",
                filename="fixture.pdf",
                status="QUARANTINED",
                metadata={},
            )
        )
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == ev_id)
            .values(status="ACCEPTED", clean_key="fixture", clean_version="1")
        )
    return ev_id


def test_case_isolation_guards_revision_and_human_authority(h):
    _, _, case = setup_case(h)
    assert (
        h.call("GET", f"/api/v1/approval-cases/{case['id']}/case-summary", actor="b").status_code
        == 404
    )
    assert (
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            json={"expected_revision": 1, "action": "CLEAR", "reason": "Test attempt"},
        ).status_code
        == 403
    )
    cleared = ok(
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="supervisor",
            mfa=True,
            json={"expected_revision": 1, "action": "CLEAR", "reason": "Verified scrutiny"},
        )
    )
    assert cleared["stage"] == "DECISION"
    assert (
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="supervisor",
            mfa=True,
            json={"expected_revision": 1, "action": "CLEAR", "reason": "Stale attempt"},
        ).json()["code"]
        == "STALE_REVISION"
    )
    assert (
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="supervisor",
            mfa=True,
            json={"expected_revision": 2, "action": "APPROVE", "reason": "Not delegated authority"},
        ).status_code
        == 403
    )


def test_upload_does_not_renew_and_verification_survives_closure(h):
    _, app, case = setup_case(h)
    item = obligation(h, app, case, "DOCUMENT_VALIDITY", True)
    ev = clean_evidence(h, app)
    future = (datetime.now(UTC) + timedelta(days=365)).isoformat()
    submitted = ok(
        h.call(
            "POST",
            f"/api/v1/obligations/{item['id']}/responses",
            json={"expected_revision": 1, "evidence_id": ev, "proposed_due_at": future},
        )
    )
    assert submitted["due_at"] == item["due_at"] and submitted["time_condition"] == "OVERDUE"
    assert submitted["accepted_evidence_id"] is None
    verified = ok(
        h.call(
            "POST",
            f"/api/v1/obligations/{item['id']}/reviews",
            actor="supervisor",
            mfa=True,
            json={"expected_revision": 2, "accept": True, "reason": "Issuer evidence reviewed"},
        )
    )
    assert verified["accepted_evidence_id"] == ev and verified["time_condition"] == "UPCOMING"
    with h.owner.begin() as conn:
        conn.execute(update(n.cases).where(n.cases.c.id == case["id"]).values(status="CLOSED"))
    assert any(x["id"] == item["id"] for x in ok(h.call("GET", "/api/v1/obligations")))


def test_deadline_intents_deduplicate_and_ignore_new_generations(h):
    from workbench.activities.niyamflow import fire_niyam_deadline, load_niyam_deadline

    _, app, case = setup_case(h)
    item = obligation(h, app, case, overdue=True)
    with h.owner.begin() as conn:
        event = (
            conn.execute(select(t.outbox).where(t.outbox.c.event_type == "NiyamDeadlineScheduled"))
            .mappings()
            .all()
        )
        event_id = next(x["id"] for x in event if x["payload"]["resource_id"] == item["id"])
    assert load_niyam_deadline(event_id)["active"]
    assert fire_niyam_deadline({"event_id": event_id, "key": "DUE"})["created"]
    assert not fire_niyam_deadline({"event_id": event_id, "key": "DUE"})["created"]
    with h.owner.begin() as conn:
        conn.execute(
            update(n.obligations).where(n.obligations.c.id == item["id"]).values(generation=2)
        )
    assert not load_niyam_deadline(event_id)["active"]
    assert (
        fire_niyam_deadline({"event_id": event_id, "key": "DUE"})["state"]
        == "SUPERSEDED_OR_NOT_DUE"
    )


def test_evc_atomic_booking_across_committees(h):
    _, _, first = setup_case(h, "NEW")
    _, _, second = setup_case(h, "NEW", "b")
    start = datetime.now(UTC) + timedelta(days=2)
    end = start + timedelta(hours=1)
    proposals = []
    shared_member = "shared-" + uuid4().hex
    for case in (first, second):
        roster = ok(
            h.call(
                "POST",
                "/api/v1/evc-rosters",
                actor="supervisor",
                mfa=True,
                json={
                    "region": "TN",
                    "source_reference": "DEMO authorized committee order",
                    "members": [shared_member, case["id"]],
                    "availability": [{"starts_at": start.isoformat(), "ends_at": end.isoformat()}],
                    "expires_at": end.isoformat(),
                },
            ),
            201,
        )
        proposals.append(
            ok(
                h.call(
                    "POST",
                    "/api/v1/evc-appointments",
                    actor="supervisor",
                    mfa=True,
                    json={
                        "case_id": case["id"],
                        "roster_id": roster["id"],
                        "starts_at": start.isoformat(),
                        "ends_at": end.isoformat(),
                    },
                ),
                201,
            )
        )

    def confirm(proposal):
        return h.call(
            "POST",
            f"/api/v1/evc-appointments/{proposal['id']}/actions",
            actor="supervisor",
            mfa=True,
            json={"action": "CONFIRM", "reason": "Confirmed within authorized availability"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(confirm, proposals))
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]


def test_all_report_families_are_scoped_and_hash_snapshots(h):
    _, app, case = setup_case(h)
    obligation(h, app, case)
    for kind in (
        "PENDENCY",
        "EVC_STATUS",
        "UNDERTAKING_COMPLIANCE",
        "DOCUMENT_VALIDITY",
        "OVERDUE",
        "REGIONAL_PERFORMANCE",
    ):
        own = ok(h.call("GET", f"/api/v1/reports/consolidated?report_type={kind}"))
        other = ok(h.call("GET", f"/api/v1/reports/consolidated?report_type={kind}", actor="b"))
        assert all(x["institution_id"] == app["institution_id"] for x in own["rows"])
        assert other["rows"] == [] and len(own["snapshot_sha256"]) == 64


def test_authority_delegation_closure_and_revocation(h):
    _, app, case = setup_case(h)
    item = obligation(h, app, case)
    created = ok(
        h.call(
            "POST",
            "/api/v1/niyam/access-grants",
            actor="supervisor",
            mfa=True,
            json={
                "actor_id": h.actors["officer"],
                "role": "AUTHORITY",
                "region": "TN",
                "application_id": app["id"],
                "source_reference": "DEMO competent-authority appointment",
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        ),
        201,
    )
    ok(
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="supervisor",
            mfa=True,
            json={"expected_revision": 1, "action": "CLEAR", "reason": "Scrutiny complete"},
        )
    )
    approved = ok(
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="officer",
            mfa=True,
            json={
                "expected_revision": 2,
                "action": "APPROVE",
                "reason": "Authorized decision recorded",
            },
        )
    )
    assert approved["status"] == "CLOSED"
    assert any(
        x["id"] == item["id"] and x["state"] == "OPEN"
        for x in ok(h.call("GET", "/api/v1/obligations"))
    )
    ok(
        h.call(
            "POST",
            f"/api/v1/niyam/access-grants/{created['id']}/revoke",
            actor="supervisor",
            mfa=True,
            json={"reason": "Delegation withdrawn"},
        )
    )
    assert (
        h.call(
            "GET", f"/api/v1/approval-cases/{case['id']}/next-actions", actor="officer", mfa=True
        ).status_code
        == 404
    )


def test_renewal_upload_permit_does_not_reopen_intake_or_extend_expiry(h):
    from workbench.adapters.auth import JWTVerifier
    from workbench.adapters.evidence_service import EvidenceService
    from workbench.platform.errors import ApplicationError

    _, app, case = setup_case(h)
    item = obligation(h, app, case, "DOCUMENT_VALIDITY", True)
    store = h.app.state.domain_store
    actor = JWTVerifier(h.settings).principal(h.token("a"))
    with h.owner.begin() as conn:
        slot = conn.scalar(select(t.slots.c.id).where(t.slots.c.application_id == app["id"]))
    with store.transaction(actor) as conn:
        application = store.application(conn, app["id"])
        with pytest.raises(ApplicationError):
            EvidenceService._require_upload_scope(conn, application, slot)
    permit = ok(
        h.call(
            "POST",
            f"/api/v1/obligations/{item['id']}/upload-permits",
            actor="supervisor",
            mfa=True,
            json={
                "slot_id": slot,
                "expires_at": (datetime.now(UTC) + timedelta(hours=4)).isoformat(),
                "source_reference": "DEMO authorized renewal response window",
            },
        ),
        201,
    )
    with store.transaction(actor) as conn:
        application = store.application(conn, app["id"])
        EvidenceService._require_upload_scope(conn, application, slot)
        assert application["stage"] == "SUBMITTED"
    current_due = ok(h.call("GET", "/api/v1/obligations"))[0]["due_at"]
    assert datetime.fromisoformat(current_due) == datetime.fromisoformat(item["due_at"])
    with h.owner.begin() as conn:
        conn.execute(
            update(n.permits)
            .where(n.permits.c.id == permit["id"])
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    with store.transaction(actor) as conn, pytest.raises(ApplicationError):
        EvidenceService._require_upload_scope(conn, application, slot)


def test_policy_demo_all_route_families_and_notice_templates():
    path = Path(__file__).parents[1] / "fixtures/niyam_demo_pack.json"
    pack = ProcessPack.model_validate(json.loads(path.read_text()))
    assert {"ONLY_SCRUTINY", "SCRUTINY_PLUS_EVC", "ONLY_EVC", "EVC_PLUS_SAC_SHC"} <= set(
        pack.routes
    )
    assert pack.demo_only and pack.notice_templates


def test_delegated_committee_gets_audited_evidence_head_only_in_scope(h):
    _, app, _ = setup_case(h)
    ev = clean_evidence(h, app)
    assert (
        h.call("HEAD", f"/api/v1/evidence/{ev}/content", actor="officer", mfa=True).status_code
        == 404
    )
    ok(
        h.call(
            "POST",
            "/api/v1/niyam/access-grants",
            actor="supervisor",
            mfa=True,
            json={
                "actor_id": h.actors["officer"],
                "role": "COMMITTEE",
                "region": "TN",
                "application_id": app["id"],
                "source_reference": "DEMO committee assignment order",
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        ),
        201,
    )
    response = h.call("HEAD", f"/api/v1/evidence/{ev}/content", actor="officer", mfa=True)
    assert response.status_code == 200 and response.headers["content-length"] == "1"
    assert (
        h.call("HEAD", f"/api/v1/evidence/{ev}/content", actor="officer", mfa=False).status_code
        == 404
    )
    assert h.call("HEAD", f"/api/v1/evidence/{ev}/content", actor="b", mfa=True).status_code == 404


def test_reconciliation_prioritizes_expired_leases_over_unleased_traffic(h):
    app = h.create()
    expired = str(uuid4())
    past = datetime.now(UTC) - timedelta(hours=1)
    with h.owner.begin() as conn:
        for _ in range(3):
            conn.execute(
                insert(t.outbox).values(
                    id=str(uuid4()),
                    institution_id=h.institutions["a"],
                    application_id=app["id"],
                    event_type="UnleasedFixture",
                    payload={},
                )
            )
        conn.execute(
            insert(t.outbox).values(
                id=expired,
                institution_id=h.institutions["a"],
                application_id=app["id"],
                event_type="ExpiredFixture",
                payload={},
                lease_owner="test-worker",
                lease_until=past,
            )
        )
    result = ok(
        h.call(
            "POST",
            "/api/v1/operations/reconcile",
            actor="supervisor",
            mfa=True,
            json={"target": "OUTBOX", "dry_run": False, "batch_size": 1},
        )
    )
    assert result["reconciled_count"] == 1
    with h.owner.begin() as conn:
        # Other expired fixtures may be older; repeated bounded calls still make progress.
        remaining = conn.scalar(select(t.outbox.c.lease_owner).where(t.outbox.c.id == expired))
    for _ in range(10):
        if remaining is None:
            break
        ok(
            h.call(
                "POST",
                "/api/v1/operations/reconcile",
                actor="supervisor",
                mfa=True,
                json={"target": "OUTBOX", "dry_run": False, "batch_size": 10},
            )
        )
        with h.owner.begin() as conn:
            remaining = conn.scalar(select(t.outbox.c.lease_owner).where(t.outbox.c.id == expired))
    assert remaining is None


def test_pause_and_idempotent_returns_preserve_receipt(h):
    _, _, case = setup_case(h)
    paused = ok(
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/pause",
            actor="supervisor",
            mfa=True,
            json={
                "expected_revision": 1,
                "paused": True,
                "reason": "Approved operational pause",
                "source_reference": "DEMO pause authority",
            },
        )
    )
    assert paused["received_at"] == case["received_at"] and paused["due_at"] == case["due_at"]
    assert (
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="supervisor",
            mfa=True,
            json={"expected_revision": 2, "action": "CLEAR", "reason": "Blocked during pause"},
        ).json()["code"]
        == "CASE_BLOCKED"
    )
    ok(
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/pause",
            actor="supervisor",
            mfa=True,
            json={
                "expected_revision": 2,
                "paused": False,
                "reason": "Approved work resumed",
                "source_reference": "DEMO resume authority",
            },
        )
    )
    key = uuid4().hex
    data = {"expected_revision": 3, "action": "RETURN", "reason": "Recorded clarification needed"}
    first = ok(
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="supervisor",
            mfa=True,
            key=key,
            json=data,
        )
    )
    again = ok(
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="supervisor",
            mfa=True,
            key=key,
            json=data,
        )
    )
    assert (
        first == again
        and first["stage"] == "RE_SCRUTINY"
        and first["received_at"] == case["received_at"]
    )


def test_evc_report_clock_starts_from_configured_actual_completion(h, monkeypatch):
    from workbench.adapters import niyam_service

    _, app, case = setup_case(h, "NEW")
    report = clean_evidence(h, app)
    ok(
        h.call(
            "POST",
            "/api/v1/niyam/access-grants",
            actor="supervisor",
            mfa=True,
            json={
                "actor_id": h.actors["officer"],
                "role": "COMMITTEE",
                "region": "TN",
                "application_id": app["id"],
                "source_reference": "DEMO EVC assignment",
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        ),
        201,
    )
    start = datetime.now(UTC) + timedelta(days=3)
    end = start + timedelta(hours=1)
    roster = ok(
        h.call(
            "POST",
            "/api/v1/evc-rosters",
            actor="supervisor",
            mfa=True,
            json={
                "region": "TN",
                "source_reference": "DEMO authorized roster",
                "members": [uuid4().hex],
                "availability": [{"starts_at": start.isoformat(), "ends_at": end.isoformat()}],
                "expires_at": end.isoformat(),
            },
        ),
        201,
    )
    proposal = ok(
        h.call(
            "POST",
            "/api/v1/evc-appointments",
            actor="supervisor",
            mfa=True,
            json={
                "case_id": case["id"],
                "roster_id": roster["id"],
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
            },
        ),
        201,
    )
    ok(
        h.call(
            "POST",
            f"/api/v1/evc-appointments/{proposal['id']}/actions",
            actor="supervisor",
            mfa=True,
            json={"action": "CONFIRM", "reason": "Authorized time confirmed"},
        )
    )
    completed_at = end + timedelta(minutes=10)
    monkeypatch.setattr(niyam_service, "now", lambda: completed_at)
    for action in ("COMPLETE", "SUBMIT_REPORT"):
        ok(
            h.call(
                "POST",
                f"/api/v1/evc-appointments/{proposal['id']}/actions",
                actor="officer",
                mfa=True,
                json={
                    "action": action,
                    "reason": "Committee milestone recorded",
                    "evidence_id": report if action == "SUBMIT_REPORT" else None,
                },
            )
        )
    current = ok(
        h.call(
            "GET", f"/api/v1/approval-cases/{case['id']}/next-actions", actor="supervisor", mfa=True
        )
    )
    assert datetime.fromisoformat(current["due_at"]) == completed_at + timedelta(hours=1)
    assert current["milestones"]["report_clock_basis"] == "ACTUAL_COMPLETION"
    assert (
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="supervisor",
            mfa=True,
            json={
                "expected_revision": current["revision"],
                "action": "CLEAR",
                "reason": "Premature advancement",
            },
        ).json()["code"]
        == "EVC_REPORT_REQUIRED"
    )
    ok(
        h.call(
            "POST",
            f"/api/v1/evc-appointments/{proposal['id']}/actions",
            actor="supervisor",
            mfa=True,
            json={"action": "ACCEPT_REPORT", "reason": "Report reviewed independently"},
        )
    )
    current = ok(
        h.call(
            "GET", f"/api/v1/approval-cases/{case['id']}/next-actions", actor="supervisor", mfa=True
        )
    )
    assert current["milestones"]["report_accepted_at"]
    ok(
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/transitions",
            actor="supervisor",
            mfa=True,
            json={
                "expected_revision": current["revision"],
                "action": "CLEAR",
                "reason": "Accepted report permits handoff",
            },
        )
    )


def test_notice_generation_is_governed_draft_not_case_decision(h):
    content = json.loads((Path(__file__).parents[1] / "fixtures/niyam_demo_pack.json").read_text())
    _, _, case = setup_case(h, content=content)
    draft = ok(
        h.call(
            "POST",
            f"/api/v1/approval-cases/{case['id']}/notice-drafts",
            actor="supervisor",
            mfa=True,
            json={
                "template_key": "DEFICIENCY",
                "reason": "Referenced document needs clarification",
            },
        )
    )
    assert (
        draft["state"] == "DRAFT_REQUIRES_AUTHORIZED_ISSUE" and len(draft["content_sha256"]) == 64
    )
    current = ok(h.call("GET", f"/api/v1/approval-cases/{case['id']}/next-actions"))
    assert current["revision"] == case["revision"] and current["stage"] == case["stage"]


def test_workspace_permissions_and_alert_acknowledgement(h):
    from workbench.activities.niyamflow import fire_niyam_deadline

    _, app, case = setup_case(h)
    item = obligation(h, app, case, overdue=True)
    session = ok(h.call("GET", "/api/v1/niyam/session"))
    assert session["can_respond"] and not session["can_process"]
    elevated = ok(h.call("GET", "/api/v1/niyam/session", actor="supervisor", mfa=True))
    assert elevated["can_process"] and not elevated["can_publish_pack"]
    with h.owner.begin() as conn:
        event = next(
            x
            for x in conn.execute(
                select(t.outbox).where(
                    t.outbox.c.application_id == app["id"],
                    t.outbox.c.event_type == "NiyamDeadlineScheduled",
                )
            ).mappings()
            if x["payload"]["resource_id"] == item["id"]
        )
    fire_niyam_deadline({"event_id": event["id"], "key": "DUE"})
    alerts = ok(h.call("GET", "/api/v1/niyam/alerts"))
    assert len(alerts) == 1
    assert (
        h.call(
            "POST",
            f"/api/v1/niyam/alerts/{alerts[0]['id']}/acknowledge",
            actor="b",
            json={"reason": "Wrong recipient"},
        ).status_code
        == 404
    )
    result = ok(
        h.call(
            "POST",
            f"/api/v1/niyam/alerts/{alerts[0]['id']}/acknowledge",
            json={"reason": "Follow-up acknowledged"},
        )
    )
    assert result["state"] == "ACKNOWLEDGED" and not result["obligation_closed"]
    assert ok(h.call("GET", "/api/v1/obligations"))[0]["state"] == "OPEN"


def test_roster_read_is_region_scoped_even_for_legacy_officers(h):
    outsider = str(uuid4())
    with h.owner.begin() as conn:
        conn.execute(
            insert(n.rosters).values(
                id=outsider,
                region="KA",
                source_reference="External region fixture",
                members=[str(uuid4())],
                availability=[],
                conflicts=[],
                mode="ONLINE",
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
    for actor in ("officer", "supervisor"):
        rows = ok(h.call("GET", "/api/v1/evc-rosters", actor=actor, mfa=True))
        assert all(x["id"] != outsider and x["region"] == "TN" for x in rows)
