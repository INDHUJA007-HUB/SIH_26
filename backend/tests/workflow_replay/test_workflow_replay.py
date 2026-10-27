"""Phase 5 workflow determinism and history replay compatibility test suite."""

from datetime import timedelta
from typing import Any

import pytest
from temporalio import activity, workflow
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from workbench.workflows.contracts import TaskQueue
from workbench.workflows.evaluation import RuleEvaluationWorkflow
from workbench.workflows.extraction import DocumentExtractionWorkflow
from workbench.workflows.media import MediaAnalysisWorkflow
from workbench.workflows.reporting import ReportGenerationWorkflow
from workbench.workflows.retention import RetentionPurgeWorkflow
from workbench.workflows.screening import EvidenceScreeningWorkflow
from workbench.workflows.timers import ResponseWindowTimerWorkflow
from workbench.workflows.verification import SourceVerificationWorkflow


# Mock activity implementations for fast replay generation
@activity.defn(name="screen_evidence_activity")
async def mock_screen_evidence(input_dict: dict[str, Any]) -> dict[str, Any]:
    return {"status": "SUCCEEDED", "clean_key": "clean/test", "replayed": False}


@activity.defn(name="extract_facts_activity")
async def mock_extract_facts(input_dict: dict[str, Any]) -> dict[str, Any]:
    return {"status": "SUCCEEDED", "extracted_facts": {"page_count": 1}, "replayed": False}


@activity.defn(name="verify_source_records_activity")
async def mock_verify_source(input_dict: dict[str, Any]) -> dict[str, Any]:
    return {"status": "SUCCEEDED", "verified": True, "replayed": False}


@activity.defn(name="evaluate_rules_activity")
async def mock_evaluate_rules(input_dict: dict[str, Any]) -> dict[str, Any]:
    return {"status": "SUCCEEDED", "evaluation_result": "PASSED", "replayed": False}


@activity.defn(name="generate_report_activity")
async def mock_generate_report(input_dict: dict[str, Any]) -> dict[str, Any]:
    return {"status": "SUCCEEDED", "report_artifact_id": "rpt_test", "replayed": False}


@activity.defn(name="wait_response_window_activity")
async def mock_wait_timer(input_dict: dict[str, Any]) -> dict[str, Any]:
    return {"status": "SUCCEEDED", "window_id": "win_test", "replayed": False}


@activity.defn(name="purge_retention_records_activity")
async def mock_purge_retention(input_dict: dict[str, Any]) -> dict[str, Any]:
    return {"status": "SUCCEEDED", "purged_records": 0, "replayed": False}


@activity.defn(name="analyze_media_activity")
async def mock_analyze_media(input_dict: dict[str, Any]) -> dict[str, Any]:
    return {"status": "SUCCEEDED", "tampering_detected": False, "replayed": False}


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_evidence_screening_workflow_determinism_and_replay():
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=TaskQueue.SCAN.value,
            workflows=[EvidenceScreeningWorkflow],
            activities=[mock_screen_evidence],
        ),
    ):
        handle = await env.client.start_workflow(
            EvidenceScreeningWorkflow.run,
            {
                "evidence_id": "ev_001",
                "institution_id": "inst_001",
                "application_id": "app_001",
            },
            id="replay-screening-001",
            task_queue=TaskQueue.SCAN.value,
        )
        res = await handle.result()
        assert res["status"] == "SUCCEEDED"

        history = await handle.fetch_history()
        assert len(history.events) > 0

        # Replay history against workflow definition
        replayer = Replayer(workflows=[EvidenceScreeningWorkflow])
        await replayer.replay_workflow(history)


