"""Evidence screening durable workflow chaining Phase 6 document extraction."""

from __future__ import annotations

from typing import Any

from temporalio import workflow

from workbench.workflows.contracts import TaskQueue
from workbench.workflows.retry_policy import (
    DOCUMENT_RETRY_POLICY,
    SCAN_RETRY_POLICY,
    TIMEOUT_DOCUMENT,
    TIMEOUT_DOCUMENT_HEARTBEAT,
    TIMEOUT_SCAN,
    TIMEOUT_SCAN_HEARTBEAT,
)


@workflow.defn(name="EvidenceScreeningWorkflow")
class EvidenceScreeningWorkflow:
    def __init__(self) -> None:
        self._status = "INITIALIZED"

    @workflow.run
    async def run(self, input_dict: dict[str, Any]) -> dict[str, Any]:
        self._status = "RUNNING"
        screen_result = await workflow.execute_activity(
            "screen_evidence_activity",
            input_dict,
            task_queue=TaskQueue.SCAN.value,
            start_to_close_timeout=TIMEOUT_SCAN,
            heartbeat_timeout=TIMEOUT_SCAN_HEARTBEAT,
            retry_policy=SCAN_RETRY_POLICY,
        )

        final_result = dict(screen_result)

        # When screening succeeds and evidence is accepted, chain Phase 6 extraction
        screening_status = screen_result.get("status")
        if screening_status in ("CLEAN", "ACCEPTED", "SUCCEEDED", "PASS"):
            extraction_input = {
                "evidence_id": input_dict.get("evidence_id", ""),
                "version_id": input_dict.get("version_id") or screen_result.get("version_id", ""),
                "institution_id": input_dict.get("institution_id", ""),
                "application_id": input_dict.get("application_id", ""),
                "document_type": input_dict.get("document_type", "UNKNOWN_DOCUMENT_TYPE"),
                "content_bytes": input_dict.get("content_bytes"),
                "synthetic_ocr_text": input_dict.get("synthetic_ocr_text"),
            }
            extraction_res = await workflow.execute_activity(
                "extract_facts_activity",
                extraction_input,
                task_queue=TaskQueue.DOCUMENT.value,
                start_to_close_timeout=TIMEOUT_DOCUMENT,
                heartbeat_timeout=TIMEOUT_DOCUMENT_HEARTBEAT,
                retry_policy=DOCUMENT_RETRY_POLICY,
            )
            final_result["extraction"] = dict(extraction_res)

        self._status = "COMPLETED"
        return final_result

    @workflow.query
    def status(self) -> str:
        return self._status
