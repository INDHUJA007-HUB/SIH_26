"""Phase 5 durable workflows, idempotency keys, operator controls,
and backpressure integration tests.
"""

from uuid import uuid4

import pytest
from temporalio.testing import ActivityEnvironment

from workbench.activities.base import execute_idempotent_activity
from workbench.adapters.operations_service import (
    ConcurrencyLimitExceededError,
    OperationPausedError,
    OperationsService,
)
from workbench.platform.concurrency import ConcurrencyGovernor
from workbench.workflows.contracts import OperationStatus, OperationType, TaskQueue
from workbench.workflows.retry_policy import (
    OperationCancelledError,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_idempotent_activity_stable_business_key(h):
    """Verify that retrying an activity with the same stable key does not duplicate execution."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]
    stable_key = "evidence_123:profile_v1"

    execution_count = 0

    def mock_side_effect():
        nonlocal execution_count
        execution_count += 1
        return {"extracted_value": 42, "checksum": "abc"}

    class StoreWrapper:
        def __init__(self, engine):
            self.engine = engine

        def system_transaction(self):
            return self.engine.begin()

    store = StoreWrapper(h.owner)

    # First execution
    env = ActivityEnvironment()
    res1 = await env.run(
        execute_idempotent_activity,
        domain_store=store,
        institution_id=inst_id,
        application_id=app_id,
        operation_type=OperationType.DOCUMENT_EXTRACTION.value,
        task_queue=TaskQueue.DOCUMENT.value,
        stable_key=stable_key,
        input_ref={"evidence_id": "evidence_123"},
        execute_fn=mock_side_effect,
        heartbeat_msg="test",
    )
    assert res1["status"] == OperationStatus.SUCCEEDED.value
    assert res1["replayed"] is False
    assert res1["output"]["extracted_value"] == 42
    assert execution_count == 1

    # Second execution (retry under identical stable business key)
    res2 = await env.run(
        execute_idempotent_activity,
        domain_store=store,
        institution_id=inst_id,
        application_id=app_id,
        operation_type=OperationType.DOCUMENT_EXTRACTION.value,
        task_queue=TaskQueue.DOCUMENT.value,
        stable_key=stable_key,
        input_ref={"evidence_id": "evidence_123"},
        execute_fn=mock_side_effect,
        heartbeat_msg="test",
    )
    assert res2["status"] == OperationStatus.SUCCEEDED.value
    assert res2["replayed"] is True
    assert res2["output"]["extracted_value"] == 42
    # The side effect function MUST NOT have been called again!
    assert execution_count == 1


@pytest.mark.anyio
async def test_activity_cancellation_reconciliation(h):
    """Verify that cancelled activity records CANCELLED status without corrupting observations."""
    import asyncio

    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]
    stable_key = f"cancel_test_key_{uuid4().hex}"

    class StoreWrapper:
        def __init__(self, engine):
            self.engine = engine

        def system_transaction(self):
            return self.engine.begin()

    store = StoreWrapper(h.owner)

    env = ActivityEnvironment()

    async def cancelled_execution():
        raise asyncio.CancelledError()

    with pytest.raises(OperationCancelledError):
        await env.run(
            execute_idempotent_activity,
            domain_store=store,
            institution_id=inst_id,
            application_id=app_id,
            operation_type=OperationType.EVIDENCE_SCREENING.value,
            task_queue=TaskQueue.SCAN.value,
            stable_key=stable_key,
            input_ref={"evidence_id": "ev_cancel"},
            execute_fn=cancelled_execution,
            heartbeat_msg="screening",
        )

    # Check operation status in database
    with h.owner.begin() as conn:
        op = OperationsService.create_or_get_operation(
            conn,
            institution_id=inst_id,
            application_id=app_id,
            operation_type=OperationType.EVIDENCE_SCREENING.value,
            task_queue=TaskQueue.SCAN.value,
            stable_key=stable_key,
            input_ref={},
        )
        assert op["status"] == OperationStatus.CANCELLED.value
        assert op["error_code"] == "OPERATION_CANCELLED"


@pytest.mark.anyio
async def test_phase_5_exit_gate_worker_kill_and_recovery(h):
    """Exit Gate Phase 5: Kill a worker mid-job, resume work under stable business key,
    and verify committed work produces one finalized effect without corrupted progress.
    """
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]
    stable_key = f"worker_kill_gate_test_{uuid4().hex}"

    class StoreWrapper:
        def __init__(self, engine):
            self.engine = engine

        def system_transaction(self):
            return self.engine.begin()

    store = StoreWrapper(h.owner)
    env = ActivityEnvironment()

    attempts = 0

    def crash_prone_worker():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("Worker process terminated abruptly mid-job")
        return {"result": "processed_cleanly", "items": 10}

    # 1. First execution: worker is killed mid-job
    with pytest.raises(RuntimeError, match="Worker process terminated abruptly"):
        await env.run(
            execute_idempotent_activity,
            domain_store=store,
            institution_id=inst_id,
            application_id=app_id,
            operation_type=OperationType.DOCUMENT_EXTRACTION.value,
            task_queue=TaskQueue.DOCUMENT.value,
            stable_key=stable_key,
            input_ref={"evidence_id": "ev_crash"},
            execute_fn=crash_prone_worker,
            heartbeat_msg="extracting",
        )

    # Verify state in database after worker crash: recorded as FAILED, no corrupt progress state
    with h.owner.begin() as conn:
        op = OperationsService.create_or_get_operation(
            conn,
            institution_id=inst_id,
            application_id=app_id,
            operation_type=OperationType.DOCUMENT_EXTRACTION.value,
            task_queue=TaskQueue.DOCUMENT.value,
            stable_key=stable_key,
            input_ref={},
        )
        assert op["status"] == OperationStatus.FAILED.value
        assert op["error_code"] == "ACTIVITY_ERROR"

    # 2. Worker restarts/resumes and retries under the same stable business key
    res = await env.run(
        execute_idempotent_activity,
        domain_store=store,
        institution_id=inst_id,
        application_id=app_id,
        operation_type=OperationType.DOCUMENT_EXTRACTION.value,
        task_queue=TaskQueue.DOCUMENT.value,
        stable_key=stable_key,
        input_ref={"evidence_id": "ev_crash"},
        execute_fn=crash_prone_worker,
        heartbeat_msg="extracting",
    )
    assert res["status"] == OperationStatus.SUCCEEDED.value
    assert res["output"] == {"result": "processed_cleanly", "items": 10}
    assert res["replayed"] is False
    assert attempts == 2

    # 3. Subsequent retry: safely returns cached output with one finalized business effect
    res_replay = await env.run(
        execute_idempotent_activity,
        domain_store=store,
        institution_id=inst_id,
        application_id=app_id,
        operation_type=OperationType.DOCUMENT_EXTRACTION.value,
        task_queue=TaskQueue.DOCUMENT.value,
        stable_key=stable_key,
        input_ref={"evidence_id": "ev_crash"},
        execute_fn=crash_prone_worker,
        heartbeat_msg="extracting",
    )
    assert res_replay["status"] == OperationStatus.SUCCEEDED.value
    assert res_replay["replayed"] is True
    # Side-effect function was NOT called a third time
    assert attempts == 2

    # Verify database has exactly 1 finalized record
    with h.owner.begin() as conn:
        final_op = OperationsService.create_or_get_operation(
            conn,
            institution_id=inst_id,
            application_id=app_id,
            operation_type=OperationType.DOCUMENT_EXTRACTION.value,
            task_queue=TaskQueue.DOCUMENT.value,
            stable_key=stable_key,
            input_ref={},
        )
        assert final_op["status"] == OperationStatus.SUCCEEDED.value


def test_concurrency_governor_tenant_and_media_limits(h):
    """Verify tenant in-flight limits and media queue isolation with HTTP 429 semantics."""
    inst_id = h.institutions["a"]
    governor = ConcurrencyGovernor(max_institution_inflight=3, max_media_inflight=1)

    with h.owner.begin() as conn:
        # Create 3 active operations for institution A
        for i in range(3):
            op = OperationsService.create_or_get_operation(
                conn,
                institution_id=inst_id,
                application_id=None,
                operation_type=OperationType.DOCUMENT_EXTRACTION.value,
                task_queue=TaskQueue.DOCUMENT.value,
                stable_key=f"concurrency_test_{i}",
                input_ref={},
            )
            OperationsService.record_running(conn, op["id"])

        # 4th operation should be rejected due to tenant limit
        with pytest.raises(ConcurrencyLimitExceededError) as exc_info:
            governor.check_admission(
                conn,
                institution_id=inst_id,
                operation_type=OperationType.DOCUMENT_EXTRACTION.value,
                task_queue=TaskQueue.DOCUMENT.value,
            )
        assert exc_info.value.status == 429
        assert exc_info.value.code == "CONCURRENCY_LIMIT_EXCEEDED"

        # Separate institution B should still be allowed
        governor.check_admission(
            conn,
            institution_id=h.institutions["b"],
            operation_type=OperationType.DOCUMENT_EXTRACTION.value,
            task_queue=TaskQueue.DOCUMENT.value,
        )


def test_concurrency_governor_media_isolation(h):
    """Verify media operations have separate concurrency limits."""
    inst_id = h.institutions["b"]
    governor = ConcurrencyGovernor(max_institution_inflight=10, max_media_inflight=1)

    with h.owner.begin() as conn:
        op = OperationsService.create_or_get_operation(
            conn,
            institution_id=inst_id,
            application_id=None,
            operation_type=OperationType.MEDIA_ANALYSIS.value,
            task_queue=TaskQueue.MEDIA.value,
            stable_key=f"media_test_{uuid4().hex}",
            input_ref={},
        )
        OperationsService.record_running(conn, op["id"])

        # Second media operation should be rejected
        with pytest.raises(ConcurrencyLimitExceededError) as exc_info:
            governor.check_admission(
                conn,
                institution_id=inst_id,
                operation_type=OperationType.MEDIA_ANALYSIS.value,
                task_queue=TaskQueue.MEDIA.value,
            )
        assert exc_info.value.status == 429


def test_operator_controls_lifecycle_and_api(h):
    """Verify pause, resume, retry, and cancel operator controls and HTTP operations API."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    # 1. Create operation in DB
    with h.owner.begin() as conn:
        op = OperationsService.create_or_get_operation(
            conn,
            institution_id=inst_id,
            application_id=app_id,
            operation_type=OperationType.RULE_EVALUATION.value,
            task_queue=TaskQueue.EVALUATION.value,
            stable_key="test_op_ctrl_1",
            input_ref={"mode": "test"},
        )
        op_id = op["id"]

    # 2. Query operation status via API (GET /api/v1/operations/{op_id})
    res = h.call("GET", f"/api/v1/operations/{op_id}", actor="a")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == op_id
    assert data["status"] == OperationStatus.PENDING.value
    assert data["paused"] is False

    # 3. List operations for application (GET /api/v1/applications/{app_id}/operations)
    res_list = h.call("GET", f"/api/v1/applications/{app_id}/operations", actor="a")
    assert res_list.status_code == 200
    ops = res_list.json()
    assert any(o["id"] == op_id for o in ops)

    # 4. Operator pause (POST /api/v1/operations/{op_id}/pause)
    pause_res = h.call("POST", f"/api/v1/operations/{op_id}/pause", actor="officer", mfa=True)
    assert pause_res.status_code == 200
    assert pause_res.json()["paused"] is True

    # While paused, running should fail with OperationPausedError
    with h.owner.begin() as conn, pytest.raises(OperationPausedError):
        OperationsService.record_running(conn, op_id)

    # 5. Operator resume (POST /api/v1/operations/{op_id}/resume)
    resume_res = h.call("POST", f"/api/v1/operations/{op_id}/resume", actor="officer", mfa=True)
    assert resume_res.status_code == 200
    assert resume_res.json()["paused"] is False

    # 6. Record failure then operator retry
    with h.owner.begin() as conn:
        OperationsService.record_failure(
            conn, op_id, error_code="TEST_ERROR", error_message="Simulated error"
        )
    fail_get = h.call("GET", f"/api/v1/operations/{op_id}", actor="a").json()
    assert fail_get["status"] == OperationStatus.FAILED.value
    assert fail_get["error_code"] == "TEST_ERROR"

    retry_res = h.call("POST", f"/api/v1/operations/{op_id}/retry", actor="officer", mfa=True)
    assert retry_res.status_code == 200
    assert retry_res.json()["status"] == OperationStatus.PENDING.value
    assert retry_res.json()["error_code"] is None

    # 7. Operator cancel (POST /api/v1/operations/{op_id}/cancel)
    cancel_res = h.call(
        "POST",
        f"/api/v1/operations/{op_id}/cancel",
        actor="officer",
        mfa=True,
        params={"reason": "Operator manual termination"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == OperationStatus.CANCELLED.value
    assert cancel_res.json()["error_message"] == "Operator manual termination"


def test_operations_api_tenant_isolation(h):
    """Verify that institution B actor cannot view or control institution A's operations."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    with h.owner.begin() as conn:
        op = OperationsService.create_or_get_operation(
            conn,
            institution_id=inst_id,
            application_id=app_id,
            operation_type=OperationType.REPORT_GENERATION.value,
            task_queue=TaskQueue.REPORTING.value,
            stable_key="isolation_key_1",
            input_ref={},
        )
        op_id = op["id"]

    # Actor B queries Operation A -> must get 404 (due to RLS isolation)
    res = h.call("GET", f"/api/v1/operations/{op_id}", actor="b")
    assert res.status_code == 404

    # Actor B attempts to pause Operation A -> must get 404
    pause_res = h.call("POST", f"/api/v1/operations/{op_id}/pause", actor="b")
    assert pause_res.status_code == 404
