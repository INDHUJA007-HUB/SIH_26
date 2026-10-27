"""Phase 6 extraction domain models and schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DocumentType(StrEnum):
    FIRE_CERTIFICATE = "FIRE_CERTIFICATE"
    LAND_DOCUMENT = "LAND_DOCUMENT"
    EOA_APPROVAL = "EOA_APPROVAL"
    FACULTY_ROSTER = "FACULTY_ROSTER"
    BANDWIDTH_BILL = "BANDWIDTH_BILL"
    UNKNOWN_DOCUMENT_TYPE = "UNKNOWN_DOCUMENT_TYPE"


class ExtractionMethod(StrEnum):
    DIGITAL_TEXT = "DIGITAL_TEXT"
    OCR = "OCR"
    HYBRID = "HYBRID"
    HUMAN_CORRECTION = "HUMAN_CORRECTION"


class UncertaintyLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CALIBRATED_LOW = "CALIBRATED_LOW"


@dataclass(frozen=True)
class BoundingBox:
    """Normalized bounding box coordinates [0.0, 1.0] relative to page dimensions."""

    x0: float
    y0: float
    x1: float
    y1: float

    def to_dict(self) -> dict[str, float]:
        return {
            "x0": round(self.x0, 4),
            "y0": round(self.y0, 4),
            "x1": round(self.x1, 4),
            "y1": round(self.y1, 4),
        }

    @classmethod
    def from_points(
        cls, x0: float, y0: float, x1: float, y1: float, page_width: float, page_height: float
    ) -> BoundingBox:
        w = max(page_width, 1.0)
        h = max(page_height, 1.0)
        return cls(
            x0=max(0.0, min(1.0, x0 / w)),
            y0=max(0.0, min(1.0, y0 / h)),
            x1=max(0.0, min(1.0, x1 / w)),
            y1=max(0.0, min(1.0, y1 / h)),
        )


@dataclass(frozen=True)
class PageGeometry:
    """PDF/Image page dimensions, orientation, and DPI."""

    page_number: int
    width: float
    height: float
    rotation: int = 0
    dpi: int = 72
    has_digital_text: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "rotation": self.rotation,
            "dpi": self.dpi,
            "has_digital_text": self.has_digital_text,
        }


@dataclass(frozen=True)
class ExtractedTextSpan:
    """Single extracted text element with geometry and confidence."""

    text: str
    page_number: int
    bounding_box: BoundingBox
    confidence: float = 1.0
    method: ExtractionMethod = ExtractionMethod.DIGITAL_TEXT

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "page_number": self.page_number,
            "bounding_box": self.bounding_box.to_dict(),
            "confidence": round(self.confidence, 4),
            "method": self.method.value,
        }


@dataclass(frozen=True)
class DocumentClassification:
    """Result of document-type classification with abstention semantics."""

    document_type: DocumentType
    confidence: float
    abstained: bool = False
    reason: str | None = None
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type.value,
            "confidence": round(self.confidence, 4),
            "abstained": self.abstained,
            "reason": self.reason,
            "signals": self.signals,
        }


@dataclass
class ExtractedFieldData:
    """A single domain field extracted from evidence."""

    field_name: str
    field_type: str
    raw_value: str
    normalized_value: dict[str, Any]
    page_number: int
    bounding_box: BoundingBox
    rotation: int = 0
    confidence: float = 1.0
    uncertainty: UncertaintyLevel = UncertaintyLevel.LOW
    method: ExtractionMethod = ExtractionMethod.DIGITAL_TEXT

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "field_type": self.field_type,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "page_number": self.page_number,
            "bounding_box": self.bounding_box.to_dict(),
            "rotation": self.rotation,
            "confidence": round(self.confidence, 4),
            "uncertainty": self.uncertainty.value,
            "method": self.method.value,
        }
