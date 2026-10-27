"""Pure immutable manifest and declaration rules."""

import hashlib
import json
import math
import unicodedata
from typing import Any

from workbench.platform.errors import ApplicationError


def canonical(value: Any) -> str:
    def check(item: Any) -> None:
        if isinstance(item, float) and (not math.isfinite(item)):
            raise ApplicationError("INVALID_FACT", "Non-finite declarations are not supported", 422)
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ApplicationError("INVALID_FACT", "Declaration keys must be strings", 422)
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)

    check(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def portal_reference(value: str | None) -> str | None:
    return unicodedata.normalize("NFKC", value).strip().upper() if value else None


def require_draft(stage: str) -> None:
    if stage != "DRAFT":
        raise ApplicationError(
            "SUBMISSION_FROZEN", "Submitted evidence and declarations are frozen", 409
        )
