"""Verify complete institution streams using the versioned PostgreSQL jsonb text format."""

import hashlib
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


def verify_stream(connection: Connection, stream: str) -> dict[str, Any]:
    previous, sequence = "0" * 64, 0
    for item in connection.execute(
        text(
            "SELECT sequence,previous_hash,sha256,event::jsonb::text AS body "
            "FROM audit_events WHERE stream=:stream ORDER BY sequence"
        ),
        {"stream": stream},
    ):
        sequence += 1
        expected = hashlib.sha256(
            f"{previous}|{stream}|{sequence}|{item.body}".encode()
        ).hexdigest()
        if item.sequence != sequence or item.previous_hash != previous or item.sha256 != expected:
            return {"valid": False, "events": sequence, "first_invalid_sequence": item.sequence}
        previous = item.sha256
    return {
        "valid": True,
        "events": sequence,
        "head_sha256": previous,
        "format": "postgres-jsonb-text-sha256-v1",
    }
