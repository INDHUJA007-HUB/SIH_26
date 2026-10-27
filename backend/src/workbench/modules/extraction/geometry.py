"""PDF page geometry and digital text extraction pipeline."""

from __future__ import annotations

import io
from typing import Any, BinaryIO

import pypdf

from workbench.modules.extraction.models import (
    BoundingBox,
    ExtractedTextSpan,
    ExtractionMethod,
    PageGeometry,
)


class GeometryPipeline:
    """Inspects PDF files, preserves page dimensions and rotation, and extracts digital text."""

    def __init__(self) -> None:
        pass

    def inspect_pages(self, pdf_stream: bytes | BinaryIO) -> list[PageGeometry]:
        """Inspect page dimensions, orientation, and digital text presence for all pages."""
        stream = io.BytesIO(pdf_stream) if isinstance(pdf_stream, bytes) else pdf_stream
        reader = pypdf.PdfReader(stream)
        pages_geometry: list[PageGeometry] = []

        for idx, page in enumerate(reader.pages, start=1):
            box = page.mediabox
            width = float(box.width)
            height = float(box.height)
            rotation = int(page.get("/Rotate", 0) or 0) % 360

            # Inspect if digital text is present
            raw_text = page.extract_text() or ""
            has_text = len(raw_text.strip()) > 10

            pages_geometry.append(
                PageGeometry(
                    page_number=idx,
                    width=width,
                    height=height,
                    rotation=rotation,
                    dpi=72,
                    has_digital_text=has_text,
                )
            )

        return pages_geometry

    def extract_digital_spans(self, pdf_bytes: bytes) -> list[ExtractedTextSpan]:
        """Extract digital text with bounding boxes using pdfplumber when available,
        falling back to pypdf character/visitor extraction."""
        spans: list[ExtractedTextSpan] = []

        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for idx, page in enumerate(pdf.pages, start=1):
                    p_w = float(page.width)
                    p_h = float(page.height)
                    words = page.extract_words()
                    if words:
                        for w in words:
                            bbox = BoundingBox.from_points(
                                x0=float(w["x0"]),
                                y0=float(w["top"]),
                                x1=float(w["x1"]),
                                y1=float(w["bottom"]),
                                page_width=p_w,
                                page_height=p_h,
                            )
                            spans.append(
                                ExtractedTextSpan(
                                    text=w["text"],
                                    page_number=idx,
                                    bounding_box=bbox,
                                    confidence=1.0,
                                    method=ExtractionMethod.DIGITAL_TEXT,
                                )
                            )
                    else:
                        # Fallback for page text if words is empty
                        raw = page.extract_text() or ""
                        if raw.strip():
                            spans.append(
                                ExtractedTextSpan(
                                    text=raw.strip(),
                                    page_number=idx,
                                    bounding_box=BoundingBox(0.05, 0.05, 0.95, 0.95),
                                    confidence=0.95,
                                    method=ExtractionMethod.DIGITAL_TEXT,
                                )
                            )
            return spans
        except Exception:
            # Fallback to pure pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for idx, pypdf_page in enumerate(reader.pages, start=1):
                box = pypdf_page.mediabox
                p_w = float(box[2]) - float(box[0])
                p_h = float(box[3]) - float(box[1])
                extracted_words: list[tuple[str, list[float]]] = []

                def visitor_body(
                    text: str,
                    cm: list[float],
                    tm: list[float],
                    font_dict: dict[str, Any],
                    font_size: float,
                    _p_h: float = p_h,
                    _words: list[tuple[str, list[float]]] = extracted_words,
                ) -> None:
                    if text and text.strip():
                        # tm is [a, b, c, d, e, f], where e, f are roughly x, y coordinates
                        x = tm[4] if len(tm) > 4 else 0.0
                        y = tm[5] if len(tm) > 5 else 0.0
                        w = len(text) * font_size * 0.5
                        h = font_size
                        _words.append((text, [x, _p_h - y - h, x + w, _p_h - y]))

                try:
                    pypdf_page.extract_text(visitor_text=visitor_body)
                except Exception:
                    raw = pypdf_page.extract_text() or ""
                    if raw.strip():
                        extracted_words.append((raw.strip(), [0.0, 0.0, p_w, p_h]))

                for text_item, coords in extracted_words:
                    bbox = BoundingBox.from_points(
                        x0=coords[0],
                        y0=coords[1],
                        x1=coords[2],
                        y1=coords[3],
                        page_width=p_w,
                        page_height=p_h,
                    )
                    spans.append(
                        ExtractedTextSpan(
                            text=text_item,
                            page_number=idx,
                            bounding_box=bbox,
                            confidence=0.98,
                            method=ExtractionMethod.DIGITAL_TEXT,
                        )
                    )

            return spans
