# Phase 6 Backend Verification: Document Extraction, Provenance, and Versioned Facts

Implementation root: `c:/Users/indhu/SIH_26/backend`. Scope: local, synthetic development release and PostgreSQL RLS integration.
This document details the architectural implementation and test verification of Phase 6 as specified in [BACKEND_IMPLEMENTATION_PLAN.md](../../docs/BACKEND_IMPLEMENTATION_PLAN.md) (Section 6.2, Section 8.2, and Section 10).

---

## 1. Architecture and Pipeline Topology

```mermaid
flowchart TD
    subgraph Intake ["Phase 5 Intake & Screening"]
        CleanDoc["Accepted / Clean PDF Evidence (evidence_versions)"]
        Workflow["EvidenceScreeningWorkflow"]
        CleanDoc --> Workflow
    end

    subgraph GeometryAndOCR ["Subphase 6.1 & 6.2: Geometry & OCR Engine"]
        Workflow --> Activity["extract_facts_activity"]
        Activity --> Service["ExtractionService.run_pipeline"]
        Service --> Geo["GeometryPipeline (pypdf / pdfplumber)"]
        Geo --> Pages["PageGeometry (Dimensions, Rotation)"]
        Geo --> DigitalSpans["Digital Text Spans + BBoxes"]
        Service --> OCR["OCRProvider (PaddleOCR / Fallback OCR)"]
        OCR --> ScannedSpans["Scanned Text Spans + BBoxes"]
    end

    subgraph ClassificationAndExtraction ["Subphase 6.2: Classification & Calibrated Extraction"]
        Pages & DigitalSpans & ScannedSpans --> Classifier["DocumentClassifier"]
        Classifier -->|Score >= 0.60| SpecificExtractor["Document Extractors (Fire, Land, EOA, Faculty, Bandwidth)"]
        Classifier -->|Score < 0.60| Abstain["UNKNOWN_DOCUMENT_TYPE (Calibrated Abstention)"]
        SpecificExtractor --> ExtractedFields["Extracted Fields with Confidence & BoundingBoxes"]
    end

    subgraph NormalizationAndFacts ["Subphase 6.3 & 6.4: Normalization & Frozen FactSets"]
        ExtractedFields --> Normalizer["Claims & Units Normalizer"]
        Normalizer --> NormDates["ISO Dates (Preserving Ambiguity Markers)"]
        Normalizer --> NormUnits["Exact Decimal Quantities + Conversion Traces"]
        Normalizer --> NormIdentity["Unicode NFKC Normalized Identity Strings"]
        NormDates & NormUnits & NormIdentity --> FactSet["Canonical FactSet (FROZEN, SHA-256 Content Hash)"]
    end

    subgraph ClaimsAndProvenance ["Subphase 6.3 & 6.4: Reconciliation & Provenance API"]
        DeclaredClaim["Declared Claim (claims)"]
        FactSet & DeclaredClaim --> Reconciler["ClaimReconciler"]
        Reconciler --> Links["claim_evidence_links (SUPPORTS, CONTRADICTS, INCONCLUSIVE)"]
        Links --> ProvenanceAPI["GET /api/v1/claims/{id}/provenance"]
    end

    subgraph HumanCorrections ["Subphase 6.4: Supervised Human Corrections"]
        Officer["Assigned Reviewer / Officer"]
        Officer -->|POST /api/v1/evidence/{id}/corrections| Correct["field_corrections (Append-Only Chain)"]
        Correct --> Supersede["Supercede Old FactSet -> Freeze New FactSet Version"]
    end
```

---

## 2. Database Schema & Multi-Tenant RLS Policies

