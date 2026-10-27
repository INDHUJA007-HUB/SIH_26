"""Phase 5 & 6 document extraction activity contract and implementation."""

from __future__ import annotations

from typing import Any

from temporalio import activity

from workbench.activities.base import SimpleDomainStore, execute_idempotent_activity
from workbench.adapters.extraction_service import ExtractionService
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.workflows.contracts import ExtractionInput, OperationType, TaskQueue


@activity.defn(name="extract_facts_activity")
async def extract_facts_activity(input_dict: dict[str, Any]) -> dict[str, Any]:
    params = ExtractionInput(
        evidence_id=str(input_dict.get("evidence_id", "")),
        institution_id=str(input_dict.get("institution_id", "")),
        application_id=str(input_dict.get("application_id", "")),
        document_type=str(input_dict.get("document_type", "UNKNOWN_DOCUMENT_TYPE")),
        version_id=str(input_dict.get("version_id", "")),
        page_range=str(input_dict.get("page_range", "1-end")),
    )
    settings = Settings()
    engine = build_engine(settings.worker_database_url.get_secret_value())
    store = SimpleDomainStore(engine)
    service = ExtractionService(engine)

    def do_extraction() -> dict[str, Any]:
        content = input_dict.get("content_bytes")
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        elif isinstance(content, bytes):
            content_bytes = content
        else:
            content_bytes = b"%PDF-1.4\n%synthetic"

        synthetic_text = input_dict.get("synthetic_ocr_text")
        return service.run_pipeline(
            institution_id=params.institution_id,
            application_id=params.application_id,
            evidence_version_id=params.version_id or params.evidence_id,
            content_bytes=content_bytes,
            synthetic_ocr_text=synthetic_text,
        )

    try:
        return await execute_idempotent_activity(
            domain_store=store,
            institution_id=params.institution_id,
            application_id=params.application_id,
            operation_type=OperationType.DOCUMENT_EXTRACTION.value,
            task_queue=TaskQueue.DOCUMENT.value,
            stable_key=params.stable_key,
            input_ref=input_dict,
            execute_fn=do_extraction,
            heartbeat_msg="extraction",
        )
    finally:
        engine.dispose()
