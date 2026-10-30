"""Phase 8.3 digital signature checks, structured QR verification, and manual confirmation."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlparse

from workbench.modules.verification.contracts import (
    SignatureStatus,
    SignerRole,
)

# Approved domains for government and statutory institutional QR destinations
APPROVED_DOMAINS = [
    "aicte-india.org",
    "gov.in",
    "nic.in",
    "digilocker.gov.in",
    "tn.gov.in",
    "karnataka.gov.in",
    "maharashtra.gov.in",
]


class SignatureVerificationEngine:
    """Inspects PDF digital signatures and structured QR verification codes."""

    def inspect_pdf_signatures(self, content_bytes: bytes) -> dict[str, Any]:
        """Cryptographic integrity inspection, offline and fail-closed for issuer trust.

        A valid signature container does not establish an authorized issuer or current
        revocation status. Those require an approved trust and authorization policy.
        """
        import io

        result: dict[str, Any] = {
            "validation_type": "PDF_DIGITAL_SIGNATURE",
            "status": SignatureStatus.UNKNOWN,
            "signer_identity": None,
            "signer_role": SignerRole.UNKNOWN,
            "simulated": False,
            "details": {},
        }
        try:
            from pyhanko.pdf_utils.reader import PdfFileReader
            from pyhanko.sign.validation import validate_pdf_signature
            from pyhanko_certvalidator import ValidationContext
        except ImportError:
            result["details"] = {
                "reason": "Cryptographic validator unavailable; manual verification required"
            }
            return result
        try:
            reader = PdfFileReader(io.BytesIO(content_bytes))
            signatures = reader.embedded_signatures
            if not signatures:
                result["details"] = {"reason": "No embedded PDF signatures"}
                return result
            checks = []
            for signature in signatures:
                check = validate_pdf_signature(
                    signature,
                    signer_validation_context=ValidationContext(
                        trust_roots=[],
                        allow_fetching=False,
                        revocation_mode="hard-fail",
                    ),
                )
                checks.append(
                    {
                        "intact": check.intact,
                        "cryptographically_valid": check.valid,
                        "trusted": check.trusted,
                        "revoked": check.revoked,
                    }
                )
            first = signatures[0]
            result["signer_identity"] = first.signer_cert.subject.human_friendly
            result["certificate_sha256"] = hashlib.sha256(first.signer_cert.dump()).hexdigest()
            result["details"] = {
                "signatures": checks,
                "issuer_authorization": "UNKNOWN",
                "revocation_policy": "OFFLINE_HARD_FAIL",
                "reason": "No approved issuer trust bundle configured",
            }
            if any(c["revoked"] for c in checks):
                result["status"] = SignatureStatus.REVOKED
            elif any(not c["intact"] or not c["cryptographically_valid"] for c in checks):
                result["status"] = SignatureStatus.INVALID
            else:
                result["status"] = SignatureStatus.CHAIN_INCOMPLETE
        except Exception:
            result["status"] = SignatureStatus.MALFORMED
            result["details"] = {"reason": "PDF signature container could not be validated"}
        return result

    def decode_and_verify_qr(self, qr_text_or_url: str) -> dict[str, Any]:
        """Decode structured QR and verify target destination against allowlist."""
        qr_text = qr_text_or_url.strip()
        parsed = urlparse(qr_text)
        is_url = bool(parsed.scheme and parsed.netloc)

        if not is_url:
            # Treat as structured JSON or reference code
            try:
                data = json.loads(qr_text)
                return {
                    "validation_type": "STRUCTURED_QR",
                    "status": SignatureStatus.UNKNOWN,
                    "qr_payload": data,
                    "qr_target_url": None,
                    "destination_safe": True,
                    "simulated": True,
                    "details": {"format": "STRUCTURED_JSON_CODE"},
                }
            except Exception:
                return {
                    "validation_type": "STRUCTURED_QR",
                    "status": SignatureStatus.UNKNOWN,
                    "qr_payload": {"raw_text": qr_text},
                    "qr_target_url": None,
                    "destination_safe": True,
                    "simulated": True,
                    "details": {"format": "OPAQUE_TEXT"},
                }

        # URL validation against government domain allowlist
        hostname = (parsed.hostname or "").lower()
        is_safe = (
            parsed.scheme == "https"
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
            and any(
                hostname == approved or hostname.endswith("." + approved)
                for approved in APPROVED_DOMAINS
            )
        )

        status = SignatureStatus.UNKNOWN if is_safe else SignatureStatus.INVALID
        return {
            "validation_type": "STRUCTURED_QR",
            "status": status,
            "qr_payload": {"url": qr_text, "domain": hostname},
            "qr_target_url": qr_text,
            "destination_safe": is_safe,
            "simulated": True,
            "details": {
                "allowlist_matched": is_safe,
                "safety_evaluation": "APPROVED_GOVERNMENT_DESTINATION"
                if is_safe
                else "UNAPPROVED_OR_MALICIOUS_REDIRECT",
            },
        }
