"""Transactional approval/continuing-compliance application service."""

from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn

from sqlalchemy import Connection, Table, insert, select, text, update

from workbench.adapters import niyam_tables as n
from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore, now, uid
from workbench.modules.applications.domain import digest
from workbench.modules.approval_workflow import ProcessPack, clock, time_condition
from workbench.modules.approval_workflow.policy import due_after
from workbench.platform.errors import ApplicationError


def fail(code: str, message: str, status: int = 409) -> NoReturn:
    raise ApplicationError(code, message, status)


class NiyamService:
    def __init__(self, conn: Connection, store: DomainStore | None = None) -> None:
        self.c, self.store = conn, store
        self._packs: dict[str, ProcessPack] = {}

    def actor(self) -> str:
        return str(self.c.scalar(text("SELECT wb.actor_id()")))

    def get(self, table: Table, identifier: str, lock: bool = False) -> dict[str, Any]:
        if lock:
            self.c.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "niyam:" + table.name + ":" + identifier},
            )
        query = select(table).where(table.c.id == identifier)
        item = (
            self.c.execute(query.with_for_update() if lock and self.store else query)
            .mappings()
            .first()
        )
        if not item:
            fail("NOT_FOUND", "Resource is unavailable in your scope", 404)
        return dict(item or {})

    def role(self, role: str, record: dict[str, Any]) -> None:
        permitted = self.c.scalar(
            text("SELECT wb.niyam_role(:role,:region,:app)"),
            {"role": role, "region": record["region"], "app": record.get("application_id")},
        )
        if role == "OFFICER":
            permitted = permitted or self.c.scalar(
                text("""SELECT wb.elevated() AND (
                (wb.has_role('officer') AND wb.can_access(:inst,:app,true))
                OR (wb.has_role('supervisor') AND wb.manages(:inst))
                OR wb.niyam_role('REGIONAL',:region,:app)
                OR wb.niyam_role('BUREAU',:region,:app))"""),
                {
                    "inst": record["institution_id"],
                    "app": record.get("application_id"),
                    "region": record["region"],
                },
            )
        if not permitted:
            fail("ACCESS_DENIED", f"Scoped {role} authority with fresh MFA required", 403)

    def admin(self, role: str) -> None:
        if not self.c.scalar(text("SELECT wb.elevated() AND wb.has_role(:role)"), {"role": role}):
            fail("ACCESS_DENIED", "Fresh MFA and the required governance role are required", 403)

    def audit(self, record: dict[str, Any], kind: str, payload: dict[str, Any]) -> None:
        actor = self.c.scalar(text("SELECT wb.actor_id()")) if self.store else None
        self.c.execute(
            insert(n.events).values(
                id=uid(),
                institution_id=record.get("institution_id"),
                application_id=record.get("application_id"),
                case_id=record.get("case_id"),
                resource_id=record["id"],
                actor_id=actor,
                kind=kind,
                payload=payload,
                created_at=now(),
            )
        )
        # Existing hash chain provides a protected receipt; domain history remains tenant scoped.
        audit_store = self.store or DomainStore(self.c.engine, self.c.engine)
        audit_store.audit(
            self.c,
            None,
            None,
            "NIYAM_" + kind,
            {
                "resource_id": record["id"],
                "institution_id": record.get("institution_id"),
                "event_sha256": digest(payload),
            },
            uid(),
        )

    def pack(self, identifier: str) -> ProcessPack:
        if identifier in self._packs:
            return self._packs[identifier]
        record = self.get(n.packs, identifier)
        if record["state"] != "PUBLISHED":
            fail("PACK_NOT_PUBLISHED", "Publish the reviewed process pack first")
        if digest(record["content"]) != record["sha256"]:
            fail("PACK_INTEGRITY", "Process pack content does not match its frozen hash")
        result = ProcessPack.model_validate(record["content"])
        self._packs[identifier] = result
        return result

    def create_pack(self, content: dict[str, Any]) -> dict[str, Any]:
        self.admin("rule_author")
        pack = ProcessPack.model_validate(content).model_dump(mode="json")
        record = {
            "id": uid(),
            "content": pack,
            "sha256": digest(pack),
            "state": "DRAFT",
            "author_id": self.actor(),
            "approver_id": None,
            "created_at": now(),
            "published_at": None,
        }
        self.c.execute(insert(n.packs).values(**record))
        self.audit(record, "PACK_DRAFTED", {"sha256": record["sha256"]})
        return record

    def publish(self, identifier: str, source_review: str) -> dict[str, Any]:
        self.admin("rule_approver")
        record = self.get(n.packs, identifier, True)
        if record["state"] != "DRAFT":
            fail("PACK_FROZEN", "Published packs are immutable")
        people = (
            self.c.execute(
                text("SELECT person_id FROM actor_identities WHERE id IN (:a,:b)"),
                {"a": record["author_id"], "b": self.actor()},
            )
            .scalars()
            .all()
        )
        # Actor RLS hides the author; a security helper checks the actual people.
        distinct = self.c.scalar(
            text("SELECT wb.distinct_people(:a,:b)"), {"a": record["author_id"], "b": self.actor()}
        )
        if not distinct or (len(people) == 2 and people[0] == people[1]):
            fail("SEPARATION_OF_DUTIES", "A different person must approve the pack", 403)
        ProcessPack.model_validate(record["content"])
        record.update(state="PUBLISHED", approver_id=self.actor(), published_at=now())
        self.c.execute(
            update(n.packs)
            .where(n.packs.c.id == identifier)
            .values(
                state="PUBLISHED",
                approver_id=record["approver_id"],
                published_at=record["published_at"],
            )
        )
        self.audit(
            record, "PACK_PUBLISHED", {"source_review": source_review, "sha256": record["sha256"]}
        )
        return record

    def create_case(self, application_id: str, pack_id: str) -> dict[str, Any]:
        app = self.get(t.applications, application_id)
        scope = {
            "institution_id": app["institution_id"],
            "application_id": app["id"],
            "region": app["jurisdiction"],
        }
        self.role("OFFICER", scope)
        if app["stage"] != "SUBMITTED":
            fail("NOT_SUBMITTED", "An approval case requires a submitted intake application")
        pack = self.pack(pack_id)
        if pack.academic_cycle != app["cycle_start"]:
            fail("CYCLE_MISMATCH", "Pack and application academic cycles differ", 422)
        route = next((s.route for s in pack.selectors if s.category == app["category"]), None)
        if route is None:
            fail("ROUTE_REVIEW_REQUIRED", "No unambiguous approved route for this category", 422)
        stage = pack.stage(pack.routes[route])
        stamp = now()
        submitted = self.c.scalar(
            select(t.revisions.c.created_at)
            .where(
                t.revisions.c.application_id == application_id, t.revisions.c.stage == "SUBMITTED"
            )
            .order_by(t.revisions.c.created_at)
            .limit(1)
        )
        milestones = {"queue_entered_at": stamp.isoformat()} if stage.evc_queue else {}
        record = {
            "id": uid(),
            **scope,
            "pack_id": pack_id,
            "route": route,
            "stage": stage.key,
            "status": "ACTIVE",
            "revision": 1,
            "generation": 1,
            "received_at": submitted or stamp,
            "stage_entered_at": stamp,
            "due_at": due_after(stamp, stage.target_seconds),
            "pauses": [],
            "milestones": milestones,
            "facts": {"category": app["category"], "demo_only": pack.demo_only},
        }
        if stage.evc_queue:
            record["due_at"] = due_after(stamp, pack.evc_scheduling_seconds)
            record["milestones"].update(
                readiness_confirmed_at=stamp.isoformat(),
                scheduling_due_at=record["due_at"].isoformat() if record["due_at"] else None,
            )
        record["facts"]["is_new_institution"] = app["category"] in pack.new_institution_categories
        self.c.execute(insert(n.cases).values(**record))
        self.audit(
            {**record, "case_id": record["id"]},
            "CASE_CREATED",
            {"route": route, "stage": stage.key},
        )
        self.schedule(record, "CASE")
        return self.decorate(record)

    def revision(self, record: dict[str, Any], expected: int) -> None:
        if record["revision"] != expected:
            fail("STALE_REVISION", "Reload the record before acting")

    def decorate(self, record: dict[str, Any]) -> dict[str, Any]:
        result = {
            key: value.astimezone(UTC) if isinstance(value, datetime) else value
            for key, value in record.items()
        }
        result["time_condition"] = time_condition(record.get("due_at"), now())
        if "received_at" in record:
            result["clocks"] = clock(record["received_at"], record["pauses"], now())
            stage = self.pack(record["pack_id"]).stage(record["stage"])
            result["next_actions"] = list(stage.next)
            result["required_role"] = stage.actor_role
            result["policy_basis"] = self.pack(record["pack_id"]).source_reference
            try:
                self.role(stage.actor_role, record)
                result["allowed_to_act"] = record["status"] == "ACTIVE"
            except ApplicationError:
                result["allowed_to_act"] = False
        return result

    def transition(
        self, identifier: str, expected: int, action: str, reason: str
    ) -> dict[str, Any]:
        case = self.get(n.cases, identifier, True)
        self.revision(case, expected)
        pack = self.pack(case["pack_id"])
        stage = pack.stage(case["stage"])
        self.role(stage.actor_role, case)
        if case["status"] != "ACTIVE" or any(p["end"] is None for p in case["pauses"]):
            fail("CASE_BLOCKED", "The case is closed or has an authorized active pause")
        if action not in stage.next:
            fail("INVALID_TRANSITION", "This action is not permitted at the current stage", 422)
        for code in stage.required_obligations:
            item = (
                self.c.execute(
                    select(n.obligations).where(
                        n.obligations.c.case_id == identifier, n.obligations.c.code == code
                    )
                )
                .mappings()
                .first()
            )
            if (
                not item
                or item["state"] != "VERIFIED"
                or (item["kind"] == "DOCUMENT_VALIDITY" and item["due_at"] <= now())
            ):
                fail("OBLIGATION_BLOCKER", f"Verified, applicable evidence is required for {code}")
        if stage.requires_evc_report and not case["milestones"].get("report_accepted_at"):
            fail("EVC_REPORT_REQUIRED", "An authorized accepted EVC report is required")
        target = pack.stage(stage.next[action])
        stamp = now()
        milestones = dict(case["milestones"])
        if target.evc_queue:
            milestones = {"queue_entered_at": stamp.isoformat()}
        case.update(
            stage=target.key,
            status="CLOSED" if target.terminal else "ACTIVE",
            revision=expected + 1,
            generation=case["generation"] + 1,
            stage_entered_at=stamp,
            due_at=due_after(stamp, target.target_seconds),
            milestones=milestones,
        )
        if target.evc_queue:
            case["due_at"] = due_after(stamp, pack.evc_scheduling_seconds)
            case["milestones"].update(
                readiness_confirmed_at=stamp.isoformat(),
                scheduling_due_at=case["due_at"].isoformat() if case["due_at"] else None,
            )
        self.c.execute(update(n.cases).where(n.cases.c.id == identifier).values(**case))
        self.audit(
            {**case, "case_id": identifier},
            "TRANSITION",
            {
                "from": stage.key,
                "to": target.key,
                "action": action,
                "reason": reason,
                "revision": case["revision"],
                "pack_id": case["pack_id"],
            },
        )
        self.schedule(case, "CASE")
        return self.decorate(case)

    def pause(
        self, identifier: str, expected: int, paused: bool, reason: str, source: str
    ) -> dict[str, Any]:
        case = self.get(n.cases, identifier, True)
        self.role("OFFICER", case)
        self.revision(case, expected)
        if case["status"] != "ACTIVE" or not self.pack(case["pack_id"]).pause_authorized:
            fail(
                "PAUSE_NOT_AUTHORIZED", "This process pack does not authorize an operational pause"
            )
        pauses = list(case["pauses"])
        active = bool(pauses and pauses[-1]["end"] is None)
        if active == paused:
            fail("PAUSE_CONFLICT", "Pause state has already changed")
        if paused:
            pauses.append(
                {
                    "start": now().isoformat(),
                    "end": None,
                    "reason": reason,
                    "source": source,
                    "actor": self.actor(),
                }
            )
        else:
            pauses[-1] = {**pauses[-1], "end": now().isoformat()}
        self.c.execute(
            update(n.cases)
            .where(n.cases.c.id == identifier)
            .values(pauses=pauses, revision=expected + 1)
        )
        self.audit(
            {**case, "case_id": identifier},
            "PAUSE" if paused else "RESUME",
            {"reason": reason, "source": source},
        )
        return self.decorate(self.get(n.cases, identifier))

    def create_obligation(self, data: dict[str, Any]) -> dict[str, Any]:
        inst = self.get(t.institutions, data["institution_id"])
        scope = {
            "institution_id": inst["id"],
            "region": inst["jurisdiction"],
            "application_id": data.get("application_id"),
        }
        self.role("OFFICER", scope)
        if data.get("case_id"):
            case = self.get(n.cases, data["case_id"])
            if any(case[k] != scope[k] for k in ("institution_id", "application_id")):
                fail("LINEAGE_MISMATCH", "The case and institution/application differ", 422)
            if case["pack_id"] != data["pack_id"]:
                fail("PACK_MISMATCH", "The obligation must use the case's pinned process pack", 422)
        self.pack(data["pack_id"])
        record = {
            **data,
            **scope,
            "id": uid(),
            "state": "OPEN",
            "revision": 1,
            "generation": 1,
            "accepted_evidence_id": None,
            "submitted_evidence_id": None,
            "submitted_due_at": None,
            "reviewer_id": None,
            "reason": None,
            "created_at": now(),
        }
        self.c.execute(insert(n.obligations).values(**record))
        self.audit(
            record,
            "OBLIGATION_CREATED",
            {
                "kind": data["kind"],
                "source_reference": data["source_reference"],
                "due_at": data["due_at"].isoformat(),
            },
        )
        self.schedule(record, "OBLIGATION")
        return self.decorate(record)

    def evidence(self, record: dict[str, Any], identifier: str) -> dict[str, Any]:
        item = self.get(t.evidence, identifier)
        if (
            item["institution_id"] != record["institution_id"]
            or item["application_id"] != record["application_id"]
        ):
            fail("EVIDENCE_LINEAGE", "Evidence belongs to a different institution/application", 422)
        if item["status"] != "ACCEPTED":
            fail("EVIDENCE_NOT_CLEAN", "Only accepted clean evidence can support a response", 422)
        return item

    def respond(
        self, identifier: str, expected: int, evidence_id: str, proposed_due: datetime | None
    ) -> dict[str, Any]:
        record = self.get(n.obligations, identifier, True)
        self.revision(record, expected)
        if not self.store:
            raise RuntimeError("Response requires an authenticated application transaction")
        self.store.institution_editor(self.c, record["institution_id"])
        if record["state"] == "CANCELLED" or (
            record["kind"] == "UNDERTAKING" and record["state"] == "VERIFIED"
        ):
            fail("OBLIGATION_CLOSED", "The undertaking is already closed")
        self.evidence(record, evidence_id)
        if record["kind"] == "DOCUMENT_VALIDITY" and (
            proposed_due is None or proposed_due <= record["due_at"]
        ):
            fail(
                "RENEWAL_DATE",
                "A replacement expiry later than the accepted expiry is required",
                422,
            )
        self.c.execute(
            update(n.obligations)
            .where(n.obligations.c.id == identifier)
            .values(
                state="SUBMITTED",
                submitted_evidence_id=evidence_id,
                submitted_due_at=proposed_due,
                revision=expected + 1,
                reviewer_id=None,
                reason=None,
            )
        )
        self.audit(
            record,
            "RESPONSE_SUBMITTED",
            {
                "evidence_id": evidence_id,
                "proposed_due_at": proposed_due.isoformat() if proposed_due else None,
            },
        )
        return self.decorate(self.get(n.obligations, identifier))

    def review(self, identifier: str, expected: int, accept: bool, reason: str) -> dict[str, Any]:
        record = self.get(n.obligations, identifier, True)
        self.role("OFFICER", record)
        self.revision(record, expected)
        if record["state"] != "SUBMITTED":
            fail("NO_RESPONSE", "There is no submitted response to verify")
        submitted_by = self.c.scalar(
            select(n.events.c.actor_id)
            .where(n.events.c.resource_id == identifier, n.events.c.kind == "RESPONSE_SUBMITTED")
            .order_by(n.events.c.created_at.desc())
            .limit(1)
        )
        if submitted_by == self.actor():
            fail("SEPARATION_OF_DUTIES", "The submitter cannot verify their own response", 403)
        self.evidence(record, record["submitted_evidence_id"])
        changes: dict[str, Any] = {
            "revision": expected + 1,
            "state": "VERIFIED" if accept else "RETURNED",
            "reviewer_id": self.actor(),
            "reason": reason,
        }
        if accept:
            changes.update(
                accepted_evidence_id=record["submitted_evidence_id"],
                generation=record["generation"] + 1,
            )
            if record["kind"] == "DOCUMENT_VALIDITY":
                if record["submitted_due_at"] <= now():
                    fail("EXPIRED_RENEWAL", "The proposed replacement is already expired", 422)
                changes["due_at"] = record["submitted_due_at"]
        self.c.execute(
            update(n.obligations).where(n.obligations.c.id == identifier).values(**changes)
        )
        self.audit(
            record,
            "RESPONSE_VERIFIED" if accept else "RESPONSE_RETURNED",
            {"reason": reason, "evidence_id": record["submitted_evidence_id"]},
        )
        result = self.get(n.obligations, identifier)
        self.schedule(result, "OBLIGATION")
        return self.decorate(result)

    def extend(
        self, identifier: str, expected: int, due_at: datetime, reason: str, source: str
    ) -> dict[str, Any]:
        record = self.get(n.obligations, identifier, True)
        self.role("AUTHORITY", record)
        self.revision(record, expected)
        if record["kind"] != "UNDERTAKING" or record["state"] in {"VERIFIED", "CANCELLED"}:
            fail(
                "EXTENSION_NOT_PERMITTED",
                "Document validity requires verified issuer evidence; it cannot be extended here",
            )
        if due_at <= record["due_at"]:
            fail("INVALID_EXTENSION", "The new due date must be later", 422)
        self.c.execute(
            update(n.obligations)
            .where(n.obligations.c.id == identifier)
            .values(due_at=due_at, revision=expected + 1, generation=record["generation"] + 1)
        )
        self.audit(
            record,
            "DEADLINE_EXTENDED",
            {
                "old_due_at": record["due_at"].isoformat(),
                "new_due_at": due_at.isoformat(),
                "reason": reason,
                "source": source,
            },
        )
        result = self.get(n.obligations, identifier)
        self.schedule(result, "OBLIGATION")
        return self.decorate(result)

    def schedule(self, record: dict[str, Any], kind: str) -> None:
        if self.store is None:
            return
        self.c.execute(
            update(n.alerts)
            .where(
                n.alerts.c.resource_id == record["id"],
                n.alerts.c.state == "OPEN",
                n.alerts.c.generation != record["generation"],
            )
            .values(state="SUPERSEDED")
        )
        self.store.event(
            self.c,
            {"id": record.get("application_id"), "institution_id": record["institution_id"]},
            "NiyamDeadlineScheduled",
            {
                "resource_id": record["id"],
                "resource_kind": kind,
                "generation": record["generation"],
            },
        )

    def deadline_plan(self, identifier: str, kind: str, generation: int) -> dict[str, Any]:
        record = self.get(n.cases if kind == "CASE" else n.obligations, identifier)
        active = (
            record["status"] == "ACTIVE"
            if kind == "CASE"
            else (
                record["state"] != "CANCELLED"
                and (record["kind"] == "DOCUMENT_VALIDITY" or record["state"] != "VERIFIED")
            )
        )
        if (
            kind == "CASE"
            and record["milestones"].get("report_accepted_at")
            and self.pack(record["pack_id"]).stage(record["stage"]).evc_queue
        ):
            active = False
        if not active or record["generation"] != generation or record["due_at"] is None:
            return {"active": False, "triggers": []}
        pack = self.pack(record["pack_id"])
        return {
            "active": True,
            "triggers": [
                {
                    "key": rule.key,
                    "at": (record["due_at"] + timedelta(seconds=rule.offset_seconds)).isoformat(),
                    "recipient_role": rule.recipient_role,
                }
                for rule in sorted(pack.reminders, key=lambda r: r.offset_seconds)
            ],
        }

    def fire_deadline(
        self, identifier: str, kind: str, generation: int, key: str
    ) -> dict[str, Any]:
        record = self.get(n.cases if kind == "CASE" else n.obligations, identifier, True)
        plan = self.deadline_plan(identifier, kind, generation)
        rule = next((r for r in plan["triggers"] if r["key"] == key), None)
        if not rule or datetime.fromisoformat(rule["at"]) > now():
            return {"state": "SUPERSEDED_OR_NOT_DUE"}
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        result = self.c.execute(
            pg_insert(n.alerts)
            .values(
                id=uid(),
                institution_id=record["institution_id"],
                application_id=record.get("application_id"),
                resource_id=identifier,
                resource_kind=kind,
                generation=generation,
                rule_key=key,
                recipient_role=rule["recipient_role"],
                state="OPEN",
                trigger_at=datetime.fromisoformat(rule["at"]),
                created_at=now(),
            )
            .on_conflict_do_nothing()
            .returning(n.alerts.c.id)
        ).scalar()
        if result:
            self.audit(
                record,
                "DEADLINE_ALERT",
                {"rule": key, "recipient_role": rule["recipient_role"], "generation": generation},
            )
        return {"state": "OPEN", "created": bool(result)}

    def create_roster(self, data: dict[str, Any]) -> dict[str, Any]:
        record = {**data, "id": uid()}
        self.c.execute(
            insert(n.rosters).values(**record)
        )  # RLS checks jurisdiction and governance role.
        self.audit(record, "ROSTER_RECORDED", {"source_reference": data["source_reference"]})
        return record

    def proposal(self, data: dict[str, Any]) -> dict[str, Any]:
        case = self.get(n.cases, data["case_id"])
        self.role("OFFICER", case)
        pack = self.pack(case["pack_id"])
        if case["status"] != "ACTIVE" or not pack.stage(case["stage"]).evc_queue:
            fail(
                "EVC_NOT_READY",
                "The applicable preliminary process must place the case in an EVC queue",
            )
        roster = self.get(n.rosters, data["roster_id"])
        start, end = data["starts_at"], data["ends_at"]
        if roster["region"] != case["region"] or roster["expires_at"] < end or start <= now():
            fail(
                "INELIGIBLE_ROSTER",
                "Roster region, authorization or appointment date is invalid",
                422,
            )
        if case["institution_id"] in roster["conflicts"]:
            fail("CONFLICT_OF_INTEREST", "Roster conflicts with the institution", 422)
        if not any(
            datetime.fromisoformat(slot["starts_at"]) <= start
            and end <= datetime.fromisoformat(slot["ends_at"])
            for slot in roster["availability"]
        ):
            fail("OUTSIDE_AVAILABILITY", "The appointment is outside authorized availability", 422)
        record = {
            "id": uid(),
            "institution_id": case["institution_id"],
            "application_id": case["application_id"],
            **data,
            "region": case["region"],
            "state": "PROPOSED",
            "members": roster["members"],
            "created_at": now(),
            "confirmed_by": None,
            "explanation": {
                "method": "CONSTRAINT_CHECKED_PROPOSAL",
                "solver_status": "FEASIBLE_CANDIDATE",
                "roster_source": roster["source_reference"],
                "mode": roster["mode"],
                "requires_confirmation": True,
            },
        }
        self.c.execute(insert(n.appointments).values(**record))
        self.audit({**case, "case_id": case["id"]}, "EVC_PROPOSED", {"proposal_id": record["id"]})
        return record

    def appointment(
        self, identifier: str, action: str, reason: str, evidence_id: str | None
    ) -> dict[str, Any]:
        proposal = self.get(n.appointments, identifier, True)
        case = self.get(n.cases, proposal["case_id"], True)
        self.role("COMMITTEE" if action in {"COMPLETE", "SUBMIT_REPORT"} else "OFFICER", case)
        if action == "CONFIRM":
            if proposal["state"] != "PROPOSED":
                fail("BOOKING_STATE", "Only a current proposal can be confirmed")
            # Serialize all common members across different authorized committees.
            for member in sorted(proposal["members"]):
                self.c.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                    {"key": "evc-member:" + member},
                )
            self.proposal_check(proposal, case)
            bookings = (
                self.c.execute(
                    select(n.appointments).where(
                        n.appointments.c.state.in_(["CONFIRMED", "COMPLETED"]),
                        n.appointments.c.starts_at < proposal["ends_at"],
                        n.appointments.c.ends_at > proposal["starts_at"],
                    )
                )
                .mappings()
                .all()
            )
            if any(set(p["members"]) & set(proposal["members"]) for p in bookings):
                fail("MEMBER_DOUBLE_BOOKING", "An individual committee member is already booked")
            milestone = {
                **case["milestones"],
                "confirmed_at": now().isoformat(),
                "appointment_id": identifier,
            }
            pack = self.pack(case["pack_id"])
            milestone.update(
                planned_starts_at=proposal["starts_at"].isoformat(),
                planned_ends_at=proposal["ends_at"].isoformat(),
                report_clock_basis=pack.evc_report_clock,
            )
            origin = now() if pack.evc_report_clock == "CONFIRMATION" else proposal["ends_at"]
            report_due = (
                due_after(origin, pack.evc_report_seconds)
                if pack.evc_report_clock != "ACTUAL_COMPLETION"
                else None
            )
            milestone["report_due_at"] = report_due.isoformat() if report_due else None
            due = report_due or proposal["ends_at"]
            state = "CONFIRMED"
        elif action == "CANCEL":
            if proposal["state"] not in {"PROPOSED", "CONFIRMED"}:
                fail("BOOKING_STATE", "The appointment can no longer be cancelled")
            if proposal["state"] == "PROPOSED":
                self.c.execute(
                    update(n.appointments)
                    .where(n.appointments.c.id == identifier)
                    .values(state="CANCELLED")
                )
                self.audit(
                    {**case, "case_id": case["id"]},
                    "EVC_CANCEL",
                    {"appointment_id": identifier, "reason": reason, "unconfirmed": True},
                )
                return self.get(n.appointments, identifier)
            milestone = {
                "queue_entered_at": case["milestones"].get("queue_entered_at", now().isoformat()),
                "cancelled_at": now().isoformat(),
            }
            due = due_after(
                datetime.fromisoformat(milestone["queue_entered_at"]),
                self.pack(case["pack_id"]).evc_scheduling_seconds,
            )
            state = "CANCELLED"
        else:
            milestones = case["milestones"]
            required = {
                "COMPLETE": "CONFIRMED",
                "SUBMIT_REPORT": "COMPLETED",
                "ACCEPT_REPORT": "COMPLETED",
            }
            if (
                proposal["state"] != required[action]
                or milestones.get("appointment_id") != identifier
            ):
                fail("BOOKING_STATE", "Appointment milestones must be completed in order")
            if action == "COMPLETE" and now() < proposal["ends_at"]:
                fail("VISIT_NOT_FINISHED", "The scheduled appointment has not finished")
            if action == "SUBMIT_REPORT":
                if not evidence_id:
                    fail("REPORT_EVIDENCE_REQUIRED", "Submit the clean committee report", 422)
                self.evidence(case, evidence_id)
            if action == "ACCEPT_REPORT" and not milestones.get("report_submitted_at"):
                fail("REPORT_NOT_SUBMITTED", "Committee report submission is required")
            if action == "ACCEPT_REPORT" and milestones.get("report_submitted_by") == self.actor():
                fail(
                    "SEPARATION_OF_DUTIES",
                    "A different authorized officer must accept the report",
                    403,
                )
            key = {
                "COMPLETE": "visit_completed_at",
                "SUBMIT_REPORT": "report_submitted_at",
                "ACCEPT_REPORT": "report_accepted_at",
            }[action]
            if milestones.get(key):
                fail("MILESTONE_ALREADY_RECORDED", "This milestone has already been recorded")
            milestone = {**milestones, key: now().isoformat()}
            if evidence_id:
                milestone["report_evidence_id"] = evidence_id
                milestone["report_submitted_by"] = self.actor()
            due, state = case["due_at"], "COMPLETED"
            pack = self.pack(case["pack_id"])
            if action == "COMPLETE" and pack.evc_report_clock == "ACTUAL_COMPLETION":
                due = due_after(now(), pack.evc_report_seconds)
                milestone["report_due_at"] = due.isoformat() if due else None
        self.c.execute(
            update(n.appointments)
            .where(n.appointments.c.id == identifier)
            .values(
                state=state,
                confirmed_by=self.actor() if action == "CONFIRM" else proposal["confirmed_by"],
            )
        )
        self.c.execute(
            update(n.cases)
            .where(n.cases.c.id == case["id"])
            .values(
                milestones=milestone,
                due_at=due,
                revision=case["revision"] + 1,
                generation=case["generation"] + 1,
            )
        )
        self.audit(
            {**case, "case_id": case["id"]},
            "EVC_" + action,
            {"appointment_id": identifier, "reason": reason},
        )
        self.schedule(self.get(n.cases, case["id"]), "CASE")
        return self.get(n.appointments, identifier)

    def proposal_check(self, proposal: dict[str, Any], case: dict[str, Any]) -> None:
        # Rosters are append-only. Locking them would require unnecessary UPDATE grants.
        roster = self.get(n.rosters, proposal["roster_id"])
        if (
            case["status"] != "ACTIVE"
            or not self.pack(case["pack_id"]).stage(case["stage"]).evc_queue
        ):
            fail("STALE_PROPOSAL", "The case is no longer in an eligible EVC stage")
        if proposal["starts_at"] <= now() or roster["expires_at"] < proposal["ends_at"]:
            fail("STALE_PROPOSAL", "Appointment or authorization has expired")
        if (
            case["institution_id"] in roster["conflicts"]
            or proposal["members"] != roster["members"]
        ):
            fail("STALE_PROPOSAL", "Roster membership or conflict state changed")
        if self.c.scalar(
            select(n.appointments.c.id).where(
                n.appointments.c.case_id == case["id"], n.appointments.c.state == "CONFIRMED"
            )
        ):
            fail("CASE_ALREADY_BOOKED", "The case already has a confirmed appointment")

    def summary(self, identifier: str) -> dict[str, Any]:
        case = self.get(n.cases, identifier)
        return {
            "generated_at": now().isoformat(),
            "case": self.decorate(case),
            "obligations": [
                self.decorate(dict(x))
                for x in self.c.execute(
                    select(n.obligations).where(n.obligations.c.case_id == identifier)
                ).mappings()
            ],
            "history": [
                dict(x)
                for x in self.c.execute(
                    select(n.events)
                    .where(n.events.c.case_id == identifier)
                    .order_by(n.events.c.created_at)
                ).mappings()
            ],
            "appointments": [
                dict(x)
                for x in self.c.execute(
                    select(n.appointments).where(n.appointments.c.case_id == identifier)
                ).mappings()
            ],
            "document_status": "GENERATED_CASE_SUMMARY_NOT_AN_ISSUED_NOTICE",
        }

    def notice(self, identifier: str, template_key: str, reason: str) -> dict[str, Any]:
        case = self.get(n.cases, identifier)
        self.role("OFFICER", case)
        pack = self.pack(case["pack_id"])
        if template_key not in pack.notice_templates:
            fail("TEMPLATE_NOT_APPROVED", "Choose a template from this case's published pack", 422)
        content = pack.notice_templates[template_key].format_map(
            {
                "case_reference": case["id"],
                "institution_reference": case["institution_id"],
                "stage": case["stage"],
                "reason": reason,
                "generated_at": now().isoformat(),
            }
        )
        record = {
            "id": uid(),
            "state": "DRAFT_REQUIRES_AUTHORIZED_ISSUE",
            "template_key": template_key,
            "case_id": identifier,
            "pack_id": case["pack_id"],
            "content": content,
            "content_sha256": digest(content),
            "generated_at": now().isoformat(),
        }
        self.audit({**case, "case_id": identifier}, "NOTICE_DRAFTED", record)
        return record

    def plan(self, case_ids: list[str], roster_ids: list[str]) -> dict[str, Any]:
        cases = [self.get(n.cases, key) for key in set(case_ids)]
        rosters = [self.get(n.rosters, key) for key in set(roster_ids)]
        candidates: dict[str, list[dict[str, Any]]] = {}
        for case in cases:
            self.role("OFFICER", case)
            candidates[case["id"]] = []
            if (
                case["status"] != "ACTIVE"
                or not self.pack(case["pack_id"]).stage(case["stage"]).evc_queue
            ):
                continue
            for roster in rosters:
                if (
                    roster["region"] != case["region"]
                    or case["institution_id"] in roster["conflicts"]
                ):
                    continue
                for slot in roster["availability"]:
                    start, end = (datetime.fromisoformat(slot[k]) for k in ("starts_at", "ends_at"))
                    if now() < start < end <= roster["expires_at"]:
                        candidates[case["id"]].append(
                            {
                                "case_id": case["id"],
                                "roster_id": roster["id"],
                                "starts_at": start,
                                "ends_at": end,
                                "members": roster["members"],
                            }
                        )
        existing = [
            dict(x)
            for x in self.c.execute(
                select(n.appointments).where(n.appointments.c.state.in_(["CONFIRMED", "COMPLETED"]))
            ).mappings()
        ]
        chosen, unassigned = [], []
        for case in sorted(
            cases,
            key=lambda x: (
                x["due_at"] or datetime.max.replace(tzinfo=UTC),
                len(candidates[x["id"]]),
                x["received_at"],
                x["id"],
            ),
        ):
            available = None
            for option in sorted(
                candidates[case["id"]], key=lambda x: (x["starts_at"], x["roster_id"])
            ):
                if not any(
                    set(b["members"]) & set(option["members"])
                    and b["starts_at"] < option["ends_at"]
                    and b["ends_at"] > option["starts_at"]
                    for b in existing
                ):
                    available = option
                    break
            if available is None:
                unassigned.append(
                    {
                        "case_id": case["id"],
                        "reason": "NO_ELIGIBLE_AVAILABLE_SLOT_OR_CASE_NOT_READY",
                    }
                )
            else:
                existing.append(available)
                data = {k: v for k, v in available.items() if k != "members"}
                chosen.append(self.proposal(data))
        return {
            "method": "SCARCITY_AWARE_EARLIEST_DEADLINE",
            "optimality_proven": False,
            "proposals": chosen,
            "unassigned": unassigned,
            "note": "Proposals require atomic confirmation; no statutory ordering is inferred.",
        }

    def report(self, report_type: str, region: str | None) -> dict[str, Any]:
        allowed = {
            "PENDENCY",
            "EVC_STATUS",
            "UNDERTAKING_COMPLIANCE",
            "DOCUMENT_VALIDITY",
            "OVERDUE",
            "REGIONAL_PERFORMANCE",
        }
        if report_type not in allowed:
            fail("INVALID_REPORT_TYPE", "Choose one of the six report families", 422)
        tables = {
            "PENDENCY": n.cases,
            "REGIONAL_PERFORMANCE": n.cases,
            "EVC_STATUS": n.cases,
            "UNDERTAKING_COMPLIANCE": n.obligations,
            "DOCUMENT_VALIDITY": n.obligations,
            "OVERDUE": n.obligations,
        }
        target = tables[report_type]
        query = select(target)
        if region:
            query = query.where(target.c.region == region)
        if report_type in {"UNDERTAKING_COMPLIANCE", "DOCUMENT_VALIDITY"}:
            query = query.where(
                target.c.kind
                == (
                    "UNDERTAKING"
                    if report_type == "UNDERTAKING_COMPLIANCE"
                    else "DOCUMENT_VALIDITY"
                )
            )
        items = [dict(x) for x in self.c.execute(query.order_by(target.c.id)).mappings()]
        if target in (n.cases, n.obligations):
            items = [self.decorate(x) for x in items]
        if report_type == "EVC_STATUS":
            items = [x for x in items if x["milestones"].get("queue_entered_at")]
            for item in items:
                item["appointments"] = [
                    dict(x)
                    for x in self.c.execute(
                        select(n.appointments).where(n.appointments.c.case_id == item["id"])
                    ).mappings()
                ]
        if report_type == "OVERDUE":
            items = [
                x
                for x in items
                if x["time_condition"] == "OVERDUE"
                and x["state"] != "CANCELLED"
                and not (x["kind"] == "UNDERTAKING" and x["state"] == "VERIFIED")
            ]
            case_query = select(n.cases).where(
                n.cases.c.status == "ACTIVE", n.cases.c.due_at < now()
            )
            if region:
                case_query = case_query.where(n.cases.c.region == region)
            items += [self.decorate(dict(x)) for x in self.c.execute(case_query).mappings()]
        aggregates: dict[str, dict[str, int]] = {}
        for item in items:
            counts = aggregates.setdefault(
                item["region"], {"total": 0, "active": 0, "closed": 0, "overdue": 0}
            )
            counts["total"] += 1
            counts["active"] += item.get("status") == "ACTIVE"
            counts["closed"] += item.get("status") == "CLOSED"
            counts["overdue"] += item.get("time_condition") == "OVERDUE" and (
                item.get("status") == "ACTIVE"
                or item.get("kind") == "DOCUMENT_VALIDITY"
                or (
                    item.get("kind") == "UNDERTAKING"
                    and item.get("state") not in {"VERIFIED", "CANCELLED"}
                )
            )
        # JSON-safe frozen response used by the command receipt/export caller.
        from fastapi.encoders import jsonable_encoder

        snapshot = jsonable_encoder(
            {
                "report_type": report_type,
                "filters": {"region": region},
                "generated_at": now(),
                "scope_actor_id": self.actor(),
                "rows": items,
                "aggregates": aggregates,
                "calendar_basis": "ELAPSED_SECONDS",
            }
        )
        return {**snapshot, "snapshot_sha256": digest(snapshot)}
