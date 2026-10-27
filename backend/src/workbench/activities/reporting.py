"""Phase 5 report generation activity contract and implementation."""

from typing import Any

from temporalio import activity

from workbench.activities.base import SimpleDomainStore, execute_idempotent_activity
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.workflows.contracts import OperationType, ReportInput, TaskQueue


@activity.defn(name="generate_report_activity")
async def generate_report_activity(input_dict: dict[str, Any]) -> dict[str, Any]:
    params = ReportInput(**input_dict)
    settings = Settings()
    engine = build_engine(settings.worker_database_url.get_secret_value())
    store = SimpleDomainStore(engine)

    def do_reporting() -> dict[str, Any]:
        return {
            "application_id": params.application_id,
            "run_id": params.run_id,
            "template_version": params.template_version,
            "audience_policy": params.audience_policy,
            "report_artifact_id": f"rpt_{params.run_id}_{params.audience_policy.lower()}",
            "generated_pages": 4,
            "status": "RENDERED",
        }

    try:
        return await execute_idempotent_activity(
            domain_store=store,
            institution_id=params.institution_id,
            application_id=params.application_id,
            operation_type=OperationType.REPORT_GENERATION.value,
            task_queue=TaskQueue.REPORTING.value,
            stable_key=params.stable_key,
            input_ref=input_dict,
            execute_fn=do_reporting,
            heartbeat_msg="report_generation",
        )
    finally:
        engine.dispose()
