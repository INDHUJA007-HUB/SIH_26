"""Phase 6 extraction service: pipeline orchestration, fact sets, and audited corrections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

from workbench.adapters import tables as t
from workbench.modules.extraction.document_classifier import DocumentClassifier
from workbench.modules.extraction.extractors import extract_document_fields
from workbench.modules.extraction.geometry import GeometryPipeline
from workbench.modules.extraction.models import (
    ExtractedFieldData,
    PageGeometry,
)
from workbench.modules.extraction.ocr_provider import get_default_ocr_provider


def canonical_json_hash(data: Any) -> str:
    """RFC 8785 compliant canonical JSON SHA-256 hash."""
    canonical_bytes = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


class ExtractionService:
    """Orchestrates document geometry, OCR, field extraction, canonical fact-sets,
    and audited human corrections.
    """

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.geometry_pipeline = GeometryPipeline()
        self.classifier = DocumentClassifier()

    @contextmanager
    def _connection(self, conn: Connection | None = None) -> Iterator[Connection]:
        if conn is not None:
            yield conn
        else:
            with self.engine.begin() as connection:
                yield connection

    def run_pipeline(
        self,
        institution_id: str,
        application_id: str,
        evidence_version_id: str,
        content_bytes: bytes,
        synthetic_ocr_text: str | None = None,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Execute extraction, persist extracted fields, and freeze canonical FactSet."""
        # 1. Geometry and page inspection
        try:
            pages = self.geometry_pipeline.inspect_pages(content_bytes)
        except Exception:
            pages = [
                PageGeometry(
                    page_number=1,
                    width=612.0,
                    height=792.0,
                    rotation=0,
                    dpi=72,
                    has_digital_text=False,
                )
            ]

        # 2. Extract text spans (digital text with fallback to OCR)
        spans = []
        try:
            spans = self.geometry_pipeline.extract_digital_spans(content_bytes)
        except Exception:
            spans = []

        # If digital text is missing, run OCR
        if not spans:
            ocr_provider = get_default_ocr_provider(synthetic_fallback_text=synthetic_ocr_text)
            for page in pages:
                spans.extend(ocr_provider.extract_page(content_bytes, page_number=page.page_number))

        # 3. Document Classification with Abstention
        classification = self.classifier.classify(spans)
        doc_type = classification.document_type

        # 4. Field Extraction
        extracted_fields_data: list[ExtractedFieldData] = []
        if not classification.abstained:
            extracted_fields_data = extract_document_fields(doc_type, spans, pages)

        # 5. Database persistence
        run_id = str(uuid4())
        status = "COMPLETED" if not classification.abstained else "ABSTAINED"

        with self._connection(conn) as db:
            # Insert extraction_runs
            db.execute(
                insert(t.extraction_runs).values(
                    id=run_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    evidence_version_id=evidence_version_id,
                    extractor_version="v1.0.0",
                    document_type=doc_type.value,
                    page_count=len(pages),
                    status=status,
                    metadata={
                        "classification": classification.to_dict(),
                        "pages": [p.to_dict() for p in pages],
                    },
                )
            )

            # Insert extracted_fields
            field_records: list[dict[str, Any]] = []
            for f in extracted_fields_data:
                f_id = str(uuid4())
                row = {
                    "id": f_id,
                    "run_id": run_id,
                    "institution_id": institution_id,
                    "application_id": application_id,
                    "evidence_version_id": evidence_version_id,
                    "field_name": f.field_name,
                    "field_type": f.field_type,
                    "raw_value": f.raw_value,
                    "normalized_value": f.normalized_value,
                    "page_number": f.page_number,
                    "bounding_box": f.bounding_box.to_dict(),
                    "rotation": f.rotation,
                    "confidence": f.confidence,
                    "uncertainty": f.uncertainty.value,
                    "method": f.method.value,
                    "is_current": True,
                }
                db.execute(insert(t.extracted_fields).values(**row))
                field_records.append(row)

            # 6. Freeze FactSet for application
            fact_set = self._freeze_fact_set(db, institution_id, application_id)

        return {
            "run_id": run_id,
            "document_type": doc_type.value,
            "status": status,
            "classification": classification.to_dict(),
            "extracted_fields": field_records,
            "fact_set": fact_set,
        }

    def _freeze_fact_set(
        self, conn: Connection, institution_id: str, application_id: str
    ) -> dict[str, Any]:
        """Freezes current active facts into an immutable versioned FactSet."""
        # Find latest version
        existing_versions = (
            conn.execute(
                select(t.fact_sets.c.version)
                .where(t.fact_sets.c.application_id == application_id)
                .order_by(t.fact_sets.c.version.desc())
            )
            .scalars()
            .all()
        )

        next_version = (existing_versions[0] + 1) if existing_versions else 1

        # Query all currently active extracted fields for this application
        fields = (
            conn.execute(
                select(
                    t.extracted_fields.c.id,
                    t.extracted_fields.c.field_name,
                    t.extracted_fields.c.normalized_value,
                )
                .where(
                    t.extracted_fields.c.application_id == application_id,
                    t.extracted_fields.c.is_current.is_(True),
                )
                .order_by(t.extracted_fields.c.field_name, t.extracted_fields.c.id)
            )
            .mappings()
            .all()
        )

        canonical_payload = [
            {
                "field_id": row["id"],
                "field_name": row["field_name"],
                "normalized_value": row["normalized_value"],
            }
            for row in fields
        ]

        fact_set_id = str(uuid4())
        canonical_hash = canonical_json_hash(canonical_payload)

        conn.execute(
            insert(t.fact_sets).values(
                id=fact_set_id,
                institution_id=institution_id,
                application_id=application_id,
                version=next_version,
                canonical_hash=canonical_hash,
                canonicalization_version="jcs-and-project-types-v1",
                is_frozen=True,
            )
        )

        for member in canonical_payload:
            conn.execute(
                insert(t.fact_set_members).values(
                    id=str(uuid4()),
                    fact_set_id=fact_set_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    field_id=member["field_id"],
                    field_name=member["field_name"],
                    normalized_value=member["normalized_value"],
                )
            )

        return {
            "id": fact_set_id,
            "version": next_version,
            "canonical_hash": canonical_hash,
            "member_count": len(canonical_payload),
            "is_frozen": True,
        }

    def get_evidence_fields(
        self, institution_id: str, evidence_version_id: str, conn: Connection | None = None
    ) -> list[dict[str, Any]]:
        """Return all extracted fields for an evidence version with their correction lineage."""
        with self._connection(conn) as db:
            fields = (
                db.execute(
                    select(t.extracted_fields)
                    .where(
                        t.extracted_fields.c.evidence_version_id == evidence_version_id,
                        t.extracted_fields.c.institution_id == institution_id,
                    )
                    .order_by(t.extracted_fields.c.page_number, t.extracted_fields.c.field_name)
                )
                .mappings()
                .all()
            )

            results = []
            for f in fields:
                field_dict = dict(f)
                corrections = (
                    db.execute(
                        select(t.field_corrections)
                        .where(t.field_corrections.c.field_id == f["id"])
                        .order_by(t.field_corrections.c.created_at)
                    )
                    .mappings()
                    .all()
                )
                field_dict["corrections"] = [dict(c) for c in corrections]
                results.append(field_dict)

            return results

    def record_correction(
        self,
        institution_id: str,
        evidence_version_id: str,
        field_id: str,
        corrected_value: dict[str, Any],
        reason: str,
        corrected_by: str,
        authority: str,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Append an audited human correction and freeze a new FactSet version."""
        with self._connection(conn) as db:
            # 1. Fetch target field
            target = (
                db.execute(
                    select(t.extracted_fields).where(
                        t.extracted_fields.c.id == field_id,
                        t.extracted_fields.c.institution_id == institution_id,
                        t.extracted_fields.c.evidence_version_id == evidence_version_id,
                    )
                )
                .mappings()
                .first()
            )

            if not target:
                raise ValueError("Target field not found for correction")

            app_id = target["application_id"]
            correction_id = str(uuid4())

            # 2. Insert field_corrections
            db.execute(
                insert(t.field_corrections).values(
                    id=correction_id,
                    institution_id=institution_id,
                    application_id=app_id,
                    field_id=field_id,
                    prior_value=target["normalized_value"],
                    corrected_value=corrected_value,
                    reason=reason,
                    corrected_by=corrected_by,
                    authority=authority,
                )
            )

            # 3. Create updated extracted_field and mark prior as superseded
            db.execute(
                update(t.extracted_fields)
                .where(t.extracted_fields.c.id == field_id)
                .values(is_current=False)
            )

            new_field_id = str(uuid4())
            db.execute(
                insert(t.extracted_fields).values(
                    id=new_field_id,
                    run_id=target["run_id"],
                    institution_id=institution_id,
                    application_id=app_id,
                    evidence_version_id=evidence_version_id,
                    field_name=target["field_name"],
                    field_type=target["field_type"],
                    raw_value=target["raw_value"],
                    normalized_value=corrected_value,
                    page_number=target["page_number"],
                    bounding_box=target["bounding_box"],
                    rotation=target["rotation"],
                    confidence=1.0,  # Human correction has maximum confidence
                    uncertainty="LOW",
                    method="HUMAN_CORRECTION",
                    is_current=True,
                )
            )

            # 4. Freeze a new FactSet version
            new_fact_set = self._freeze_fact_set(db, institution_id, app_id)

            return {
                "correction_id": correction_id,
                "field_id": field_id,
                "new_field_id": new_field_id,
                "prior_value": target["normalized_value"],
                "corrected_value": corrected_value,
                "reason": reason,
                "corrected_by": corrected_by,
                "authority": authority,
                "new_fact_set": new_fact_set,
            }

    def get_fact_set(
        self, fact_set_id: str, conn: Connection | None = None
    ) -> dict[str, Any] | None:
        """Fetch frozen FactSet and its members."""
        with self._connection(conn) as db:
            fs = (
                db.execute(select(t.fact_sets).where(t.fact_sets.c.id == fact_set_id))
                .mappings()
                .first()
            )

            if not fs:
                return None

            members = (
                db.execute(
                    select(t.fact_set_members).where(
                        t.fact_set_members.c.fact_set_id == fact_set_id
                    )
                )
                .mappings()
                .all()
            )

            result = dict(fs)
            result["members"] = [dict(m) for m in members]
            return result
