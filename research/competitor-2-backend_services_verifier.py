import datetime
import json
from typing import Dict, Any, Tuple

class SimulatedVerificationAdapter:
    """
    Simulated verification adapter for local hackathon prototype.
    Returns deterministic results based on certificate identifiers or document content.
    Includes test scenarios for: Valid, Mismatch, Expired, Not Found, Source Unavailable.
    """

    def __init__(self):
        # Known test registry for deterministic prototype demonstrations
        self.registry = {
            "AFF-UNIV-2026/8942": {
                "status": "Verified",
                "authority": "State Technological University",
                "institution_name": "Delhi Institute of Technology & Science",
                "valid_until": "2027-06-30",
                "approved_intake": 420,
                "remarks": "Official university affiliation active and renewed for academic session 2026-2027."
            },
            "AFF-UNIV-2024/7711": {
                "status": "Expired",
                "authority": "Karnataka State Technical Affiliating Board",
                "institution_name": "Apex Institute of Management & Research, Bengaluru",
                "valid_until": "2025-06-30",
                "approved_intake": 240,
                "remarks": "Affiliation lapsed on 30-June-2025. Renewal application under objection."
            },
            "AFF-UNIV-2026/9021": {
                "status": "Mismatch Detected",
                "authority": "Maharashtra State Technical University",
                "institution_name": "Konkan Coast Engineering College, Ratnagiri",
                "valid_until": "2027-06-30",
                "approved_intake": 240, # Application claims 360
                "approved_programmes": ["Civil Engineering", "Mechanical Engineering"],
                "remarks": "University gazette records approve 240 intake. Computer Science & AI branch expansion not sanctioned."
            },
            "FIRE-NOC/DL/2026/041": {
                "status": "Verified",
                "authority": "Directorate of Delhi Fire Service",
                "institution_name": "Delhi Institute of Technology & Science",
                "valid_until": "2028-03-31",
                "building_blocks": "Blocks A, B, C & Academic Quadrangle",
                "remarks": "Full fire safety compliance verified after joint on-site inspection."
            },
            "FIRE-NOC/MH/2025/112": {
                "status": "Source Unavailable",
                "authority": "State Fire Services e-Clearance Portal",
                "institution_name": "Saraswati Technical Campus, Lucknow",
                "remarks": "Gateway Error HTTP 503: State Fire Portal database service endpoint is undergoing maintenance. Unable to query live register."
            },
            "LU-MUNC-88421": {
                "status": "Verified",
                "authority": "Municipal Town Planning Authority",
                "institution_name": "Delhi Institute of Technology & Science",
                "area_sqm": 25000,
                "remarks": "Institutional educational land use approved under master plan zoning."
            }
        }

    def verify_document(self, document_type: str, certificate_no: str, institution_name: str) -> Tuple[str, Dict[str, Any], str]:
        """
        Executes simulated verification.
        Returns: (status, response_payload, summary)
        """
        request_time = datetime.datetime.utcnow().isoformat()
        
        # 1. Exact match in deterministic registry
        if certificate_no and certificate_no in self.registry:
            record = self.registry[certificate_no]
            status = record["status"]
            summary = f"Simulated verification via {record.get('authority', 'Authority')}: Status = {status}. {record.get('remarks', '')}"
            response_payload = {
                "simulated_provider": "AICTE-DigiVerify-Sandbox",
                "query_certificate_no": certificate_no,
                "verified_at": datetime.datetime.utcnow().isoformat(),
                "authority_record": record
            }
            return status, response_payload, summary

        # 2. Heuristic checks for special test keywords
        cert_upper = (certificate_no or "").upper()
        if "EXPIRED" in cert_upper:
            status = "Expired"
            summary = "Authority registry indicates certificate validity expired prior to the active review cycle."
            payload = {"error": "CERTIFICATE_EXPIRED", "detail": "Valid until 2025-05-15"}
            return status, payload, summary
            
        if "MISMATCH" in cert_upper:
            status = "Mismatch Detected"
            summary = "Official records return different institutional parameters than submitted application."
            payload = {"error": "DATA_MISMATCH", "official_institution": "Alternative Trust Name"}
            return status, payload, summary

        if "UNAVAILABLE" in cert_upper or "ERROR" in cert_upper:
            status = "Source Unavailable"
            summary = "External issuing authority portal connection timed out. Manual review recommended."
            payload = {"error": "GATEWAY_TIMEOUT", "http_code": 504}
            return status, payload, summary

        if not certificate_no or certificate_no.startswith("UNKNOWN") or cert_upper == "NONE":
            status = "Manual Review Required"
            summary = "Document does not possess a machine-readable certificate identifier for automated lookup."
            payload = {"notice": "No structured identifier extracted for remote querying"}
            return status, payload, summary

        # 3. Default fallback scenario: certificate not found in synthetic registry
        status = "Verified"
        summary = f"Simulated automated authority verification completed successfully for {document_type}."
        payload = {
            "simulated_provider": "AICTE-DigiVerify-Sandbox",
            "query_certificate_no": certificate_no,
            "status": "Verified",
            "verification_confidence": 0.98,
            "verified_at": datetime.datetime.utcnow().isoformat(),
            "notes": "Authenticity verified against simulated central repository."
        }
        return status, payload, summary

# Singleton adapter instance
verifier_service = SimulatedVerificationAdapter()

