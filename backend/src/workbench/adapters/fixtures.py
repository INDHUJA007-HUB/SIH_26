"""Explicit synthetic-only local actor/institution directory."""

import json
from pathlib import Path
from typing import Any

from workbench.contracts.foundation import Actor, Institution


class FixtureDirectory:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"actors": [], "institutions": []}
        data: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("synthetic") is not True:
            raise ValueError("Foundation fixtures must be explicitly synthetic")
        return data

    def lookup_actor(self, subject: str) -> Actor | None:
        for actor in self._read()["actors"]:
            if actor["subject"] == subject:
                return Actor(**actor)
        return None

    def get_institution(self, institution_id: str) -> Institution | None:
        for institution in self._read()["institutions"]:
            if institution["id"] == institution_id:
                return Institution(**institution)
        return None
