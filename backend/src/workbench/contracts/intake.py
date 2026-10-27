"""Identity and safe evidence results shared across module boundaries."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str
    session_id: str
    issued_at: int
    expires_at: int
    auth_time: int
    mfa: bool


class Storage(Protocol):
    def head(
        self, key: str, version: str | None = None, bucket: str | None = None
    ) -> dict[str, Any]: ...
    def read(
        self, key: str, version: str, bucket: str, start: int = 0, end: int | None = None
    ) -> Any: ...


@dataclass(frozen=True)
class FileInspection:
    media_type: str
    page_count: int
    derivatives: tuple[dict[str, Any], ...]
    metadata: dict[str, Any]
