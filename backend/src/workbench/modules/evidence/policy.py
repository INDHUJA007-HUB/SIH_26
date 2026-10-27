"""Bounded type, filename, range and checksum policies without provider dependencies."""

import re
from pathlib import PurePath

from workbench.platform.errors import ApplicationError

ALLOWED_MEDIA = frozenset({"application/pdf", "image/png", "image/jpeg", "video/mp4"})


def safe_filename(value: str) -> str:
    name = PurePath(value.replace("\\", "/")).name
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:120] or "evidence"


def byte_range(header: str | None, size: int) -> tuple[int, int, int]:
    if not header:
        return 0, size - 1, 200
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if not match or not any(match.groups()):
        raise ApplicationError("INVALID_RANGE", "A single valid byte range is required", 416)
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix <= 0:
            raise ApplicationError("INVALID_RANGE", "The byte range is not satisfiable", 416)
        start, end = max(0, size - suffix), size - 1
    else:
        start, end = int(first), min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise ApplicationError("INVALID_RANGE", "The byte range is not satisfiable", 416)
    return start, end, 206
