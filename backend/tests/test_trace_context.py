from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from workbench.api.app import create_app
from workbench.platform.telemetry import SafeSpanExporter


def test_incoming_trace_context_is_preserved_without_headers_or_query_content(settings):
    app = create_app(settings)
    sink = InMemorySpanExporter()
    app.state.tracer_provider.add_span_processor(SimpleSpanProcessor(SafeSpanExporter(sink)))
    trace_id = "1234567890abcdef1234567890abcdef"
    parent_id = "1234567890abcdef"
    with TestClient(app) as client:
        response = client.get(
            "/version?document=private-identifier",
            headers={
                "traceparent": f"00-{trace_id}-{parent_id}-01",
                "authorization": "Bearer private-token",
            },
        )
        assert response.status_code == 200
        spans = sink.get_finished_spans()
        span = next(item for item in spans if item.name == "http.request")
        assert f"{span.context.trace_id:032x}" == trace_id
        assert f"{span.parent.span_id:016x}" == parent_id
        assert span.attributes["http.route"] == "/version"
        assert "private-identifier" not in str(span.attributes)
        assert "private-token" not in str(span.attributes)
