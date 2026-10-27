import os

import pytest
from sqlalchemy import text

from workbench.platform.database import build_engine


@pytest.mark.integration
def test_seed_database_has_only_disabled_draft_rules():
    url = os.environ.get("WB_INTEGRATION_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL integration URL not supplied; not a successful integration claim")
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM foundation_institutions")) == 2
            assert connection.scalar(text("SELECT count(*) FROM seed_rule_candidates")) == 22
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM seed_rule_candidates "
                        "WHERE production_enabled OR adverse_action_allowed"
                    )
                )
                == 0
            )
    finally:
        engine.dispose()
