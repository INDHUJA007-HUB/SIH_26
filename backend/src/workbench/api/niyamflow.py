"""Authenticated SIH26262 API; database policies remain the scope boundary."""

import csv
import io
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.encoders import jsonable_encoder
from pydantic import Field, field_validator, model_validator
from sqlalchemy import insert, select, text, update

from workbench.adapters import niyam_tables as n
from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore, now, uid
from workbench.adapters.niyam_service import NiyamService, fail
from workbench.contracts.intake import Principal
from workbench.modules.approval_workflow import ProcessPack, aware
from workbench.modules.approval_workflow.policy import StrictModel


class Reason(StrictModel):
    reason: str = Field(min_length=3, max_length=2000)


class Publish(StrictModel):
    source_review: str = Field(min_length=3, max_length=2000)


class CreateCase(StrictModel):
    application_id: str
    pack_id: str


class Transition(Reason):
    expected_revision: int = Field(ge=1)
    action: str = Field(min_length=1, max_length=60)


class Pause(Reason):
    expected_revision: int = Field(ge=1)
    paused: bool
    source_reference: str = Field(min_length=3, max_length=1000)


class Obligation(StrictModel):
    institution_id: str
    application_id: str | None = None
    case_id: str | None = None
    pack_id: str
    kind: Literal["UNDERTAKING", "DOCUMENT_VALIDITY"]
    code: str = Field(pattern=r"^[A-Z0-9_]{1,60}$")
    title: str = Field(min_length=3, max_length=500)
    source_reference: str = Field(min_length=3, max_length=1000)
    due_at: datetime

    _due = field_validator("due_at")(aware)


class Respond(StrictModel):
    expected_revision: int = Field(ge=1)
    evidence_id: str
    proposed_due_at: datetime | None = None

    @field_validator("proposed_due_at")
    @classmethod
    def date(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value else None


class Review(Reason):
    expected_revision: int = Field(ge=1)
    accept: bool


class Extend(Reason):
    expected_revision: int = Field(ge=1)
    due_at: datetime
    source_reference: str = Field(min_length=3, max_length=1000)

    _due = field_validator("due_at")(aware)


class Slot(StrictModel):
    starts_at: datetime
    ends_at: datetime

    _dates = field_validator("starts_at", "ends_at")(aware)

    @model_validator(mode="after")
    def interval(self) -> "Slot":
        if self.starts_at >= self.ends_at:
            raise ValueError("The appointment must have positive duration")
        return self


class Roster(StrictModel):
    region: str = Field(min_length=1, max_length=40)
    source_reference: str = Field(min_length=3, max_length=1000)
    members: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        min_length=1, max_length=30
    )
    availability: list[Slot] = Field(min_length=1, max_length=100)
    conflicts: list[str] = Field(default_factory=list, max_length=500)
    mode: Literal["ONLINE", "OFFLINE"] = "ONLINE"
    expires_at: datetime

    _expires = field_validator("expires_at")(aware)

    @model_validator(mode="after")
    def distinct_members(self) -> "Roster":
        if len(set(self.members)) != len(self.members):
            raise ValueError("Roster membership must be unique")
        if any(slot.ends_at > self.expires_at for slot in self.availability):
            raise ValueError("Availability must be within authorization validity")
        return self


class Proposal(Slot):
    case_id: str
    roster_id: str


class AppointmentAction(Reason):
    action: Literal["CONFIRM", "CANCEL", "COMPLETE", "SUBMIT_REPORT", "ACCEPT_REPORT"]
    evidence_id: str | None = None


class Plan(StrictModel):
    case_ids: list[str] = Field(min_length=1, max_length=100)
    roster_ids: list[str] = Field(min_length=1, max_length=30)


class Grant(StrictModel):
    actor_id: str
    role: Literal["REGIONAL", "BUREAU", "COMMITTEE", "AUTHORITY"]
    region: str = Field(min_length=1, max_length=40)
    application_id: str | None = None
    source_reference: str = Field(min_length=3, max_length=1000)
    expires_at: datetime

    _expires = field_validator("expires_at")(aware)


class UploadPermit(StrictModel):
    slot_id: str
    expires_at: datetime
    source_reference: str = Field(min_length=3, max_length=1000)

    _expires = field_validator("expires_at")(aware)


