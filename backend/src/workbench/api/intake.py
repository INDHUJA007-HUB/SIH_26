"""Phase 2–4 HTTP contracts. Handlers delegate to transactional application boundaries."""

from typing import Any, Literal

import anyio
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.types import Receive, Scope, Send

from workbench.adapters import tables as t
from workbench.adapters.application_service import ApplicationService
from workbench.adapters.auth import JWTVerifier
from workbench.adapters.claims_service import ClaimsService
from workbench.adapters.delivery_service import DeliveryService
from workbench.adapters.domain_store import DomainStore, row
from workbench.adapters.evidence_service import EvidenceService
from workbench.adapters.extraction_service import ExtractionService
from workbench.adapters.identity_service import IdentityService
from workbench.adapters.object_storage import ObjectStorage
from workbench.adapters.operations_service import OperationsService
from workbench.contracts.intake import Principal
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.platform.errors import AuthenticationRequired, NotFoundError

bearer = HTTPBearer(auto_error=False)


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SlotBody(StrictBody):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_\.]+$")
    required: bool = True


class ApplicationBody(StrictBody):
    institution_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    category: str = Field(min_length=1, max_length=50)
    cycle_start: int = Field(ge=2024, le=2100, strict=True)
    programme: str = Field(min_length=1, max_length=80)
    level: Literal["DIPLOMA", "UG", "PG"]
    portal_system: str | None = Field(default=None, min_length=1, max_length=80)
    portal_reference: str | None = Field(default=None, min_length=1, max_length=120)
    declared_facts: dict[str, Any] = Field(default_factory=dict)
    slots: list[SlotBody] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_scope(self) -> Any:
        if bool(self.portal_system) != bool(self.portal_reference):
            raise ValueError("Portal system and reference must be supplied together")
        if len({slot.code for slot in self.slots}) != len(self.slots):
            raise ValueError("Duplicate evidence slots")
        return self


class RevisionBody(StrictBody):
    expected_revision: int = Field(ge=1, strict=True)
    declared_facts: dict[str, Any]


class SubmitBody(StrictBody):
    expected_revision: int = Field(ge=1, strict=True)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)


class UploadBody(StrictBody):
    slot_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    filename: str = Field(min_length=1, max_length=200)
    media_type: Literal["application/pdf", "image/png", "image/jpeg", "video/mp4"]
    size_bytes: int = Field(ge=1, le=100 * 1024 * 1024, strict=True)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mode: Literal["SINGLE", "MULTIPART"] = "SINGLE"
    parent_version_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")


class CompleteBody(StrictBody):
    version_id: str | None = Field(default=None, min_length=1, max_length=200)


class CorrectionBody(StrictBody):
    field_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    corrected_value: dict[str, Any]
    reason: str = Field(min_length=5, max_length=500)
    authority: str = Field(default="STATUTORY_REVIEWER", min_length=2, max_length=80)


class AssignmentBody(StrictBody):
    institution_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    application_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    actor_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    access_role: Literal["officer", "auditor"]
    reason: str = Field(min_length=10, max_length=500)
    lifetime_seconds: int = Field(ge=60, le=7 * 24 * 3600)


class MembershipBody(StrictBody):
    actor_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    institution_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")
    role: Literal[
        "institution_editor",
        "institution_viewer",
        "officer",
        "auditor",
        "rule_author",
        "rule_approver",
    ]
    jurisdiction: str = Field(min_length=1, max_length=40)
    lifetime_seconds: int = Field(ge=60, le=30 * 24 * 3600)

    @model_validator(mode="after")
    def check_institution(self) -> Any:
        if self.role.startswith("institution_") != bool(self.institution_id):
            raise ValueError("Institution roles require institution scope; global roles do not")
        return self


class EmergencyBody(StrictBody):
    institution_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    application_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    reason: str = Field(min_length=20, max_length=500)
    lifetime_seconds: int = Field(ge=60, le=3600)


