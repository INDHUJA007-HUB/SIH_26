"""Transactional command handlers over the pure application/manifest policies."""

from typing import Any

from sqlalchemy import insert, select, update

from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore, now, row, uid
from workbench.contracts.intake import Principal
from workbench.modules.applications.domain import canonical, digest, portal_reference, require_draft
from workbench.platform.errors import ApplicationError


class ApplicationService:
    def __init__(self, store: DomainStore) -> None:
        self.store = store

    def create(
        self, principal: Principal, payload: dict[str, Any], key: str, request: str
    ) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            inst = payload["institution_id"]
            self.store.institution_editor(connection, inst)
            institution = row(
                connection.execute(
                    select(t.institutions).where(t.institutions.c.id == inst)
                ).first()
            )
            if not institution:
                raise ApplicationError("NOT_FOUND", "Institution not available", 404)

            def operation() -> dict[str, Any]:
                app_id = uid()
                application = {
                    "id": app_id,
                    "institution_id": inst,
                    "category": payload["category"],
                    "cycle_start": payload["cycle_start"],
                    "programme": payload["programme"],
                    "level": payload["level"],
                    "jurisdiction": institution["jurisdiction"],
                    "portal_system": portal_reference(payload.get("portal_system")),
                    "portal_reference": portal_reference(payload.get("portal_reference")),
                    "stage": "DRAFT",
                    "revision": 1,
                    "declared_facts": payload["declared_facts"],
                    "created_by": self.store.actor(connection)["id"],
                }
                connection.execute(insert(t.applications).values(**application))
                for slot in payload["slots"]:
                    connection.execute(
                        insert(t.slots).values(
                            id=uid(),
                            institution_id=inst,
                            application_id=app_id,
                            code=slot["code"],
                            required=slot["required"],
                        )
                    )
                manifest = self.manifest(application, [])
                connection.execute(
                    insert(t.revisions).values(
                        id=uid(),
                        institution_id=inst,
                        application_id=app_id,
                        revision=1,
                        stage="DRAFT",
                        manifest=manifest,
                        sha256=digest(manifest),
                    )
                )
                self.store.audit(
                    connection, inst, app_id, "ApplicationDraftCreated", {"revision": 1}, request
                )
                return {"id": app_id, "revision": 1, "stage": "DRAFT"}

            return self.store.command(connection, "create-application", key, payload, operation)

    @staticmethod
    def manifest(application: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "schema_version": "intake-manifest-v1",
            "institution_id": application["institution_id"],
            "application_id": application["id"],
            "category": application["category"],
            "academic_cycle_start": application["cycle_start"],
            "programme": application["programme"],
            "level": application["level"],
            "jurisdiction": application["jurisdiction"],
            "portal_system": application.get("portal_system"),
            "portal_reference": application.get("portal_reference"),
            "declaration_basis": "INSTITUTION_DECLARATION_UNVERIFIED",
            "declared_facts": application["declared_facts"],
            "evidence": sorted(evidence, key=lambda item: item["id"]),
        }

    def revise(
        self,
        principal: Principal,
        app_id: str,
        facts: dict[str, Any],
        revision: int,
        key: str,
        request: str,
    ) -> dict[str, Any]:
        canonical(facts)
        with self.store.transaction(principal) as connection:
            application = self.store.application(connection, app_id, lock=True)
            self.store.institution_editor(connection, application["institution_id"])

            def operation() -> dict[str, Any]:
                require_draft(application["stage"])
                if application["revision"] != revision:
                    raise ApplicationError("REVISION_CONFLICT", "Refresh the current revision", 409)
                updated = {**application, "revision": revision + 1, "declared_facts": facts}
                connection.execute(
                    update(t.applications)
                    .where(t.applications.c.id == app_id)
                    .values(revision=revision + 1, declared_facts=facts)
                )
                manifest = self.manifest(updated, [])
                connection.execute(
                    insert(t.revisions).values(
                        id=uid(),
                        institution_id=application["institution_id"],
                        application_id=app_id,
                        revision=revision + 1,
                        stage="DRAFT",
                        manifest=manifest,
                        sha256=digest(manifest),
                    )
                )
                self.store.audit(
                    connection,
                    application["institution_id"],
                    app_id,
                    "ApplicationDraftRevised",
                    {"revision": revision + 1, "facts_sha256": digest(facts)},
                    request,
                )
                return {"id": app_id, "revision": revision + 1, "stage": "DRAFT"}

            return self.store.command(
                connection,
                "revise:" + app_id,
                key,
                {"facts": facts, "revision": revision},
                operation,
            )

    def submit(
        self,
        principal: Principal,
        app_id: str,
        revision: int,
        evidence_ids: list[str],
        key: str,
        request: str,
    ) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            application = self.store.application(connection, app_id, lock=True)
            self.store.institution_editor(connection, application["institution_id"])

            def operation() -> dict[str, Any]:
                require_draft(application["stage"])
                if application["revision"] != revision:
                    raise ApplicationError("REVISION_CONFLICT", "Refresh the current revision", 409)
                pending = connection.execute(
                    select(t.uploads.c.id).where(
                        t.uploads.c.application_id == app_id,
                        t.uploads.c.status == "PENDING",
                        t.uploads.c.expires_at > now(),
                    )
                ).first()
                if pending:
                    raise ApplicationError(
                        "UPLOADS_PENDING",
                        "Complete or expire pending uploads before submission",
                        409,
                    )
                selected = [
                    row(item)
                    for item in connection.execute(
                        select(t.evidence).where(
                            t.evidence.c.application_id == app_id, t.evidence.c.id.in_(evidence_ids)
                        )
                    )
                ]
                if len(selected) != len(set(evidence_ids)) or any(
                    item["status"] != "ACCEPTED" for item in selected
                ):
                    raise ApplicationError(
                        "EVIDENCE_NOT_ACCEPTED",
                        "Only accepted evidence from this application can be submitted",
                        409,
                    )
                frozen = [
                    {
                        name: item[name]
                        for name in (
                            "id",
                            "slot_id",
                            "sha256",
                            "size_bytes",
                            "media_type",
                            "clean_key",
                            "clean_version",
                        )
                    }
                    for item in selected
                ]
                manifest = self.manifest(application, frozen)
                manifest["submitted_revision"] = revision + 1
                manifest_hash = digest(manifest)
                connection.execute(
                    insert(t.revisions).values(
                        id=uid(),
                        institution_id=application["institution_id"],
                        application_id=app_id,
                        revision=revision + 1,
                        stage="SUBMITTED",
                        manifest=manifest,
                        sha256=manifest_hash,
                    )
                )
                connection.execute(
                    update(t.applications)
                    .where(t.applications.c.id == app_id)
                    .values(revision=revision + 1, stage="SUBMITTED")
                )
                self.store.audit(
                    connection,
                    application["institution_id"],
                    app_id,
                    "ApplicationSubmitted",
                    {"revision": revision + 1, "manifest_sha256": manifest_hash},
                    request,
                )
                event_id = self.store.event(
                    connection,
                    application,
                    "ApplicationSubmitted",
                    {"revision": revision + 1, "manifest_sha256": manifest_hash},
                )
                return {
                    "id": app_id,
                    "stage": "SUBMITTED",
                    "revision": revision + 1,
                    "manifest_sha256": manifest_hash,
                    "event_id": event_id,
                }

            return self.store.command(
                connection,
                "submit:" + app_id,
                key,
                {"revision": revision, "evidence_ids": sorted(set(evidence_ids))},
                operation,
            )

    def view(self, principal: Principal, app_id: str) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            application = self.store.application(connection, app_id)
            application["slots"] = [
                row(item)
                for item in connection.execute(
                    select(t.slots).where(t.slots.c.application_id == app_id)
                )
            ]
            return application

    def history(
        self, principal: Principal, app_id: str, after: int = 0, limit: int = 50
    ) -> list[dict[str, Any]]:
        with self.store.transaction(principal) as connection:
            self.store.application(connection, app_id)
            return [
                row(item)
                for item in connection.execute(
                    select(t.revisions)
                    .where(t.revisions.c.application_id == app_id, t.revisions.c.revision > after)
                    .order_by(t.revisions.c.revision)
                    .limit(limit)
                )
            ]

    def summary(self, principal: Principal, app_id: str) -> dict[str, Any]:
        with self.store.transaction(principal) as connection:
            application = self.store.application(connection, app_id)
            slot_rows = [
                row(item)
                for item in connection.execute(
                    select(t.slots).where(t.slots.c.application_id == app_id)
                )
            ]
            versions = [
                row(item)
                for item in connection.execute(
                    select(t.evidence).where(t.evidence.c.application_id == app_id)
                )
            ]
            if application["stage"] == "SUBMITTED":
                manifest = connection.scalar(
                    select(t.revisions.c.manifest).where(
                        t.revisions.c.application_id == app_id,
                        t.revisions.c.revision == application["revision"],
                    )
                )
                assert manifest is not None
                selected = {item["id"] for item in manifest["evidence"]}
                versions = [item for item in versions if item["id"] in selected]
            accepted_slots = {item["slot_id"] for item in versions if item["status"] == "ACCEPTED"}
            return {
                "application_id": app_id,
                "stage": application["stage"],
                "revision": application["revision"],
                "evidence_versions": len(versions),
                "accepted_versions": sum(v["status"] == "ACCEPTED" for v in versions),
                "quarantined_versions": sum(v["status"] != "ACCEPTED" for v in versions),
                "required_slots": sum(s["required"] for s in slot_rows),
                "missing_slots": [
                    s["code"] for s in slot_rows if s["required"] and s["id"] not in accepted_slots
                ],
                "source_verification": "NOT_IMPLEMENTED_UNTIL_PHASE_8",
                "compliance": "NOT_EVALUATED",
            }
