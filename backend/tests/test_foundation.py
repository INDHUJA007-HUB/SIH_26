import json
from pathlib import Path

import pytest
from temporalio.testing import ActivityEnvironment

from workbench.platform.config import PROJECT_ROOT
from workbench.tools import bootstrap
from workbench.worker import foundation_ping


def test_bootstrap_is_repeatable_and_keeps_all_research_rules_disabled(tmp_path: Path):
    (tmp_path / "backend/fixtures").mkdir(parents=True)
    (tmp_path / "output").mkdir()
    for relative in (
        "backend/fixtures/foundation.json",
        "output/AICTE_PS26261_Rule_Evidence_Register.json",
    ):
        (tmp_path / relative).write_bytes((PROJECT_ROOT / relative).read_bytes())
    first = bootstrap(tmp_path)
    original_key = (tmp_path / ".local/fixture-private.pem").read_bytes()
    original_env = (tmp_path / ".env").read_bytes()
    second = bootstrap(tmp_path)
    assert first == second
    assert first["draft_rules"] == 22
    assert original_key == (tmp_path / ".local/fixture-private.pem").read_bytes()
    assert original_env == (tmp_path / ".env").read_bytes()
    rules = json.loads((tmp_path / ".local/rule-candidates.json").read_text())
    assert all(not rule["production_enabled"] for rule in rules["rules"])


@pytest.mark.anyio
async def test_workflow_activity_contract():
    environment = ActivityEnvironment()
    assert await environment.run(foundation_ping, "synthetic-fixture") == "SYNTHETIC_PLATFORM_OK"


@pytest.fixture
def anyio_backend():
    return "asyncio"