class DisableBody(StrictBody):
    reason: str = Field(min_length=10, max_length=500)


def register_intake_api(app: FastAPI, settings: Settings) -> DomainStore:
    if (
        not settings.app_database_url.get_secret_value()
        or not settings.delivery_database_url.get_secret_value()
    ):
        raise ValueError(
            "Domain API requires separate application and delivery database credentials"
        )
    store = DomainStore(
        build_engine(settings.app_database_url.get_secret_value()),
        build_engine(settings.delivery_database_url.get_secret_value()),
    )
    identity, applications = IdentityService(store), ApplicationService(store)
    storage = ObjectStorage(settings)
    evidence, delivery = EvidenceService(store, storage, settings), DeliveryService(store, storage)
    extraction_service = ExtractionService(store.engine)
    claims_service = ClaimsService(store.engine)
    verifier = JWTVerifier(settings)
    router = APIRouter(prefix="/api/v1")

    def principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
        if credentials is None:
            raise AuthenticationRequired()
        return verifier.principal(credentials.credentials)

    def command_key(idempotency_key: str = Header(pattern=r"^[a-zA-Z0-9_-]{8,128}$")) -> str:
        return idempotency_key

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, _: IntegrityError) -> Any:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {
                "code": "CONSTRAINT_CONFLICT",
                "title": "The command conflicts with stored scope or state",
                "status": 409,
                "request_id": request.state.request_id,
            },
            status_code=409,
        )

    @app.exception_handler(ClientError)
    async def storage_error(request: Request, error: ClientError) -> Any:
        from fastapi.responses import JSONResponse

        pending = error.response["Error"]["Code"] in {"404", "NoSuchKey", "NoSuchVersion"}
        status = 409 if pending else 503
        return JSONResponse(
            {
                "code": "UPLOAD_NOT_READY" if pending else "STORAGE_UNAVAILABLE",
                "title": "The requested storage operation is not available",
                "status": status,
                "request_id": request.state.request_id,
            },
            status_code=status,
        )

    @router.get("/me", tags=["identity"])
    def me(actor: Principal = Depends(principal)) -> Any:
        return identity.me(actor)

    @router.get("/me/assignments", tags=["identity"])
    def assignments(actor: Principal = Depends(principal)) -> Any:
        return identity.assignments(actor)

    @router.post("/me/revoke-session", tags=["identity"])
    def revoke_session(request: Request, actor: Principal = Depends(principal)) -> Any:
        return identity.revoke_session(actor, request.state.request_id)

    @router.post("/assignments", status_code=201, tags=["identity"])
    def grant_assignment(
        body: AssignmentBody,
        request: Request,
        actor: Principal = Depends(principal),
        key: str = Depends(command_key),
    ) -> Any:
        return identity.grant_assignment(actor, body.model_dump(), key, request.state.request_id)

    @router.post("/assignments/{assignment_id}/revoke", tags=["identity"])
    def revoke_assignment(
        assignment_id: str, request: Request, actor: Principal = Depends(principal)
    ) -> Any:
        return identity.revoke_assignment(actor, assignment_id, request.state.request_id)

    @router.post("/memberships", status_code=201, tags=["identity"])
    def grant_membership(
        body: MembershipBody,
        request: Request,
        actor: Principal = Depends(principal),
        key: str = Depends(command_key),
    ) -> Any:
        return identity.grant_membership(actor, body.model_dump(), key, request.state.request_id)

    @router.post("/memberships/{membership_id}/revoke", tags=["identity"])
    def revoke_membership(
        membership_id: str, request: Request, actor: Principal = Depends(principal)
    ) -> Any:
        return identity.revoke_membership(actor, membership_id, request.state.request_id)

    @router.post("/emergency-grants", status_code=201, tags=["identity"])
    def emergency_request(
        body: EmergencyBody,
        request: Request,
        actor: Principal = Depends(principal),
        key: str = Depends(command_key),
    ) -> Any:
        return identity.request_emergency(actor, body.model_dump(), key, request.state.request_id)

    @router.post("/actors/{actor_id}/disable", tags=["identity"])
    def disable_actor(
        actor_id: str, body: DisableBody, request: Request, actor: Principal = Depends(principal)
    ) -> Any:
        return identity.disable_actor(actor, actor_id, body.reason, request.state.request_id)

    @router.post("/emergency-grants/{grant_id}/revoke", tags=["identity"])
    def emergency_revoke(
        grant_id: str, request: Request, actor: Principal = Depends(principal)
    ) -> Any:
        return identity.revoke_emergency(actor, grant_id, request.state.request_id)

    @router.post("/emergency-grants/{grant_id}/approve", tags=["identity"])
    def emergency_approve(
        grant_id: str, request: Request, actor: Principal = Depends(principal)
    ) -> Any:
        return identity.approve_emergency(actor, grant_id, request.state.request_id)

    @router.post("/applications", status_code=201, tags=["applications"])
    def create_application(
        body: ApplicationBody,
        request: Request,
        actor: Principal = Depends(principal),
        key: str = Depends(command_key),
    ) -> Any:
        return applications.create(actor, body.model_dump(), key, request.state.request_id)

    @router.get("/applications", tags=["applications"])
    def list_applications(
        after: str = "",
        limit: int = Query(default=50, ge=1, le=100),
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as connection:
            return [
                row(item)
                for item in connection.execute(
                    select(t.applications)
                    .where(t.applications.c.id > after)
                    .order_by(t.applications.c.id)
                    .limit(limit)
                )
            ]

    @router.get("/applications/{application_id}", tags=["applications"])
    def get_application(
        application_id: str, response: Response, actor: Principal = Depends(principal)
    ) -> Any:
        result = applications.view(actor, application_id)
        response.headers["ETag"] = '"' + str(result["revision"]) + '"'
        return result

    @router.patch("/applications/{application_id}", tags=["applications"])
    def revise_application(
        application_id: str,
        body: RevisionBody,
        request: Request,
        actor: Principal = Depends(principal),
        key: str = Depends(command_key),
    ) -> Any:
        return applications.revise(
            actor,
            application_id,
            body.declared_facts,
            body.expected_revision,
            key,
            request.state.request_id,
        )

    @router.post("/applications/{application_id}/submit", tags=["applications"])
    def submit_application(
        application_id: str,
        body: SubmitBody,
        request: Request,
        actor: Principal = Depends(principal),
        key: str = Depends(command_key),
    ) -> Any:
        return applications.submit(
            actor,
            application_id,
            body.expected_revision,
            body.evidence_ids,
            key,
            request.state.request_id,
        )

    @router.get("/applications/{application_id}/revisions", tags=["applications"])
    def application_history(
        application_id: str,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=100),
        actor: Principal = Depends(principal),
    ) -> Any:
        return applications.history(actor, application_id, after, limit)

    @router.get("/applications/{application_id}/summary", tags=["applications"])
    def application_summary(application_id: str, actor: Principal = Depends(principal)) -> Any:
        return applications.summary(actor, application_id)

    @router.post(
        "/applications/{application_id}/upload-sessions", status_code=201, tags=["evidence"]
    )
    def initiate_upload(
        application_id: str,
        body: UploadBody,
        request: Request,
        actor: Principal = Depends(principal),
        key: str = Depends(command_key),
    ) -> Any:
        return evidence.initiate(
            actor, application_id, body.model_dump(), key, request.state.request_id
        )

    @router.get("/upload-sessions/{upload_id}", tags=["evidence"])
    def describe_upload(upload_id: str, actor: Principal = Depends(principal)) -> Any:
        return evidence.describe(actor, upload_id)

    @router.get("/upload-sessions/{upload_id}/parts/{number}", tags=["evidence"])
    def part_grant(upload_id: str, number: int, actor: Principal = Depends(principal)) -> Any:
        return evidence.part_grant(actor, upload_id, number)

    @router.post("/upload-sessions/{upload_id}/complete", status_code=202, tags=["evidence"])
    def complete_upload(
        upload_id: str,
        body: CompleteBody,
        request: Request,
        actor: Principal = Depends(principal),
        key: str = Depends(command_key),
    ) -> Any:
        return evidence.complete(actor, upload_id, body.model_dump(), key, request.state.request_id)

    @router.post("/upload-sessions/{upload_id}/abort", tags=["evidence"])
    def abort_upload(
        upload_id: str, request: Request, actor: Principal = Depends(principal)
    ) -> Any:
        return evidence.abort(actor, upload_id, request.state.request_id)

    @router.get("/evidence/{evidence_id}", tags=["evidence"])
    def evidence_metadata(evidence_id: str, actor: Principal = Depends(principal)) -> Any:
        return delivery.metadata(actor, evidence_id)

    @router.get("/applications/{application_id}/evidence", tags=["evidence"])
    def evidence_history(
        application_id: str,
        after: str = "",
        limit: int = Query(default=50, ge=1, le=100),
        actor: Principal = Depends(principal),
    ) -> Any:
        return delivery.history(actor, application_id, after, limit)

    @router.get(
        "/evidence/{evidence_id}/content", tags=["evidence"], operation_id="get_evidence_content"
    )
    @router.head(
        "/evidence/{evidence_id}/content", tags=["evidence"], operation_id="head_evidence_content"
    )
    def original(evidence_id: str, request: Request, actor: Principal = Depends(principal)) -> Any:
        stream, headers, status = delivery.prepare(
            actor,
            evidence_id,
            None,
            request.headers.get("range"),
            request.state.request_id,
            head_only=request.method == "HEAD",
        )
        return (
            Response(headers=headers, status_code=status)
            if request.method == "HEAD"
            else ClosingStream(stream, headers=headers, status_code=status)
        )

    @router.get("/evidence/{evidence_id}/pages/{page}", tags=["evidence"])
    def page_image(
        evidence_id: str, page: int, request: Request, actor: Principal = Depends(principal)
    ) -> Any:
        stream, headers, status = delivery.prepare(
            actor, evidence_id, page, request.headers.get("range"), request.state.request_id
        )
        return ClosingStream(stream, headers=headers, status_code=status)

    @router.get("/applications/{application_id}/audit-events", tags=["history"])
    def audit_history(
        application_id: str,
        after: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=100),
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as connection:
            store.application(connection, application_id)
            return [
                row(item)
                for item in connection.execute(
                    select(t.audit)
                    .where(t.audit.c.application_id == application_id, t.audit.c.sequence > after)
                    .order_by(t.audit.c.sequence)
                    .limit(limit)
                )
            ]

    @router.get("/evidence/{evidence_id}/access-events", tags=["history"])
    def access_history(
        evidence_id: str,
        after: str = "",
        limit: int = Query(default=50, ge=1, le=100),
        actor: Principal = Depends(principal),
    ) -> Any:
        delivery.metadata(actor, evidence_id)
        with store.transaction(actor) as connection:
            return [
                row(item)
                for item in connection.execute(
                    select(t.access)
                    .where(t.access.c.evidence_id == evidence_id, t.access.c.id > after)
                    .order_by(t.access.c.id)
                    .limit(limit)
                )
            ]

    @router.get("/applications/{application_id}/tasks", tags=["history"])
    def pending_tasks(application_id: str, actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as connection:
            store.application(connection, application_id)
            return [
                row(item)
                for item in connection.execute(
                    select(t.tasks)
                    .where(t.tasks.c.application_id == application_id, t.tasks.c.state == "OPEN")
                    .limit(100)
                )
            ]

    @router.get("/operations/{operation_id}", tags=["operations"])
    def get_operation_status(operation_id: str, actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as connection:
            return OperationsService.get_operation(connection, operation_id)

    @router.get("/applications/{application_id}/operations", tags=["operations"])
    def list_application_operations(
        application_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as connection:
            store.application(connection, application_id)
            return OperationsService.list_operations(connection, application_id, limit)

    @router.post("/operations/{operation_id}/pause", tags=["operations"])
    def pause_op(operation_id: str, actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as connection:
            return OperationsService.pause_operation(connection, operation_id)

    @router.post("/operations/{operation_id}/resume", tags=["operations"])
    def resume_op(operation_id: str, actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as connection:
            return OperationsService.resume_operation(connection, operation_id)

    @router.post("/operations/{operation_id}/retry", tags=["operations"])
    def retry_op(operation_id: str, actor: Principal = Depends(principal)) -> Any:
        with store.transaction(actor) as connection:
            return OperationsService.retry_operation(connection, operation_id)

    @router.post("/operations/{operation_id}/cancel", tags=["operations"])
    def cancel_op(
        operation_id: str,
        reason: str | None = None,
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as connection:
            return OperationsService.cancel_operation(
                connection, operation_id, reason or "Cancelled by operator"
            )

    @router.get("/evidence/{version_id}/fields", tags=["extraction"])
    def get_evidence_fields_endpoint(
        version_id: str,
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as connection:
            ev = (
                connection.execute(select(t.evidence).where(t.evidence.c.id == version_id))
                .mappings()
                .first()
            )
            if not ev:
                raise NotFoundError("Evidence version")
            if ev["application_id"]:
                store.application(connection, ev["application_id"])
            return extraction_service.get_evidence_fields(
                ev["institution_id"], version_id, conn=connection
            )

    @router.post("/evidence/{version_id}/corrections", tags=["extraction"])
    def create_field_correction_endpoint(
        version_id: str,
        body: CorrectionBody,
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as connection:
            ev = (
                connection.execute(select(t.evidence).where(t.evidence.c.id == version_id))
                .mappings()
                .first()
            )
            if not ev:
                raise NotFoundError("Evidence version")
            if ev["application_id"]:
                store.application(connection, ev["application_id"])

            actor_id = (
                connection.execute(
                    select(t.actors.c.id).where(
                        t.actors.c.issuer == actor.issuer,
                        t.actors.c.subject == actor.subject,
                    )
                ).scalar()
                or actor.subject
            )

            return extraction_service.record_correction(
                institution_id=ev["institution_id"],
                evidence_version_id=version_id,
                field_id=body.field_id,
                corrected_value=body.corrected_value,
                reason=body.reason,
                corrected_by=str(actor_id),
                authority=body.authority,
                conn=connection,
            )

    @router.get("/fact-sets/{id}", tags=["extraction"])
    def get_fact_set_endpoint(
        id: str,
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as connection:
            fs = extraction_service.get_fact_set(id, conn=connection)
            if not fs:
                raise NotFoundError("Fact set")
            if fs.get("application_id"):
                store.application(connection, fs["application_id"])
            return fs

    @router.get("/claims/{id}/provenance", tags=["claims"])
    def get_claim_provenance_endpoint(
        id: str,
        actor: Principal = Depends(principal),
    ) -> Any:
        with store.transaction(actor) as connection:
            cl = connection.execute(select(t.claims).where(t.claims.c.id == id)).mappings().first()
            if not cl:
                raise NotFoundError("Claim")
            if cl.get("application_id"):
                store.application(connection, cl["application_id"])
            prov = claims_service.get_claim_provenance(cl["institution_id"], id, conn=connection)
            if not prov:
                raise NotFoundError("Claim provenance")
            return prov

    app.include_router(router)
    app.state.domain_store = store
    return store


class ClosingStream(StreamingResponse):
    def __init__(self, stream: Any, **kwargs: Any) -> None:
        self.source = stream
        super().__init__(stream, **kwargs)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                if hasattr(self.source, "close"):
                    await anyio.to_thread.run_sync(self.source.close)
