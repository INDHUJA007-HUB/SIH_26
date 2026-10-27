"""Development API through secure Phase 4 intake; no regulatory decision endpoints."""

import re
import time
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any
from uuid import uuid4

import anyio
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from opentelemetry import propagate
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from workbench import __version__
from workbench.adapters.auth import JWTVerifier
from workbench.adapters.fixtures import FixtureDirectory
from workbench.api.body_limit import CommandBodyLimit
from workbench.contracts.foundation import Actor
from workbench.modules.institutions.application import FoundationInstitutionService
from workbench.platform.config import Settings, get_settings
from workbench.platform.database import build_engine
from workbench.platform.errors import AccessDenied, ApplicationError, AuthenticationRequired
from workbench.platform.telemetry import (
    build_tracing,
    configure_logging,
    log_event,
    request_id_context,
)

bearer = HTTPBearer(auto_error=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    configure_logging()
    provider = build_tracing(config)
    tracer = provider.get_tracer("workbench.api")
    directory = FixtureDirectory(config.fixture_store)
    verifier = JWTVerifier(config)
    service = FoundationInstitutionService(directory)
    request_counts: Counter[tuple[str, str]] = Counter()
    engine = (
        build_engine(config.database_url.get_secret_value(), provider)
        if (config.database_url.get_secret_value())
        else None
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if domain_store is not None:
            await anyio.to_thread.run_sync(domain_store.validate_roles)
        log_event("service_started", service=config.service_name)
        yield
        if domain_store is not None:
            domain_store.close()
        if engine is not None:
            engine.dispose()
        provider.shutdown()

    app = FastAPI(
        title="AICTE Evidence Workbench — Secure Intake"
        if config.domain_enabled
        else "AICTE Evidence Workbench — Foundation",
        version=__version__,
        lifespan=lifespan,
        description="Development evidence intake. No live verification or compliance decisions.",
    )
    app.state.settings = config
    app.add_middleware(CommandBodyLimit)
    app.state.tracer_provider = provider
    domain_store = None
    if config.domain_enabled:
        from workbench.api.intake import register_intake_api

        domain_store = register_intake_api(app, config)

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        candidate = request.headers.get("x-request-id", "")
        request_id = candidate if re.fullmatch(r"[a-zA-Z0-9-]{1,64}", candidate) else str(uuid4())
        token = request_id_context.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        context = propagate.extract(dict(request.headers))
        try:
            with tracer.start_as_current_span("http.request", context=context) as span:
                try:
                    response = await call_next(request)
                except Exception:
                    log_event("request_failed", error_code="INTERNAL_ERROR")
                    response = JSONResponse(
                        {
                            "code": "INTERNAL_ERROR",
                            "title": "An internal error occurred",
                            "status": 500,
                            "request_id": request_id,
                        },
                        status_code=500,
                    )
                route = getattr(request.scope.get("route"), "path", "unmatched")
                span.set_attribute("http.route", route)
                span.set_attribute("http.request.method", request.method)
                span.set_attribute("http.response.status_code", response.status_code)
                request_counts[(route, str(response.status_code))] += 1
                response.headers["x-request-id"] = request_id
                response.headers["cache-control"] = "no-store"
                response.headers["x-content-type-options"] = "nosniff"
                log_event(
                    "request_completed",
                    route=route,
                    method=request.method,
                    status=response.status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                return response
        finally:
            request_id_context.reset(token)

    @app.exception_handler(ApplicationError)
    async def application_error(request: Request, error: ApplicationError) -> JSONResponse:
        headers = dict(error.headers or {})
        if error.status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            {
                "type": f"urn:workbench:error:{error.code.lower()}",
                "title": error.title,
                "code": error.code,
                "status": error.status,
                "request_id": request.state.request_id,
            },
            status_code=error.status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {
                "code": "INVALID_REQUEST",
                "title": "Request validation failed",
                "status": 422,
                "request_id": request.state.request_id,
            },
            status_code=422,
        )

    async def authenticated_actor(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> Actor:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise AuthenticationRequired()
        subject = await anyio.to_thread.run_sync(verifier.subject, credentials.credentials)
        actor = directory.lookup_actor(subject)
        if actor is None:
            raise AccessDenied()
        if domain_store is not None:

            def verify_current_assignment() -> None:
                with domain_store.transaction(
                    verifier.principal(credentials.credentials)
                ) as connection:
                    current = domain_store.actor(connection)
                    if not any(
                        m["institution_id"] == actor.institution_id
                        and m["role"].startswith("institution_")
                        for m in current["memberships"]
                    ):
                        raise AccessDenied()

            await anyio.to_thread.run_sync(verify_current_assignment)
        return actor

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> JSONResponse:
        checks: dict[str, str] = {}
        if config.dependency_checks:

            def check_database() -> None:
                if engine is None:
                    raise RuntimeError("Database is not configured")
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))

            try:
                await anyio.to_thread.run_sync(check_database)
                checks["database"] = "ready"
            except Exception:
                checks["database"] = "unavailable"
        else:
            checks["profile"] = "native-foundation-no-dependency-checks"
        available = "unavailable" not in checks.values()
        return JSONResponse(
            {
                "status": "ready" if available else "not_ready",
                "checks": checks,
                "scope": "PHASE_4_INTAKE" if config.domain_enabled else "PHASE_1_FOUNDATION",
            },
            status_code=200 if available else 503,
        )

    @app.get("/version", tags=["health"])
    async def version() -> dict[str, str]:
        return {
            "version": __version__,
            "revision": config.build_revision,
            "release_scope": "PHASE_4_INTAKE" if config.domain_enabled else "PHASE_1_FOUNDATION",
        }

    @app.get("/api/v1/capabilities", tags=["foundation"])
    async def capabilities() -> dict[str, Any]:
        return {
            "release_scope": "PHASE_4_INTAKE" if config.domain_enabled else "PHASE_1_FOUNDATION",
            "synthetic_only": True,
            "authentication": config.auth_mode,
            "live_source_verification": False,
            "regulatory_rule_publication": False,
            "official_decisions": False,
            "fixture_endpoint": True,
            "persisted_authorization": config.domain_enabled,
            "immutable_submissions": config.domain_enabled,
            "quarantine_intake": config.domain_enabled,
        }

    @app.get("/api/v1/foundation/fixture", tags=["foundation"])
    async def own_fixture(actor: Actor = Depends(authenticated_actor)) -> dict[str, Any]:
        return {
            "institution": asdict(service.own_fixture(actor)),
            "mode": "SYNTHETIC_FOUNDATION_FIXTURE",
        }

    if config.expose_local_metrics:

        @app.get("/metrics", include_in_schema=False)
        async def metrics() -> PlainTextResponse:
            from workbench.platform.intake_metrics import render

            lines = ["# TYPE workbench_http_requests_total counter"]
            for (route, status), count in sorted(request_counts.items()):
                lines.append(
                    f'workbench_http_requests_total{{route="{route}",status="{status}"}} {count}'
                )
            return PlainTextResponse("\n".join(lines) + "\n" + render())

    return app
