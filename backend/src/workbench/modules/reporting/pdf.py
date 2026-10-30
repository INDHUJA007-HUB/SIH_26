"""Deterministic PDF rendering from an already authorized frozen report."""

import io
from typing import Any
from xml.sax.saxutils import escape


def render_report_pdf(report: dict[str, Any]) -> bytes:
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    content = report["content"]
    story: list[Any] = [
        Paragraph(f"{escape(report['audience'])} Validation Report", styles["Title"]),
        Paragraph(
            "Preliminary decision support. This report does not approve or reject an application.",
            styles["BodyText"],
        ),
        Spacer(1, 12),
    ]
    for key, value in content["report_metadata"].items():
        story.append(Paragraph(f"{escape(key)}: {escape(str(value))}", styles["BodyText"]))
    story.extend([Spacer(1, 12), Paragraph("Findings", styles["Heading1"])])
    for finding in content["findings"]:
        story.append(Paragraph(escape(str(finding["rule_id"])), styles["Heading2"]))
        story.append(Paragraph(escape(str(finding["explanation"])), styles["BodyText"]))
        if report["audience"] == "OFFICER" and finding.get("trace"):
            story.append(Paragraph(escape(str(finding["trace"])), styles["BodyText"]))
    story.append(
        Paragraph(f"Frozen report SHA-256: {escape(report['report_hash'])}", styles["BodyText"])
    )
    SimpleDocTemplate(
        buffer, title="Validation Report", author="Evidence Workbench", invariant=1
    ).build(story)
    return buffer.getvalue()
