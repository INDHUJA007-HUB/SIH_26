"""Phase 5 Operations domain service for durable operation tracking,
stable business keys, and operator controls.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from workbench.adapters import tables as t
from workbench.platform.errors import ApplicationError
from workbench.workflows.contracts import OperationStatus


class OperationNotFoundError(ApplicationError):
    def __init__(self, operation_id: str):
        super().__init__(
            code="OPERATION_NOT_FOUND",
            title=f"Operation '{operation_id}' not found",
            status=404,
        )


class ConcurrencyLimitExceededError(ApplicationError):
    def __init__(self, message: str = "Institution concurrency limit exceeded"):
        super().__init__(
            code="CONCURRENCY_LIMIT_EXCEEDED",
            title=message,
            status=429,
        )


class OperationPausedError(ApplicationError):
    def __init__(self, operation_id: str):
        super().__init__(
            code="OPERATION_PAUSED",
            title=f"Operation '{operation_id}' is paused by operator",
            status=409,
        )


class OperationsService:
    @staticmethod
    def create_or_get_operation(
        connection: Any,
        *,
        institution_id: str,
        application_id: str | None,
        operation_type: str,
        task_queue: str,
        stable_key: str,
        input_ref: dict[str, Any],
        workflow_id: str | None = None,
    ) -> dict[str, Any]:
        """Idempotently register or fetch an operation using its stable business key."""
        query = select(t.operations).where(
            t.operations.c.institution_id == institution_id,
            t.operations.c.operation_type == operation_type,
            t.operations.c.stable_key == stable_key,
        )
        existing = connection.execute(query).mappings().first()
        if existing:
            return dict(existing)

        operation_id = str(uuid4())
        stmt = (
            pg_insert(t.operations)
            .values(
                id=operation_id,
                institution_id=institution_id,
                application_id=application_id,
                operation_type=operation_type,
                task_queue=task_queue,
                status=OperationStatus.PENDING.value,
                stable_key=stable_key,
                workflow_id=workflow_id,
                input_ref=input_ref,
                result=None,
                error_code=None,
                error_message=None,
                attempts=0,
                paused=False,
            )
            .on_conflict_do_nothing(
                index_elements=["institution_id", "operation_type", "stable_key"]
            )
        )
        connection.execute(stmt)
        record = connection.execute(query).mappings().first()
        return dict(record)

    @staticmethod
    def get_operation(connection: Any, operation_id: str) -> dict[str, Any]:
        query = select(t.operations).where(t.operations.c.id == operation_id)
        row = connection.execute(query).mappings().first()
        if not row:
            raise OperationNotFoundError(operation_id)
        return dict(row)

    @staticmethod
    def list_operations(
        connection: Any,
        application_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = (
            select(t.operations)
            .where(t.operations.c.application_id == application_id)
            .order_by(t.operations.c.created_at.desc())
            .limit(limit)
        )
        return [dict(r) for r in connection.execute(query).mappings().all()]

    @staticmethod
    def record_running(
        connection: Any,
        operation_id: str,
        workflow_id: str | None = None,
    ) -> dict[str, Any]:
        current = OperationsService.get_operation(connection, operation_id)
        if current.get("paused"):
            raise OperationPausedError(operation_id)

        values: dict[str, Any] = {
            "status": OperationStatus.RUNNING.value,
            "attempts": current["attempts"] + 1,
            "updated_at": datetime.now(UTC),
        }
        if workflow_id:
            values["workflow_id"] = workflow_id

        stmt = (
            update(t.operations)
            .where(t.operations.c.id == operation_id)
            .values(**values)
        )
        connection.execute(stmt)
        return OperationsService.get_operation(connection, operation_id)

    @staticmethod
    def record_success(
        connection: Any,
        operation_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        stmt = (
            update(t.operations)
            .where(t.operations.c.id == operation_id)
            .values(
                status=OperationStatus.SUCCEEDED.value,
                result=result,
                error_code=None,
                error_message=None,
                updated_at=datetime.now(UTC),
            )
        )
        connection.execute(stmt)
        return OperationsService.get_operation(connection, operation_id)

    @staticmethod
    def record_failure(
        connection: Any,
        operation_id: str,
        error_code: str,
        error_message: str,
        requires_operator: bool = False,
    ) -> dict[str, Any]:
        status = (
            OperationStatus.REQUIRES_OPERATOR.value
            if requires_operator
            else OperationStatus.FAILED.value
        )
        stmt = (
            update(t.operations)
            .where(t.operations.c.id == operation_id)
            .values(
                status=status,
                error_code=error_code,
                error_message=error_message,
                updated_at=datetime.now(UTC),
            )
        )
        connection.execute(stmt)
        return OperationsService.get_operation(connection, operation_id)

    @staticmethod
    def pause_operation(connection: Any, operation_id: str) -> dict[str, Any]:
        stmt = (
            update(t.operations)
            .where(t.operations.c.id == operation_id)
            .values(paused=True, updated_at=datetime.now(UTC))
        )
        connection.execute(stmt)
        return OperationsService.get_operation(connection, operation_id)

    @staticmethod
    def resume_operation(connection: Any, operation_id: str) -> dict[str, Any]:
        stmt = (
            update(t.operations)
            .where(t.operations.c.id == operation_id)
            .values(paused=False, updated_at=datetime.now(UTC))
        )
        connection.execute(stmt)
        return OperationsService.get_operation(connection, operation_id)

    @staticmethod
    def retry_operation(connection: Any, operation_id: str) -> dict[str, Any]:
        OperationsService.get_operation(connection, operation_id)
        stmt = (
            update(t.operations)
            .where(t.operations.c.id == operation_id)
            .values(
                status=OperationStatus.PENDING.value,
                paused=False,
                error_code=None,
                error_message=None,
                updated_at=datetime.now(UTC),
            )
        )
        connection.execute(stmt)
        return OperationsService.get_operation(connection, operation_id)

    @staticmethod
    def cancel_operation(
        connection: Any,
        operation_id: str,
        reason: str = "Cancelled by operator",
    ) -> dict[str, Any]:
        stmt = (
            update(t.operations)
            .where(t.operations.c.id == operation_id)
            .values(
                status=OperationStatus.CANCELLED.value,
                error_code="OPERATION_CANCELLED",
                error_message=reason,
                updated_at=datetime.now(UTC),
            )
        )
        connection.execute(stmt)
        return OperationsService.get_operation(connection, operation_id)

    @staticmethod
    def record_cancellation(
        connection: Any,
        operation_id: str,
        reason: str = "Temporal activity cancelled",
    ) -> dict[str, Any]:
        return OperationsService.cancel_operation(connection, operation_id, reason)

    @staticmethod
    def get_inflight_count_for_institution(connection: Any, institution_id: str) -> int:
        active_statuses = [OperationStatus.PENDING.value, OperationStatus.RUNNING.value]
        query = select(func.count(t.operations.c.id)).where(
            t.operations.c.institution_id == institution_id,
            t.operations.c.status.in_(active_statuses),
        )
        return int(connection.execute(query).scalar_one() or 0)
