"""Pure authorization decisions. Database grants/assignments remain authoritative."""

from datetime import UTC, datetime

from workbench.contracts.intake import Principal
from workbench.platform.errors import ApplicationError

ASSIGNABLE_ROLES = frozenset(
    {
        "institution_editor",
        "institution_viewer",
        "officer",
        "auditor",
        "rule_author",
        "rule_approver",
    }
)


def require_step_up(principal: Principal, max_age: int = 300) -> None:
    age = int(datetime.now(UTC).timestamp()) - principal.auth_time
    if not principal.mfa or age < -30 or age > max_age:
        raise ApplicationError(
            "STEP_UP_REQUIRED", "Recent multi-factor authentication is required", 403
        )


def require_distinct_people(first: str, second: str) -> None:
    if first == second:
        raise ApplicationError(
            "SEPARATION_OF_DUTIES", "A different authorized person must approve", 403
        )
