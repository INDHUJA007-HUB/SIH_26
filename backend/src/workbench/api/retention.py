"""Phase 15 Retention API endpoints: policies, legal holds, purge runs, and manifests."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request

from workbench.adapters.domain_store import DomainStore
from workbench.adapters.object_storage import ObjectStorage
from workbench.contracts.intake import Principal
from workbench.modules.retention.contracts import (
    LegalHoldCreate,
    LegalHoldRelease,
    LegalHoldResponse,
    PurgeManifestResponse,
    PurgeRunRequest,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
)
from workbench.modules.retention.service import RetentionService


def create_retention_router(
    store: DomainStore,
    principal: Any,
    storage: ObjectStorage | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/retention", tags=["retention"])
    service = RetentionService(store=store, storage=storage)

    @router.post("/policies", response_model=RetentionPolicyResponse)
    def create_policy_endpoint(
        body: RetentionPolicyCreate,
        request: Request,
        actor: Principal = Depends(principal),
    ) -> RetentionPolicyResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return service.create_policy(actor, body, request_id)

    @router.get("/policies", response_model=list[RetentionPolicyResponse])
    def list_policies_endpoint(
        actor: Principal = Depends(principal),
    ) -> list[RetentionPolicyResponse]:
        return service.list_policies(actor)

    @router.post("/legal-holds", response_model=LegalHoldResponse)
    def place_legal_hold_endpoint(
        body: LegalHoldCreate,
        request: Request,
        actor: Principal = Depends(principal),
    ) -> LegalHoldResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return service.place_legal_hold(actor, body, request_id)

    @router.get("/legal-holds", response_model=list[LegalHoldResponse])
    def list_legal_holds_endpoint(
        active_only: bool = Query(True),
        institution_id: str | None = Query(None),
        actor: Principal = Depends(principal),
    ) -> list[LegalHoldResponse]:
        return service.list_legal_holds(
            actor, active_only=active_only, institution_id=institution_id
        )

    @router.post("/legal-holds/{id}/release", response_model=LegalHoldResponse)
    def release_legal_hold_endpoint(
        id: str,
        body: LegalHoldRelease,
        request: Request,
        actor: Principal = Depends(principal),
    ) -> LegalHoldResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return service.release_legal_hold(actor, id, body, request_id)

    @router.post("/purge-runs", response_model=PurgeManifestResponse)
    def execute_purge_run_endpoint(
        body: PurgeRunRequest,
        request: Request,
        actor: Principal = Depends(principal),
    ) -> PurgeManifestResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return service.execute_purge(
            actor,
            policy_id=body.policy_id,
            dry_run=body.dry_run,
            max_items=body.max_items,
            request_id=request_id,
        )

    @router.get("/purge-manifests/{id}", response_model=PurgeManifestResponse)
    def get_purge_manifest_endpoint(
        id: str,
        actor: Principal = Depends(principal),
    ) -> PurgeManifestResponse:
        return service.get_purge_manifest(actor, id)

    return router
