"""Local maintenance verification of a complete stream, never a partial scoped view."""

import argparse
import json

from workbench.adapters.audit_verifier import verify_stream
from workbench.platform.config import Settings
from workbench.platform.database import build_engine

parser = argparse.ArgumentParser()
parser.add_argument("stream", help="Institution UUID or SECURITY")
arguments = parser.parse_args()
settings = Settings()
if settings.environment not in {"local", "test"}:
    raise SystemExit("Use the approved maintenance identity in deployed environments")
engine = build_engine(settings.database_url.get_secret_value())
try:
    with engine.connect() as connection:
        result = verify_stream(connection, arguments.stream)
    print(json.dumps(result, indent=2))
    if not result["valid"]:
        raise SystemExit(1)
finally:
    engine.dispose()
