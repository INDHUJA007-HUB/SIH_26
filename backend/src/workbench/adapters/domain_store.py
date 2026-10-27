"""Transaction boundary, verified session context, receipts and append-only audit ports."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import insert, select, text
from sqlalchemy.engine import Connection, Engine

from workbench.adapters import tables as t
from workbench.contracts.intake import Principal
from workbench.modules.applications.domain import digest
from workbench.modules.identity_access.policy import require_step_up
from workbench.platform.errors import ApplicationError, AuthenticationRequired
from workbench.platform.runtime_roles import validate_runtime_role


def now() -> datetime:
    return datetime.now(UTC)


def uid() -> str:
    return str(uuid4())


def row(value: Any) -> dict[str, Any]:
    return dict(value._mapping) if value is not None else {}


class DomainStore:
    def __init__(self, engine: Engine, delivery_engine: Engine) -> None:
        self.engine, self.delivery_engine = engine, delivery_engine

    def validate_roles(self) -> None:
        """Fail startup if a runtime credential could bypass row-level policies."""
        for engine, group in ((self.engine, "wb_app"), (self.delivery_engine, "wb_delivery")):
            validate_runtime_role(engine, group)

    def close(self) -> None:
        self.engine.dispose()
        self.delivery_engine.dispose()

    @contextmanager
    def transaction(self, principal: Principal, *, delivery: bool = False) -> Iterator[Connection]:
        engine = self.delivery_engine if delivery else self.engine
        with engine.begin() as connection:
            for key, value in {
                "issuer": principal.issuer,
                "subject": principal.subject,
                "sid": principal.session_id,
                "iat": principal.issued_at,
                "exp": principal.expires_at,
                "mfa": str(principal.mfa).lower(),
                "auth_time": principal.auth_time,
            }.items():
                connection.execute(
                    text("SELECT set_config(:key,:value,true)"),
                    {"key": "wb." + key, "value": str(value)},
                )
            if connection.scalar(text("SELECT wb.actor_id()")) is None:
                raise AuthenticationRequired()
            yield connection

    def actor(self, connection: Connection) -> dict[str, Any]:
        actor = row(
            connection.execute(
                select(t.actors).where(
                    t.actors.c.id == connection.scalar(text("SELECT wb.actor_id()"))
                )
            ).first()
        )
        actor["memberships"] = [
            row(item)
            for item in connection.execute(
                select(t.memberships).where(
                    t.memberships.c.actor_id == actor["id"],
                    t.memberships.c.revoked_at.is_(None),
                    (t.memberships.c.expires_at.is_(None)) | (t.memberships.c.expires_at > now()),
                )
            )
        ]
        return actor

    def application(
        self, connection: Connection, application_id: str, *, lock: bool = False
    ) -> dict[str, Any]:
        query = select(t.applications).where(t.applications.c.id == application_id)
        result = row(connection.execute(query.with_for_update() if lock else query).first())
        if not result:
            raise ApplicationError("NOT_FOUND", "The requested resource is not available", 404)
        return result

    def institution_editor(self, connection: Connection, institution_id: str) -> None:
        actor = self.actor(connection)
        if not any(
            m["institution_id"] == institution_id and m["role"] == "institution_editor"
            for m in actor["memberships"]
        ):
            raise ApplicationError("ACCESS_DENIED", "Institution edit authority is required", 403)

    def manager(self, connection: Connection, principal: Principal, institution_id: str) -> None:
        require_step_up(principal)
        if not connection.scalar(text("SELECT wb.manages(:id)"), {"id": institution_id}):
            raise ApplicationError("ACCESS_DENIED", "Scoped management authority is required", 403)

    def audit(
        self,
        connection: Connection,
        institution_id: str | None,
        application_id: str | None,
        kind: str,
        payload: dict[str, Any],
        request_id: str,
    ) -> None:
        from workbench.modules.applications.domain import canonical

        connection.execute(
            text("SELECT wb.append_audit(:id,:inst,:app,:kind,CAST(:payload AS jsonb),:request)"),
            {
                "id": uid(),
                "inst": institution_id,
                "app": application_id,
                "kind": kind,
                "payload": canonical(payload),
                "request": request_id,
            },
        )

    def command(
        self,
        connection: Connection,
        route: str,
        key: str,
        payload: Any,
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        actor_id = str(connection.scalar(text("SELECT wb.actor_id()")))
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": "command:" + actor_id + ":" + route + ":" + key},
        )
        query = select(t.idempotency).where(
            t.idempotency.c.actor_id == actor_id,
            t.idempotency.c.route == route,
            t.idempotency.c.key == key,
        )
        existing = row(connection.execute(query).first())
        fingerprint = digest(payload)
        if existing:
            if existing["fingerprint"] != fingerprint:
                raise ApplicationError(
                    "IDEMPOTENCY_CONFLICT", "The key was used for different content", 409
                )
            return dict(existing["response"])
        result = operation()
        connection.execute(
            insert(t.idempotency).values(
                actor_id=actor_id, route=route, key=key, fingerprint=fingerprint, response=result
            )
        )
        return result

    def event(
        self,
        connection: Connection,
        application: dict[str, Any],
        kind: str,
        payload: dict[str, Any],
    ) -> str:
        event_id = uid()
        connection.execute(
            insert(t.outbox).values(
                id=event_id,
                institution_id=application["institution_id"],
                application_id=application["id"],
                event_type=kind,
                payload=payload,
            )
        )
        return event_id
