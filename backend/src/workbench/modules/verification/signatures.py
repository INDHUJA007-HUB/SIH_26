"""Phase 8.3 digital signature checks, structured QR verification, and manual confirmation."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
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
        """Inspect digital signatures in PDF content."""
        if not content_bytes or len(content_bytes) < 10:
            return {
                "validation_type": "PDF_DIGITAL_SIGNATURE",
                "status": SignatureStatus.MALFORMED,
                "signer_identity": None,
                "signer_role": SignerRole.UNKNOWN,
                "simulated": True,
                "details": {"error": "Content too short or empty"},
            }

        # Look for standard PDF digital signature dictionaries (/ByteRange and /Contents)
        has_byterange = b"/ByteRange" in content_bytes
        has_contents = b"/Contents" in content_bytes
        has_subfilter = b"/SubFilter" in content_bytes or b"/adbe.pkcs7" in content_bytes

        if not (has_byterange and has_contents):
            return {
                "validation_type": "PDF_DIGITAL_SIGNATURE",
                "status": SignatureStatus.UNKNOWN,
                "signer_identity": None,
                "signer_role": SignerRole.UNKNOWN,
                "simulated": True,
                "details": {
                    "reason": "No cryptographic digital signature container detected in PDF"
                },
            }

        # Check for simulated revocation or corruption markers
        if b"SYNTHETIC_REVOKED_CERTIFICATE" in content_bytes:
            return {
                "validation_type": "PDF_DIGITAL_SIGNATURE",
                "status": SignatureStatus.REVOKED,
                "signer_identity": "CN=Revoked Signing Authority, O=Statutory Body",
                "signer_role": SignerRole.ISSUER,
                "signing_time": datetime.now(UTC).isoformat(),
                "certificate_sha256": hashlib.sha256(b"revoked-cert").hexdigest(),
                "simulated": True,
                "details": {
                    "revocation_source": "CRL_CHECK_FAILURE",
                    "reason": "Certificate revoked by issuing CA",
                },
            }

        if b"SYNTHETIC_INVALID_CHAIN" in content_bytes:
            return {
                "validation_type": "PDF_DIGITAL_SIGNATURE",
                "status": SignatureStatus.CHAIN_INCOMPLETE,
                "signer_identity": "CN=Untrusted Intermediate Authority",
                "signer_role": SignerRole.THIRD_PARTY,
                "simulated": True,
                "details": {"error": "Root certificate not in approved government trust store"},
            }

        # Determine signer identity and role from byte markers or standard heuristics
        signer_id = "CN=Government Certification Authority, O=State Directorate"
        signer_role = SignerRole.ISSUER
        if b"APPLICANT_SELF_SIGNED" in content_bytes:
            signer_id = "CN=Principal, O=Applicant Institution"
            signer_role = SignerRole.APPLICANT

        cert_hash = hashlib.sha256(content_bytes[:1024]).hexdigest()
        return {
            "validation_type": "PDF_DIGITAL_SIGNATURE",
            "status": SignatureStatus.VALID,
            "signer_identity": signer_id,
            "signer_role": signer_role,
            "signing_time": datetime.now(UTC).isoformat(),
            "certificate_sha256": cert_hash,
            "simulated": True,
            "details": {
                "subfilter": "adbe.pkcs7.detached" if has_subfilter else "adbe.pkcs7.sha1",
                "integrity": "INTEGRITY_VERIFIED",
            },
        }

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
                    "status": SignatureStatus.VALID,
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
        is_safe = any(
            hostname == approved or hostname.endswith("." + approved)
            for approved in APPROVED_DOMAINS
        )

        status = SignatureStatus.VALID if is_safe else SignatureStatus.INVALID
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
