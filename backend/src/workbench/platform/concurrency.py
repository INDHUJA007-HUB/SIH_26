"""Phase 5 backpressure, concurrency limits, and admission governance."""

from typing import Any

from sqlalchemy import func, select

from workbench.adapters import tables as t
from workbench.adapters.operations_service import ConcurrencyLimitExceededError
from workbench.platform.telemetry import log_event
from workbench.workflows.contracts import OperationStatus, OperationType, TaskQueue


class ConcurrencyGovernor:
    DEFAULT_MAX_INSTITUTION_INFLIGHT = 5
    DEFAULT_MAX_MEDIA_INFLIGHT = 1
    DEFAULT_MAX_PROVIDER_INFLIGHT = 2

    def __init__(
        self,
        max_institution_inflight: int = DEFAULT_MAX_INSTITUTION_INFLIGHT,
        max_media_inflight: int = DEFAULT_MAX_MEDIA_INFLIGHT,
        max_provider_inflight: int = DEFAULT_MAX_PROVIDER_INFLIGHT,
    ):
        self.max_institution_inflight = max_institution_inflight
        self.max_media_inflight = max_media_inflight
        self.max_provider_inflight = max_provider_inflight

    def check_admission(
        self,
        connection: Any,
        *,
        institution_id: str,
        operation_type: str,
        task_queue: str | None = None,
    ) -> None:
        """Enforce tenant concurrency limits and queue-specific admission."""
        active_statuses = [OperationStatus.PENDING.value, OperationStatus.RUNNING.value]

        # 1. Total institution in-flight check
        query = select(func.count(t.operations.c.id)).where(
            t.operations.c.institution_id == institution_id,
            t.operations.c.status.in_(active_statuses),
        )
        current_inflight = int(connection.execute(query).scalar_one() or 0)

        if current_inflight >= self.max_institution_inflight:
            log_event(
                "admission_rejected_concurrency",
                institution_id=institution_id,
                current_inflight=current_inflight,
                limit=self.max_institution_inflight,
                operation_type=operation_type,
            )
            msg = (
                f"Institution '{institution_id}' has reached maximum in-flight operations "
                f"({self.max_institution_inflight})"
            )
            raise ConcurrencyLimitExceededError(msg)

        # 2. Media isolation: strictly limit heavy media operations
        is_media = (
            operation_type == OperationType.MEDIA_ANALYSIS.value
            or task_queue == TaskQueue.MEDIA.value
        )
        if is_media:
            media_query = select(func.count(t.operations.c.id)).where(
                t.operations.c.institution_id == institution_id,
                t.operations.c.operation_type == OperationType.MEDIA_ANALYSIS.value,
                t.operations.c.status.in_(active_statuses),
            )
            media_inflight = int(connection.execute(media_query).scalar_one() or 0)
            if media_inflight >= self.max_media_inflight:
                log_event(
                    "admission_rejected_media_quota",
                    institution_id=institution_id,
                    media_inflight=media_inflight,
                    limit=self.max_media_inflight,
                )
                media_msg = (
                    f"Institution '{institution_id}' has reached maximum concurrent "
                    f"media operations ({self.max_media_inflight})"
                )
                raise ConcurrencyLimitExceededError(media_msg)
