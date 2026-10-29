"""Phase 15 Operations API: health, containment, reconciliation, drift, sweeps."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from workbench.adapters.domain_store import DomainStore
from workbench.contracts.intake import Principal
from workbench.modules.operations.contracts import (
    AccessReviewSummary,
    AccessSweepResult,
    DriftEvaluationResult,
    IncidentContainmentCommand,
    IncidentContainmentRecord,
    OperationalHealthSummary,
    ReconciliationCommand,
    ReconciliationSummary,
    ReleaseContainmentCommand,
)
from workbench.modules.operations.drift import evaluate_champion_challenger
from workbench.modules.operations.service import OperationsService


class DriftAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_version: str = Field(min_length=3, max_length=100)
    champion_version: str = Field(
        default="aicte_ocr_extractor_v1.0.0", min_length=3, max_length=100
    )
    manifests_path: str | None = None


def create_operations_router(store: DomainStore, principal: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1/operations", tags=["operations"])
    service = OperationsService(store)

    @router.get("/health-summary", response_model=OperationalHealthSummary)
    def health_summary_endpoint(
        window_minutes: int = Query(default=60, ge=1, le=1440),
        actor: Principal = Depends(principal),
    ) -> OperationalHealthSummary:
        return service.get_health_summary(actor, window_minutes=window_minutes)

    @router.post("/containment", response_model=IncidentContainmentRecord)
    def contain_incident_endpoint(
        body: IncidentContainmentCommand,
        request: Request,
        actor: Principal = Depends(principal),
    ) -> IncidentContainmentRecord:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return service.contain_incident(actor, body, request_id)

    @router.get("/containment", response_model=list[IncidentContainmentRecord])
    def list_containments_endpoint(
        active_only: bool = Query(True),
        actor: Principal = Depends(principal),
    ) -> list[IncidentContainmentRecord]:
        return service.list_containments(actor, active_only=active_only)

    @router.post("/containment/{id}/release", response_model=IncidentContainmentRecord)
    def release_containment_endpoint(
        id: str,
        body: ReleaseContainmentCommand,
        request: Request,
        actor: Principal = Depends(principal),
    ) -> IncidentContainmentRecord:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return service.release_containment(actor, id, body, request_id)

    @router.post("/reconcile", response_model=ReconciliationSummary)
    def reconcile_operations_endpoint(
        body: ReconciliationCommand,
        request: Request,
        actor: Principal = Depends(principal),
    ) -> ReconciliationSummary:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return service.reconcile_operations(actor, body, request_id)

    @router.post("/drift-analysis", response_model=DriftEvaluationResult)
    def drift_analysis_endpoint(
        body: DriftAnalysisRequest,
        actor: Principal = Depends(principal),
    ) -> DriftEvaluationResult:
        mpath = Path(body.manifests_path) if body.manifests_path else None
        return evaluate_champion_challenger(
            candidate_version=body.candidate_version,
            champion_version=body.champion_version,
            manifests_path=mpath,
        )

    @router.post("/access-review/sweep", response_model=AccessSweepResult)
    def sweep_access_endpoint(
        request: Request,
        actor: Principal = Depends(principal),
    ) -> AccessSweepResult:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return service.sweep_expired_access(actor, request_id)

    @router.get("/access-review/summary", response_model=AccessReviewSummary)
    def access_review_summary_endpoint(
        actor: Principal = Depends(principal),
    ) -> AccessReviewSummary:
        return service.get_access_review_summary(actor)

    return router
