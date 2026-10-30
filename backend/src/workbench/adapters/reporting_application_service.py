"""Phase 9 service for generating immutable officer and applicant validation reports."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, Engine, desc, insert, select

from workbench.adapters import tables as t
from workbench.modules.reporting.contracts import (
    DisclosurePolicy,
    ReportAudience,
    ReportStatus,
)
from workbench.platform.errors import ApplicationError


class ReportService:
    def __init__(self, engine: Engine):
        self.engine = engine

    def generate_report(
        self,
        *,
        institution_id: str,
        application_id: str,
        evaluation_run_id: str,
        audience: ReportAudience | str,
        version: int = 1,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Generate a versioned, immutable validation report for officer or applicant audience.

        V1 is immutable: once generated, re-requesting returns the exact frozen report.
        Simulated source results are explicitly labelled 'SIMULATED' in every report.
        """
        aud_val = (
            audience.value
            if isinstance(audience, ReportAudience)
            else ReportAudience(audience).value
        )

        def _execute(c: Connection) -> dict[str, Any]:
            # 1. Check if report already exists for this (application_id, audience, version)
            #    -> IMMUTABILITY
            existing = (
                c.execute(
                    select(t.validation_reports).where(
                        t.validation_reports.c.application_id == application_id,
                        t.validation_reports.c.audience == aud_val,
                        t.validation_reports.c.version == version,
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                if existing["evaluation_run_id"] != evaluation_run_id:
                    raise ApplicationError(
                        "REPORT_VERSION_CONFLICT", "This version belongs to another frozen run", 409
                    )
                return dict(existing)

            # 2. Fetch evaluation run
            run_row = (
                c.execute(
                    select(t.evaluation_runs).where(t.evaluation_runs.c.id == evaluation_run_id)
                )
                .mappings()
                .first()
            )
            if not run_row:
                raise ApplicationError(
                    "NOT_FOUND", f"Evaluation run {evaluation_run_id} not found", 404
                )
            if (
                run_row["institution_id"] != institution_id
                or run_row["application_id"] != application_id
            ):
                raise ApplicationError(
                    "RUN_LINEAGE_MISMATCH", "Run belongs to another application", 422
                )

            # 3. Fetch findings
            findings_rows = (
                c.execute(select(t.findings).where(t.findings.c.run_id == evaluation_run_id))
                .mappings()
                .all()
            )

            # 4. Fetch requirement outcomes
            outcomes_rows = (
                c.execute(
                    select(t.requirement_outcomes).where(
                        t.requirement_outcomes.c.run_id == evaluation_run_id
                    )
                )
                .mappings()
                .all()
            )

            # 5. Fetch source observations for institution
            obs_rows = (
                (run_row.get("manifest") or {})
                .get("evidence_manifest", {})
                .get("source_observations", [])
            )

            # Format source observations: MUST label simulated results as SIMULATED
            formatted_observations: list[dict[str, Any]] = []
            for obs in obs_rows:
                formatted_observations.append(
                    {
                        "id": obs["id"],
                        "provider_code": obs["provider_code"],
                        "status": obs["status"],
                        "mode": obs["mode"],
                        "simulated": obs["simulated"],
                        "live_success": obs["live_success"],
                        "simulated_label": "SIMULATED" if obs["simulated"] else obs["mode"],
                        "freshness_timestamp": obs["freshness_timestamp"].isoformat()
                        if hasattr(obs["freshness_timestamp"], "isoformat")
                        else str(obs["freshness_timestamp"]),
                    }
                )

            # Format findings according to audience disclosure policy
            is_officer = aud_val == ReportAudience.OFFICER.value
            disclosure = DisclosurePolicy(
                audience=ReportAudience(aud_val),
                include_forensic_signals=is_officer,
                include_internal_stacktraces=is_officer,
                include_investigator_identities=is_officer,
                include_remediation_instructions=True,
                simulated_results_labeled=True,
            )

            formatted_findings: list[dict[str, Any]] = []
            for f in findings_rows:
                expl = (
                    f.get("applicant_explanation")
                    or f.get("description")
                    or f.get("title")
                    or f.get("explanation")
                    or ""
                )
                item: dict[str, Any] = {
                    "finding_id": f["id"],
                    "semantic_key": f["semantic_key"],
                    "rule_id": f["rule_id"],
                    "clause": f.get("clause") or f["semantic_key"],
                    "severity": f["severity"],
                    "finding_type": f.get("dimension") or f.get("finding_type") or "DEFICIENCY",
                    "explanation": expl,
                    "rectification_guidance": expl if not is_officer else None,
                }
                if is_officer:
                    item["trace"] = f.get("calculation_trace") or f.get("trace")
                    item["forensic_flags"] = []
                    item["internal_decision_support"] = (
                        "PRELIMINARY_AUTOMATED_FLAG_REQUIRES_OFFICER_DISPOSITION"
                    )
                formatted_findings.append(item)

            summary = {
                "overall_status": run_row.get("compliance_status")
                or run_row.get("overall_status")
                or "UNKNOWN",
                "total_requirements": len(outcomes_rows),
                "total_findings": len(findings_rows),
                "verified_sources": len(
                    [
                        o
                        for o in formatted_observations
                        if o["status"] == "VERIFIED" and not o["simulated"] and o["live_success"]
                    ]
                ),
                "simulated_sources_count": sum(o["simulated"] for o in formatted_observations),
                "source_verification_mode": sorted({o["mode"] for o in formatted_observations}),
            }

            content = {
                "report_metadata": {
                    "report_type": f"AICTE_{aud_val}_VALIDATION_REPORT",
                    "audience": aud_val,
                    "version": version,
                    "application_id": application_id,
                    "institution_id": institution_id,
                    "evaluation_run_id": evaluation_run_id,
                    "rule_release_id": run_row.get("rule_release_id") or run_row.get("release_id"),
                    "generated_at": datetime.now(UTC).isoformat(),
                    "simulated_environment_badge": "SIMULATED",
                },
                "summary": summary,
                "findings": formatted_findings,
                "source_observations": formatted_observations,
                "disclosure_level": "RESTRICTED_OFFICER_INTERNAL"
                if is_officer
                else "PUBLIC_APPLICANT_RECTIFICATION",
            }

            # Canonical report hash (SHA-256)
            canonical_bytes = json.dumps(content, sort_keys=True).encode("utf-8")
            report_hash = hashlib.sha256(canonical_bytes).hexdigest()

            report_id = str(uuid4())
            now = datetime.now(UTC)
            c.execute(
                insert(t.validation_reports).values(
                    id=report_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    evaluation_run_id=evaluation_run_id,
                    audience=aud_val,
                    version=version,
                    report_hash=report_hash,
                    status=ReportStatus.FINAL.value,
                    summary=summary,
                    content=content,
                    disclosure_policy=disclosure.model_dump(),
                    created_at=now,
                )
            )

            return {
                "id": report_id,
                "institution_id": institution_id,
                "application_id": application_id,
                "evaluation_run_id": evaluation_run_id,
                "audience": aud_val,
                "version": version,
                "report_hash": report_hash,
                "status": ReportStatus.FINAL.value,
                "summary": summary,
                "content": content,
                "disclosure_policy": disclosure.model_dump(),
                "created_at": now.isoformat(),
            }

        if conn is not None:
            return _execute(conn)
        with self.engine.begin() as c:
            return _execute(c)

    def get_report(self, report_id: str, conn: Connection | None = None) -> dict[str, Any]:
        def _execute(c: Connection) -> dict[str, Any]:
            row = (
                c.execute(
                    select(t.validation_reports).where(t.validation_reports.c.id == report_id)
                )
                .mappings()
                .first()
            )
            if not row:
                raise ApplicationError("NOT_FOUND", f"Report {report_id} not found", 404)
            return dict(row)

        if conn is not None:
            return _execute(conn)
        with self.engine.connect() as c:
            return _execute(c)

    def list_reports(
        self,
        *,
        institution_id: str,
        application_id: str | None = None,
        audience: str | None = None,
        conn: Connection | None = None,
    ) -> list[dict[str, Any]]:
        def _execute(c: Connection) -> list[dict[str, Any]]:
            query = select(t.validation_reports).where(
                t.validation_reports.c.institution_id == institution_id
            )
            if application_id:
                query = query.where(t.validation_reports.c.application_id == application_id)
            if audience:
                query = query.where(t.validation_reports.c.audience == audience)
            query = query.order_by(desc(t.validation_reports.c.created_at))
            rows = c.execute(query).mappings().all()
            return [dict(r) for r in rows]

        if conn is not None:
            return _execute(conn)
        with self.engine.connect() as c:
            return _execute(c)