class Notice(Reason):
    template_key: str = Field(min_length=1, max_length=80)


def create_niyam_router(store: DomainStore, principal: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["NiyamFlow SIH26262"])
    key_type = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]

    def command(
        actor: Principal, key: str, route: str, body: StrictModel, operation: Any
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            service = NiyamService(conn, store)
            return store.command(
                conn,
                route,
                key,
                body.model_dump(mode="json"),
                lambda: jsonable_encoder(operation(service)),
            )

    @router.get("/niyam/session")
    def session(actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as conn:
            identity = store.actor(conn)
            memberships = {m["role"] for m in identity["memberships"]}
            delegated = [
                dict(x)
                for x in conn.execute(
                    select(n.grants).where(
                        n.grants.c.actor_id == identity["id"],
                        n.grants.c.revoked_at.is_(None),
                        n.grants.c.expires_at > now(),
                    )
                ).mappings()
            ]
            roles = memberships | {g["role"] for g in delegated}
            elevated = bool(conn.scalar(text("SELECT wb.elevated()")))
            return {
                "actor_id": identity["id"],
                "roles": sorted(roles),
                "delegations": delegated,
                "elevated": elevated,
                "can_process": elevated
                and bool(roles & {"officer", "supervisor", "REGIONAL", "BUREAU"}),
                "can_respond": "institution_editor" in roles,
                "can_author_pack": elevated and "rule_author" in roles,
                "can_publish_pack": elevated and "rule_approver" in roles,
            }

    @router.get("/process-packs")
    def packs(actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as conn:
            return [dict(x) for x in conn.execute(select(n.packs)).mappings()]

    @router.post("/process-packs", status_code=201)
    def create_pack(
        body: ProcessPack, idempotency_key: key_type, actor: Principal = Depends(principal)
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "pack-create",
            body,
            lambda s: s.create_pack(body.model_dump(mode="json")),
        )

    @router.post("/process-packs/{identifier}/publish")
    def publish(
        identifier: str,
        body: Publish,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "pack-publish:" + identifier,
            body,
            lambda s: s.publish(identifier, body.source_review),
        )

    @router.post("/niyam/access-grants", status_code=201)
    def grant(body: Grant, idempotency_key: key_type, actor: Principal = Depends(principal)) -> Any:
        def operation(s: NiyamService) -> Any:
            s.admin("supervisor")
            if body.region == "*" or body.expires_at <= now():
                fail("INVALID_GRANT", "Provision a named region and a future expiry", 422)
            if not s.c.scalar(
                text(
                    "SELECT EXISTS(SELECT FROM memberships WHERE actor_id=wb.actor_id() "
                    "AND jurisdiction=:r AND revoked_at IS NULL "
                    "AND (expires_at IS NULL OR expires_at>now()))"
                ),
                {"r": body.region},
            ):
                fail("REGION_SCOPE", "A supervisor cannot delegate outside their jurisdiction", 403)
            if not s.c.scalar(
                text("SELECT wb.distinct_people(:a,:b)"), {"a": body.actor_id, "b": s.actor()}
            ):
                fail("SEPARATION_OF_DUTIES", "Delegation requires a different person", 403)
            if body.role == "COMMITTEE" and not body.application_id:
                fail("ASSIGNMENT_REQUIRED", "Committee access requires a specific application", 422)
            if body.application_id:
                app = s.get(t.applications, body.application_id)
                if app["jurisdiction"] != body.region:
                    fail("REGION_SCOPE", "Application and delegation regions differ", 422)
            data = {"id": uid(), **body.model_dump(), "granted_by": s.actor(), "revoked_at": None}
            s.c.execute(insert(n.grants).values(**data))
            s.audit(
                data,
                "ACCESS_DELEGATED",
                {"role": body.role, "region": body.region, "source": body.source_reference},
            )
            return data

        return command(actor, idempotency_key, "grant-create", body, operation)

    @router.post("/niyam/access-grants/{identifier}/revoke")
    def revoke(
        identifier: str,
        body: Reason,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        def operation(s: NiyamService) -> Any:
            s.admin("supervisor")
            record = s.get(n.grants, identifier, True)
            if record["granted_by"] != s.actor():
                fail("ACCESS_DENIED", "The delegating supervisor must revoke this grant", 403)
            s.c.execute(
                update(n.grants).where(n.grants.c.id == identifier).values(revoked_at=now())
            )
            s.audit(record, "ACCESS_REVOKED", {"reason": body.reason})
            return {"revoked": True}

        return command(actor, idempotency_key, "grant-revoke:" + identifier, body, operation)

    @router.post("/approval-cases", status_code=201)
    def create_case(
        body: CreateCase, idempotency_key: key_type, actor: Principal = Depends(principal)
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "case-create",
            body,
            lambda s: s.create_case(body.application_id, body.pack_id),
        )

    @router.get("/approval-cases")
    def cases(
        region: str | None = None,
        limit: int = Query(100, ge=1, le=500),
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as conn:
            query = select(n.cases).order_by(n.cases.c.received_at).limit(limit)
            if region:
                query = query.where(n.cases.c.region == region)
            service = NiyamService(conn, store)
            return [service.decorate(dict(x)) for x in conn.execute(query).mappings()]

    @router.get("/approval-cases/{identifier}/next-actions")
    def actions(identifier: str, actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as conn:
            s = NiyamService(conn, store)
            return s.decorate(s.get(n.cases, identifier))

    @router.get("/approval-cases/{identifier}/case-summary")
    def summary(identifier: str, actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as conn:
            return NiyamService(conn, store).summary(identifier)

    @router.post("/approval-cases/{identifier}/transitions")
    def transition(
        identifier: str,
        body: Transition,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "transition:" + identifier,
            body,
            lambda s: s.transition(identifier, body.expected_revision, body.action, body.reason),
        )

    @router.post("/approval-cases/{identifier}/pause")
    def pause(
        identifier: str,
        body: Pause,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "pause:" + identifier,
            body,
            lambda s: s.pause(
                identifier, body.expected_revision, body.paused, body.reason, body.source_reference
            ),
        )

    @router.post("/approval-cases/{identifier}/notice-drafts")
    def notice(
        identifier: str,
        body: Notice,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "notice:" + identifier,
            body,
            lambda s: s.notice(identifier, body.template_key, body.reason),
        )

    @router.post("/obligations", status_code=201)
    def create_obligation(
        body: Obligation, idempotency_key: key_type, actor: Principal = Depends(principal)
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "obligation-create",
            body,
            lambda s: s.create_obligation(body.model_dump()),
        )

    @router.get("/obligations")
    def obligations(
        limit: int = Query(100, ge=1, le=500), actor: Principal = Depends(principal)
    ) -> Any:
        with store.transaction(actor) as conn:
            s = NiyamService(conn, store)
            return [
                s.decorate(dict(x))
                for x in conn.execute(
                    select(n.obligations).order_by(n.obligations.c.due_at).limit(limit)
                ).mappings()
            ]

    @router.post("/obligations/{identifier}/responses")
    def respond(
        identifier: str,
        body: Respond,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "respond:" + identifier,
            body,
            lambda s: s.respond(
                identifier, body.expected_revision, body.evidence_id, body.proposed_due_at
            ),
        )

    @router.post("/obligations/{identifier}/upload-permits", status_code=201)
    def upload_permit(
        identifier: str,
        body: UploadPermit,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        def operation(s: NiyamService) -> Any:
            record = s.get(n.obligations, identifier, True)
            s.role("OFFICER", record)
            slot = s.get(t.slots, body.slot_id)
            if (
                slot["institution_id"] != record["institution_id"]
                or slot["application_id"] != record["application_id"]
            ):
                fail("EVIDENCE_LINEAGE", "The upload slot belongs to a different application", 422)
            if body.expires_at <= now() or body.expires_at - now() > timedelta(days=30):
                fail("PERMIT_LIFETIME", "A demo upload permit must expire within 30 days", 422)
            data = {
                "id": uid(),
                "institution_id": record["institution_id"],
                "application_id": record["application_id"],
                "obligation_id": identifier,
                "authorized_by": s.actor(),
                **body.model_dump(),
                "revoked_at": None,
            }
            s.c.execute(insert(n.permits).values(**data))
            s.audit(
                record,
                "RENEWAL_UPLOAD_AUTHORIZED",
                {
                    "permit_id": data["id"],
                    "source": body.source_reference,
                    "expires_at": body.expires_at.isoformat(),
                },
            )
            return data

        return command(actor, idempotency_key, "permit:" + identifier, body, operation)

    @router.post("/obligations/{identifier}/reviews")
    def review(
        identifier: str,
        body: Review,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "review:" + identifier,
            body,
            lambda s: s.review(identifier, body.expected_revision, body.accept, body.reason),
        )

    @router.post("/obligations/{identifier}/extensions")
    def extend(
        identifier: str,
        body: Extend,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "extend:" + identifier,
            body,
            lambda s: s.extend(
                identifier, body.expected_revision, body.due_at, body.reason, body.source_reference
            ),
        )

    @router.post("/evc-rosters", status_code=201)
    def roster(
        body: Roster, idempotency_key: key_type, actor: Principal = Depends(principal)
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "roster-create",
            body,
            lambda s: s.create_roster(body.model_dump(mode="json")),
        )

    @router.get("/evc-rosters")
    def rosters(actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as conn:
            return [dict(x) for x in conn.execute(select(n.rosters)).mappings()]

    @router.post("/evc-appointments", status_code=201)
    def proposal(
        body: Proposal, idempotency_key: key_type, actor: Principal = Depends(principal)
    ) -> Any:
        return command(
            actor, idempotency_key, "evc-propose", body, lambda s: s.proposal(body.model_dump())
        )

    @router.post("/evc-appointments/{identifier}/actions")
    def appointment(
        identifier: str,
        body: AppointmentAction,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        return command(
            actor,
            idempotency_key,
            "evc-action:" + identifier,
            body,
            lambda s: s.appointment(identifier, body.action, body.reason, body.evidence_id),
        )

    @router.post("/evc-plans")
    def plan(body: Plan, idempotency_key: key_type, actor: Principal = Depends(principal)) -> Any:
        return command(
            actor,
            idempotency_key,
            "evc-plan",
            body,
            lambda s: s.plan(body.case_ids, body.roster_ids),
        )

    @router.get("/analytics/pendency-dashboard")
    def dashboard(region: str | None = None, actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as conn:
            return NiyamService(conn, store).report("PENDENCY", region)

    @router.get("/reports/consolidated")
    def report(
        report_type: str,
        region: str | None = None,
        format: Literal["json", "csv"] = "json",
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as conn:
            snapshot = NiyamService(conn, store).report(report_type, region)
            if format == "json":
                return snapshot
            stream = io.StringIO()
            fields = sorted({key for row in snapshot["rows"] for key in row})
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for item in snapshot["rows"]:
                # Prevent spreadsheet formula injection in institution-controlled fields.
                writer.writerow(
                    {
                        k: "'" + str(v)
                        if str(v).startswith(("=", "+", "-", "@", "\t", "\r"))
                        else v
                        for k, v in item.items()
                    }
                )
            return Response(
                stream.getvalue(),
                media_type="text/csv",
                headers={
                    "Content-Disposition": 'attachment; filename="niyam-report.csv"',
                    "X-Snapshot-SHA256": snapshot["snapshot_sha256"],
                },
            )

    @router.get("/niyam/alerts")
    def alerts(actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as conn:
            return [
                dict(x)
                for x in conn.execute(
                    select(n.alerts).order_by(n.alerts.c.created_at.desc()).limit(500)
                ).mappings()
            ]

    @router.post("/niyam/alerts/{identifier}/acknowledge")
    def acknowledge(
        identifier: str,
        body: Reason,
        idempotency_key: key_type,
        actor: Principal = Depends(principal),
    ) -> Any:
        def operation(s: NiyamService) -> Any:
            alert = s.get(n.alerts, identifier, True)
            if alert["state"] != "OPEN":
                fail("ALERT_NOT_OPEN", "This alert is already acknowledged or superseded")
            s.c.execute(
                update(n.alerts).where(n.alerts.c.id == identifier).values(state="ACKNOWLEDGED")
            )
            s.audit(
                alert, "ALERT_ACKNOWLEDGED", {"reason": body.reason, "obligation_closed": False}
            )
            return {"id": identifier, "state": "ACKNOWLEDGED", "obligation_closed": False}

        return command(actor, idempotency_key, "alert-ack:" + identifier, body, operation)

    return router