@pytest.mark.anyio
async def test_document_extraction_workflow_replay():
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=TaskQueue.DOCUMENT.value,
            workflows=[DocumentExtractionWorkflow],
            activities=[mock_extract_facts],
        ),
    ):
        handle = await env.client.start_workflow(
            DocumentExtractionWorkflow.run,
            {
                "evidence_id": "ev_002",
                "institution_id": "inst_001",
                "application_id": "app_001",
                "document_type": "ANNEXURE_A",
                "version_id": "v1",
            },
            id="replay-extraction-002",
            task_queue=TaskQueue.DOCUMENT.value,
        )
        res = await handle.result()
        assert res["status"] == "SUCCEEDED"

        history = await handle.fetch_history()
        replayer = Replayer(workflows=[DocumentExtractionWorkflow])
        await replayer.replay_workflow(history)


@pytest.mark.anyio
async def test_source_verification_workflow_replay():
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=TaskQueue.CONNECTOR.value,
            workflows=[SourceVerificationWorkflow],
            activities=[mock_verify_source],
        ),
    ):
        handle = await env.client.start_workflow(
            SourceVerificationWorkflow.run,
            {
                "claim_id": "claim_001",
                "evidence_id": "ev_001",
                "institution_id": "inst_001",
                "provider_id": "bank_mock",
                "request_fingerprint": "fp_001",
            },
            id="replay-verification-003",
            task_queue=TaskQueue.CONNECTOR.value,
        )
        res = await handle.result()
        assert res["status"] == "SUCCEEDED"

        history = await handle.fetch_history()
        replayer = Replayer(workflows=[SourceVerificationWorkflow])
        await replayer.replay_workflow(history)


@pytest.mark.anyio
async def test_rule_evaluation_workflow_replay():
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=TaskQueue.EVALUATION.value,
            workflows=[RuleEvaluationWorkflow],
            activities=[mock_evaluate_rules],
        ),
    ):
        handle = await env.client.start_workflow(
            RuleEvaluationWorkflow.run,
            {
                "application_id": "app_001",
                "institution_id": "inst_001",
                "manifest_hash": "hash_001",
                "evaluator_digest": "digest_001",
                "rule_release_id": "rel_001",
            },
            id="replay-evaluation-004",
            task_queue=TaskQueue.EVALUATION.value,
        )
        res = await handle.result()
        assert res["status"] == "SUCCEEDED"

        history = await handle.fetch_history()
        replayer = Replayer(workflows=[RuleEvaluationWorkflow])
        await replayer.replay_workflow(history)


@pytest.mark.anyio
async def test_report_generation_workflow_replay():
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=TaskQueue.REPORTING.value,
            workflows=[ReportGenerationWorkflow],
            activities=[mock_generate_report],
        ),
    ):
        handle = await env.client.start_workflow(
            ReportGenerationWorkflow.run,
            {
                "application_id": "app_001",
                "institution_id": "inst_001",
                "run_id": "run_001",
                "template_version": "v1",
                "audience_policy": "OFFICER",
            },
            id="replay-reporting-005",
            task_queue=TaskQueue.REPORTING.value,
        )
        res = await handle.result()
        assert res["status"] == "SUCCEEDED"

        history = await handle.fetch_history()
        replayer = Replayer(workflows=[ReportGenerationWorkflow])
        await replayer.replay_workflow(history)


@pytest.mark.anyio
async def test_media_analysis_workflow_replay():
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=TaskQueue.MEDIA.value,
            workflows=[MediaAnalysisWorkflow],
            activities=[mock_analyze_media],
        ),
    ):
        handle = await env.client.start_workflow(
            MediaAnalysisWorkflow.run,
            {
                "evidence_id": "ev_media_001",
                "institution_id": "inst_001",
                "application_id": "app_001",
                "video_role": "CAMPUS_WALKTHROUGH",
                "max_frames": 60,
            },
            id="replay-media-006",
            task_queue=TaskQueue.MEDIA.value,
        )
        res = await handle.result()
        assert res["status"] == "SUCCEEDED"

        history = await handle.fetch_history()
        replayer = Replayer(workflows=[MediaAnalysisWorkflow])
        await replayer.replay_workflow(history)


