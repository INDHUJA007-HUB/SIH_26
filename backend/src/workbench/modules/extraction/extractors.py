"""Document-type specific field extractors producing normalized facts and bounding boxes."""

from __future__ import annotations

import re

from workbench.modules.claims.normalization import (
    normalize_date,
    normalize_unit,
)
from workbench.modules.extraction.models import (
    BoundingBox,
    DocumentType,
    ExtractedFieldData,
    ExtractedTextSpan,
    ExtractionMethod,
    PageGeometry,
    UncertaintyLevel,
)


class BaseExtractor:
    """Base class for document-type extractors."""

    def extract(
        self, spans: list[ExtractedTextSpan], pages: list[PageGeometry]
    ) -> list[ExtractedFieldData]:
        raise NotImplementedError


class FireCertificateExtractor(BaseExtractor):
    """Extracts fire safety NOC fields: certificate number, issue date, validity status."""

    def extract(
        self, spans: list[ExtractedTextSpan], pages: list[PageGeometry]
    ) -> list[ExtractedFieldData]:
        fields: list[ExtractedFieldData] = []
        full_text = "\n".join(s.text for s in spans)

        # 1. Certificate / NOC Number
        noc_match = re.search(
            r"(?:noc\s*(?:no|number)|certificate\s*(?:no|number))\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
            full_text,
            re.IGNORECASE,
        )
        if noc_match:
            raw_noc = noc_match.group(1).strip()
            span = self._find_matching_span(raw_noc, spans)
            fields.append(
                ExtractedFieldData(
                    field_name="fire_safety_noc_number",
                    field_type="IDENTIFIER",
                    raw_value=raw_noc,
                    normalized_value={"noc_number": raw_noc},
                    page_number=span.page_number if span else 1,
                    bounding_box=span.bounding_box if span else BoundingBox(0.1, 0.1, 0.5, 0.15),
                    confidence=0.96,
                    uncertainty=UncertaintyLevel.LOW,
                    method=span.method if span else ExtractionMethod.DIGITAL_TEXT,
                )
            )

        # 2. Issue Date
        date_match = re.search(
            r"(?:issued\s*on|date\s*of\s*issue|dated)\s*[:\-]?\s*([0-9A-Za-z\-/,\. ]{6,20})",
            full_text,
            re.IGNORECASE,
        )
        if date_match:
            raw_date = date_match.group(1).strip()
            norm_date = normalize_date(raw_date)
            span = self._find_matching_span(raw_date, spans)
            fields.append(
                ExtractedFieldData(
                    field_name="fire_safety_issue_date",
                    field_type="DATE",
                    raw_value=raw_date,
                    normalized_value=norm_date,
                    page_number=span.page_number if span else 1,
                    bounding_box=span.bounding_box if span else BoundingBox(0.1, 0.2, 0.5, 0.25),
                    confidence=0.92 if not norm_date.get("ambiguous") else 0.75,
                    uncertainty=UncertaintyLevel.LOW
                    if not norm_date.get("ambiguous")
                    else UncertaintyLevel.MEDIUM,
                    method=span.method if span else ExtractionMethod.DIGITAL_TEXT,
                )
            )

        # 3. Expiry / Valid Up To
        expiry_match = re.search(
            r"(?:valid\s*up\s*to|validity|expires\s*on)\s*[:\-]?\s*([0-9A-Za-z\-/,\. ]{6,20})",
            full_text,
            re.IGNORECASE,
        )
        if expiry_match:
            raw_expiry = expiry_match.group(1).strip()
            norm_expiry = normalize_date(raw_expiry)
            span = self._find_matching_span(raw_expiry, spans)
            fields.append(
                ExtractedFieldData(
                    field_name="fire_safety_expiry_date",
                    field_type="DATE",
                    raw_value=raw_expiry,
                    normalized_value=norm_expiry,
                    page_number=span.page_number if span else 1,
                    bounding_box=span.bounding_box if span else BoundingBox(0.1, 0.3, 0.5, 0.35),
                    confidence=0.92 if not norm_expiry.get("ambiguous") else 0.75,
                    uncertainty=UncertaintyLevel.LOW
                    if not norm_expiry.get("ambiguous")
                    else UncertaintyLevel.MEDIUM,
                    method=span.method if span else ExtractionMethod.DIGITAL_TEXT,
                )
            )

        return fields

    def _find_matching_span(
        self, term: str, spans: list[ExtractedTextSpan]
    ) -> ExtractedTextSpan | None:
        term_clean = term.lower().strip()
        for s in spans:
            if term_clean in s.text.lower():
                return s
        return spans[0] if spans else None


