"""Simulator providers and registry for Phase 8 authorized source verification.
Implements 8.1 simulator framework and 8.4 adapter contract with blocked access declaration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from workbench.modules.verification.contracts import (
    ProviderCapability,
    ProviderMode,
    SourceVerificationProvider,
    SourceVerificationStatus,
    VerificationRequest,
    VerificationResponse,
)


def compute_request_fingerprint(req: VerificationRequest, provider_code: str) -> str:
    payload = {
        "provider": provider_code,
        "inst": req.institution_id,
        "doc_type": req.document_type,
        "predicate": req.predicate,
        "declared": req.declared_value,
        "as_of": req.as_of_date,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class AICTEHistoricalSimulatorProvider(SourceVerificationProvider):
    """Simulates AICTE portal historical records verification (EoA, intake, deficiencies)."""

    def get_capability(self) -> ProviderCapability:
        return ProviderCapability(
            name="AICTE Portal Records Simulator",
            code="AICTE_HISTORICAL_SIMULATOR",
            mode=ProviderMode.SIMULATED,
            supported_doc_types=[
                "AICTE_APPROVAL_LETTER",
                "EOA_RECOMMENDATION",
                "DEFICIENCY_REPORT",
            ],
            supported_predicates=["approved_intake", "program_approval", "deficiencies_cleared"],
            live_coverage_available=False,
            blocked_reason=(
                "Live AICTE portal database connector requires institutional API gateway access."
            ),
        )

    def verify(self, request: VerificationRequest) -> VerificationResponse:
        fingerprint = compute_request_fingerprint(request, "AICTE_HISTORICAL_SIMULATOR")
        now_iso = datetime.now(UTC).isoformat()

        if request.force_fault == "OUTAGE":
            return VerificationResponse(
                status=SourceVerificationStatus.SOURCE_UNAVAILABLE,
                freshness_timestamp=now_iso,
                request_fingerprint=fingerprint,
                simulated=True,
                live_success=False,
                error_code="PROVIDER_OUTAGE",
                error_message="AICTE Portal service connection timed out after 3 retries",
                requires_manual_review=True,
            )

        if request.force_fault == "MISMATCH":
            return VerificationResponse(
                status=SourceVerificationStatus.MISMATCH_DETECTED,
                observed_value={"approved_intake": 120, "academic_cycle": 2025},
                discrepancy_details={
                    "declared": request.declared_value,
                    "authoritative": {"approved_intake": 120},
                    "difference": "Declared intake exceeds portal approved intake by 60 seats",
                },
                freshness_timestamp=now_iso,
                request_fingerprint=fingerprint,
                simulated=True,
                live_success=False,
            )

        # Default happy-path simulation
        return VerificationResponse(
            status=SourceVerificationStatus.VERIFIED,
            observed_value={
                "approved_intake": request.declared_value.get("intake", 180)
                if request.declared_value
                else 180,
                "cycle": 2026,
            },
            freshness_timestamp=now_iso,
            request_fingerprint=fingerprint,
            simulated=True,
            live_success=False,
        )


class FireSafetySimulatorProvider(SourceVerificationProvider):
    """Simulates Fire & Emergency Services NOC/Certificate verification."""

    def get_capability(self) -> ProviderCapability:
        return ProviderCapability(
            name="Fire & Emergency Services NOC Simulator",
            code="FIRE_SAFETY_SIMULATOR",
            mode=ProviderMode.SIMULATED,
            supported_doc_types=["FIRE_SAFETY_CERTIFICATE"],
            supported_predicates=["fire_noc_validity", "fire_safety_compliance"],
            live_coverage_available=False,
            blocked_reason="State Fire Directorate digital verification integration in progress.",
        )

    def verify(self, request: VerificationRequest) -> VerificationResponse:
        fingerprint = compute_request_fingerprint(request, "FIRE_SAFETY_SIMULATOR")
        now_iso = datetime.now(UTC).isoformat()

        if request.force_fault == "OUTAGE":
            return VerificationResponse(
                status=SourceVerificationStatus.SOURCE_UNAVAILABLE,
                freshness_timestamp=now_iso,
                request_fingerprint=fingerprint,
                simulated=True,
                live_success=False,
                error_code="STATE_FIRE_PORTAL_DOWN",
                error_message="State Fire Services portal returned HTTP 503 Service Unavailable",
                requires_manual_review=True,
            )

        if request.force_fault == "EXPIRED":
            return VerificationResponse(
                status=SourceVerificationStatus.EXPIRED,
                observed_value={"valid_until": "2024-12-31", "status": "EXPIRED"},
                discrepancy_details={
                    "review_date": request.as_of_date or "2026-10-26",
                    "valid_until": "2024-12-31",
                },
                freshness_timestamp=now_iso,
                request_fingerprint=fingerprint,
                simulated=True,
                live_success=False,
            )

        if request.force_fault == "MISMATCH":
            return VerificationResponse(
                status=SourceVerificationStatus.MISMATCH_DETECTED,
                observed_value={"building_name": "BLOCK_B", "floors_covered": 2},
                discrepancy_details={
                    "declared": request.declared_value,
                    "reason": "Certificate covers Block B only, application claims Campus Wide",
                },
                freshness_timestamp=now_iso,
                request_fingerprint=fingerprint,
                simulated=True,
                live_success=False,
            )

        return VerificationResponse(
            status=SourceVerificationStatus.VERIFIED,
            observed_value={
                "certificate_number": "FS-NOC-2026-9912",
                "valid_until": "2027-03-31",
                "status": "ACTIVE",
            },
            freshness_timestamp=now_iso,
            request_fingerprint=fingerprint,
            simulated=True,
            live_success=False,
        )


class LandRecordsSimulatorProvider(SourceVerificationProvider):
    """Simulates State Land Revenue Directorate verification."""

    def get_capability(self) -> ProviderCapability:
        return ProviderCapability(
            name="State Revenue Land Records Simulator",
            code="LAND_RECORDS_SIMULATOR",
            mode=ProviderMode.SIMULATED,
            supported_doc_types=["LAND_REGISTRATION_DEED"],
            supported_predicates=["land_area", "land_ownership_type"],
            live_coverage_available=False,
            blocked_reason="State Land Revenue Digital Records API awaiting government MOU.",
        )

    def verify(self, request: VerificationRequest) -> VerificationResponse:
        fingerprint = compute_request_fingerprint(request, "LAND_RECORDS_SIMULATOR")
        now_iso = datetime.now(UTC).isoformat()

        if request.force_fault == "OUTAGE":
            return VerificationResponse(
                status=SourceVerificationStatus.SOURCE_UNAVAILABLE,
                freshness_timestamp=now_iso,
                request_fingerprint=fingerprint,
                simulated=True,
                live_success=False,
                error_code="REVENUE_API_GATEWAY_TIMEOUT",
                error_message="Revenue department gateway unreachable",
                requires_manual_review=True,
            )

        return VerificationResponse(
            status=SourceVerificationStatus.VERIFIED,
            observed_value={
                "survey_number": "104/3",
                "land_area_acres": "6.5",
                "ownership": "OWNED",
            },
            freshness_timestamp=now_iso,
            request_fingerprint=fingerprint,
            simulated=True,
            live_success=False,
        )


class ProductionAuthorizedConnector(SourceVerificationProvider):
    """Subphase 8.4 Adapter contract and simulator for production authorized source connector.
    Delivers the full adapter contract and simulator while explicitly recording the real
    connector as BLOCKED by missing production access credentials and onboarding.
    """

    def get_capability(self) -> ProviderCapability:
        return ProviderCapability(
            name="AICTE National Portal Production Connector",
            code="AICTE_PRODUCTION_CONNECTOR",
            mode=ProviderMode.SIMULATED,
            supported_doc_types=[
                "AICTE_APPROVAL_LETTER",
                "EOA_RECOMMENDATION",
                "FIRE_SAFETY_CERTIFICATE",
                "LAND_REGISTRATION_DEED",
            ],
            supported_predicates=["approved_intake", "fire_noc_validity", "land_area"],
            live_coverage_available=False,
            blocked_reason=(
                "BLOCKED_BY_MISSING_ACCESS: Production API contract, writeback credentials, "
                "and production network gateway are not provisioned in this environment."
            ),
        )

    def verify(self, request: VerificationRequest) -> VerificationResponse:
        fingerprint = compute_request_fingerprint(request, "AICTE_PRODUCTION_CONNECTOR")
        now_iso = datetime.now(UTC).isoformat()

        # Invariant: Every simulated result must carry simulated=True and live_success=False
        if request.force_fault == "OUTAGE":
            return VerificationResponse(
                status=SourceVerificationStatus.SOURCE_UNAVAILABLE,
                freshness_timestamp=now_iso,
                request_fingerprint=fingerprint,
                simulated=True,
                live_success=False,
                error_code="CONNECTOR_ACCESS_BLOCKED",
                error_message=(
                    "Production connector cannot reach live API: missing production credentials"
                ),
                requires_manual_review=True,
            )

        return VerificationResponse(
            status=SourceVerificationStatus.VERIFIED,
            observed_value={
                "connector_state": "SIMULATED_ADAPTER",
                "verified_via": "CONTRACT_SIMULATOR",
            },
            freshness_timestamp=now_iso,
            request_fingerprint=fingerprint,
            simulated=True,
            live_success=False,
        )


class SimulatorRegistry:
    """Registry managing available source verification providers and simulator capabilities."""

    def __init__(self) -> None:
        self._providers: dict[str, SourceVerificationProvider] = {}
        self.register(AICTEHistoricalSimulatorProvider())
        self.register(FireSafetySimulatorProvider())
        self.register(LandRecordsSimulatorProvider())
        self.register(ProductionAuthorizedConnector())

    def register(self, provider: SourceVerificationProvider) -> None:
        self._providers[provider.get_capability().code] = provider

    def get_provider(self, code: str) -> SourceVerificationProvider | None:
        return self._providers.get(code)

    def list_capabilities(self) -> list[ProviderCapability]:
        return [p.get_capability() for p in self._providers.values()]

    def find_provider_for_doc_type(self, doc_type: str) -> SourceVerificationProvider | None:
        for provider in self._providers.values():
            if doc_type in provider.get_capability().supported_doc_types:
                return provider
        return None
