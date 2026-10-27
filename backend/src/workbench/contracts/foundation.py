"""Phase 1 typed ports; full case authorization is delivered in Phase 2."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Actor:
    subject: str
    institution_id: str
    role: str


@dataclass(frozen=True)
class Institution:
    id: str
    display_name: str
    synthetic: bool = True


class ActorDirectory(Protocol):
    def lookup_actor(self, subject: str) -> Actor | None: ...


class InstitutionReader(Protocol):
    def get_institution(self, institution_id: str) -> Institution | None: ...


class TokenVerifier(Protocol):
    def subject(self, token: str) -> str: ...
