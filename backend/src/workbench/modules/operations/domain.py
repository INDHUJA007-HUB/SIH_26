"""Domain logic and invariants for operations, incident containment, and reconciliation."""

from __future__ import annotations

from workbench.modules.operations.contracts import (
    ContainmentAction,
    ContainmentTargetType,
    HealthStatus,
    IncidentContainmentCommand,
)
from workbench.platform.errors import ApplicationError


def validate_containment_command(command: IncidentContainmentCommand) -> None:
    """Validate containment command invariants."""
    if not command.reason or len(command.reason.strip()) < 5:
        raise ApplicationError(
            code="INVALID_CONTAINMENT_REASON",
            title="A containment reason with at least 5 characters is mandatory",
            status=422,
        )

    # Valid combinations of target type and action
    valid_combos = {
        ContainmentTargetType.ACTOR: {ContainmentAction.REVOKE_SESSION},
        ContainmentTargetType.PROVIDER: {ContainmentAction.TRIP_CIRCUIT},
        ContainmentTargetType.WORKFLOW_JOB: {ContainmentAction.QUARANTINE_JOB},
    }

    allowed_actions = valid_combos.get(command.target_type, set())
    if command.containment_action not in allowed_actions:
        action = command.containment_action
        target = command.target_type
        raise ApplicationError(
            code="INVALID_CONTAINMENT_ACTION",
            title=f"Action '{action}' is not valid for target '{target}'",
            status=422,
        )


def evaluate_slo_health(
    api_availability: float,
    p95_latency_ms: float,
    queue_max_age_sec: float,
    extraction_failure_rate_pct: float,
) -> HealthStatus:
    """Aggregate health signals into a single status."""
    if (
        api_availability < 99.0
        or p95_latency_ms > 1000.0
        or queue_max_age_sec > 600.0
        or extraction_failure_rate_pct > 25.0
    ):
        return HealthStatus.CRITICAL
    if (
        api_availability < 99.9
        or p95_latency_ms > 300.0
        or queue_max_age_sec > 180.0
        or extraction_failure_rate_pct > 5.0
    ):
        return HealthStatus.DEGRADED
    return HealthStatus.HEALTHY


def assert_compliance_findings_unmutated(
    before_checksum: str,
    after_checksum: str,
) -> None:
    """Verify that an operational action has not mutated any compliance findings."""
    if before_checksum != after_checksum:
        raise ApplicationError(
            code="INVARIANT_VIOLATION_FINDINGS_MUTATED",
            title="Operational containment or maintenance must NEVER mutate compliance findings",
            status=500,
        )
