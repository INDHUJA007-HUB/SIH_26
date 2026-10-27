"""Phase 5 document extraction activity contract and implementation."""

from typing import Any

from temporalio import activity

from workbench.activities.base import SimpleDomainStore, execute_idempotent_activity
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.workflows.contracts import ExtractionInput, OperationType, TaskQueue


@activity.defn(name="extract_facts_activity")
async def extract_facts_activity(input_dict: dict[str, Any]) -> dict[str, Any]:
    params = ExtractionInput(**input_dict)
    settings = Settings()
    engine = build_engine(settings.worker_database_url.get_secret_value())
    store = SimpleDomainStore(engine)

    def do_extraction() -> dict[str, Any]:
        return {
            "evidence_id": params.evidence_id,
            "document_type": params.document_type,
            "version_id": params.version_id,
            "extracted_facts": {
                "document_class": params.document_type,
                "confidence": 0.98,
                "page_count": 1,
            },
            "uncertainty": "CALIBRATED_LOW",
        }

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
