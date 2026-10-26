# SIH 2026 — AICTE PS26261 Research Package

This repository contains the consolidated research and solution specification for **AICTE PS26261**, focused on evidence-led application validation, document authentication, regulatory compliance, rectification, auditability, and officer review.

## Start here

- [`output/AICTE_PS26261_Revised_Solution_Context.pdf`](output/AICTE_PS26261_Revised_Solution_Context.pdf) — formatted 28-page research report.
- [`output/AICTE_PS26261_Revised_Solution_Context.md`](output/AICTE_PS26261_Revised_Solution_Context.md) — editable report source.
- [`output/AICTE_PS26261_Source_Register.json`](output/AICTE_PS26261_Source_Register.json) — source URLs, provenance, retrieval details, pinned competitor revisions, and hashes.
- [`output/AICTE_PS26261_Rule_Evidence_Register.json`](output/AICTE_PS26261_Rule_Evidence_Register.json) — draft, evidence-linked rule records. Every rule remains disabled for production and adverse action until it passes legal/policy approval and testing.

## Repository structure

```text
output/    Final report and machine-readable evidence registers
sources/   Uploaded source material and amendment copies used in the analysis
research/  Extracted text, pinned competitor evidence, QA records, and report builder
```

Temporary rendered page images used only for visual QA are intentionally excluded.

## Evidence labels

The report distinguishes claims by provenance:

- **V-U** — verified against an uploaded source.
- **V-P** — verified against a primary web source.
- **V-M** — verified against a public mirror where the publisher copy was unavailable.
- **C-S** — verified by inspecting pinned competitor source code.
- **C-R** — competitor author/README claim, not independently demonstrated.
- **P** — proposed design, target, or implementation plan.
- **O** — open question requiring authoritative confirmation.

These labels are important: proposed product behavior and benchmark targets must not be presented as completed or independently validated capabilities.

## Important compliance caveats

- AICTE's official website and some approval routes were unavailable during the final verification pass. Current-year completeness therefore remains unresolved where only mirrored amendment copies were accessible.
- The Annexure 4 faculty-cadre formulas contain an arithmetic/interpretation ambiguity documented in the report. They must not be converted into adverse automated findings without an approved interpretation.
- Source authentication, completeness, forensic concern, document validity, and regulatory compliance are modeled as separate decisions. A forensic signal alone is not proof of fraud or non-compliance.
- The sample rule register is a design artifact, not a production policy pack. It requires maker-checker approval, version pinning, regression tests, and legal/policy sign-off.
- Third-party competitor snapshots under `research/` are retained solely as pinned research evidence. Their original repositories and licenses govern reuse.

## Research scope

The package covers:

- AICTE Approval Process Handbook 2024–27 and accessible 2025–26/2026–27 amendments.
- Correction of earlier assumptions around faculty ratios, cadre formulas, safety certificates, video evidence, rectification, and affidavit requirements.
- The seven requested additions: video checks, alert workflows, applicant/officer reports, access logging, audit/pending-action screens, a visible discrepancy check, and separated completeness/source/forensic outcomes.
- Competitive implementation review with revision-pinned evidence.
- Architecture, data model, APIs, rule governance, security, privacy, retention, accessibility, and licensing considerations.
- Prioritized build plan, five-minute demo narrative, evaluation design, red-team tests, and claim-readiness register.

## Reproducibility

Input SHA-256 hashes and web-source metadata are stored in the source register. The report builder is in `research/build_deliverables.py`; its environment-specific font/runtime assumptions may need adjustment on another machine.

## Research date

The final verification pass was completed on **26 October 2026**. Revalidate AICTE circulars, amendments, portal behavior, data-protection commencement dates, and integration availability before a production deployment or formal compliance claim.
