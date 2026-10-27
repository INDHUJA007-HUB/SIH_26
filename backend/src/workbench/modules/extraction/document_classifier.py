"""Document-type classification with calibrated abstention."""

from __future__ import annotations

import re

from workbench.modules.extraction.models import (
    DocumentClassification,
    DocumentType,
    ExtractedTextSpan,
)

# Characteristic domain signals for supported document types
CLASSIFICATION_SIGNALS: dict[DocumentType, list[tuple[str, float]]] = {
    DocumentType.FIRE_CERTIFICATE: [
        ("fire", 0.3),
        ("safety", 0.2),
        ("no objection certificate", 0.5),
        ("noc", 0.3),
        ("fire service", 0.4),
        ("fire station", 0.4),
        ("valid up to", 0.2),
        ("emergency services", 0.3),
    ],
    DocumentType.LAND_DOCUMENT: [
        ("land", 0.3),
        ("survey number", 0.5),
        ("khasra", 0.5),
        ("acres", 0.4),
        ("hectares", 0.4),
        ("sub-registrar", 0.4),
        ("deed", 0.3),
        ("title deed", 0.5),
        ("registration", 0.2),
        ("patta", 0.4),
    ],
    DocumentType.EOA_APPROVAL: [
        ("extension of approval", 0.6),
        ("eoa", 0.4),
        ("aicte", 0.5),
        ("all india council for technical education", 0.6),
        ("approved intake", 0.5),
        ("academic year", 0.3),
        ("application no", 0.3),
    ],
    DocumentType.FACULTY_ROSTER: [
        ("faculty", 0.4),
        ("professor", 0.4),
        ("associate professor", 0.4),
        ("assistant professor", 0.4),
        ("designation", 0.3),
        ("qualification", 0.3),
        ("ph.d", 0.3),
        ("cadre", 0.4),
        ("department", 0.2),
    ],
    DocumentType.BANDWIDTH_BILL: [
        ("bandwidth", 0.5),
        ("mbps", 0.5),
        ("gbps", 0.5),
        ("internet service", 0.4),
        ("leased line", 0.5),
        ("telecom", 0.3),
        ("billing period", 0.3),
        ("invoice", 0.2),
    ],
}


class DocumentClassifier:
    """Classifies documents into supported regulatory types or abstains."""

    def __init__(self, confidence_threshold: float = 0.45) -> None:
        self.confidence_threshold = confidence_threshold

    def classify(self, spans: list[ExtractedTextSpan]) -> DocumentClassification:
        all_text = " ".join(s.text.lower() for s in spans)

        scores: dict[DocumentType, float] = {}
        matched_signals: dict[DocumentType, list[str]] = {}

        for doc_type, rules in CLASSIFICATION_SIGNALS.items():
            type_score = 0.0
            found_signals: list[str] = []
            for phrase, weight in rules:
                if re.search(r"\b" + re.escape(phrase) + r"\b", all_text):
                    type_score += weight
                    found_signals.append(phrase)

            # Cap type_score at 1.0
            scores[doc_type] = min(1.0, type_score)
            matched_signals[doc_type] = found_signals

        if not scores:
            return DocumentClassification(
                document_type=DocumentType.UNKNOWN_DOCUMENT_TYPE,
                confidence=0.0,
                abstained=True,
                reason="No readable text available for classification",
            )

        best_type, best_score = max(scores.items(), key=lambda item: item[1])

        if best_score < self.confidence_threshold:
            return DocumentClassification(
                document_type=DocumentType.UNKNOWN_DOCUMENT_TYPE,
                confidence=best_score,
                abstained=True,
                reason=(
                    f"Confidence {best_score:.2f} below threshold {self.confidence_threshold:.2f}; "
                    "refusing to force unsupported document into a supported template"
                ),
                signals=matched_signals.get(best_type, []),
            )

        return DocumentClassification(
            document_type=best_type,
            confidence=best_score,
            abstained=False,
            reason=None,
            signals=matched_signals.get(best_type, []),
        )
