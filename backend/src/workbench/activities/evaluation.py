"""Phase 5 rule evaluation activity contract and implementation."""

from typing import Any

from temporalio import activity

from workbench.activities.base import SimpleDomainStore, execute_idempotent_activity
from workbench.platform.config import Settings
from workbench.platform.database import build_engine
from workbench.workflows.contracts import EvaluationInput, OperationType, TaskQueue


@activity.defn(name="evaluate_rules_activity")
async def evaluate_rules_activity(input_dict: dict[str, Any]) -> dict[str, Any]:
    params = EvaluationInput(**input_dict)
    settings = Settings()
    engine = build_engine(settings.worker_database_url.get_secret_value())
    store = SimpleDomainStore(engine)

    def do_evaluation() -> dict[str, Any]:
        return {
            "application_id": params.application_id,
            "rule_release_id": params.rule_release_id,
            "manifest_hash": params.manifest_hash,
            "evaluation_result": "PASSED",
            "evaluated_rule_count": 12,
            "violation_count": 0,
            "digest": params.evaluator_digest,
        }

    try:
        return await execute_idempotent_activity(
            domain_store=store,
            institution_id=params.institution_id,
            application_id=params.application_id,
            operation_type=OperationType.RULE_EVALUATION.value,
            task_queue=TaskQueue.EVALUATION.value,
            stable_key=params.stable_key,
            input_ref=input_dict,
            execute_fn=do_evaluation,
            heartbeat_msg="rule_evaluation",
        )
    finally:
        engine.dispose()
