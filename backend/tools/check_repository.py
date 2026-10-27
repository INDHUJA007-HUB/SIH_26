"""Validate Phase 0 contracts and immutable development image/action references."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
(ROOT / "artifacts").mkdir(exist_ok=True)
rules = json.loads((ROOT / "output/AICTE_PS26261_Rule_Evidence_Register.json").read_text())
assert len(rules["rules"]) == 22
assert all(rule["publication_state"] == "DRAFT" for rule in rules["rules"])
assert all(
    not rule["production_enabled"] and not rule["adverse_action_allowed"] for rule in rules["rules"]
)
assert len(list((ROOT / "docs/architecture/adr").glob("ADR-*.md"))) == 12
pack = json.loads((ROOT / "docs/policy/demo-rule-pack.json").read_text())
assert pack["production_enabled"] is False and pack["adverse_action_allowed"] is False
compose = yaml.safe_load((ROOT / "infra/compose/compose.yaml").read_text())
for name, service in compose["services"].items():
    if service.get("image", "").startswith("sih-workbench:"):
        continue
    assert re.search(r"@sha256:[0-9a-f]{64}$", service["image"]), name
    for port in service.get("ports", []):
        assert port.startswith("127.0.0.1:"), (name, port)
for path in (ROOT / ".github/workflows").glob("*.yml"):
    workflow = yaml.safe_load(path.read_text())
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if "uses" in step:
                assert re.search(r"@[0-9a-f]{40}$", step["uses"]), step["uses"]
print("Phase 0 contracts, draft seeds, image/action pins, loopback ports: PASS")
