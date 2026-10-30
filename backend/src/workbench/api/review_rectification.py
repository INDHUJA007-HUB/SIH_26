"""API endpoints for Phase 9 officer review, reports, response windows, and rectification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import Connection, select, text

from workbench.adapters import tables as t
from workbench.adapters.domain_store import DomainStore
from workbench.adapters.rectification_application_service import RectificationService
from workbench.adapters.reporting_application_service import ReportService
from workbench.adapters.review_application_service import ReviewService
from workbench.contracts.intake import Principal
from workbench.platform.errors import ApplicationError


def _is_officer(conn: Connection) -> bool:
    return bool(
        conn.scalar(
            text("SELECT wb.elevated() AND (wb.has_role('officer') OR wb.has_role('supervisor'))")
        )
    )


def _require_officer(conn: Connection) -> None:
    if not _is_officer(conn):
        raise ApplicationError("ACCESS_DENIED", "Officer with fresh MFA required", 403)


def _check_institution_access(
    conn: Connection,
    institution_id: str,
    write: bool = False,
) -> None:
    allowed = conn.scalar(
        text("SELECT wb.can_access(:id, NULL, :write) OR wb.manages(:id)"),
        {"id": institution_id, "write": write},
    )
    if allowed:
        return
    is_supervisor = conn.scalar(text("SELECT wb.elevated() AND wb.has_role('supervisor')"))
    if not is_supervisor:
        raise ApplicationError("ACCESS_DENIED", "Access to institution is denied", 403)


class RecordDispositionBody(BaseModel):
    institution_id: str
    application_id: str
    finding_id: str
    evaluation_run_id: str
    disposition: str  # CONFIRMED, OVERRIDDEN, RECTIFICATION_REQUESTED, EXEMPTED, NOTED
    rationale: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpenWindowBody(BaseModel):
    institution_id: str
    application_id: str
    authority_reference: str
    allowed_slots: list[str] = Field(default_factory=list)
    allowed_fields: list[str] = Field(default_factory=list)
    deadline: str
    max_rounds: int = 2


class SubmitResponseBody(BaseModel):
    institution_id: str
    application_id: str
    window_id: str
    evidence_replacements: dict[str, str] | None = None
    field_updates: dict[str, Any] | None = None


class GenerateReportBody(BaseModel):
    institution_id: str
    application_id: str
    evaluation_run_id: str
    audience: str  # OFFICER or APPLICANT
    version: int = 1


class ReassessBody(BaseModel):
    institution_id: str
    application_id: str
    response_id: str
    baseline_run_id: str
    reassessed_findings: list[dict[str, Any]] = Field(default_factory=list)
    new_run_id: str | None = None


def create_phase_9_router(
    store: DomainStore,
    principal_dep: Any,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["review_rectification"])
    review_svc = ReviewService(store.engine)
    report_svc = ReportService(store.engine)
    rect_svc = RectificationService(store.engine)

    # 1. Review Dispositions
    @router.post("/review/dispositions")
    def record_disposition_endpoint(
        body: RecordDispositionBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            act = store.actor(conn)
            is_elevated = actor.mfa and any(
                m["role"] in {"officer", "supervisor"} for m in act.get("memberships", [])
            )
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED",
                    "Officer or supervisor with fresh MFA required to record dispositions",
                    403,
                )

            return review_svc.record_disposition(
                institution_id=body.institution_id,
                application_id=body.application_id,
                finding_id=body.finding_id,
                evaluation_run_id=body.evaluation_run_id,
                officer_id=str(act["id"]),
                disposition=body.disposition,
                rationale=body.rationale,
                metadata=body.metadata,
                conn=conn,
            )

    @router.get("/review/dispositions")
    def list_dispositions_endpoint(
        institution_id: str,
        application_id: str | None = None,
        finding_id: str | None = None,
        evaluation_run_id: str | None = None,
        actor: Principal = Depends(principal_dep),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, institution_id, write=False)
            return review_svc.list_dispositions(
                institution_id=institution_id,
                application_id=application_id,
                finding_id=finding_id,
                evaluation_run_id=evaluation_run_id,
                conn=conn,
            )

    # 2. Review Tasks & Pending Summary Read Models
    @router.get("/review/tasks")
    def list_tasks_endpoint(
        institution_id: str,
        application_id: str | None = None,
        waiting_on: str | None = None,
        status: str | None = None,
        actor: Principal = Depends(principal_dep),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, institution_id, write=False)
            return review_svc.list_tasks(
                institution_id=institution_id,
                application_id=application_id,
                waiting_on=waiting_on,
                status=status,
                conn=conn,
            )

    @router.get("/review/pending-summary")
    def pending_summary_endpoint(
        institution_id: str,
        application_id: str | None = None,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, institution_id, write=False)
            return review_svc.get_pending_action_summary(
                institution_id=institution_id,
                application_id=application_id,
                conn=conn,
            )

    # 3. Reports
    @router.post("/reports/generate")
    def generate_report_endpoint(
        body: GenerateReportBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            if body.audience == "OFFICER":
                _require_officer(conn)
            return report_svc.generate_report(
                institution_id=body.institution_id,
                application_id=body.application_id,
                evaluation_run_id=body.evaluation_run_id,
                audience=body.audience,
                version=body.version,
                conn=conn,
            )

    @router.get("/reports/{report_id}")
    def get_report_endpoint(
        report_id: str,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            report = report_svc.get_report(report_id, conn=conn)
            _check_institution_access(conn, report["institution_id"], write=False)
            if report["audience"] == "OFFICER":
                _require_officer(conn)
            return report

    @router.get("/reports/{report_id}/pdf")
    def get_report_pdf_endpoint(
        report_id: str,
        actor: Principal = Depends(principal_dep),
    ) -> Response:
        import hashlib
        from uuid import uuid4

        from workbench.modules.reporting.pdf import render_report_pdf

        with store.transaction(actor) as conn:
            report = report_svc.get_report(report_id, conn=conn)
            _check_institution_access(conn, report["institution_id"])
            if report["audience"] == "OFFICER":
                _require_officer(conn)
            content = render_report_pdf(report)
            store.audit(
                conn,
                report["institution_id"],
                report["application_id"],
                "ReportPDFServed",
                {"report_id": report_id, "sha256": hashlib.sha256(content).hexdigest()},
                str(uuid4()),
            )
            return Response(
                content=content,
                media_type="application/pdf",
                headers={
                    "Cache-Control": "private, no-store",
                    "X-Content-Type-Options": "nosniff",
                    "ETag": '"' + hashlib.sha256(content).hexdigest() + '"',
                },
            )

    @router.get("/reports")
    def list_reports_endpoint(
        institution_id: str,
        application_id: str | None = None,
        audience: str | None = None,
        actor: Principal = Depends(principal_dep),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, institution_id, write=False)
            if not _is_officer(conn):
                if audience == "OFFICER":
                    _require_officer(conn)
                audience = "APPLICANT"
            return report_svc.list_reports(
                institution_id=institution_id,
                application_id=application_id,
                audience=audience,
                conn=conn,
            )

    # 4. Response Windows (Rectification)
    @router.post("/rectification/windows")
    def open_window_endpoint(
        body: OpenWindowBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            act = store.actor(conn)
            is_elevated = actor.mfa and any(
                m["role"] in {"officer", "supervisor"} for m in act.get("memberships", [])
            )
            if not is_elevated:
                raise ApplicationError(
                    "ACCESS_DENIED",
                    "Officer or supervisor with fresh MFA required to open response window",
                    403,
                )

            deadline_dt = datetime.fromisoformat(body.deadline)
            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(tzinfo=UTC)

            result = rect_svc.open_response_window(
                institution_id=body.institution_id,
                application_id=body.application_id,
                opened_by=str(act["id"]),
                authority_reference=body.authority_reference,
                allowed_slots=body.allowed_slots,
                allowed_fields=body.allowed_fields,
                deadline=deadline_dt,
                max_rounds=body.max_rounds,
                conn=conn,
            )
            store.audit(
                conn,
                body.institution_id,
                body.application_id,
                "ResponseWindowOpened",
                {"window_id": result["id"], "round": result["round_number"]},
                str(uuid4()),
            )
            return result

    @router.get("/rectification/windows")
    def list_windows_endpoint(
        institution_id: str,
        application_id: str | None = None,
        actor: Principal = Depends(principal_dep),
    ) -> list[dict[str, Any]]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, institution_id, write=False)
            return rect_svc.list_windows(
                institution_id=institution_id,
                application_id=application_id,
                conn=conn,
            )

    # 5. Rectification Response Submission
    @router.post("/rectification/responses")
    def submit_response_endpoint(
        body: SubmitResponseBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            act = store.actor(conn)
            result = rect_svc.submit_rectification_response(
                institution_id=body.institution_id,
                application_id=body.application_id,
                window_id=body.window_id,
                submitted_by=str(act["id"]),
                evidence_replacements=body.evidence_replacements,
                field_updates=body.field_updates,
                conn=conn,
            )
            store.audit(
                conn,
                body.institution_id,
                body.application_id,
                "RectificationResponseSubmitted",
                {"response_id": result["id"], "revision": result["application_revision"]},
                str(uuid4()),
            )
            return result

    # 6. Reassessment & Finding Diff
    @router.post("/rectification/reassess")
    def reassess_endpoint(
        body: ReassessBody,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            _check_institution_access(conn, body.institution_id, write=True)
            _require_officer(conn)
            if body.reassessed_findings:
                raise ApplicationError(
                    "CLIENT_RESULTS_FORBIDDEN", "Reassessment reads finalized stored runs", 422
                )
            if not body.new_run_id:
                response = (
                    conn.execute(
                        select(t.rectification_responses).where(
                            t.rectification_responses.c.id == body.response_id,
                            t.rectification_responses.c.application_id == body.application_id,
                            t.rectification_responses.c.institution_id == body.institution_id,
                        )
                    )
                    .mappings()
                    .first()
                )
                if response is None:
                    raise ApplicationError("NOT_FOUND", "Response not found", 404)
                body.new_run_id = response["reassessment_run_id"]
                if not body.new_run_id:
                    return {"response_id": body.response_id, "status": "QUEUED"}
            return rect_svc.reassess_and_diff(
                institution_id=body.institution_id,
                application_id=body.application_id,
                response_id=body.response_id,
                baseline_run_id=body.baseline_run_id,
                reassessed_findings=body.reassessed_findings,
                new_run_id=body.new_run_id,
                conn=conn,
            )

    @router.get("/rectification/diffs/{diff_id}")
    def get_diff_endpoint(
        diff_id: str,
        actor: Principal = Depends(principal_dep),
    ) -> dict[str, Any]:
        with store.transaction(actor) as conn:
            diff = rect_svc.get_diff(diff_id, conn=conn)
            _check_institution_access(conn, diff["institution_id"], write=False)
            return diff

    return router
