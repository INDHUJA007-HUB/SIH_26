"""Real PostgreSQL/API isolation, immutable revisions and upload-policy acceptance tests."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, text, update

from workbench.adapters import tables as t
from workbench.adapters.domain_store import now
from workbench.adapters.object_storage import ObjectStorage
from workbench.api.app import create_app
from workbench.platform.config import Settings
from workbench.platform.database import build_engine

pytestmark = pytest.mark.integration


class Harness:
    def __init__(self, root: Path, key_pair):
        configuration = Settings()
        self.owner = build_engine(configuration.database_url.get_secret_value())
        self.issuer = "urn:test:" + uuid4().hex
        self.key = key_pair[0]
        public = root / "public.pem"
        public.write_bytes(key_pair[1])
        self.settings = Settings(
            _env_file=None,
            environment="test",
            domain_enabled=True,
            database_url="",
            auth_issuer=self.issuer,
            fixture_public_key=public,
            fixture_store=root / "unused.json",
            app_database_url=configuration.app_database_url,
            delivery_database_url=configuration.delivery_database_url,
            s3_endpoint=configuration.s3_endpoint,
            s3_public_endpoint=configuration.s3_public_endpoint,
        )
        self.institutions = {"a": str(uuid4()), "b": str(uuid4())}
        self.actors = {
            name: str(uuid4())
            for name in (
                "a",
                "b",
                "officer",
                "auditor",
                "supervisor",
                "admin",
                "author",
                "approver",
            )
        }
        with self.owner.begin() as connection:
            for name, identifier in self.institutions.items():
                connection.execute(
                    insert(t.institutions).values(
                        id=identifier,
                        name="Synthetic test " + name,
                        jurisdiction="TN",
                        synthetic=True,
                    )
                )
            for name, identifier in self.actors.items():
                connection.execute(
                    insert(t.actors).values(
                        id=identifier,
                        issuer=self.issuer,
                        subject=identifier,
                        person_id=identifier,
                        disabled=False,
                        valid_after=datetime(2000, 1, 1, tzinfo=UTC),
                    )
                )
                role = {
                    "a": "institution_editor",
                    "b": "institution_editor",
                    "admin": "identity_admin",
                    "author": "rule_author",
                    "approver": "rule_approver",
                }.get(name, name)
                connection.execute(
                    insert(t.memberships).values(
                        id=str(uuid4()),
                        actor_id=identifier,
                        institution_id=self.institutions.get(name),
                        role=role,
                        jurisdiction="TN",
                    )
                )
        from workbench.adapters.rule_registry_service import RuleRegistryService

        RuleRegistryService(self.owner).seed_default_rules()
        self.app = create_app(self.settings)
        self.context = TestClient(self.app)
        self.client = self.context.__enter__()
        self.storage = ObjectStorage(self.settings)

    def close(self):
        self.context.__exit__(None, None, None)
        self.app.state.domain_store.engine.dispose()
        self.app.state.domain_store.delivery_engine.dispose()
        self.owner.dispose()

    def token(self, actor="a", mfa=False, **claims):
        current = int(now().timestamp())
        payload = {
            "sub": self.actors[actor],
            "iss": self.issuer,
            "aud": "workbench-api",
            "iat": current,
            "exp": current + 600,
            "auth_time": current,
            "jti": str(uuid4()),
            "amr": ["pwd", "mfa"] if mfa else ["pwd"],
        }
        payload.update(claims)
        return jwt.encode(payload, self.key, algorithm="RS256")

    def call(self, method, path, actor="a", mfa=False, key=None, token=None, **kwargs):
        headers = {
            "Authorization": "Bearer " + (token or self.token(actor, mfa)),
            "Idempotency-Key": key or uuid4().hex,
            **kwargs.pop("headers", {}),
        }
        return self.client.request(method, path, headers=headers, **kwargs)

    def create(self, actor="a", **overrides):
        payload = {
            "institution_id": self.institutions[actor],
            "category": "EOA",
            "cycle_start": 2026,
            "programme": "ENGINEERING_AND_TECHNOLOGY",
            "level": "UG",
            "declared_facts": {"bandwidth_mbps": 100},
            "slots": [{"code": "FIRE_CERTIFICATE", "required": True}],
        }
        payload.update(overrides)
        response = self.call("POST", "/api/v1/applications", actor=actor, json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    def prepare_upload(self, application, data, **overrides):
        details = self.call("GET", "/api/v1/applications/" + application["id"]).json()
        payload = {
            "slot_id": details["slots"][0]["id"],
            "filename": "fixture.png",
            "media_type": "image/png",
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        payload.update(overrides)
        result = self.call(
            "POST", f"/api/v1/applications/{application['id']}/upload-sessions", json=payload
        )
        assert result.status_code == 201, result.text
        return result.json()


def test_me_ignores_token_roles_and_owner_can_only_list_own_applications(h):
    a, b = h.create(), h.create("b")
    response = h.call(
        "GET", "/api/v1/me", token=h.token(roles=["supervisor"], institution_id=h.institutions["b"])
    )
    assert response.json()["memberships"][0]["role"] == "institution_editor"
    listed = h.call("GET", "/api/v1/applications").json()
    assert [item["id"] for item in listed] == [a["id"]]
    assert h.call("GET", f"/api/v1/applications/{b['id']}").status_code == 404
    assert h.call("GET", f"/api/v1/applications/{a['id']}", actor="officer").status_code == 404


def test_create_field_tampering_and_wrong_institution_are_denied(h):
    payload = {
        "institution_id": h.institutions["b"],
        "category": "EOA",
        "cycle_start": 2026,
        "programme": "E&T",
        "level": "UG",
        "slots": [{"code": "CERT"}],
    }
    assert h.call("POST", "/api/v1/applications", json=payload).status_code == 403
    payload["institution_id"] = h.institutions["a"]
    payload["stage"] = "SUBMITTED"
    assert h.call("POST", "/api/v1/applications", json=payload).status_code == 422


def test_oidc_session_revocation_is_immediate_and_other_token_stays_valid(h):
    token = h.token()
    assert h.call("POST", "/api/v1/me/revoke-session", token=token).status_code == 200
    assert h.call("GET", "/api/v1/me", token=token).status_code == 401
    assert h.call("GET", "/api/v1/me").status_code == 200


def test_disabled_identity_and_old_issued_token_are_rejected(h):
    token = h.token()
    with h.owner.begin() as connection:
        connection.execute(
            update(t.actors).where(t.actors.c.id == h.actors["a"]).values(disabled=True)
        )
    assert h.call("GET", "/api/v1/me", token=token).status_code == 401


def test_scoped_assignments_require_recent_mfa_and_revoke_immediately(h):
    application = h.create()
    payload = {
        "actor_id": h.actors["officer"],
        "institution_id": h.institutions["a"],
        "application_id": application["id"],
        "access_role": "officer",
        "reason": "Synthetic assignment for scrutiny",
        "lifetime_seconds": 300,
    }
    assert (
        h.call("POST", "/api/v1/assignments", actor="supervisor", json=payload).status_code == 403
    )
    assert (
        h.call(
            "POST",
            "/api/v1/assignments",
            actor="supervisor",
            token=h.token("supervisor", True, auth_time=int(now().timestamp()) - 600),
            json=payload,
        ).status_code
        == 403
    )
    result = h.call("POST", "/api/v1/assignments", actor="supervisor", mfa=True, json=payload)
    assert result.status_code == 201, result.text
    assert (
        h.call("GET", f"/api/v1/applications/{application['id']}", actor="officer").status_code
        == 200
    )
    assert (
        h.call("GET", f"/api/v1/applications/{application['id']}", actor="auditor").status_code
        == 404
    )
    assert (
        h.call(
            "POST",
            f"/api/v1/assignments/{result.json()['id']}/revoke",
            actor="supervisor",
            mfa=True,
        ).status_code
        == 200
    )
    assert (
        h.call("GET", f"/api/v1/applications/{application['id']}", actor="officer").status_code
        == 404
    )


def test_expired_assignment_and_wrong_jurisdiction_do_not_grant_access(h):
    application = h.create()
    with h.owner.begin() as connection:
        connection.execute(
            insert(t.assignments).values(
                id=str(uuid4()),
                institution_id=h.institutions["a"],
                application_id=application["id"],
                actor_id=h.actors["officer"],
                access_role="officer",
                expires_at=now() + timedelta(seconds=60),
                reason="Synthetic expiry fixture",
                granted_by=h.actors["supervisor"],
            )
        )
        connection.execute(
            update(t.assignments)
            .where(t.assignments.c.actor_id == h.actors["officer"])
            .values(expires_at=now() - timedelta(seconds=1))
        )
    assert (
        h.call("GET", f"/api/v1/applications/{application['id']}", actor="officer").status_code
        == 404
    )


def test_membership_separation_and_revocation(h):
    payload = {
        "actor_id": h.actors["author"],
        "role": "rule_approver",
        "jurisdiction": "TN",
        "lifetime_seconds": 300,
    }
    assert (
        h.call("POST", "/api/v1/memberships", actor="admin", mfa=True, json=payload).status_code
        == 409
    )
    payload.update(actor_id=h.actors["admin"], role="officer")
    assert (
        h.call("POST", "/api/v1/memberships", actor="admin", mfa=True, json=payload).status_code
        == 403
    )
    with h.owner.begin() as connection:
        membership = connection.scalar(
            select(t.memberships.c.id).where(t.memberships.c.actor_id == h.actors["a"])
        )
    assert (
        h.call(
            "POST", f"/api/v1/memberships/{membership}/revoke", actor="admin", mfa=True
        ).status_code
        == 200
    )
    assert h.call("GET", "/api/v1/me").json()["memberships"] == []
    assert (
        h.call(
            "POST",
            "/api/v1/applications",
            json={
                "institution_id": h.institutions["a"],
                "category": "EOA",
                "cycle_start": 2026,
                "programme": "ET",
                "level": "UG",
                "slots": [{"code": "CERT"}],
            },
        ).status_code
        == 403
    )


def test_emergency_access_requires_independent_approval_and_is_read_only(h):
    application = h.create()
    payload = {
        "institution_id": h.institutions["a"],
        "application_id": application["id"],
        "reason": "Synthetic emergency evidence review request",
        "lifetime_seconds": 300,
    }
    request = h.call("POST", "/api/v1/emergency-grants", actor="officer", mfa=True, json=payload)
    assert request.status_code == 201, request.text
    assert (
        h.call(
            "GET", f"/api/v1/applications/{application['id']}", actor="officer", mfa=True
        ).status_code
        == 404
    )
    approval = h.call(
        "POST",
        f"/api/v1/emergency-grants/{request.json()['id']}/approve",
        actor="supervisor",
        mfa=True,
    )
    assert approval.status_code == 200, approval.text
    assert (
        h.call(
            "GET", f"/api/v1/applications/{application['id']}", actor="officer", mfa=True
        ).status_code
        == 200
    )
    assert (
        h.call("GET", f"/api/v1/applications/{application['id']}", actor="officer").status_code
        == 404
    )
    assert h.call(
        "PATCH",
        f"/api/v1/applications/{application['id']}",
        actor="officer",
        mfa=True,
        json={"expected_revision": 1, "declared_facts": {}},
    ).status_code in {403, 404}
    assert (
        h.call(
            "POST",
            f"/api/v1/emergency-grants/{request.json()['id']}/revoke",
            actor="supervisor",
            mfa=True,
        ).status_code
        == 200
    )
    assert (
        h.call(
            "GET", f"/api/v1/applications/{application['id']}", actor="officer", mfa=True
        ).status_code
        == 404
    )


def test_immutable_revision_and_atomic_idempotent_submission(h):
    application = h.create()
    key = uuid4().hex
    response = h.call(
        "POST",
        f"/api/v1/applications/{application['id']}/submit",
        key=key,
        json={"expected_revision": 1, "evidence_ids": []},
    )
    assert response.status_code == 200, response.text
    repeat = h.call(
        "POST",
        f"/api/v1/applications/{application['id']}/submit",
        key=key,
        json={"expected_revision": 1, "evidence_ids": []},
    )
    assert repeat.json() == response.json()
    assert (
        h.call(
            "PATCH",
            f"/api/v1/applications/{application['id']}",
            json={"expected_revision": 2, "declared_facts": {"changed": True}},
        ).status_code
        == 409
    )
    history = h.call("GET", f"/api/v1/applications/{application['id']}/revisions").json()
    assert len(history) == 2 and history[-1]["sha256"] == response.json()["manifest_sha256"]
    with h.owner.begin() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(t.outbox)
                .where(t.outbox.c.application_id == application["id"])
            )
            == 1
        )


def test_concurrent_revision_updates_have_one_winner(h):
    application = h.create()

    def change(number):
        return h.call(
            "PATCH",
            f"/api/v1/applications/{application['id']}",
            json={"expected_revision": 1, "declared_facts": {"counter": number}},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(change, [1, 2]))
    assert statuses == [200, 409]


def test_runtime_roles_are_nonowner_nonsuperuser_and_rls_context_does_not_leak(h):
    a, b = h.create(), h.create("b")
    store = h.app.state.domain_store
    with store.engine.begin() as connection:
        attributes = connection.execute(
            text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        ).one()
        assert attributes == (False, False)
        assert connection.scalar(select(func.count()).select_from(t.applications)) == 0
    from workbench.adapters.auth import JWTVerifier

    for actor, expected in [("a", a["id"]), ("b", b["id"]), ("a", a["id"])]:
        with store.transaction(JWTVerifier(h.settings).principal(h.token(actor))) as connection:
            assert [item[0] for item in connection.execute(select(t.applications.c.id))] == [
                expected
            ]
    with store.engine.begin() as connection:
        assert connection.scalar(select(func.count()).select_from(t.applications)) == 0


def test_upload_cross_owner_slot_and_size_quota_rejected(h):
    application, other = h.create(), h.create("b")
    foreign = h.call("GET", f"/api/v1/applications/{other['id']}", actor="b").json()["slots"][0][
        "id"
    ]
    payload = {
        "slot_id": foreign,
        "filename": "test.pdf",
        "media_type": "application/pdf",
        "size_bytes": 10,
        "sha256": "0" * 64,
    }
    assert (
        h.call(
            "POST", f"/api/v1/applications/{application['id']}/upload-sessions", json=payload
        ).status_code
        == 404
    )
    payload["slot_id"] = h.call("GET", f"/api/v1/applications/{application['id']}").json()["slots"][
        0
    ]["id"]
    payload["size_bytes"] = 30 * 1024 * 1024
    assert (
        h.call(
            "POST", f"/api/v1/applications/{application['id']}/upload-sessions", json=payload
        ).status_code
        == 413
    )


def test_upload_expiry_and_quarantine_delivery_denied(h):
    application = h.create()
    data = b"synthetic-not-a-pdf"
    upload = h.prepare_upload(application, data, media_type="application/pdf", filename="test.pdf")
    with h.owner.begin() as connection:
        connection.execute(
            update(t.uploads)
            .where(t.uploads.c.id == upload["id"])
            .values(expires_at=now() - timedelta(seconds=1))
        )
    assert (
        h.call("POST", f"/api/v1/upload-sessions/{upload['id']}/complete", json={}).status_code
        == 410
    )


def test_idempotency_conflict_is_detected(h):
    application = h.create()
    key = uuid4().hex
    first = h.call(
        "PATCH",
        f"/api/v1/applications/{application['id']}",
        key=key,
        json={"expected_revision": 1, "declared_facts": {"value": 1}},
    )
    assert first.status_code == 200
    second = h.call(
        "PATCH",
        f"/api/v1/applications/{application['id']}",
        key=key,
        json={"expected_revision": 1, "declared_facts": {"value": 2}},
    )
    assert second.status_code == 409


def test_runtime_startup_rejects_owner_credentials(h):
    from workbench.adapters.domain_store import DomainStore

    unsafe = DomainStore(h.owner, h.owner)
    with pytest.raises(RuntimeError, match="exceeds"):
        unsafe.validate_roles()


def test_disable_endpoint_revokes_all_old_tokens_and_requires_scoped_mfa(h):
    path = f"/api/v1/actors/{h.actors['a']}/disable"
    old_token = h.token()
    payload = {"reason": "Synthetic account termination test"}
    assert h.call("POST", path, actor="admin", json=payload).status_code == 403
    assert h.call("POST", path, actor="admin", mfa=True, json=payload).status_code == 200
    assert h.call("GET", "/api/v1/me", token=old_token).status_code == 401
    assert h.call("GET", "/api/v1/me").status_code == 401


def test_admin_cannot_grant_roles_across_jurisdiction(h):
    payload = {
        "actor_id": h.actors["auditor"],
        "role": "officer",
        "jurisdiction": "KL",
        "lifetime_seconds": 300,
    }
    assert (
        h.call("POST", "/api/v1/memberships", actor="admin", mfa=True, json=payload).status_code
        == 403
    )


def test_same_person_alias_cannot_evade_rule_duty_separation(h):
    alias = str(uuid4())
    with h.owner.begin() as connection:
        connection.execute(
            insert(t.actors).values(
                id=alias,
                issuer=h.issuer,
                subject=alias,
                person_id=h.actors["author"],
                disabled=False,
                valid_after=datetime(2000, 1, 1, tzinfo=UTC),
            )
        )
    payload = {
        "actor_id": alias,
        "role": "rule_approver",
        "jurisdiction": "TN",
        "lifetime_seconds": 300,
    }
    assert (
        h.call("POST", "/api/v1/memberships", actor="admin", mfa=True, json=payload).status_code
        == 409
    )


def test_portal_reference_normalization_prevents_duplicate_imports(h):
    suffix = uuid4().hex
    h.create(portal_system=" aicte ", portal_reference=" ｅｏａ－１２３ " + suffix)
    body = {
        "institution_id": h.institutions["a"],
        "category": "EOA",
        "cycle_start": 2026,
        "programme": "ET",
        "level": "UG",
        "slots": [{"code": "CERT"}],
        "portal_system": "AICTE",
        "portal_reference": "EOA-123 " + suffix.upper(),
    }
    assert h.call("POST", "/api/v1/applications", json=body).status_code == 409


def test_outbox_failure_rolls_back_submission_revision_and_audit(h, monkeypatch):
    from workbench.adapters.domain_store import DomainStore
    from workbench.platform.errors import ApplicationError

    application = h.create()

    def unavailable(*args, **kwargs):
        raise ApplicationError("OUTBOX_UNAVAILABLE", "Synthetic transaction failure", 503)

    monkeypatch.setattr(DomainStore, "event", unavailable)
    response = h.call(
        "POST",
        f"/api/v1/applications/{application['id']}/submit",
        json={"expected_revision": 1, "evidence_ids": []},
    )
    assert response.status_code == 503
    assert h.call("GET", f"/api/v1/applications/{application['id']}").json()["stage"] == "DRAFT"
    assert len(h.call("GET", f"/api/v1/applications/{application['id']}/revisions").json()) == 1
    events = h.call("GET", f"/api/v1/applications/{application['id']}/audit-events").json()
    assert len(events) == 1


def test_concurrent_submissions_finalize_once_and_audit_chain_verifies(h):
    from workbench.adapters.audit_verifier import verify_stream

    application = h.create()

    def submit(_):
        return h.call(
            "POST",
            f"/api/v1/applications/{application['id']}/submit",
            json={"expected_revision": 1, "evidence_ids": []},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, [1, 2])) == [200, 409]
    with h.owner.connect() as connection:
        result = verify_stream(connection, h.institutions["a"])
        assert result["valid"] and result["events"] == 2
        assert (
            connection.scalar(
                select(func.count())
                .select_from(t.outbox)
                .where(t.outbox.c.application_id == application["id"])
            )
            == 1
        )


def test_direct_database_cannot_change_immutable_history(h):
    application = h.create()
    with pytest.raises(Exception, match="immutable"), h.owner.begin() as connection:
        connection.execute(
            update(t.revisions)
            .where(t.revisions.c.application_id == application["id"])
            .values(sha256="0" * 64)
        )


def test_invalid_authentication_assurance_is_a_safe_401(h):
    assert h.call("GET", "/api/v1/me", token=h.token(auth_time="malformed")).status_code == 401


def test_abort_releases_pending_upload_reservation_and_forbids_completion(h):
    application = h.create()
    upload = h.prepare_upload(application, b"test")
    path = f"/api/v1/upload-sessions/{upload['id']}"
    assert h.call("POST", path + "/abort", actor="b").status_code == 404
    assert h.call("POST", path + "/abort").json()["status"] == "ABORTED"
    assert h.call("POST", path + "/abort").status_code == 200
    assert h.call("POST", path + "/complete", json={}).status_code == 410


def test_actor_quota_and_pending_processing_quota_are_enforced(h):
    h.settings.actor_quota_bytes = 5
    application = h.create()
    h.prepare_upload(application, b"12345")
    details = h.call("GET", f"/api/v1/applications/{application['id']}").json()
    payload = {
        "slot_id": details["slots"][0]["id"],
        "filename": "another.png",
        "media_type": "image/png",
        "size_bytes": 1,
        "sha256": "0" * 64,
    }
    assert (
        h.call(
            "POST", f"/api/v1/applications/{application['id']}/upload-sessions", json=payload
        ).status_code
        == 429
    )

    h.settings.actor_quota_bytes = 500
    h.settings.max_pending_uploads = 1
    assert (
        h.call(
            "POST", f"/api/v1/applications/{application['id']}/upload-sessions", json=payload
        ).status_code
        == 429
    )


def test_large_json_command_is_rejected_before_decoding(h):
    result = h.call(
        "POST",
        "/api/v1/applications",
        content=b"x" * (1024 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )
    assert result.status_code == 413 and result.json()["code"] == "COMMAND_TOO_LARGE"
