"""Run the phase review suite on a dedicated local PostgreSQL database.

Set WB_REVIEW_DATABASE_URL to an owner URL whose database starts with phase_review_.
The database must already exist. Existing project configuration is not modified.
"""

import os
import secrets
import sys

import pytest
from sqlalchemy.engine import make_url

from workbench.platform.domain_bootstrap import ROLE_CONFIG


def main() -> int:
    source = make_url(os.environ["WB_REVIEW_DATABASE_URL"])
    if source.host not in {"127.0.0.1", "localhost"} or not (source.database or "").startswith(
        "phase_review_"
    ):
        raise ValueError("Use a dedicated local phase_review_ database")
    os.environ["WB_DATABASE_URL"] = source.render_as_string(hide_password=False)
    os.environ["WB_INTEGRATION_DATABASE_URL"] = os.environ["WB_DATABASE_URL"]
    os.environ["WB_ENVIRONMENT"] = "test"
    for label, (login, _) in ROLE_CONFIG.items():
        password = secrets.token_urlsafe(32)
        os.environ[f"{label}_DATABASE_PASSWORD"] = password
        os.environ[f"WB_{label}_DATABASE_URL"] = source.set(
            username=login, password=password
        ).render_as_string(hide_password=False)
    from workbench.platform.config import Settings
    from workbench.platform.migrate import main as migrate
    from workbench.tools import seed_database

    migrate()
    seed_database(Settings())
    return int(pytest.main(sys.argv[1:] or ["backend/tests", "-q", "--tb=short", "-rN"]))


if __name__ == "__main__":
    raise SystemExit(main())