class LandDocumentExtractor(BaseExtractor):
    """Extracts land area, survey numbers, and ownership."""

    def extract(
        self, spans: list[ExtractedTextSpan], pages: list[PageGeometry]
    ) -> list[ExtractedFieldData]:
        fields: list[ExtractedFieldData] = []
        full_text = "\n".join(s.text for s in spans)

        # 1. Land Area (Acres, Hectares, Sq Meters)
        area_match = re.search(
            r"(?:total\s*land\s*area|land\s*area|area)\s*[:\-]?\s*([0-9,.]+\s*(?:acres?|hectares?|sq\s*meters?|sqm))",
            full_text,
            re.IGNORECASE,
        )
        if area_match:
            raw_area = area_match.group(1).strip()
            norm_area = normalize_unit(raw_area, default_unit="ACRES")
            span = spans[0] if spans else None
            fields.append(
                ExtractedFieldData(
                    field_name="land_area",
                    field_type="QUANTITY",
                    raw_value=raw_area,
                    normalized_value=norm_area,
                    page_number=span.page_number if span else 1,
                    bounding_box=span.bounding_box if span else BoundingBox(0.1, 0.2, 0.6, 0.25),
                    confidence=0.95,
                    uncertainty=UncertaintyLevel.LOW,
                    method=span.method if span else ExtractionMethod.DIGITAL_TEXT,
                )
            )

        # 2. Survey Number
        survey_match = re.search(
            r"(?:survey\s*(?:no|number)|khasra\s*(?:no|number))\s*[:\-]?\s*([0-9\-/,\. ]+)",
            full_text,
            re.IGNORECASE,
        )
        if survey_match:
            raw_survey = survey_match.group(1).strip()
            span = spans[0] if spans else None
            fields.append(
                ExtractedFieldData(
                    field_name="land_survey_number",
                    field_type="IDENTIFIER",
                    raw_value=raw_survey,
                    normalized_value={"survey_number": raw_survey},
                    page_number=span.page_number if span else 1,
                    bounding_box=span.bounding_box if span else BoundingBox(0.1, 0.3, 0.6, 0.35),
                    confidence=0.90,
                    uncertainty=UncertaintyLevel.LOW,
                    method=span.method if span else ExtractionMethod.DIGITAL_TEXT,
                )
            )

        return fields


class EOAExtractor(BaseExtractor):
    """Extracts Extension of Approval intake, academic year, and institution name."""

    def extract(
        self, spans: list[ExtractedTextSpan], pages: list[PageGeometry]
    ) -> list[ExtractedFieldData]:
        fields: list[ExtractedFieldData] = []
        full_text = "\n".join(s.text for s in spans)

        # 1. Approved Intake
        intake_match = re.search(
            r"(?:approved\s*intake|total\s*intake|intake)\s*[:\-]?\s*([0-9]+)",
            full_text,
            re.IGNORECASE,
        )
        if intake_match:
            raw_intake = intake_match.group(1).strip()
            norm_intake = normalize_unit(raw_intake, default_unit="SEATS")
            span = spans[0] if spans else None
            fields.append(
                ExtractedFieldData(
                    field_name="approved_intake",
                    field_type="QUANTITY",
                    raw_value=raw_intake,
                    normalized_value=norm_intake,
                    page_number=span.page_number if span else 1,
                    bounding_box=span.bounding_box if span else BoundingBox(0.1, 0.2, 0.6, 0.25),
                    confidence=0.97,
                    uncertainty=UncertaintyLevel.LOW,
                    method=span.method if span else ExtractionMethod.DIGITAL_TEXT,
                )
            )

        # 2. Academic Year
        acad_match = re.search(
            r"(?:academic\s*year|session)\s*[:\-]?\s*(20\d{2}[-/]20\d{2}|20\d{2}[-/]\d{2})",
            full_text,
            re.IGNORECASE,
        )
        if acad_match:
            raw_acad = acad_match.group(1).strip()
            norm_acad = normalize_date(raw_acad)
            span = spans[0] if spans else None
            fields.append(
                ExtractedFieldData(
                    field_name="eoa_academic_year",
                    field_type="ACADEMIC_YEAR",
                    raw_value=raw_acad,
                    normalized_value=norm_acad,
                    page_number=span.page_number if span else 1,
                    bounding_box=span.bounding_box if span else BoundingBox(0.1, 0.15, 0.6, 0.2),
                    confidence=0.95,
                    uncertainty=UncertaintyLevel.LOW,
                    method=span.method if span else ExtractionMethod.DIGITAL_TEXT,
                )
            )

        return fields


