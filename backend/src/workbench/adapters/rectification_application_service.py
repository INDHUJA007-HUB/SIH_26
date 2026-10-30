"""Phase 9 service for response windows, scoped rectification submission,
and reassessment diffing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, Engine, desc, insert, select, update

from workbench.adapters import tables as t
from workbench.adapters.application_service import ApplicationService
from workbench.adapters.tasks_alerts_application_service import TasksAlertsService
from workbench.modules.applications.domain import digest
from workbench.modules.rectification.contracts import (
    FindingDiffClassification,
    FindingDiffItem,
    WindowStatus,
)
from workbench.modules.tasks_alerts.contracts import ScheduleTimerRequest
from workbench.platform.errors import ApplicationError


class RectificationService:
    def __init__(self, engine: Engine):
        self.engine = engine

    def open_response_window(
        self,
        *,
        institution_id: str,
        application_id: str,
        opened_by: str,
        authority_reference: str,
        allowed_slots: list[str],
        allowed_fields: list[str],
        deadline: datetime,
        max_rounds: int = 2,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Open a scoped response window for permitted applicant rectification."""
        if not allowed_slots and not allowed_fields:
            raise ApplicationError(
                "INVALID_SCOPE",
                "At least one allowed slot or field must be specified for response window",
                400,
            )

        def _execute(c: Connection) -> dict[str, Any]:
            # Fetch application
            app_row = (
                c.execute(
                    select(t.applications)
                    .where(
                        t.applications.c.id == application_id,
                        t.applications.c.institution_id == institution_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not app_row:
                raise ApplicationError("NOT_FOUND", f"Application {application_id} not found", 404)

            # Check existing rounds
            existing_windows = (
                c.execute(
                    select(t.response_windows).where(
                        t.response_windows.c.application_id == application_id
                    )
                )
                .mappings()
                .all()
            )

            round_num = len(existing_windows) + 1
            if round_num > max_rounds:
                raise ApplicationError(
                    "MAX_ROUNDS_EXCEEDED",
                    f"Maximum rectification rounds ({max_rounds}) reached for application",
                    400,
                )

            # Check for any currently OPEN window
            open_win = [w for w in existing_windows if w["status"] == WindowStatus.OPEN.value]
            if open_win:
                raise ApplicationError(
                    "ACTIVE_WINDOW_EXISTS", "An active response window is already open", 409
                )

            win_id = str(uuid4())
            now = datetime.now(UTC)
            if deadline <= now or max_rounds < 1 or max_rounds > 2:
                raise ApplicationError(
                    "INVALID_WINDOW_POLICY", "Use a future deadline and at most two rounds", 422
                )
            c.execute(
                insert(t.response_windows).values(
                    id=win_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    opened_by=opened_by,
                    authority_reference=authority_reference,
                    round_number=round_num,
                    max_rounds=max_rounds,
                    allowed_slots=allowed_slots,
                    allowed_fields=allowed_fields,
                    deadline=deadline,
                    status=WindowStatus.OPEN.value,
                    current_revision=app_row["revision"],
                    created_at=now,
                )
            )

            # Update or create review task indicating waiting on APPLICANT
            TasksAlertsService(c).schedule_timer(
                ScheduleTimerRequest(
                    institution_id=institution_id,
                    application_id=application_id,
                    timer_type="RESPONSE_DEADLINE",
                    generation=round_num,
                    deadline=deadline,
                    details={"window_id": win_id},
                )
            )
            c.execute(
                insert(t.review_tasks).values(
                    id=str(uuid4()),
                    institution_id=institution_id,
                    application_id=application_id,
                    task_type="DEFICIENCY_RECTIFICATION_RESPONSE",
                    waiting_on="APPLICANT",
                    status="PENDING",
                    details={
                        "window_id": win_id,
                        "allowed_slots": allowed_slots,
                        "allowed_fields": allowed_fields,
                        "round_number": round_num,
                    },
                    deadline=deadline,
                    created_at=now,
                )
            )

            return {
                "id": win_id,
                "institution_id": institution_id,
                "application_id": application_id,
                "opened_by": opened_by,
                "authority_reference": authority_reference,
                "round_number": round_num,
                "max_rounds": max_rounds,
                "allowed_slots": allowed_slots,
                "allowed_fields": allowed_fields,
                "deadline": deadline.isoformat(),
                "status": WindowStatus.OPEN.value,
                "current_revision": app_row["revision"],
                "created_at": now.isoformat(),
            }

        if conn is not None:
            return _execute(conn)
        with self.engine.begin() as c:
            return _execute(c)

    def submit_rectification_response(
        self,
        *,
        institution_id: str,
        application_id: str,
        window_id: str,
        submitted_by: str,
        evidence_replacements: dict[str, str] | None = None,
        field_updates: dict[str, Any] | None = None,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Submit rectification response with strict scope and deadline validation.

        Validates uploads and declared field changes against allowed scope at final submission.
        Unrelated slot or field changes are strictly rejected with 422 OUT_OF_SCOPE_CHANGE.
        """
        replacements = evidence_replacements or {}
        updates = field_updates or {}

        if not replacements and not updates:
            raise ApplicationError(
                "EMPTY_RESPONSE",
                "At least one permitted slot replacement or field update is required",
                400,
            )

        def _execute(c: Connection) -> dict[str, Any]:
            app = (
                c.execute(
                    select(t.applications)
                    .where(
                        t.applications.c.id == application_id,
                        t.applications.c.institution_id == institution_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not app:
                raise ApplicationError("NOT_FOUND", "Application not found", 404)
            win = (
                c.execute(
                    select(t.response_windows)
                    .where(t.response_windows.c.id == window_id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not win:
                raise ApplicationError("NOT_FOUND", f"Response window {window_id} not found", 404)

            if win["institution_id"] != institution_id or win["application_id"] != application_id:
                raise ApplicationError(
                    "ACCESS_DENIED",
                    "Window does not belong to specified institution/application",
                    403,
                )

            if win["status"] != WindowStatus.OPEN.value:
                raise ApplicationError(
                    "WINDOW_CLOSED", f"Response window is closed (status: {win['status']})", 400
                )

            now = datetime.now(UTC)
            if app["revision"] != win["current_revision"]:
                raise ApplicationError(
                    "STALE_WINDOW", "Application changed after window opened", 409
                )
            win_deadline = win["deadline"]
            if win_deadline.tzinfo is None:
                win_deadline = win_deadline.replace(tzinfo=UTC)
            if now > win_deadline:
                c.execute(
                    update(t.response_windows)
                    .where(t.response_windows.c.id == window_id)
                    .values(status=WindowStatus.EXPIRED.value, closed_at=now)
                )
                raise ApplicationError(
                    "WINDOW_EXPIRED", "Rectification window deadline has expired", 400
                )

            # Strict scope check on slot replacements
            allowed_slots = set(win["allowed_slots"] or [])
            for slot_code in replacements:
                if slot_code not in allowed_slots:
                    raise ApplicationError(
                        "OUT_OF_SCOPE_CHANGE",
                        f"Slot '{slot_code}' is not permitted for rectification in this window",
                        422,
                    )

            # Strict scope check on declared field updates
            allowed_fields = set(win["allowed_fields"] or [])
            for field_name in updates:
                if field_name not in allowed_fields:
                    raise ApplicationError(
                        "OUT_OF_SCOPE_CHANGE",
                        f"Field '{field_name}' is not permitted for rectification in this window",
                        422,
                    )

            prior = (
                c.execute(
                    select(t.revisions).where(
                        t.revisions.c.application_id == application_id,
                        t.revisions.c.revision == app["revision"],
                    )
                )
                .mappings()
                .first()
            )
            selected = {
                e["slot_id"]: e for e in (prior["manifest"].get("evidence", []) if prior else [])
            }
            for code, evidence_id in replacements.items():
                ev = (
                    c.execute(
                        select(t.evidence)
                        .join(t.slots, t.slots.c.id == t.evidence.c.slot_id)
                        .where(
                            t.evidence.c.id == evidence_id,
                            t.evidence.c.application_id == application_id,
                            t.evidence.c.institution_id == institution_id,
                            t.evidence.c.status == "ACCEPTED",
                            t.slots.c.code == code,
                        )
                    )
                    .mappings()
                    .first()
                )
                if not ev:
                    raise ApplicationError(
                        "INVALID_REPLACEMENT",
                        "Replacement must be accepted evidence in the permitted slot",
                        422,
                    )
                selected[ev["slot_id"]] = {
                    k: ev[k]
                    for k in (
                        "id",
                        "slot_id",
                        "sha256",
                        "size_bytes",
                        "media_type",
                        "clean_key",
                        "clean_version",
                    )
                }
            revised = {
                **dict(app),
                "revision": app["revision"] + 1,
                "declared_facts": {**app["declared_facts"], **updates},
            }
            manifest = ApplicationService.manifest(revised, list(selected.values()))
            manifest["response_window_id"] = window_id
            c.execute(
                insert(t.revisions).values(
                    id=str(uuid4()),
                    institution_id=institution_id,
                    application_id=application_id,
                    revision=revised["revision"],
                    stage=app["stage"],
                    manifest=manifest,
                    sha256=digest(manifest),
                )
            )
            c.execute(
                update(t.applications)
                .where(t.applications.c.id == application_id)
                .values(
                    revision=revised["revision"],
                    declared_facts=revised["declared_facts"],
                )
            )
            # Scope checks passed: record response and close window
            resp_id = str(uuid4())
            c.execute(
                insert(t.rectification_responses).values(
                    id=resp_id,
                    window_id=window_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    submitted_by=submitted_by,
                    application_revision=win["current_revision"] + 1,
                    response_manifest={
                        "evidence_replacements": replacements,
                        "submitted_at": now.isoformat(),
                    },
                    declared_field_updates=updates,
                    created_at=now,
                )
            )

            c.execute(
                update(t.response_windows)
                .where(t.response_windows.c.id == window_id)
                .values(status=WindowStatus.SUBMITTED.value, closed_at=now)
            )
            c.execute(
                t.outbox.insert().values(
                    id=str(uuid4()),
                    institution_id=institution_id,
                    application_id=application_id,
                    event_type="RectificationSubmitted",
                    payload={"response_id": resp_id},
                )
            )

            # Transition task to OFFICER review
            c.execute(
                update(t.durable_timers)
                .where(
                    t.durable_timers.c.application_id == application_id,
                    t.durable_timers.c.timer_type == "RESPONSE_DEADLINE",
                    t.durable_timers.c.status == "SCHEDULED",
                )
                .values(status="CANCELLED", cancelled_at=now)
            )
            c.execute(
                update(t.review_tasks)
                .where(
                    t.review_tasks.c.application_id == application_id,
                    t.review_tasks.c.task_type == "DEFICIENCY_RECTIFICATION_RESPONSE",
                    t.review_tasks.c.status == "PENDING",
                )
                .values(status="COMPLETED")
            )
            c.execute(
                insert(t.review_tasks).values(
                    id=str(uuid4()),
                    institution_id=institution_id,
                    application_id=application_id,
                    task_type="OFFICER_REASSESSMENT_REQUIRED",
                    waiting_on="OFFICER",
                    status="PENDING",
                    details={"response_id": resp_id, "window_id": window_id},
                    created_at=now,
                )
            )

            return {
                "id": resp_id,
                "window_id": window_id,
                "institution_id": institution_id,
                "application_id": application_id,
                "submitted_by": submitted_by,
                "application_revision": win["current_revision"] + 1,
                "response_manifest": {"evidence_replacements": replacements},
                "declared_field_updates": updates,
                "created_at": now.isoformat(),
            }

        if conn is not None:
            return _execute(conn)
        with self.engine.begin() as c:
            return _execute(c)

    def reassess_and_diff(
        self,
        *,
        institution_id: str,
        application_id: str,
        response_id: str,
        baseline_run_id: str,
        reassessed_findings: list[dict[str, Any]],
        new_run_id: str | None = None,
        conn: Connection | None = None,
    ) -> dict[str, Any]:
        """Perform reassessment diff against baseline findings.

        Classifies into RESOLVED, UNCHANGED, NEW, CHANGED, NO_LONGER_EVALUABLE.
        The baseline run and original submission remain reproducible and unmodified.
        """

        def _execute(c: Connection) -> dict[str, Any]:
            response = (
                c.execute(
                    select(t.rectification_responses)
                    .where(
                        t.rectification_responses.c.id == response_id,
                        t.rectification_responses.c.application_id == application_id,
                        t.rectification_responses.c.institution_id == institution_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not response:
                raise ApplicationError("NOT_FOUND", "Response not found", 404)
            if response["reassessment_run_id"]:
                prior_diff = (
                    c.execute(
                        select(t.reassessment_diffs).where(
                            t.reassessment_diffs.c.response_id == response_id,
                        )
                    )
                    .mappings()
                    .first()
                )
                if prior_diff:
                    return dict(prior_diff)
            baseline = (
                c.execute(
                    select(t.evaluation_runs).where(
                        t.evaluation_runs.c.id == baseline_run_id,
                        t.evaluation_runs.c.application_id == application_id,
                        t.evaluation_runs.c.institution_id == institution_id,
                    )
                )
                .mappings()
                .first()
            )
            if not baseline or not new_run_id:
                raise ApplicationError(
                    "FINALIZED_RUN_REQUIRED", "Provide a stored reassessment run", 422
                )
            new_run = (
                c.execute(
                    select(t.evaluation_runs).where(
                        t.evaluation_runs.c.id == new_run_id,
                        t.evaluation_runs.c.application_id == application_id,
                        t.evaluation_runs.c.institution_id == institution_id,
                    )
                )
                .mappings()
                .first()
            )
            revision = c.execute(
                select(t.revisions.c.id).where(
                    t.revisions.c.application_id == application_id,
                    t.revisions.c.revision == response["application_revision"],
                )
            ).scalar()
            if (
                not new_run
                or new_run["application_revision_id"] != revision
                or new_run_id == baseline_run_id
            ):
                raise ApplicationError(
                    "RUN_LINEAGE_MISMATCH", "Run must evaluate the response revision", 422
                )
            reassessed_findings = [
                dict(r)
                for r in c.execute(
                    select(t.findings).where(
                        t.findings.c.run_id == new_run_id,
                    )
                ).mappings()
            ]
            baseline_rows = (
                c.execute(select(t.findings).where(t.findings.c.run_id == baseline_run_id))
                .mappings()
                .all()
            )

            baseline_map = {b["semantic_key"]: dict(b) for b in baseline_rows}
            reassessed_map = {r["semantic_key"]: r for r in reassessed_findings}

            diff_items: list[dict[str, Any]] = []
            summary = {
                "resolved": 0,
                "unchanged": 0,
                "new": 0,
                "changed": 0,
                "no_longer_evaluable": 0,
            }

            def _get_expl(item: dict[str, Any]) -> str:
                return str(
                    item.get("explanation")
                    or item.get("applicant_explanation")
                    or item.get("description")
                    or item.get("title")
                    or ""
                )

            all_keys = set(baseline_map.keys()).union(set(reassessed_map.keys()))
            for key in sorted(all_keys):
                in_base = key in baseline_map
                in_re = key in reassessed_map

                if in_base and not in_re:
                    outcome = c.execute(
                        select(t.requirement_outcomes.c.outcome).where(
                            t.requirement_outcomes.c.run_id == new_run_id,
                            t.requirement_outcomes.c.rule_id == baseline_map[key]["rule_id"],
                        )
                    ).scalar()
                    # Deficiency existed in baseline, but resolved in reassessment
                    resolved = outcome == "PASS" or (
                        baseline_map[key]["rule_id"] == "COMPLETENESS.SLOT"
                        and new_run["completeness_status"] == "COMPLETE"
                    )
                    classification = (
                        FindingDiffClassification.RESOLVED
                        if resolved
                        else FindingDiffClassification.NO_LONGER_EVALUABLE
                    )
                    rationale = (
                        "Requirement passed in stored reassessment"
                        if resolved
                        else "No passing outcome exists in reassessment"
                    )
                    summary["resolved" if resolved else "no_longer_evaluable"] += 1
                    diff_items.append(
                        FindingDiffItem(
                            finding_key=key,
                            rule_id=baseline_map[key]["rule_id"],
                            clause=baseline_map[key].get("clause") or key,
                            classification=classification,
                            baseline_state={
                                "severity": baseline_map[key].get("severity"),
                                "explanation": _get_expl(baseline_map[key]),
                            },
                            reassessed_state=None,
                            rationale=rationale,
                        ).model_dump()
                    )
                elif not in_base and in_re:
                    # New finding not present in baseline
                    classification = FindingDiffClassification.NEW
                    rationale = "New deficiency identified in rectified evidence"
                    summary["new"] += 1
                    diff_items.append(
                        FindingDiffItem(
                            finding_key=key,
                            rule_id=reassessed_map[key]["rule_id"],
                            clause=reassessed_map[key].get("clause") or key,
                            classification=classification,
                            baseline_state=None,
                            reassessed_state={
                                "severity": reassessed_map[key].get("severity"),
                                "explanation": _get_expl(reassessed_map[key]),
                            },
                            rationale=rationale,
                        ).model_dump()
                    )
                else:
                    b_item = baseline_map[key]
                    r_item = reassessed_map[key]
                    b_expl = _get_expl(b_item)
                    r_expl = _get_expl(r_item)

                    if (
                        r_item.get("finding_type") == "NOT_EVALUABLE"
                        or r_item.get("dimension") == "NOT_EVALUABLE"
                    ):
                        classification = FindingDiffClassification.NO_LONGER_EVALUABLE
                        rationale = "Requirement could no longer be evaluated"
                        summary["no_longer_evaluable"] += 1
                    elif b_item.get("severity") == r_item.get("severity") and b_expl == r_expl:
                        classification = FindingDiffClassification.UNCHANGED
                        rationale = "Deficiency remains unchanged"
                        summary["unchanged"] += 1
                    else:
                        classification = FindingDiffClassification.CHANGED
                        rationale = "Deficiency parameters or severity changed"
                        summary["changed"] += 1

                    diff_items.append(
                        FindingDiffItem(
                            finding_key=key,
                            rule_id=b_item["rule_id"],
                            clause=b_item.get("clause") or key,
                            classification=classification,
                            baseline_state={
                                "severity": b_item.get("severity"),
                                "explanation": b_expl,
                            },
                            reassessed_state={
                                "severity": r_item.get("severity"),
                                "explanation": r_expl,
                            },
                            rationale=rationale,
                        ).model_dump()
                    )

            diff_id = str(uuid4())
            reassessment_run = new_run_id or str(uuid4())
            now = datetime.now(UTC)

            c.execute(
                insert(t.reassessment_diffs).values(
                    id=diff_id,
                    institution_id=institution_id,
                    application_id=application_id,
                    response_id=response_id,
                    baseline_run_id=baseline_run_id,
                    reassessment_run_id=reassessment_run,
                    diff_summary=summary,
                    finding_diffs=diff_items,
                    created_at=now,
                )
            )

            # Link reassessment_run_id on rectification response
            c.execute(
                update(t.rectification_responses)
                .where(t.rectification_responses.c.id == response_id)
                .values(reassessment_run_id=reassessment_run)
            )

            return {
                "id": diff_id,
                "institution_id": institution_id,
                "application_id": application_id,
                "response_id": response_id,
                "baseline_run_id": baseline_run_id,
                "reassessment_run_id": reassessment_run,
                "diff_summary": summary,
                "finding_diffs": diff_items,
                "created_at": now.isoformat(),
            }

        if conn is not None:
            return _execute(conn)
        with self.engine.begin() as c:
            return _execute(c)

    def get_diff(self, diff_id: str, conn: Connection | None = None) -> dict[str, Any]:
        def _execute(c: Connection) -> dict[str, Any]:
            row = (
                c.execute(select(t.reassessment_diffs).where(t.reassessment_diffs.c.id == diff_id))
                .mappings()
                .first()
            )
            if not row:
                raise ApplicationError("NOT_FOUND", f"Diff {diff_id} not found", 404)
            return dict(row)

        if conn is not None:
            return _execute(conn)
        with self.engine.connect() as c:
            return _execute(c)

    def list_windows(
        self,
        *,
        institution_id: str,
        application_id: str | None = None,
        conn: Connection | None = None,
    ) -> list[dict[str, Any]]:
        def _execute(c: Connection) -> list[dict[str, Any]]:
            query = select(t.response_windows).where(
                t.response_windows.c.institution_id == institution_id
            )
            if application_id:
                query = query.where(t.response_windows.c.application_id == application_id)
            query = query.order_by(desc(t.response_windows.c.created_at))
            rows = c.execute(query).mappings().all()
            return [dict(r) for r in rows]

        if conn is not None:
            return _execute(conn)
        with self.engine.connect() as c:
            return _execute(c)
