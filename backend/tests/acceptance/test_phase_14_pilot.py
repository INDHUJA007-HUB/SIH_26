"""Phase 14 Pilot onboarding and scope activation gates acceptance tests.

Validates:
1. Role & MFA enforcement: Applicant and officer rejected; supervisor requires MFA.
2. Capability gate: advisory_mode_only=False strictly rejected (auto-adverse forbidden).
3. Capability gate: live provider mode rejected without verified credentials.
4. Capability gate: outbound notifications rejected without verified production channel.
5. Successful pilot activation persists state, reflects in /capabilities, and enforces single active scope.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import select

from workbench.adapters import tables as t

DATABASE_URL = os.environ.get("WB_INTEGRATION_DATABASE_URL", "")

pytestmark = pytest.mark.integration


def test_pilot_scope_activation_role_and_mfa_enforcement(h):
    """Applicant and officer actors are denied; supervisor requires recent MFA elevation."""
    payload = {
        "cohort_id": "PILOT-2026-COHORT-A",
        "institution_ids": [h.institutions["a"]],
        "provider_mode": "SIMULATED",
        "outbound_notifications_enabled": False,
        "advisory_mode_only": True,
        "approval_officer_ids": [h.actors["officer"]],
    }

    # 1. Applicant cannot activate pilot scope -> 403
    resp_app = h.call("POST", "/api/v1/operations/pilot-scope", actor="a", json=payload)
    assert resp_app.status_code == 403, f"Expected 403 for applicant, got {resp_app.status_code}"
    assert "ACCESS_DENIED" in resp_app.text

    # 2. Officer cannot activate pilot scope -> 403
    resp_off = h.call(
        "POST", "/api/v1/operations/pilot-scope", actor="officer", mfa=True, json=payload
    )
    assert resp_off.status_code == 403, f"Expected 403 for officer, got {resp_off.status_code}"

    # 3. Supervisor WITHOUT MFA cannot activate pilot scope -> 403
    resp_sup_no_mfa = h.call(
        "POST", "/api/v1/operations/pilot-scope", actor="supervisor", mfa=False, json=payload
    )
    assert resp_sup_no_mfa.status_code == 403, (
        f"Expected 403 for supervisor without MFA, got {resp_sup_no_mfa.status_code}"
    )
    assert "MFA" in resp_sup_no_mfa.text or "ACCESS_DENIED" in resp_sup_no_mfa.text


def test_pilot_scope_capability_gates_block_prohibited_modes(h):
    """Capability gates block auto-adverse action, unverified live providers, and unverified outbound channels."""
    # 1. Gate 1: Non-advisory mode (auto-adverse action) is strictly prohibited -> 422
    payload_auto_adverse = {
        "cohort_id": "PILOT-2026-TEST",
        "institution_ids": [h.institutions["a"]],
        "provider_mode": "SIMULATED",
        "outbound_notifications_enabled": False,
        "advisory_mode_only": False,  # VIOLATION
        "approval_officer_ids": [h.actors["officer"]],
    }
    resp1 = h.call(
        "POST",
        "/api/v1/operations/pilot-scope",
        actor="supervisor",
        mfa=True,
        json=payload_auto_adverse,
    )
    assert resp1.status_code == 422, (
        f"Expected 422 for non-advisory mode, got {resp1.status_code}: {resp1.text}"
    )
    assert "CAPABILITY_GATE_VIOLATION" in resp1.text

    # 2. Gate 2: Live provider mode blocked without verified credentials -> 422
    payload_live_provider = {
        "cohort_id": "PILOT-2026-TEST",
        "institution_ids": [h.institutions["a"]],
        "provider_mode": "OFFICIAL_LIVE",  # VIOLATION
        "outbound_notifications_enabled": False,
        "advisory_mode_only": True,
        "approval_officer_ids": [h.actors["officer"]],
    }
    resp2 = h.call(
        "POST",
        "/api/v1/operations/pilot-scope",
        actor="supervisor",
        mfa=True,
        json=payload_live_provider,
    )
    assert resp2.status_code == 422, (
        f"Expected 422 for live provider mode, got {resp2.status_code}: {resp2.text}"
    )
    assert "CAPABILITY_GATE_VIOLATION" in resp2.text

    # 3. Gate 3: Outbound notifications blocked without verified channel -> 422
    payload_notifications = {
        "cohort_id": "PILOT-2026-TEST",
        "institution_ids": [h.institutions["a"]],
        "provider_mode": "SIMULATED",
        "outbound_notifications_enabled": True,  # VIOLATION
        "advisory_mode_only": True,
        "approval_officer_ids": [h.actors["officer"]],
    }
    resp3 = h.call(
        "POST",
        "/api/v1/operations/pilot-scope",
        actor="supervisor",
        mfa=True,
        json=payload_notifications,
    )
    assert resp3.status_code == 422, (
        f"Expected 422 for outbound notifications, got {resp3.status_code}: {resp3.text}"
    )
    assert "CAPABILITY_GATE_VIOLATION" in resp3.text


def test_pilot_scope_activation_and_capabilities_reflection(h):
    """Supervisor with MFA activates valid pilot scope; state reflects in /capabilities and replaces older scope."""
    cohort_1 = f"PILOT-2026-COHORT-{uuid4().hex[:6]}"
    cohort_2 = f"PILOT-2026-COHORT-{uuid4().hex[:6]}"

    payload_1 = {
        "cohort_id": cohort_1,
        "institution_ids": [h.institutions["a"], h.institutions["b"]],
        "provider_mode": "SIMULATED",
        "outbound_notifications_enabled": False,
        "advisory_mode_only": True,
        "approval_officer_ids": [h.actors["officer"]],
    }

    # 1. Activate Cohort 1
    resp1 = h.call(
        "POST", "/api/v1/operations/pilot-scope", actor="supervisor", mfa=True, json=payload_1
    )
    assert resp1.status_code == 200, resp1.text
    data1 = resp1.json()
    assert data1["cohort_id"] == cohort_1
    assert data1["is_active"] is True
    assert data1["advisory_mode_only"] is True

    # 2. Verify GET /api/v1/capabilities reflects active pilot scope
    caps1 = h.call("GET", "/api/v1/capabilities").json()
    assert caps1["pilot_scope_active"] is True
    assert caps1["active_cohort_id"] == cohort_1
    assert caps1["server_gate_enforced"] is True
    assert caps1["advisory_mode_only"] is True
    assert caps1["pilot_provider_mode"] == "SIMULATED"
    assert caps1["outbound_notifications_enabled"] is False

    # 3. Activate Cohort 2 -> Cohort 1 is automatically deactivated
    payload_2 = dict(payload_1)
    payload_2["cohort_id"] = cohort_2

    resp2 = h.call(
        "POST", "/api/v1/operations/pilot-scope", actor="supervisor", mfa=True, json=payload_2
    )
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["cohort_id"] == cohort_2
    assert data2["is_active"] is True

    # Check database: Cohort 1 row is now is_active=False
    with h.owner.begin() as conn:
        active_scopes = (
            conn.execute(select(t.pilot_scopes).where(t.pilot_scopes.c.is_active.is_(True)))
            .mappings()
            .all()
        )
        assert len(active_scopes) == 1, (
            f"Expected exactly 1 active scope, found {len(active_scopes)}"
        )
        assert active_scopes[0]["cohort_id"] == cohort_2

    # Capabilities now reflects Cohort 2
    caps2 = h.call("GET", "/api/v1/capabilities").json()
    assert caps2["pilot_scope_active"] is True
    assert caps2["active_cohort_id"] == cohort_2
