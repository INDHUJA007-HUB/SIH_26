"""Phase 6 extraction runs, fields, corrections, fact sets, and claims."""

import sqlalchemy as sa
from alembic import op

revision = "0008_phase_6_extraction"
down_revision = "0007_phase_5_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. extraction_runs
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36)),
        sa.Column("evidence_version_id", sa.String(36), nullable=False),
        sa.Column("extractor_version", sa.String(80), nullable=False),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(30), nullable=False),
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
            name="fk_extraction_run_institution",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_version_id"],
            ["evidence_versions.id"],
            name="fk_extraction_run_evidence_version",
        ),
    )

    # 2. extracted_fields
    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36)),
        sa.Column("evidence_version_id", sa.String(36), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_type", sa.String(50), nullable=False),
        sa.Column("raw_value", sa.Text()),
        sa.Column("normalized_value", sa.JSON()),
        sa.Column("page_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("bounding_box", sa.JSON()),
        sa.Column("rotation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("uncertainty", sa.String(50), nullable=False, server_default="LOW"),
        sa.Column("method", sa.String(50), nullable=False, server_default="DIGITAL_TEXT"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["extraction_runs.id"],
            name="fk_extracted_field_run",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_extracted_field_institution",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_version_id"],
            ["evidence_versions.id"],
            name="fk_extracted_field_evidence_version",
        ),
    )

    # 3. field_corrections
    op.create_table(
        "field_corrections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36)),
        sa.Column("field_id", sa.String(36), nullable=False),
        sa.Column("prior_value", sa.JSON()),
        sa.Column("corrected_value", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("corrected_by", sa.String(36), nullable=False),
        sa.Column("authority", sa.String(80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["field_id"],
            ["extracted_fields.id"],
            name="fk_field_correction_field",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_field_correction_institution",
        ),
    )

    # 4. fact_sets
    op.create_table(
        "fact_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("canonical_hash", sa.String(64), nullable=False),
        sa.Column(
            "canonicalization_version",
            sa.String(40),
            nullable=False,
            server_default="jcs-and-project-types-v1",
        ),
        sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("application_id", "version", name="uq_fact_set_application_version"),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_fact_set_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_fact_set_application",
        ),
    )

    # 5. fact_set_members
    op.create_table(
        "fact_set_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("fact_set_id", sa.String(36), nullable=False),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("field_id", sa.String(36), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("normalized_value", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["fact_set_id"],
            ["fact_sets.id"],
            name="fk_fact_set_member_set",
        ),
        sa.ForeignKeyConstraint(
            ["field_id"],
            ["extracted_fields.id"],
            name="fk_fact_set_member_field",
        ),
    )

    # 6. claims
    op.create_table(
        "claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("subject", sa.String(120), nullable=False),
        sa.Column("predicate", sa.String(100), nullable=False),
        sa.Column("period_start", sa.String(40)),
        sa.Column("period_end", sa.String(40)),
        sa.Column("declared_value", sa.JSON()),
        sa.Column("reconciled_value", sa.JSON()),
        sa.Column("status", sa.String(40), nullable=False, server_default="UNVERIFIED"),
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
            name="fk_claim_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_claim_application",
        ),
    )

    # 7. claim_evidence_links
    op.create_table(
        "claim_evidence_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("claim_id", sa.String(36), nullable=False),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("evidence_version_id", sa.String(36), nullable=False),
        sa.Column("field_id", sa.String(36)),
        sa.Column("relationship", sa.String(30), nullable=False, server_default="SUPPORTS"),
        sa.Column("rationale", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            name="fk_claim_evidence_link_claim",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_version_id"],
            ["evidence_versions.id"],
            name="fk_claim_evidence_link_evidence",
        ),
    )

    # Indexes
    op.create_index(
        "ix_extraction_runs_evidence",
        "extraction_runs",
        ["evidence_version_id", "status"],
    )
    op.create_index(
        "ix_extracted_fields_run",
        "extracted_fields",
        ["run_id", "field_name"],
    )
    op.create_index(
        "ix_extracted_fields_evidence",
        "extracted_fields",
        ["evidence_version_id", "field_name"],
    )
    op.create_index(
        "ix_fact_sets_application",
        "fact_sets",
        ["application_id", "version"],
    )
    op.create_index(
        "ix_claims_application",
        "claims",
        ["application_id", "subject", "predicate"],
    )
    op.create_index(
        "ix_claim_evidence_links_claim",
        "claim_evidence_links",
        ["claim_id"],
    )

    # RLS
    p6_tables = [
        "extraction_runs",
        "extracted_fields",
        "field_corrections",
        "fact_sets",
        "fact_set_members",
        "claims",
        "claim_evidence_links",
    ]
    elevated_check = "(wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('officer')))"

    for tbl in p6_tables:
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
            f"CREATE POLICY worker_{tbl} ON {tbl} FOR ALL TO wb_worker, wb_scanner, wb_relay "
            "USING (true) WITH CHECK (true)"
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO "
            "wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner"
        )


def downgrade() -> None:
    raise RuntimeError("Operational security changes require a reviewed forward migration")
