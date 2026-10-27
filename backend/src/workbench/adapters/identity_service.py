"""Scoped identity/assignment management with fresh assurance and separate people."""

from datetime import timedelta
from typing import Any

from sqlalchemy import insert, select, update

from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore, now, row, uid
from workbench.contracts.intake import Principal
from workbench.modules.identity_access.policy import (
    ASSIGNABLE_ROLES,
    require_distinct_people,
    require_step_up,
)
from workbench.platform.errors import ApplicationError


class IdentityService:
    def __init__(self, store: DomainStore) -> None:
        self.store = store

    def me(self, principal: Principal) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            actor = self.store.actor(connection)
            return {
                "actor_id": actor["id"],
                "person_id": actor["person_id"],
                "memberships": actor["memberships"],
                "assurance": "RECENT_MFA"
                if principal.mfa and int(now().timestamp()) - principal.auth_time <= 300
                else "STANDARD",
                "local_simulation": principal.issuer == "urn:sih:local-fixture",
            }

    def assignments(self, principal: Principal) -> list[dict[str, Any]]:
        with self.store.transaction(principal) as connection:
            return [
                row(item)
                for item in connection.execute(
                    select(t.assignments).order_by(t.assignments.c.created_at).limit(100)
                )
            ]

    def grant_assignment(
        self, principal: Principal, payload: dict[str, Any], key: str, request: str
    ) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            self.store.manager(connection, principal, payload["institution_id"])
            target = row(
                connection.execute(
                    select(t.actors).where(t.actors.c.id == payload["actor_id"])
                ).first()
            )
            if not target:
                raise ApplicationError("NOT_FOUND", "Actor is not available", 404)

            def operation() -> dict[str, Any]:
                assignment_id = uid()
                values = {k: v for k, v in payload.items() if k != "lifetime_seconds"}
                connection.execute(
                    insert(t.assignments).values(
                        id=assignment_id,
                        **values,
                        expires_at=now() + timedelta(seconds=payload["lifetime_seconds"]),
                        granted_by=self.store.actor(connection)["id"],
                    )
                )
                self.store.audit(
                    connection,
                    payload["institution_id"],
                    payload.get("application_id"),
                    "CaseAssignmentGranted",
                    {"assignment_id": assignment_id, "actor_id": target["id"]},
                    request,
                )
                return {"id": assignment_id}

            return self.store.command(connection, "grant-assignment", key, dict(payload), operation)

    def revoke_assignment(
        self, principal: Principal, assignment_id: str, request: str
    ) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            assignment = row(
                connection.execute(
                    select(t.assignments)
                    .where(t.assignments.c.id == assignment_id)
                    .with_for_update()
                ).first()
            )
            if not assignment:
                raise ApplicationError("NOT_FOUND", "Assignment is not available", 404)
            self.store.manager(connection, principal, assignment["institution_id"])
            if assignment["revoked_at"] is None:
                connection.execute(
                    update(t.assignments)
                    .where(t.assignments.c.id == assignment_id)
                    .values(revoked_at=now())
                )
                self.store.audit(
                    connection,
                    assignment["institution_id"],
                    assignment["application_id"],
                    "CaseAssignmentRevoked",
                    {"assignment_id": assignment_id},
                    request,
                )
            return {"id": assignment_id, "revoked": True}

    def grant_membership(
        self, principal: Principal, payload: dict[str, Any], key: str, request: str
    ) -> dict[str, Any]:
        require_step_up(principal)
        with self.store.transaction(principal) as connection:
            actor = self.store.actor(connection)
            if not any(
                m["role"] == "identity_admin" and m["jurisdiction"] == payload["jurisdiction"]
                for m in actor["memberships"]
            ):
                raise ApplicationError(
                    "ACCESS_DENIED", "Scoped identity administration is required", 403
                )
            if payload["role"] not in ASSIGNABLE_ROLES:
                raise ApplicationError(
                    "ACCESS_DENIED", "This role requires an organizational provisioning review", 403
                )
            target = row(
                connection.execute(
                    select(t.actors).where(t.actors.c.id == payload["actor_id"])
                ).first()
            )
            if not target:
                raise ApplicationError("NOT_FOUND", "Actor is not available", 404)
            require_distinct_people(actor["person_id"], target["person_id"])
            if payload.get("institution_id"):
                self.store.manager(connection, principal, payload["institution_id"])
            conflict = (
                "rule_approver"
                if payload["role"] == "rule_author"
                else "rule_author"
                if payload["role"] == "rule_approver"
                else None
            )
            if conflict:
                person_actors = select(t.actors.c.id).where(
                    t.actors.c.person_id == target["person_id"]
                )
                if connection.execute(
                    select(t.memberships.c.id).where(
                        t.memberships.c.actor_id.in_(person_actors),
                        t.memberships.c.role == conflict,
                        t.memberships.c.revoked_at.is_(None),
                        (t.memberships.c.expires_at.is_(None))
                        | (t.memberships.c.expires_at > now()),
                    )
                ).first():
                    raise ApplicationError(
                        "SEPARATION_OF_DUTIES",
                        "Rule author and approver must be different people",
                        409,
                    )

            def operation() -> dict[str, Any]:
                membership_id = uid()
                values = {k: v for k, v in payload.items() if k != "lifetime_seconds"}
                connection.execute(
                    insert(t.memberships).values(
                        id=membership_id,
                        **values,
                        expires_at=now() + timedelta(seconds=payload["lifetime_seconds"]),
                        granted_by=actor["id"],
                    )
                )
                self.store.audit(
                    connection,
                    None,
                    None,
                    "MembershipGranted",
                    {"membership_id": membership_id, "role": payload["role"]},
                    request,
                )
                return {"id": membership_id}

            return self.store.command(connection, "grant-membership", key, payload, operation)

    def revoke_membership(
        self, principal: Principal, membership_id: str, request: str
    ) -> dict[str, Any]:
        require_step_up(principal)
        with self.store.transaction(principal) as connection:
            member = row(
                connection.execute(
                    select(t.memberships)
                    .where(t.memberships.c.id == membership_id)
                    .with_for_update()
                ).first()
            )
            if not member:
                raise ApplicationError("NOT_FOUND", "Membership not available", 404)
            actor = self.store.actor(connection)
            if not any(
                m["role"] == "identity_admin" and m["jurisdiction"] == member["jurisdiction"]
                for m in actor["memberships"]
            ):
                raise ApplicationError(
                    "ACCESS_DENIED", "Scoped identity administration required", 403
                )
            if member["role"] in {"supervisor", "identity_admin"}:
                raise ApplicationError(
                    "ACCESS_DENIED", "Organizational provisioning review required", 403
                )
            connection.execute(
                update(t.memberships)
                .where(t.memberships.c.id == membership_id)
                .values(revoked_at=now())
            )
            self.store.audit(
                connection,
                None,
                None,
                "MembershipRevoked",
                {"membership_id": membership_id},
                request,
            )
            return {"id": membership_id, "revoked": True}

    def revoke_session(self, principal: Principal, request: str) -> dict[str, bool]:
        with self.store.transaction(principal) as connection:
            self.store.audit(connection, None, None, "SessionRevoked", {}, request)
            connection.execute(
                insert(t.sessions).values(issuer=principal.issuer, session_id=principal.session_id)
            )
            return {"revoked": True}

    def disable_actor(
        self, principal: Principal, actor_id: str, reason: str, request: str
    ) -> dict[str, Any]:
        require_step_up(principal)
        with self.store.transaction(principal) as connection:
            actor = self.store.actor(connection)
            target = row(
                connection.execute(
                    select(t.actors).where(t.actors.c.id == actor_id).with_for_update()
                ).first()
            )
            if not target:
                raise ApplicationError("NOT_FOUND", "Actor is not available", 404)
            require_distinct_people(actor["person_id"], target["person_id"])
            aliases = select(t.actors.c.id).where(t.actors.c.person_id == target["person_id"])
            memberships = list(
                connection.execute(
                    select(t.memberships).where(
                        t.memberships.c.actor_id.in_(aliases),
                        t.memberships.c.revoked_at.is_(None),
                        (t.memberships.c.expires_at.is_(None))
                        | (t.memberships.c.expires_at > now()),
                    )
                )
            )
            jurisdictions = {
                m["jurisdiction"] for m in actor["memberships"] if m["role"] == "identity_admin"
            }
            if not memberships or any(
                m.jurisdiction not in jurisdictions or m.role in {"identity_admin", "supervisor"}
                for m in memberships
            ):
                raise ApplicationError(
                    "ACCESS_DENIED", "Scoped identity administration required", 403
                )
            self.store.audit(
                connection,
                None,
                None,
                "IdentityDisabled",
                {"actor_id": actor_id, "reason": reason},
                request,
            )
            connection.execute(
                update(t.actors)
                .where(t.actors.c.person_id == target["person_id"])
                .values(disabled=True, valid_after=now())
            )
            return {"id": actor_id, "disabled": True}

    def revoke_emergency(self, principal: Principal, grant_id: str, request: str) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            grant = row(
                connection.execute(
                    select(t.emergency).where(t.emergency.c.id == grant_id).with_for_update()
                ).first()
            )
            if not grant:
                raise ApplicationError("NOT_FOUND", "Emergency request is not available", 404)
            self.store.manager(connection, principal, grant["institution_id"])
            if grant["revoked_at"] is None:
                connection.execute(
                    update(t.emergency).where(t.emergency.c.id == grant_id).values(revoked_at=now())
                )
                self.store.audit(
                    connection,
                    grant["institution_id"],
                    grant["application_id"],
                    "EmergencyAccessRevoked",
                    {"grant_id": grant_id},
                    request,
                )
            return {"id": grant_id, "revoked": True}

    def request_emergency(
        self, principal: Principal, payload: dict[str, Any], key: str, request: str
    ) -> dict[str, Any]:
        require_step_up(principal)
        with self.store.transaction(principal) as connection:
            actor = self.store.actor(connection)
            if not any(m["role"] == "officer" for m in actor["memberships"]):
                raise ApplicationError("ACCESS_DENIED", "Officer authority required", 403)

            def operation() -> dict[str, Any]:
                grant_id = uid()
                connection.execute(
                    insert(t.emergency).values(
                        id=grant_id,
                        requested_by=actor["id"],
                        institution_id=payload["institution_id"],
                        application_id=payload["application_id"],
                        reason=payload["reason"],
                        expires_at=now() + timedelta(seconds=payload["lifetime_seconds"]),
                    )
                )
                self.store.audit(
                    connection,
                    None,
                    None,
                    "EmergencyAccessRequested",
                    {"grant_id": grant_id},
                    request,
                )
                return {"id": grant_id, "state": "AWAITING_INDEPENDENT_APPROVAL"}

            return self.store.command(connection, "request-emergency", key, payload, operation)

    def approve_emergency(
        self, principal: Principal, grant_id: str, request: str
    ) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            grant = row(
                connection.execute(
                    select(t.emergency).where(t.emergency.c.id == grant_id).with_for_update()
                ).first()
            )
            if not grant or grant["expires_at"] <= now() or grant["revoked_at"] is not None:
                raise ApplicationError("NOT_FOUND", "Emergency request is not available", 404)
            self.store.manager(connection, principal, grant["institution_id"])
            requester = row(
                connection.execute(
                    select(t.actors).where(t.actors.c.id == grant["requested_by"])
                ).first()
            )
            require_distinct_people(
                self.store.actor(connection)["person_id"], requester["person_id"]
            )
            if grant["approved_by"] is not None:
                return {"id": grant_id, "read_only": True, "expires_at": grant["expires_at"]}
            connection.execute(
                update(t.emergency)
                .where(t.emergency.c.id == grant_id)
                .values(approved_by=self.store.actor(connection)["id"])
            )
            self.store.audit(
                connection,
                grant["institution_id"],
                grant["application_id"],
                "EmergencyAccessApproved",
                {"grant_id": grant_id},
                request,
            )
            return {"id": grant_id, "read_only": True, "expires_at": grant["expires_at"]}
