import json
import logging

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Status, StatusCode

from workbench.platform.telemetry import SafeJSONFormatter, SafeSpanExporter, safe_payload


def test_logs_drop_messages_exception_text_and_arbitrary_secret_fields():
    record = logging.LogRecord("workbench", logging.ERROR, "", 0, "secret-document-text", (), None)
    record.safe_fields = {"event": "safe", "authorization": "Bearer token", "raw_identifier": "123"}
    output = SafeJSONFormatter().format(record)
    assert json.loads(output)["event"] == "safe"
    assert "secret-document-text" not in output
    assert "Bearer" not in output
    assert "123" not in output
    assert safe_payload({"event": "ok", "document_content": "private"}) == {"event": "ok"}


def test_trace_export_removes_sql_and_exception_payload():
    sink = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(SafeSpanExporter(sink)))
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("SELECT private_identifier") as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.statement", "SELECT private_identifier FROM certificates")
        span.set_attribute("http.request.header.authorization", "Bearer secret")
        span.record_exception(ValueError("private-document-content"))
        span.set_status(Status(StatusCode.ERROR, "private-status-description"))
    result = sink.get_finished_spans()[0]
    assert result.name == "database.operation"
    assert result.attributes == {"db.system": "postgresql"}
    assert not result.events
    assert result.status.description is None
    provider.shutdown()
