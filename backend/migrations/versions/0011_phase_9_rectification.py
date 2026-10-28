"""Phase 9 officer review, reports, response windows, and controlled rectification.

Revision ID: 0011_phase_9_review_rectification
Revises: 0010_phase_8_verification
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_phase_9_rectification"
down_revision = "0010_phase_8_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. review_dispositions (stores human officer dispositions separately from machine findings)
    op.create_table(
        "review_dispositions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("finding_id", sa.String(36), nullable=False),
        sa.Column("evaluation_run_id", sa.String(36), nullable=False),
        sa.Column("officer_id", sa.String(36), nullable=False),
        sa.Column("disposition", sa.String(50), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_review_dispositions_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_review_dispositions_application",
        ),
        sa.ForeignKeyConstraint(
            ["officer_id"],
            ["actor_identities.id"],
            name="fk_review_dispositions_officer",
        ),
    )

    # 2. review_tasks (tracks pending-action read models:
    #    waiting on source/applicant/interpretation/officer)
    op.create_table(
        "review_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("waiting_on", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("assigned_to", sa.String(36)),
        sa.Column("details", sa.JSON()),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_review_tasks_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_review_tasks_application",
        ),
    )

    # 3. validation_reports (immutable audience-separated reports, v1 immutable, report hash stored)
    op.create_table(
        "validation_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("evaluation_run_id", sa.String(36), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("report_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="FINAL"),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("disclosure_policy", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_validation_reports_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_validation_reports_application",
        ),
        sa.UniqueConstraint(
            "application_id",
            "audience",
            "version",
            name="uq_validation_report_app_audience_ver",
        ),
    )

    # 4. response_windows (scoped rectification windows with rounds,
    #    allowed slots/fields, deadlines)
    op.create_table(
        "response_windows",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("opened_by", sa.String(36), nullable=False),
        sa.Column("authority_reference", sa.String(100), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_rounds", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("allowed_slots", sa.JSON(), nullable=False),
        sa.Column("allowed_fields", sa.JSON(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_response_windows_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_response_windows_application",
        ),
    )

    # 5. rectification_responses (immutable applicant response manifest and field adjustments)
    op.create_table(
        "rectification_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("window_id", sa.String(36), nullable=False),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("submitted_by", sa.String(36), nullable=False),
        sa.Column("application_revision", sa.Integer(), nullable=False),
        sa.Column("response_manifest", sa.JSON(), nullable=False),
        sa.Column("declared_field_updates", sa.JSON()),
        sa.Column("reassessment_run_id", sa.String(36)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["window_id"],
            ["response_windows.id"],
            name="fk_rectification_responses_window",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_rectification_responses_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_rectification_responses_application",
        ),
    )

    # 6. reassessment_diffs (diff engine results between baseline run and reassessment run)
    op.create_table(
        "reassessment_diffs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("response_id", sa.String(36)),
        sa.Column("baseline_run_id", sa.String(36), nullable=False),
        sa.Column("reassessment_run_id", sa.String(36), nullable=False),
        sa.Column("diff_summary", sa.JSON(), nullable=False),
        sa.Column("finding_diffs", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_reassessment_diffs_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_reassessment_diffs_application",
        ),
    )

    # Specific indexes
    op.create_index(
        "ix_review_dispositions_finding",
        "review_dispositions",
        ["finding_id"],
    )
    op.create_index(
        "ix_review_tasks_status",
        "review_tasks",
        ["status", "waiting_on"],
    )
    op.create_index(
        "ix_validation_reports_run",
        "validation_reports",
        ["evaluation_run_id", "audience", "version"],
    )
    op.create_index(
        "ix_response_windows_app",
        "response_windows",
        ["application_id", "status"],
    )
    op.create_index(
        "ix_rectification_responses_window",
        "rectification_responses",
        ["window_id"],
    )
    op.create_index(
        "ix_reassessment_diffs_runs",
        "reassessment_diffs",
        ["baseline_run_id", "reassessment_run_id"],
    )

    # RLS Policies and owner indexes
    p9_tables = [
        "review_dispositions",
        "review_tasks",
        "validation_reports",
        "response_windows",
        "rectification_responses",
        "reassessment_diffs",
    ]
    elevated_check = "(wb.elevated() AND wb.has_role('supervisor'))"
    can_read = (
        f"(wb.can_access(institution_id, application_id, false) OR wb.manages(institution_id) "
        f"OR {elevated_check})"
    )
    can_write = (
        f"(wb.can_access(institution_id, application_id, true) OR wb.manages(institution_id) "
        f"OR {elevated_check})"
    )

    for tbl in p9_tables:
        op.create_index(f"ix_{tbl}_owner_time", tbl, ["institution_id", "created_at", "id"])
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {tbl}_read ON {tbl} FOR SELECT TO wb_app USING ({can_read})")
        op.execute(
            f"CREATE POLICY {tbl}_write ON {tbl} FOR ALL TO wb_app "
            f"USING ({can_write}) "
            f"WITH CHECK ({can_write})"
        )
        op.execute(
            f"CREATE POLICY worker_{tbl} ON {tbl} FOR ALL TO wb_worker, wb_scanner, wb_relay "
            "USING (true) WITH CHECK (true)"
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO "
            "wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner"
        )

    # Refresh Phase 8 policies so unassigned officers are strictly denied cross-tenant read/write
    p8_elevated = "(wb.elevated() AND wb.has_role('supervisor'))"
    for tbl in [
        "source_observations",
        "historical_records",
        "verification_attempts",
        "signature_validations",
    ]:
        op.execute(f"DROP POLICY IF EXISTS {tbl}_read ON {tbl}")
        op.execute(f"DROP POLICY IF EXISTS {tbl}_write ON {tbl}")
        op.execute(
            f"CREATE POLICY {tbl}_read ON {tbl} FOR SELECT TO wb_app USING ("
            f"wb.can_access(institution_id, NULL, false) OR wb.manages(institution_id) "
            f"OR {p8_elevated})"
        )
        op.execute(
            f"CREATE POLICY {tbl}_write ON {tbl} FOR ALL TO wb_app "
            f"USING (wb.can_access(institution_id, NULL, true) OR wb.manages(institution_id) "
            f"OR {p8_elevated}) "
            f"WITH CHECK (wb.can_access(institution_id, NULL, true) OR wb.manages(institution_id) "
            f"OR {p8_elevated})"
        )


def downgrade() -> None:
    raise RuntimeError("Operational security changes require a reviewed forward migration")