Phase 6 introduces 7 core relational tables managed by Alembic migration [`0008_phase_6_extraction`](file:///c:/Users/indhu/SIH_26/backend/migrations/versions/0008_phase_6_extraction.py). Every table enforces PostgreSQL Row Level Security (RLS) using `wb.can_access(institution_id, application_id, false)` and case assignment verification.

| Table Name | Responsibility | Primary Key | Key Invariants & Constraints |
|---|---|---|---|
| `extraction_runs` | Tracks execution metadata, classifier decisions, page geometries, and runtime metrics | `id` (UUID) | References `evidence_versions.id`. Foreign key cascade delete on version cleanup. |
| `extracted_fields` | Stores individual extracted field values, normalized bounding boxes, and confidence scores | `id` (UUID) | Normalized bounding box `[0.0, 1.0]`. Tracks `field_name`, `field_value`, `extraction_method`, and `uncertainty`. |
| `field_corrections` | Append-only human correction audit trail | `id` (UUID) | Immutable history. References `extracted_fields.id`, records `corrected_by` actor, timestamp, and mandatory `correction_reason`. |
| `fact_sets` | Versioned, canonical bundles of verified facts | `id` (UUID) | Stores SHA-256 `content_hash` over canonical JSON. Status transitions: `DRAFT` -> `FROZEN` -> `SUPERSEDED`. |
| `fact_set_members` | Join table connecting FactSets to active extracted fields or corrections | Composite `(fact_set_id, field_id)` | Unique member mapping per fact set version. |
| `claims` | Institutional application claims declared for compliance evaluation | `id` (UUID) | Captures claim subject, property, claimed value, unit, and status (`DECLARED`, `VERIFIED`, `REJECTED`, `FLAGGED`). |
| `claim_evidence_links` | Reconciled relationships between declared claims and extracted evidence | `id` (UUID) | Relationship: `SUPPORTS`, `CONTRADICTS`, `INCONCLUSIVE`. Stores numeric delta and contradiction notes. |

---

## 3. Subphase Implementation Details

### 3.1 Subphase 6.1 & 6.2 — Text/Geometry Extraction, Scanned OCR Fallback, and Abstention
- **Geometry & Text Extraction** ([`geometry.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/modules/extraction/geometry.py)):
  - Retains page dimensions (`page_width`, `page_height`), aspect ratios, and orientations (`0, 90, 180, 270` degrees).
  - Uses `pdfplumber` character and word bounding box extraction when digital text streams exist.
  - Automatically falls back to `pypdf` visitor callbacks if layout streams are complex.
  - Generates normalized bounding box coordinates:
    $$x_0, y_0, x_1, y_1 \in [0.0, 1.0]$$
- **Scanned OCR Fallback** ([`ocr_provider.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/modules/extraction/ocr_provider.py)):
  - Extensible `OCRProvider` protocol following patterns validated in `tools/ocr_spike.py`.
  - `PaddleOCRProvider` for high-throughput multilingual optical recognition on scanned pages.
  - Deterministic `FallbackOCRProvider` ensuring full operational capability during headless container runs and testing.
- **Calibrated Classifier Abstention** ([`document_classifier.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/modules/extraction/document_classifier.py)):
  - Classifies documents into domain schemas: `FIRE_SAFETY_CERTIFICATE`, `LAND_REGISTRATION_DEED`, `EOA_APPROVAL_LETTER`, `FACULTY_ROSTER`, `BANDWIDTH_BILL`.
  - When classification confidence is below the safety threshold ($< 0.60$), the system strictly classifies the document as `UNKNOWN_DOCUMENT_TYPE` and halts field extraction with `abstention_reason`, preventing hallucinated schema mappings.

### 3.2 Subphase 6.3 — Normalization & Claim Reconciliation
- **Date Normalization** ([`normalization.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/modules/claims/normalization.py)):
  - Normalizes calendar dates into ISO 8601 (`YYYY-MM-DD`).
  - Detects ambiguous slash date formats (e.g., `05/10/2024` where month vs day is ambiguous) and explicitly attaches:
    - `"ambiguous": True`
    - `"alternate_iso_date": "2024-10-05"`
- **Exact Decimal Unit Conversion** ([`normalization.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/modules/claims/normalization.py)):
  - Uses Python's `Decimal` arithmetic to prevent binary floating-point rounding errors.
  - Preserves exact unit conversion traces (e.g., `6.5 Acres` -> `26304.568 Sq Meters` via multiplier `4046.8564224`).
- **Identity Normalization** ([`normalization.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/modules/claims/normalization.py)):
  - Applies Unicode NFKC normalization and whitespace folding to institutional codes, room numbers, and faculty names.
- **Claim Reconciliation** ([`reconciliation.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/modules/claims/reconciliation.py)):
  - Matches declared institutional claims with extracted facts.
  - Evaluates matching values within domain tolerance ($\le 2\%$ delta for continuous quantities).
  - Emits tri-state verdicts: `SUPPORTS`, `CONTRADICTS`, or `INCONCLUSIVE`.

### 3.3 Subphase 6.4 — Supervised Human Corrections & Frozen FactSets
- **Audited Correction Chain** ([`extraction_service.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/adapters/extraction_service.py)):
  - All human corrections are append-only.
  - Every correction requires the reviewer's authenticated identity (`actor_id`) and a mandatory `correction_reason`.
  - Superseded field values remain intact in `extracted_fields` for forensic review.
- **Frozen FactSet Immutability**:
  - Once frozen, a `FactSet` cannot be altered. Its content hash is cryptographically computed:
    $$\text{content\_hash} = \text{SHA256}(\text{canonical\_json}(\text{facts}))$$
  - When an officer submits an approved correction, the previous `FactSet` status becomes `SUPERSEDED`, and a new versioned `FactSet` is frozen with an incremented revision count.
- **REST Endpoints Exposed** ([`intake.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/api/intake.py)):
  - `GET /api/v1/evidence/{version_id}/fields`: Returns all extracted fields, bounding boxes, uncertainties, and active human corrections.
  - `POST /api/v1/evidence/{version_id}/corrections`: Appends an audited correction and triggers a re-freezing of the canonical FactSet.
  - `GET /api/v1/fact-sets/{id}`: Returns frozen canonical facts, member field IDs, and SHA-256 checksum.
  - `GET /api/v1/claims/{id}/provenance`: Returns complete provenance for a claim, including source document version, bounding box geometry, reconciled verdict, and supporting fact metadata.

---

## 4. Phase 5 Workflow Integration

Phase 6 extraction activities are directly integrated into the durable Temporal screening pipeline:
- In [`workflows/screening.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/workflows/screening.py), when evidence completes scanning, malware inspection, and acceptance, `EvidenceScreeningWorkflow` invokes `extract_facts_activity`.
- In [`activities/extraction.py`](file:///c:/Users/indhu/SIH_26/backend/src/workbench/activities/extraction.py), `extract_facts_activity` delegates to `ExtractionService.run_pipeline`, ensuring that every accepted evidence item immediately generates an `extraction_run`, extracts validated fields, and freezes a canonical `FactSet`.

---

## 5. Test Verification Matrix

All tests were executed against the PostgreSQL database in the development container stack (`sih-foundation-postgres-1` with RLS enforced).

### 5.1 Phase 6 Targeted Test Suite (`backend/tests/test_phase_6_extraction.py`)

| Test Function | Target Verified | Result |
|---|---|---|
| `test_geometry_pipeline_inspects_pages_and_rotation` | Page count, dimensions, landscape/portrait aspect, and rotation angle retention | **PASSED** |
| `test_bounding_box_normalized_coordinates` | Coordinate normalization, bounding box clipping ($[0.0, 1.0]$), and point ordering | **PASSED** |
| `test_ocr_provider_fallback_preserves_geometry` | OCR span generation, bounding boxes, and confidence score retention | **PASSED** |
| `test_document_classifier_supported_and_abstention` | Schema classification for fire/land docs and safe abstention on unknown documents | **PASSED** |
| `test_field_extraction_abstains_on_unknown` | Pipeline halts with `UNKNOWN_DOCUMENT_TYPE` and zero spurious fields extracted | **PASSED** |
| `test_date_normalization_and_ambiguity_markers` | ISO 8601 formatting and explicit ambiguity markers (`alternate_iso_date`) | **PASSED** |
| `test_unit_normalization_exact_decimal_and_traces` | Exact `Decimal` arithmetic for land area and bandwidth conversion traces | **PASSED** |
| `test_identity_normalization_nfkc` | Unicode NFKC normalization and whitespace standardization | **PASSED** |
| `test_claim_reconciliation_supports_and_contradicts` | Claim reconciliation generating `SUPPORTS` vs `CONTRADICTS` evidence links | **PASSED** |
| `test_human_correction_and_frozen_fact_set_lifecycle` | Immutable `FactSet` freezing, append-only corrections, and status transitions | **PASSED** |
| `test_api_endpoints_fields_correction_factset_and_provenance` | HTTP endpoints for fields, corrections, fact sets, and claim provenance | **PASSED** |
| `test_workflow_chains_extraction_on_accepted_evidence` | Phase 5 workflow automatically triggering Phase 6 extraction upon acceptance | **PASSED** |

**Summary**: **12 passed, 0 failed in 6.45s**.

### 5.2 Full Regression Suite

```text
backend\tests\test_api.py ...........                                    [ 16%]
backend\tests\test_config.py .....                                       [ 24%]
backend\tests\test_database_integration.py .                             [ 25%]
backend\tests\test_foundation.py ..                                      [ 28%]
backend\tests\test_intake_integration.py ..........................      [ 68%]
backend\tests\test_phase_5_workflows.py ......                           [ 77%]
backend\tests\test_phase_6_extraction.py ............                    [ 95%]
backend\tests\test_telemetry.py ..                                       [ 98%]
backend\tests\test_trace_context.py .                                    [100%]

66 passed, 1 warning in 86.45s
```

### 5.3 Static Analysis & Quality Gates
- **Ruff Linter**: `uv run --project backend ruff check backend/src backend/tests backend/migrations` $\rightarrow$ **All checks passed (0 errors)**.
- **Ruff Formatter**: `uv run --project backend ruff format --check backend/src backend/tests backend/migrations` $\rightarrow$ **138 files cleanly formatted**.
- **MyPy Type Checker**: `uv run --project backend mypy --config-file backend/pyproject.toml backend/src/workbench` $\rightarrow$ **Success: no issues found in 98 source files**.