class FacultyRosterExtractor(BaseExtractor):
    """Extracts faculty counts and cadre breakdown."""

    def extract(
        self, spans: list[ExtractedTextSpan], pages: list[PageGeometry]
    ) -> list[ExtractedFieldData]:
        fields: list[ExtractedFieldData] = []
        full_text = "\n".join(s.text for s in spans)

        # 1. Total Faculty Count
        fac_match = re.search(
            r"(?:total\s*faculty|faculty\s*count|teaching\s*staff)\s*[:\-]?\s*([0-9]+)",
            full_text,
            re.IGNORECASE,
        )
        if fac_match:
            raw_fac = fac_match.group(1).strip()
            norm_fac = normalize_unit(raw_fac, default_unit="COUNT")
            span = spans[0] if spans else None
            fields.append(
                ExtractedFieldData(
                    field_name="faculty_count",
                    field_type="QUANTITY",
                    raw_value=raw_fac,
                    normalized_value=norm_fac,
                    page_number=span.page_number if span else 1,
                    bounding_box=span.bounding_box if span else BoundingBox(0.1, 0.2, 0.6, 0.25),
                    confidence=0.95,
                    uncertainty=UncertaintyLevel.LOW,
                    method=span.method if span else ExtractionMethod.DIGITAL_TEXT,
                )
            )

        return fields


class BandwidthBillExtractor(BaseExtractor):
    """Extracts bandwidth speed and billing period."""

    def extract(
        self, spans: list[ExtractedTextSpan], pages: list[PageGeometry]
    ) -> list[ExtractedFieldData]:
        fields: list[ExtractedFieldData] = []
        full_text = "\n".join(s.text for s in spans)

        # 1. Bandwidth Speed
        speed_match = re.search(
            r"(?:bandwidth|speed|port\s*speed)\s*[:\-]?\s*([0-9,.]+\s*(?:mbps|gbps|kbps))",
            full_text,
            re.IGNORECASE,
        )
        if speed_match:
            raw_speed = speed_match.group(1).strip()
            norm_speed = normalize_unit(raw_speed, default_unit="MBPS")
            span = spans[0] if spans else None
            fields.append(
                ExtractedFieldData(
                    field_name="bandwidth_mbps",
                    field_type="QUANTITY",
                    raw_value=raw_speed,
                    normalized_value=norm_speed,
                    page_number=span.page_number if span else 1,
                    bounding_box=span.bounding_box if span else BoundingBox(0.1, 0.2, 0.6, 0.25),
                    confidence=0.96,
                    uncertainty=UncertaintyLevel.LOW,
                    method=span.method if span else ExtractionMethod.DIGITAL_TEXT,
                )
            )

        return fields


class UnknownDocumentExtractor(BaseExtractor):
    """Abstains cleanly on unfamiliar document types without forcing a template."""

    def extract(
        self, spans: list[ExtractedTextSpan], pages: list[PageGeometry]
    ) -> list[ExtractedFieldData]:
        # Produces no guessed fields, explicitly indicating abstention
        return []


EXTRACTOR_REGISTRY: dict[DocumentType, type[BaseExtractor]] = {
    DocumentType.FIRE_CERTIFICATE: FireCertificateExtractor,
    DocumentType.LAND_DOCUMENT: LandDocumentExtractor,
    DocumentType.EOA_APPROVAL: EOAExtractor,
    DocumentType.FACULTY_ROSTER: FacultyRosterExtractor,
    DocumentType.BANDWIDTH_BILL: BandwidthBillExtractor,
    DocumentType.UNKNOWN_DOCUMENT_TYPE: UnknownDocumentExtractor,
}


def extract_document_fields(
    doc_type: DocumentType, spans: list[ExtractedTextSpan], pages: list[PageGeometry]
) -> list[ExtractedFieldData]:
    """Dispatch extraction to appropriate document-type extractor."""
    extractor_cls = EXTRACTOR_REGISTRY.get(doc_type, UnknownDocumentExtractor)
    extractor = extractor_cls()
    return extractor.extract(spans, pages)
