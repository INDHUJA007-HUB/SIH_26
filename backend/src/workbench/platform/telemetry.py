"""Allowlist-only structured logging and content-free application tracing."""

import contextvars
import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status

from workbench.platform.config import Settings

request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
SAFE_FIELDS = frozenset(
    {
        "event",
        "request_id",
        "route",
        "method",
        "status",
        "duration_ms",
        "error_code",
        "workflow_id",
        "activity",
        "outcome",
        "service",
    }
)


def safe_payload(fields: dict[str, Any]) -> dict[str, Any]:
    """Discard unknown fields instead of trying to enumerate every possible secret."""
    return {key: value for key, value in fields.items() if key in SAFE_FIELDS}


class SafeJSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = safe_payload(getattr(record, "safe_fields", {}))
        fields.setdefault("request_id", request_id_context.get())
        fields.update(timestamp=datetime.now(UTC).isoformat(), level=record.levelname)
        # Deliberately omit record.msg, exception details, query strings, headers, and bodies.
        return json.dumps(fields, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJSONFormatter())
    logger = logging.getLogger("workbench")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_event(event: str, **fields: Any) -> None:
    logging.getLogger("workbench").info("", extra={"safe_fields": {"event": event, **fields}})


def build_tracing(settings: Settings) -> TracerProvider:
    provider = TracerProvider(resource=Resource({"service.name": settings.service_name}))
    if settings.telemetry_enabled:
        provider.add_span_processor(
            BatchSpanProcessor(
                SafeSpanExporter(OTLPSpanExporter(endpoint=settings.otlp_endpoint, timeout=3))
            )
        )
    return provider


class SafeSpanExporter(SpanExporter):
    """Remove SQL, exception messages, identifiers and unknown attributes before transport."""

    attributes = frozenset(
        {
            "http.route",
            "http.request.method",
            "http.response.status_code",
            "db.system",
            "db.system.name",
            "db.operation",
            "workflow.type",
            "activity.type",
        }
    )

    def __init__(self, delegate: SpanExporter) -> None:
        self.delegate = delegate

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        sanitized = []
        for span in spans:
            # Names can contain SQL from automatic instrumentation: normalize database spans.
            is_database = any(key.startswith("db.") for key in (span.attributes or {}))
            sanitized.append(
                ReadableSpan(
                    name="database.operation" if is_database else span.name,
                    context=span.context,
                    parent=span.parent,
                    resource=span.resource,
                    attributes={
                        key: value
                        for key, value in (span.attributes or {}).items()
                        if key in self.attributes
                    },
                    events=(),
                    links=(),
                    kind=span.kind,
                    status=Status(span.status.status_code),
                    start_time=span.start_time,
                    end_time=span.end_time,
                )
            )
        return self.delegate.export(sanitized)

    def shutdown(self) -> None:
        self.delegate.shutdown()


def current_trace_id() -> str:
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else ""
