"""Rectification requests carry only what an institution can correct, in neutral words.

Forensic indicators, cross-application (consistency) indicators and issuer-verification results stay with
officials: the request endpoint refuses them, and the institution's view of any stored request shows a title
and a plain message only, never a rule or detector code.
"""

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RICH = "APP-2026-000107"
SPARE = "APP-2026-000108"
INSTITUTION_KEYS = {"finding_id", "title", "message", "document_type"}


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def app():
    from pramana.config import get_settings

    # Reuse the world when an earlier module already seeded this session's data directory
    if not (get_settings().data_dir / "pramana.db").exists():
        if not (ROOT / "fixtures" / "out" / "manifest.json").exists():
            _load("make_fixtures").main()
        _load("seed").main(validate=True)
    from pramana.db import init_db
    from pramana.main import app as fastapi_app

    init_db()
    return fastapi_app


def _login(app, user):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"username": user, "password": "Pramana@2026"})
    assert r.status_code == 200
    c.headers["x-csrf-token"] = r.json()["csrf_token"]
    return c


def _by_category(client, aid):
    out: dict[str, list[dict]] = {}
    for f in client.get(f"/api/applications/{aid}/findings").json():
        out.setdefault(f["category"], []).append(f)
    return out


def _institution_user(client, aid):
    inst_id = client.get(f"/api/applications/{aid}").json()["institution"]["id"]
    from pramana.db import SessionLocal
    from pramana.models import User

    with SessionLocal() as db:
        return next(u.username for u in db.query(User).filter(User.institution_id == inst_id))


def _unchanged(officer, aid, before_status, before_round, finding):
    detail = officer.get(f"/api/applications/{aid}").json()
    assert detail["status"] == before_status and detail["round"] == before_round
    now = next(f for f in officer.get(f"/api/applications/{aid}/findings").json() if f["id"] == finding["id"])
    assert now["review_status"] == finding["review_status"]


@pytest.mark.parametrize("category", ["forensic", "consistency", "verification"])
def test_findings_that_stay_with_officials_are_refused(app, category):
    officer = _login(app, "officer")
    groups = _by_category(officer, RICH)
    if category not in groups:
        pytest.skip(f"no {category} finding in {RICH}")
    held = groups[category][0]
    detail = officer.get(f"/api/applications/{RICH}").json()
    r = officer.post(f"/api/applications/{RICH}/rectification",
                     json={"finding_ids": [held["id"]], "message": "Please correct this"})
    assert r.status_code == 422, r.text
    assert "stay with officials" in r.json()["detail"]
    _unchanged(officer, RICH, detail["status"], detail["round"], held)


def test_a_mixed_selection_is_refused_as_a_whole(app):
    officer = _login(app, "officer")
    groups = _by_category(officer, RICH)
    eligible = [f for c in ("completeness", "compliance", "validity") for f in groups.get(c, [])]
    assert eligible and groups.get("forensic"), "the rich application has deficiencies and forensic indicators"
    detail = officer.get(f"/api/applications/{RICH}").json()
    r = officer.post(f"/api/applications/{RICH}/rectification",
                     json={"finding_ids": [eligible[0]["id"], groups["forensic"][0]["id"]]})
    assert r.status_code == 422
    # Nothing was half-applied: the eligible finding was not marked as asked about
    _unchanged(officer, RICH, detail["status"], detail["round"], eligible[0])


def test_a_message_that_judges_the_document_is_refused(app):
    officer = _login(app, "officer")
    groups = _by_category(officer, RICH)
    eligible = [f for c in ("completeness", "compliance", "validity") for f in groups.get(c, [])]
    r = officer.post(f"/api/applications/{RICH}/rectification",
                     json={"finding_ids": [eligible[0]["id"]], "message": "This certificate looks fake."})
    assert r.status_code == 400


def test_eligible_findings_reach_the_institution_without_codes(app):
    officer = _login(app, "officer")
    groups = _by_category(officer, RICH)
    eligible = [f for c in ("completeness", "compliance", "validity") for f in groups.get(c, [])][:3]
    r = officer.post(f"/api/applications/{RICH}/rectification",
                     json={"finding_ids": [f["id"] for f in eligible], "message": "Upload the corrected documents"})
    assert r.status_code == 200, r.text
    # Officials keep the rule codes on their side
    officer_items = officer.get(f"/api/applications/{RICH}").json()["rectifications"][0]["items"]
    assert {i["code"] for i in officer_items} == {f["code"] for f in eligible}

    inst = _login(app, _institution_user(officer, RICH))
    rects = inst.get(f"/api/applications/{RICH}").json()["rectifications"]
    items = rects[0]["items"]
    assert len(items) == len(eligible)
    for item in items:
        assert set(item) <= INSTITUTION_KEYS, item
        assert item["title"] and item["message"]
    seen = json.dumps(rects)
    for f in eligible:
        assert f["code"] not in seen
    for f in groups.get("forensic", []) + groups.get("consistency", []):
        assert f["title"] not in seen and f["code"] not in seen


def test_a_stored_forensic_item_is_reworded_for_the_institution(app):
    """Requests stored before the guard existed may hold an indicator's own words; the institution never reads them."""
    officer = _login(app, "officer")
    groups = _by_category(officer, SPARE)
    held = (groups.get("forensic") or groups.get("consistency") or [None])[0]
    if held is None:
        pytest.skip(f"no indicator in {SPARE}")
    from pramana.db import SessionLocal
    from pramana.models import RectificationRequest, User

    with SessionLocal() as db:
        officer_id = db.query(User).filter(User.username == "officer").one().id
        db.add(RectificationRequest(
            application_id=SPARE, round=1, message="Legacy request", created_by=officer_id,
            items=[{"finding_id": held["id"], "code": held["code"], "title": held["title"], "message": held["message"],
                    "document_type": None, "fact_paths": ["doc.x.y"]}],
            snapshot={"declared": {}, "documents": {}}))
        db.commit()

    officer_seen = json.dumps(officer.get(f"/api/applications/{SPARE}").json()["rectifications"])
    assert held["code"] in officer_seen

    inst = _login(app, _institution_user(officer, SPARE))
    rects = inst.get(f"/api/applications/{SPARE}").json()["rectifications"]
    item = next(i for r in rects for i in r["items"] if i["finding_id"] == held["id"])
    assert set(item) <= INSTITUTION_KEYS
    seen = json.dumps(rects)
    for leak in (held["code"], held["title"], held["message"], "doc.x.y", "fact_paths"):
        assert leak not in seen, leak
    assert "needs to be resubmitted" in item["title"] or item["title"] == "Declared value needs clarification"


def test_a_message_only_request_opens_a_round(app):
    officer = _login(app, "officer")
    before = officer.get(f"/api/applications/{SPARE}").json()
    assert officer.post(f"/api/applications/{SPARE}/rectification", json={"finding_ids": []}).status_code == 400
    r = officer.post(f"/api/applications/{SPARE}/rectification",
                     json={"finding_ids": [], "message": "Upload the building plan approved by the local authority."})
    assert r.status_code == 200, r.text
    after = officer.get(f"/api/applications/{SPARE}").json()
    assert after["status"] == "rectification_requested" and after["round"] == before["round"] + 1

