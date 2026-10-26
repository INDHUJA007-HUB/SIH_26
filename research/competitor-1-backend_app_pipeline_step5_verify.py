from typing import Dict, Any, List, Tuple
from ..issuer_mock.mock_service import mock_issuer_service
from ..models.schemas import VerificationItem

def execute_step5_verify(application: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Step 5: External Issuing Authority Source Verification
    Queries mock statutory issuing gateways:
    - Registrar of Societies
    - State Land Records (Bhulekh)
    - Directorate of Fire & Emergency Services
    - Council of Architecture (CoA)
    Returns: (verification_results, advisory_flags)
    """
    verification_results: List[Dict[str, Any]] = []
    advisory_flags: List[Dict[str, Any]] = []
    
    docs_by_type = {d["doc_type"]: d for d in application.get("documents", [])}

    # 1. Registrar of Societies Check
    soc_reg = None
    soc_name = application.get("trust_name", "")
    if "TRUST_DEED" in docs_by_type:
        soc_reg = docs_by_type["TRUST_DEED"].get("extracted_fields", {}).get("registration_no")
        deed_name = docs_by_type["TRUST_DEED"].get("extracted_fields", {}).get("trust_name")
        if deed_name:
            soc_name = deed_name

    if soc_reg:
        res = mock_issuer_service.verify_society(soc_reg, soc_name)
        verification_results.append(res)
        
        if res["status"] == "MISMATCH":
            advisory_flags.append({
                "id": f"FLAG-VERIF-SOC-{soc_reg}",
                "rule_id": "RULE_ISSUER_AUTHENTICITY",
                "category": "VERIFICATION",
                "severity": "CRITICAL",
                "title": "Registrar of Societies: Record Mismatch in Government Registry",
                "evidence": {
                    "source_doc_type": "TRUST_DEED",
                    "page": 1,
                    "bounding_box": {"x": 22.0, "y": 35.0, "width": 38.0, "height": 3.8},
                    "snippet": f"Checked Reg ID: {soc_reg} against State MCA / Society Register"
                },
                "reason": res.get("details", {}).get("discrepancy") or res.get("details", {}).get("reason", "Record mismatch in state registrar portal."),
                "confidence": 0.99,
                "risk_points": 30
            })
        elif res["status"] == "SOURCE_UNAVAILABLE":
            advisory_flags.append({
                "id": f"FLAG-VERIF-SOC-UNAVAIL-{soc_reg}",
                "rule_id": "RULE_ISSUER_AUTHENTICITY",
                "category": "VERIFICATION",
                "severity": "MEDIUM",
                "title": "Registrar of Societies Portal Offline / Unresponsive",
                "evidence": {
                    "source_doc_type": "TRUST_DEED",
                    "page": 1,
                    "bounding_box": {"x": 22.0, "y": 35.0, "width": 38.0, "height": 3.8},
                    "snippet": "HTTP 503 / Timeout from State Registrar e-Portal"
                },
                "reason": "Issuing authority gateway is temporarily unavailable. Advisory flag generated: scrutiny officer may re-query or request manual registrar certified copy.",
                "confidence": 0.85,
                "risk_points": 10
            })

    # 2. State Land Revenue / Bhulekh Check
    survey_no = None
    land_acres = float(application.get("land_area_acres", 5.0))
    if "LAND_DOCUMENT" in docs_by_type:
        survey_no = docs_by_type["LAND_DOCUMENT"].get("extracted_fields", {}).get("survey_no")
        deed_acres = docs_by_type["LAND_DOCUMENT"].get("extracted_fields", {}).get("land_area_acres")
        if deed_acres:
            land_acres = float(deed_acres)

    if survey_no:
        res = mock_issuer_service.verify_land_record(
            survey_no,
            application.get("district", ""),
            application.get("state", ""),
            land_acres
        )
        verification_results.append(res)
        if res["status"] == "MISMATCH":
            advisory_flags.append({
                "id": f"FLAG-VERIF-LAND-{survey_no}",
                "rule_id": "RULE_ISSUER_AUTHENTICITY",
                "category": "VERIFICATION",
                "severity": "CRITICAL",
                "title": "State Land Records (Bhulekh): Title / Area Mismatch",
                "evidence": {
                    "source_doc_type": "LAND_DOCUMENT",
                    "page": 1,
                    "bounding_box": {"x": 20.0, "y": 38.0, "width": 32.0, "height": 3.8},
                    "snippet": f"Survey Parcel: {survey_no} in District {application.get('district')}"
                },
                "reason": res.get("details", {}).get("discrepancy", "Revenue record divergence detected."),
                "confidence": 0.98,
                "risk_points": 30
            })
        elif res["status"] == "SOURCE_UNAVAILABLE":
            advisory_flags.append({
                "id": f"FLAG-VERIF-LAND-UNAVAIL-{survey_no}",
                "rule_id": "RULE_ISSUER_AUTHENTICITY",
                "category": "VERIFICATION",
                "severity": "MEDIUM",
                "title": "State Land Revenue Gateway Unavailable",
                "evidence": {
                    "source_doc_type": "LAND_DOCUMENT",
                    "page": 1,
                    "bounding_box": {"x": 20.0, "y": 38.0, "width": 32.0, "height": 3.8},
                    "snippet": "Gateway timeout querying digital revenue maps"
                },
                "reason": "State Bhulekh portal did not respond within timeout window. Requires offline manual revenue verification.",
                "confidence": 0.85,
                "risk_points": 10
            })

    # 3. Fire Safety NOC Check
    if "FIRE_NOC" in docs_by_type:
        f_doc = docs_by_type["FIRE_NOC"]
        ef = f_doc.get("extracted_fields", {})
        noc_num = ef.get("noc_number", "")
        expiry = ef.get("expiry_date", "")
        if noc_num:
            res = mock_issuer_service.verify_fire_noc(
                noc_num,
                application.get("institution_name", ""),
                expiry
            )
            verification_results.append(res)
            if res["status"] == "MISMATCH":
                advisory_flags.append({
                    "id": f"FLAG-VERIF-FIRE-{noc_num}",
                    "rule_id": "RULE_ISSUER_AUTHENTICITY",
                    "category": "VERIFICATION",
                    "severity": "CRITICAL",
                    "title": "Fire Services Directorate: Certificate Mismatch / Tampered Validity",
                    "evidence": {
                        "source_doc_type": "FIRE_NOC",
                        "page": 1,
                        "bounding_box": {"x": 25.0, "y": 24.0, "width": 45.0, "height": 4.0},
                        "snippet": f"Dispatch Record ID: {noc_num}"
                    },
                    "reason": res.get("details", {}).get("discrepancy") or res.get("details", {}).get("reason", "Fire dispatch ledger discrepancy."),
                    "confidence": 0.98,
                    "risk_points": 30
                })

    # 4. Council of Architecture (CoA) Check
    if "ARCHITECT_CERT" in docs_by_type:
        a_doc = docs_by_type["ARCHITECT_CERT"]
        ef = a_doc.get("extracted_fields", {})
        coa_no = ef.get("coa_registration_no", "")
        arch_name = ef.get("architect_name", "")
        if coa_no:
            res = mock_issuer_service.verify_architect_license(coa_no, arch_name)
            verification_results.append(res)

    return verification_results, advisory_flags