@pytest.mark.anyio
async def test_retention_purge_workflow_replay():
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=TaskQueue.RETENTION.value,
            workflows=[RetentionPurgeWorkflow],
            activities=[mock_purge_retention],
        ),
    ):
        handle = await env.client.start_workflow(
            RetentionPurgeWorkflow.run,
            {
                "manifest_id": "man_001",
                "policy_version": "ret_v1",
                "approved_by": "sec_officer_1",
            },
            id="replay-retention-007",
            task_queue=TaskQueue.RETENTION.value,
        )
        res = await handle.result()
        assert res["status"] == "SUCCEEDED"

        history = await handle.fetch_history()
        replayer = Replayer(workflows=[RetentionPurgeWorkflow])
        await replayer.replay_workflow(history)


@pytest.mark.anyio
async def test_response_window_timer_signals_and_replay():
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue=TaskQueue.COORDINATION.value,
            workflows=[ResponseWindowTimerWorkflow],
            activities=[mock_wait_timer],
        ),
    ):
        handle = await env.client.start_workflow(
            ResponseWindowTimerWorkflow.run,
            {
                "window_id": "win_123",
                "application_id": "app_001",
                "institution_id": "inst_001",
                "duration_seconds": 10,
            },
            id="replay-timer-008",
            task_queue=TaskQueue.COORDINATION.value,
        )

        # Signal extend then cancel
        await handle.signal(ResponseWindowTimerWorkflow.extend_timer, 5)
        await handle.signal(ResponseWindowTimerWorkflow.cancel_timer)

        res = await handle.result()
        assert res["status"] == "CANCELLED"

        history = await handle.fetch_history()
        replayer = Replayer(workflows=[ResponseWindowTimerWorkflow])
        await replayer.replay_workflow(history)


# Versioning & Patching test
@activity.defn(name="version_step_one")
async def mock_step_one() -> str:
    return "STEP_1_DONE"


@activity.defn(name="version_step_two")
async def mock_step_two() -> str:
    return "STEP_2_DONE"


@workflow.defn(name="VersionedSampleWorkflow")
class VersionedSampleWorkflowV1:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            "version_step_one",
            start_to_close_timeout=timedelta(seconds=10),
        )


@workflow.defn(name="VersionedSampleWorkflow")
class VersionedSampleWorkflowV2:
    @workflow.run
    async def run(self) -> str:
        if workflow.patched("v2-feature-patch"):
            return await workflow.execute_activity(
                "version_step_two",
                start_to_close_timeout=timedelta(seconds=10),
            )
        else:
            return await workflow.execute_activity(
                "version_step_one",
                start_to_close_timeout=timedelta(seconds=10),
            )


@pytest.mark.anyio
async def test_workflow_versioning_and_patching_compatibility():
    """Verify that older execution history replays cleanly against patched workflow definition."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Run workflow V1
        async with Worker(
            env.client,
            task_queue="version-queue",
            workflows=[VersionedSampleWorkflowV1],
            activities=[mock_step_one, mock_step_two],
        ):
            handle = await env.client.start_workflow(
                VersionedSampleWorkflowV1.run,
                id="versioning-v1-run",
                task_queue="version-queue",
            )
            res = await handle.result()
            assert res == "STEP_1_DONE"
            v1_history = await handle.fetch_history()

        # Replay V1 history against Patched Workflow V2
        replayer = Replayer(workflows=[VersionedSampleWorkflowV2])
        # Should succeed deterministically because workflow.patched('v2-feature-patch')
        # returns False for V1 history
        await replayer.replay_workflow(v1_history)

        # Run fresh workflow under Workflow V2
        async with Worker(
            env.client,
            task_queue="version-queue",
            workflows=[VersionedSampleWorkflowV2],
            activities=[mock_step_one, mock_step_two],
        ):
            handle_v2 = await env.client.start_workflow(
                VersionedSampleWorkflowV2.run,
                id="versioning-v2-run",
                task_queue="version-queue",
            )
            res_v2 = await handle_v2.result()
            assert res_v2 == "STEP_2_DONE"
            v2_history = await handle_v2.fetch_history()

        # Replay V2 history against Patched Workflow V2
        await replayer.replay_workflow(v2_history)
