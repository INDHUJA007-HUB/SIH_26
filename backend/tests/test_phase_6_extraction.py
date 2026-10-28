"""Phase 6 extraction, OCR fallback, normalization, claim reconciliation,
human corrections, and frozen fact sets acceptance tests.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pypdf
import pytest
from sqlalchemy import insert, update

from workbench.adapters import tables as t
from workbench.adapters.claims_service import ClaimsService
from workbench.adapters.extraction_service import ExtractionService
from workbench.modules.claims.models import ClaimRelationship, ClaimStatus
from workbench.modules.claims.normalization import (
    normalize_date,
    normalize_identity,
    normalize_unit,
)
from workbench.modules.extraction.document_classifier import DocumentClassifier
from workbench.modules.extraction.extractors import extract_document_fields
from workbench.modules.extraction.geometry import GeometryPipeline
from workbench.modules.extraction.models import (
    BoundingBox,
    DocumentType,
    ExtractedTextSpan,
    ExtractionMethod,
)
from workbench.modules.extraction.ocr_provider import (
    FallbackOCRProvider,
)
from workbench.workflows.screening import EvidenceScreeningWorkflow

pytestmark = pytest.mark.integration


def _create_synthetic_pdf(text_lines: list[str]) -> bytes:
    """Helper to generate an in-memory synthetic PDF with digital text."""
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=612, height=792)  # Standard Letter 8.5x11 inches

    # In pypdf, we can attach text annotations or stream content
    # For robust text reading across pypdf/pdfplumber, we create a minimal content stream
    content = "BT\n/F1 12 Tf\n50 700 Td\n"
    for line in text_lines:
        content += f"({line}) '\n"
    content += "ET\n"

    stream = pypdf.generic.DecodedStreamObject()
    stream.set_data(content.encode("latin-1"))
    page[pypdf.generic.NameObject("/Contents")] = stream

    # Add standard font resource
    resources = pypdf.generic.DictionaryObject()
    font_dict = pypdf.generic.DictionaryObject()
    f1 = pypdf.generic.DictionaryObject()
    f1[pypdf.generic.NameObject("/Type")] = pypdf.generic.NameObject("/Font")
    f1[pypdf.generic.NameObject("/Subtype")] = pypdf.generic.NameObject("/Type1")
    f1[pypdf.generic.NameObject("/BaseFont")] = pypdf.generic.NameObject("/Helvetica")
    font_dict[pypdf.generic.NameObject("/F1")] = f1
    resources[pypdf.generic.NameObject("/Font")] = font_dict
    page[pypdf.generic.NameObject("/Resources")] = resources

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ==============================================================================
# Subphase 6.1 & 6.2: Geometry, OCR, and Document-Type Classification
# ==============================================================================


def test_geometry_pipeline_inspects_pages_and_rotation():
    pdf_bytes = _create_synthetic_pdf(["AICTE Approved Institution", "Survey Number: 42/1B"])
    pipeline = GeometryPipeline()
    geometries = pipeline.inspect_pages(pdf_bytes)

    assert len(geometries) == 1
    geo = geometries[0]
    assert geo.page_number == 1
    assert geo.width == 612.0
    assert geo.height == 792.0
    assert geo.rotation == 0
    assert geo.has_digital_text is True


def test_bounding_box_normalized_coordinates():
    bbox = BoundingBox.from_points(
        x0=61.2, y0=79.2, x1=306.0, y1=396.0, page_width=612.0, page_height=792.0
    )
    d = bbox.to_dict()
    assert d["x0"] == 0.1
    assert d["y0"] == 0.1
    assert d["x1"] == 0.5
    assert d["y1"] == 0.5


def test_ocr_provider_fallback_preserves_geometry():
    provider = FallbackOCRProvider(
        synthetic_text="FIRE SAFETY CERTIFICATE\nNOC Number: NOC/2024/991\nValid Up To: 2026-10-26"
    )
    spans = provider.extract_page(b"", page_number=1)

    assert len(spans) == 3
    assert spans[0].text == "FIRE SAFETY CERTIFICATE"
    assert spans[0].method == ExtractionMethod.OCR
    assert spans[0].confidence > 0.8
    assert 0.0 <= spans[0].bounding_box.x0 <= 1.0
    assert 0.0 <= spans[0].bounding_box.y1 <= 1.0


def test_document_classifier_supported_and_abstention():
    classifier = DocumentClassifier(confidence_threshold=0.45)

    # 1. Fire Certificate classification
    fire_spans = [
        ExtractedTextSpan("GOVERNMENT FIRE SERVICE DEPARTMENT", 1, BoundingBox(0, 0, 1, 0.1)),
        ExtractedTextSpan(
            "NO OBJECTION CERTIFICATE FOR FIRE SAFETY", 1, BoundingBox(0, 0.1, 1, 0.2)
        ),
        ExtractedTextSpan("Valid up to: 31-03-2027", 1, BoundingBox(0, 0.2, 1, 0.3)),
    ]
    res_fire = classifier.classify(fire_spans)
    assert res_fire.document_type == DocumentType.FIRE_CERTIFICATE
    assert not res_fire.abstained
    assert res_fire.confidence >= 0.5

    # 2. Land Document classification
    land_spans = [
        ExtractedTextSpan("SUB-REGISTRAR OFFICE TITLE DEED", 1, BoundingBox(0, 0, 1, 0.1)),
        ExtractedTextSpan(
            "Survey number 108/2A Total Land Area 5.5 Acres", 1, BoundingBox(0, 0.1, 1, 0.2)
        ),
    ]
    res_land = classifier.classify(land_spans)
    assert res_land.document_type == DocumentType.LAND_DOCUMENT
    assert not res_land.abstained

    # 3. UNKNOWN_DOCUMENT_TYPE abstention
    unknown_spans = [
        ExtractedTextSpan(
            "Random unrelated recipe for baking cookies with chocolate chips",
            1,
            BoundingBox(0, 0, 1, 0.1),
        ),
    ]
    res_unknown = classifier.classify(unknown_spans)
    assert res_unknown.document_type == DocumentType.UNKNOWN_DOCUMENT_TYPE
    assert res_unknown.abstained is True
    assert "refusing to force unsupported document into a supported template" in (
        res_unknown.reason or ""
    )


def test_field_extraction_abstains_on_unknown():
    spans = [ExtractedTextSpan("Random text", 1, BoundingBox(0, 0, 1, 0.1))]
    fields = extract_document_fields(DocumentType.UNKNOWN_DOCUMENT_TYPE, spans, [])
    assert fields == []


# ==============================================================================
# Subphase 6.3: Normalization & Claim Reconciliation
# ==============================================================================


def test_date_normalization_and_ambiguity_markers():
    # 1. ISO date: unambiguous
    res_iso = normalize_date("2024-05-12")
    assert res_iso["iso_date"] == "2024-05-12"
    assert res_iso["ambiguous"] is False

    # 2. Day > 12: unambiguous DD/MM/YYYY
    res_dd = normalize_date("25/06/2024")
    assert res_dd["iso_date"] == "2024-06-25"
    assert res_dd["ambiguous"] is False
    assert res_dd["format_inferred"] == "DD/MM/YYYY"

    # 3. Ambiguous date (day <= 12 and month <= 12 and day != month)
    res_ambig = normalize_date("05/06/2024")
    assert res_ambig["ambiguous"] is True
    assert res_ambig["iso_date"] == "2024-06-05"
    assert res_ambig["alternate_iso_date"] == "2024-05-06"
    assert "can both represent day or month" in res_ambig["ambiguity_reason"]

    # 4. Textual format
    res_text = normalize_date("15 August 2024")
    assert res_text["iso_date"] == "2024-08-15"
    assert res_text["ambiguous"] is False

    # 5. Academic Year format
    res_acad = normalize_date("2024-25")
    assert res_acad["academic_year"] == "2024-2025"
    assert res_acad["ambiguous"] is False


def test_unit_normalization_exact_decimal_and_traces():
    # 1. Land Area in Acres -> Sq Meters
    res_land = normalize_unit("5.2 Acres")
    assert res_land["unit"] == "ACRES"
    assert res_land["canonical_unit"] == "SQ_METERS"
    assert Decimal(res_land["decimal_value"]) == Decimal("5.2")
    # 5.2 * 4046.8564224 = 21043.65339648 -> quantized to 21043.65
    assert Decimal(res_land["canonical_value"]) == Decimal("21043.65")
    assert "5.2 * 4046.8564224" in res_land["conversion_trace"]

    # 2. Bandwidth in Gbps -> Mbps
    res_bw = normalize_unit("1 Gbps")
    assert res_bw["unit"] == "GBPS"
    assert res_bw["canonical_unit"] == "MBPS"
    assert Decimal(res_bw["canonical_value"]) == Decimal("1000.00")

    # 3. Approved Intake in Seats
    res_seats = normalize_unit("300 Seats")
    assert res_seats["unit"] == "SEATS"
    assert Decimal(res_seats["canonical_value"]) == Decimal("300")


def test_identity_normalization_nfkc():
    raw_name = "  Sri   Krishna  College\u00a0of  Engineering \n\t "
    normalized = normalize_identity(raw_name)
    assert normalized == "SRI KRISHNA COLLEGE OF ENGINEERING"


def test_claim_reconciliation_supports_and_contradicts():
    from workbench.modules.claims.reconciliation import ClaimReconciler

    reconciler = ClaimReconciler()

    # Case 1: Land Area Claim SUPPORTS when observed >= declared
    status, rec_val, links = reconciler.reconcile(
        subject="CAMPUS_MAIN",
        predicate="land_area",
        declared_value={"decimal_value": "5.0", "canonical_value": "20234.28", "unit": "ACRES"},
        extracted_fields=[
            {
                "id": "field_1",
                "evidence_version_id": "ev_1",
                "field_name": "land_area",
                "normalized_value": {
                    "decimal_value": "5.5",
                    "canonical_value": "22257.71",
                    "unit": "ACRES",
                },
            }
        ],
    )
    assert status == ClaimStatus.VERIFIED
    assert len(links) == 1
    assert links[0]["relationship"] == ClaimRelationship.SUPPORTS.value

    # Case 2: Land Area Claim CONTRADICTS when observed < declared
    status_fail, rec_fail, links_fail = reconciler.reconcile(
        subject="CAMPUS_MAIN",
        predicate="land_area",
        declared_value={"decimal_value": "5.0", "canonical_value": "20234.28", "unit": "ACRES"},
        extracted_fields=[
            {
                "id": "field_2",
                "evidence_version_id": "ev_2",
                "field_name": "land_area",
                "normalized_value": {
                    "decimal_value": "4.2",
                    "canonical_value": "16996.80",
                    "unit": "ACRES",
                },
            }
        ],
    )
    assert status_fail == ClaimStatus.MISMATCH_DETECTED
    assert len(links_fail) == 1
    assert links_fail[0]["relationship"] == ClaimRelationship.CONTRADICTS.value


# ==============================================================================
# Subphase 6.4: Human Correction, Frozen Fact Sets, and Provenance API
# ==============================================================================


def test_human_correction_and_frozen_fact_set_lifecycle(h):
    """End-to-end test of extraction pipeline, human correction, and frozen fact sets."""
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    # Create slot and evidence version in database
    slot_id = str(uuid4())
    upload_id = str(uuid4())
    version_id = str(uuid4())

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.slots).values(
                id=slot_id,
                institution_id=inst_id,
                application_id=app_id,
                code="FIRE_NOC",
                required=True,
            )
        )
        conn.execute(
            insert(t.uploads).values(
                id=upload_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                actor_id=h.actors["a"],
                filename="fire_noc.pdf",
                media_type="application/pdf",
                expected_size=1024,
                expected_sha256="e" * 64,
                object_key="quarantine/fire_noc.pdf",
                mode="SINGLE",
                part_size=5 * 1024 * 1024,
                status="COMPLETED",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        conn.execute(
            insert(t.evidence).values(
                id=version_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                upload_id=upload_id,
                quarantine_key="quarantine/fire_noc.pdf",
                quarantine_version="1",
                sha256="e" * 64,
                media_type="application/pdf",
                filename="fire_noc.pdf",
                size_bytes=1024,
                status="QUARANTINED",
                metadata={"type": "PDF"},
            )
        )
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == version_id)
            .values(status="ACCEPTED", clean_key="clean/fire_noc.pdf", clean_version="1")
        )

    # 1. Run extraction pipeline via ExtractionService
    extraction_service = ExtractionService(h.owner)
    synthetic_text = (
        "FIRE SAFETY CERTIFICATE\nNOC Number: NOC-TN-2024-88\n"
        "Issued on: 10/05/2024\nValid up to: 10/05/2027"
    )

    run_result = extraction_service.run_pipeline(
        institution_id=inst_id,
        application_id=app_id,
        evidence_version_id=version_id,
        content_bytes=b"%PDF-1.4 synthetic",
        synthetic_ocr_text=synthetic_text,
    )

    assert run_result["status"] == "COMPLETED"
    assert run_result["document_type"] == "FIRE_CERTIFICATE"
    fields = run_result["extracted_fields"]
    assert len(fields) >= 2

    # Check that initial FactSet v1 is frozen
    fact_set_v1 = run_result["fact_set"]
    assert fact_set_v1["version"] == 1
    assert fact_set_v1["is_frozen"] is True
    assert fact_set_v1["canonical_hash"] is not None

    # Verify fields via get_evidence_fields
    ev_fields = extraction_service.get_evidence_fields(inst_id, version_id)
    assert len(ev_fields) >= 2
    target_field = next(f for f in ev_fields if f["field_name"] == "fire_safety_noc_number")

    # 2. Record Audited Human Correction
    correction_result = extraction_service.record_correction(
        institution_id=inst_id,
        evidence_version_id=version_id,
        field_id=target_field["id"],
        corrected_value={"noc_number": "NOC-TN-2024-88-REVISED"},
        reason="Typo in OCR OCR read hyphen as slash",
        corrected_by=h.actors["officer"],
        authority="STATUTORY_OFFICER",
    )

    assert correction_result["prior_value"] == target_field["normalized_value"]
    assert correction_result["corrected_value"] == {"noc_number": "NOC-TN-2024-88-REVISED"}

    # Check that a new frozen FactSet v2 was created
    fact_set_v2 = correction_result["new_fact_set"]
    assert fact_set_v2["version"] == 2
    assert fact_set_v2["canonical_hash"] != fact_set_v1["canonical_hash"]
    assert fact_set_v2["is_frozen"] is True

    # Check that FactSet v1 remains unchanged and retrievable
    retrieved_v1 = extraction_service.get_fact_set(fact_set_v1["id"])
    assert retrieved_v1["version"] == 1
    assert retrieved_v1["canonical_hash"] == fact_set_v1["canonical_hash"]


def test_api_endpoints_fields_correction_factset_and_provenance(h):
    """Test HTTP API contracts for Phase 6 endpoints:
    - GET /api/v1/evidence/{version_id}/fields
    - POST /api/v1/evidence/{version_id}/corrections
    - GET /api/v1/fact-sets/{id}
    - GET /api/v1/claims/{id}/provenance
    """
    inst_id = h.institutions["a"]
    app = h.create(actor="a")
    app_id = app["id"]

    slot_id = str(uuid4())
    upload_id = str(uuid4())
    version_id = str(uuid4())

    with h.owner.begin() as conn:
        conn.execute(
            insert(t.slots).values(
                id=slot_id,
                institution_id=inst_id,
                application_id=app_id,
                code="LAND_DOC",
                required=True,
            )
        )
        conn.execute(
            insert(t.uploads).values(
                id=upload_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                actor_id=h.actors["a"],
                filename="land.pdf",
                media_type="application/pdf",
                expected_size=2048,
                expected_sha256="a" * 64,
                object_key="quarantine/land.pdf",
                mode="SINGLE",
                part_size=5 * 1024 * 1024,
                status="COMPLETED",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        conn.execute(
            insert(t.evidence).values(
                id=version_id,
                institution_id=inst_id,
                application_id=app_id,
                slot_id=slot_id,
                upload_id=upload_id,
                quarantine_key="quarantine/land.pdf",
                quarantine_version="1",
                sha256="a" * 64,
                media_type="application/pdf",
                filename="land.pdf",
                size_bytes=2048,
                status="QUARANTINED",
                metadata={"type": "PDF"},
            )
        )
        conn.execute(
            update(t.evidence)
            .where(t.evidence.c.id == version_id)
            .values(status="ACCEPTED", clean_key="clean/land.pdf", clean_version="1")
        )
        conn.execute(
            insert(t.assignments).values(
                id=str(uuid4()),
                institution_id=inst_id,
                application_id=app_id,
                actor_id=h.actors["officer"],
                access_role="officer",
                expires_at=datetime.now(UTC) + timedelta(days=6),
                granted_by=h.actors["admin"],
                reason="Reviewing land evidence and provenance",
            )
        )

    # Pre-populate extraction via service
    extraction_service = ExtractionService(h.owner)
    run_res = extraction_service.run_pipeline(
        institution_id=inst_id,
        application_id=app_id,
        evidence_version_id=version_id,
        content_bytes=b"%PDF-1.4 synthetic",
        synthetic_ocr_text=(
            "LAND REGISTRATION DEED\nSurvey Number: 104/3\nTotal Land Area: 6.5 Acres"
        ),
    )
    fact_set_id = run_res["fact_set"]["id"]

    # Pre-populate claim via claims service
    claims_service = ClaimsService(h.owner)
    claim_rec = claims_service.declare_claim(
        institution_id=inst_id,
        application_id=app_id,
        subject="CAMPUS_NORTH",
        predicate="land_area",
        declared_value={"decimal_value": "6.0", "unit": "ACRES"},
    )
    claim_id = claim_rec["id"]

    # Run claim reconciliation
    claims_service.reconcile_application_claims(inst_id, app_id)

    # 1. GET /api/v1/evidence/{version_id}/fields
    fields_resp = h.call("GET", f"/api/v1/evidence/{version_id}/fields", actor="officer", mfa=True)
    assert fields_resp.status_code == 200
    fields_data = fields_resp.json()
    assert len(fields_data) >= 1
    land_field = next(f for f in fields_data if f["field_name"] == "land_area")
    assert land_field["normalized_value"]["unit"] == "ACRES"

    # 2. POST /api/v1/evidence/{version_id}/corrections
    correction_payload = {
        "field_id": land_field["id"],
        "corrected_value": {"decimal_value": "7.0", "canonical_value": "28327.99", "unit": "ACRES"},
        "reason": "Survey map amendment added 0.5 acres",
        "authority": "DISTRICT_REVENUE_OFFICER",
    }
    corr_resp = h.call(
        "POST",
        f"/api/v1/evidence/{version_id}/corrections",
        actor="officer",
        mfa=True,
        json=correction_payload,
    )
    assert corr_resp.status_code == 200
    corr_data = corr_resp.json()
    assert corr_data["field_id"] == land_field["id"]
    assert corr_data["new_fact_set"]["version"] == 2

    # 3. GET /api/v1/fact-sets/{id}
    fs_resp = h.call("GET", f"/api/v1/fact-sets/{fact_set_id}", actor="officer", mfa=True)
    assert fs_resp.status_code == 200
    fs_data = fs_resp.json()
    assert fs_data["id"] == fact_set_id
    assert fs_data["is_frozen"] is True
    assert len(fs_data["members"]) >= 1

    # 4. GET /api/v1/claims/{id}/provenance
    prov_resp = h.call("GET", f"/api/v1/claims/{claim_id}/provenance", actor="officer", mfa=True)
    assert prov_resp.status_code == 200
    prov_data = prov_resp.json()
    assert prov_data["id"] == claim_id
    assert prov_data["subject"] == "CAMPUS_NORTH"
    assert "provenance_links" in prov_data
    assert len(prov_data["provenance_links"]) >= 1
    link = prov_data["provenance_links"][0]
    assert link["relationship"] == "SUPPORTS"
    assert link["field"]["bounding_box"] is not None


# ==============================================================================
# Subphase 6.5 / Phase 5: Workflow Integration
# ==============================================================================


@pytest.mark.anyio
async def test_workflow_chains_extraction_on_accepted_evidence():
    """Verify that EvidenceScreeningWorkflow chains extract_facts_activity when clean."""
    from unittest.mock import patch

    wf = EvidenceScreeningWorkflow()

    mock_screen_res = {
        "status": "CLEAN",
        "evidence_id": "ev-100",
        "version_id": "ver-200",
    }
    mock_extract_res = {
        "run_id": "run-300",
        "document_type": "FIRE_CERTIFICATE",
        "status": "COMPLETED",
        "fact_set": {"id": "fs-400", "version": 1},
    }

    async def fake_execute_activity(activity_name, input_data, **kwargs):
        if activity_name == "screen_evidence_activity":
            return mock_screen_res
        elif activity_name == "extract_facts_activity":
            return mock_extract_res
        raise ValueError(f"Unexpected activity: {activity_name}")

    with patch("temporalio.workflow.execute_activity", side_effect=fake_execute_activity):
        res = await wf.run(
            {
                "evidence_id": "ev-100",
                "version_id": "ver-200",
                "institution_id": "inst-1",
                "application_id": "app-1",
                "document_type": "FIRE_CERTIFICATE",
            }
        )

        assert res["status"] == "CLEAN"
        assert "extraction" in res
        assert res["extraction"]["run_id"] == "run-300"
        assert res["extraction"]["fact_set"]["version"] == 1
        assert wf.status() == "COMPLETED"
