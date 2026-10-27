"""Phase 7 rule sources, interpretations, releases, evaluations, outcomes, and findings."""

import sqlalchemy as sa
from alembic import op

revision = "0009_phase_7_rules"
down_revision = "0008_phase_6_extraction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. rule_sources
    op.create_table(
        "rule_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_code", sa.String(50), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("bytes_size", sa.BigInteger()),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("publisher_reference", sa.String(500)),
        sa.Column("pdf_pages", sa.Integer()),
        sa.Column("checked_on", sa.String(40)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 2. rule_interpretations
    op.create_table(
        "rule_interpretations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(100), nullable=False, unique=True),
        sa.Column("clause", sa.String(100)),
        sa.Column("source_id", sa.String(36)),
        sa.Column(
            "interpretation_state",
            sa.String(50),
            nullable=False,
            server_default="REQUIRES_AUTHORIZED_REVIEW",
        ),
        sa.Column("content_status", sa.String(50), nullable=False, server_default="V-U"),
        sa.Column("summary", sa.JSON()),
        sa.Column("notes", sa.Text()),
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
    )

    # 3. rule_versions
    op.create_table(
        "rule_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(36)),
        sa.Column("clause", sa.String(100)),
        sa.Column("printed_page", sa.Integer()),
        sa.Column("pdf_page", sa.Integer()),
        sa.Column("page_offset", sa.Integer(), nullable=False, server_default="16"),
        sa.Column("applicability", sa.JSON()),
        sa.Column("parameters", sa.JSON()),
        sa.Column("dsl_expression", sa.JSON()),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("production_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("adverse_action_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("rule_id", "version", name="uq_rule_version_rule_ver"),
    )

    # 4. rule_releases
    op.create_table(
        "rule_releases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("release_code", sa.String(50), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("academic_cycle", sa.String(50), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("approved_by", sa.String(36)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 5. release_members
    op.create_table(
        "release_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("release_id", sa.String(36), nullable=False),
        sa.Column("rule_version_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["rule_releases.id"],
            name="fk_release_member_release",
        ),
        sa.ForeignKeyConstraint(
            ["rule_version_id"],
            ["rule_versions.id"],
            name="fk_release_member_rule_version",
        ),
        sa.UniqueConstraint("release_id", "rule_id", name="uq_release_rule"),
    )

    # 6. evaluation_runs
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("application_revision_id", sa.String(36)),
        sa.Column("rule_release_id", sa.String(36)),
        sa.Column("fact_set_id", sa.String(36)),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("evaluation_as_of", sa.String(40), nullable=False),
        sa.Column("execution_mode", sa.String(40), nullable=False, server_default="DEMONSTRATION"),
        sa.Column("completeness_status", sa.String(40), nullable=False, server_default="COMPLETE"),
        sa.Column("compliance_status", sa.String(40), nullable=False, server_default="PASS"),
        sa.Column(
            "source_verification_status",
            sa.String(40),
            nullable=False,
            server_default="VERIFICATION_PENDING",
        ),
        sa.Column(
            "forensic_concern_status",
            sa.String(40),
            nullable=False,
            server_default="NONE_OBSERVED",
        ),
        sa.Column(
            "document_validity_status",
            sa.String(40),
            nullable=False,
            server_default="VALID_ON_REVIEW_DATE",
        ),
        sa.Column("case_workflow_status", sa.String(40), nullable=False, server_default="SCREENED"),
        sa.Column("adverse_action_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("manifest", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_eval_run_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_eval_run_application",
        ),
    )

    # 7. run_inputs
    op.create_table(
        "run_inputs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("input_type", sa.String(50), nullable=False),
        sa.Column("input_id", sa.String(36), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            name="fk_run_input_run",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_run_input_institution",
        ),
    )

    # 8. requirement_outcomes
    op.create_table(
        "requirement_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("requirement_name", sa.String(150), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False, server_default="PASS"),
        sa.Column("rationale", sa.Text()),
        sa.Column("observed_value", sa.JSON()),
        sa.Column("expected_value", sa.JSON()),
        sa.Column("calculation_trace", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            name="fk_req_outcome_run",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_req_outcome_institution",
        ),
    )

    # 9. findings
    op.create_table(
        "findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("semantic_key", sa.String(150), nullable=False),
        sa.Column("dimension", sa.String(40), nullable=False, server_default="COMPLIANCE"),
        sa.Column("severity", sa.String(40), nullable=False, server_default="DEFICIENCY"),
        sa.Column("status", sa.String(40), nullable=False, server_default="OPEN"),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("officer_explanation", sa.Text()),
        sa.Column("applicant_explanation", sa.Text()),
        sa.Column("calculation_trace", sa.JSON()),
        sa.Column("supporting_evidence", sa.JSON()),
        sa.Column("contradicting_evidence", sa.JSON()),
        sa.Column("unknown_reason", sa.Text()),
        sa.Column("adverse_action_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            name="fk_finding_run",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_finding_institution",
        ),
    )

    # Indexes
    op.create_index("ix_rule_sources_code", "rule_sources", ["source_code"])
    op.create_index("ix_rule_interpretations_rule", "rule_interpretations", ["rule_id"])
    op.create_index("ix_rule_versions_rule_ver", "rule_versions", ["rule_id", "version"])
    op.create_index("ix_rule_releases_code", "rule_releases", ["release_code"])
    op.create_index("ix_release_members_release", "release_members", ["release_id"])
    op.create_index(
        "ix_evaluation_runs_app", "evaluation_runs", ["application_id", "institution_id"]
    )
    op.create_index("ix_run_inputs_run", "run_inputs", ["run_id"])
    op.create_index("ix_req_outcomes_run", "requirement_outcomes", ["run_id", "rule_id"])
    op.create_index("ix_findings_run_semantic", "findings", ["run_id", "semantic_key"])

    # RLS on registry tables (Global read, supervisor write)
    rule_tables = [
        "rule_sources",
        "rule_interpretations",
        "rule_versions",
        "rule_releases",
        "release_members",
    ]
    for tbl in rule_tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {tbl}_read ON {tbl} FOR SELECT "
            "TO wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner "
            "USING (true)"
        )
        op.execute(
            f"CREATE POLICY {tbl}_write ON {tbl} FOR ALL TO wb_app "
            "USING (wb.elevated() AND wb.has_role('supervisor')) "
            "WITH CHECK (wb.elevated() AND wb.has_role('supervisor'))"
        )
        op.execute(
            f"CREATE POLICY worker_{tbl} ON {tbl} FOR ALL "
            "TO wb_worker, wb_scanner, wb_relay, wb_security_owner "
            "USING (true) WITH CHECK (true)"
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO "
            "wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner"
        )

    # RLS on tenant-scoped evaluation tables
    tenant_eval_tables = [
        "evaluation_runs",
        "run_inputs",
        "requirement_outcomes",
        "findings",
    ]
    elevated_check = "(wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('officer')))"

    for tbl in tenant_eval_tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {tbl}_read ON {tbl} FOR SELECT TO wb_app "
            f"USING (wb.can_access(institution_id, application_id, false) "
            f"OR wb.manages(institution_id) OR {elevated_check})"
        )
        op.execute(
            f"CREATE POLICY {tbl}_write ON {tbl} FOR ALL TO wb_app "
            f"USING (wb.can_access(institution_id, application_id, true) OR {elevated_check}) "
            f"WITH CHECK (wb.can_access(institution_id, application_id, true) OR {elevated_check})"
        )
        op.execute(
            f"CREATE POLICY worker_{tbl} ON {tbl} FOR ALL "
            "TO wb_worker, wb_scanner, wb_relay, wb_security_owner "
            "USING (true) WITH CHECK (true)"
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO "
            "wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner"
        )


def downgrade() -> None:
    raise RuntimeError("Operational security changes require a reviewed forward migration")
