"""Safe application errors; no raw exception or provider response is disclosed."""

from dataclasses import dataclass


@dataclass
class ApplicationError(Exception):
    code: str
    title: str
    status: int = 400
    headers: dict[str, str] | None = None


class AuthenticationRequired(ApplicationError):
    def __init__(self) -> None:
        super().__init__("AUTHENTICATION_REQUIRED", "A valid access token is required", 401)


class AccessDenied(ApplicationError):
    def __init__(self) -> None:
        super().__init__("ACCESS_DENIED", "Access is not permitted", 403)


class NotFoundError(ApplicationError):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__("NOT_FOUND", f"{resource} not found", 404)
