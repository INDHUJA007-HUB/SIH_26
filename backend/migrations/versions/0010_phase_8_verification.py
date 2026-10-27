"""Phase 8 source observations, verification attempts, historical records,
and signature validations.
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_phase_8_verification"
down_revision = "0009_phase_7_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. historical_records
    op.create_table(
        "historical_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("academic_cycle", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("external_reference", sa.String(200), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("import_lineage", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_historical_records_institution",
        ),
    )

    # 2. source_observations
    op.create_table(
        "source_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36)),
        sa.Column("evidence_version_id", sa.String(36)),
        sa.Column("claim_id", sa.String(36)),
        sa.Column("provider_code", sa.String(50), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, server_default="SIMULATED"),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("live_success", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("observed_value", sa.JSON()),
        sa.Column("discrepancy_details", sa.JSON()),
        sa.Column("freshness_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_source_observations_institution",
        ),
    )

    # 3. verification_attempts
    op.create_table(
        "verification_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("evidence_version_id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(36)),
        sa.Column("provider_code", sa.String(50), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("error_code", sa.String(50)),
        sa.Column("error_message", sa.Text()),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("outage_escalated_to_task", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("manual_task_id", sa.String(36)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_verification_attempts_institution",
        ),
    )

    # 4. signature_validations
    op.create_table(
        "signature_validations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("evidence_version_id", sa.String(36), nullable=False),
        sa.Column("validation_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("signer_identity", sa.String(200)),
        sa.Column("signer_role", sa.String(50), nullable=False, server_default="UNKNOWN"),
        sa.Column("signing_time", sa.DateTime(timezone=True)),
        sa.Column("certificate_sha256", sa.String(64)),
        sa.Column("qr_payload", sa.JSON()),
        sa.Column("qr_target_url", sa.String(1000)),
        sa.Column("destination_safe", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("details", sa.JSON()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_signature_validations_institution",
        ),
    )

    # Specific indexes
    op.create_index(
        "ix_historical_records_cycle",
        "historical_records",
        ["institution_id", "academic_cycle", "record_type"],
    )
    op.create_index(
        "ix_source_observations_claim",
        "source_observations",
        ["claim_id"],
    )
    op.create_index(
        "ix_source_observations_evidence",
        "source_observations",
        ["evidence_version_id"],
    )
    op.create_index(
        "ix_verification_attempts_req",
        "verification_attempts",
        ["request_fingerprint"],
    )
    op.create_index(
        "ix_signature_validations_evidence",
        "signature_validations",
        ["evidence_version_id"],
    )

    # RLS Policies and owner indexes
    p8_tables = [
        "historical_records",
        "source_observations",
        "verification_attempts",
        "signature_validations",
    ]
    elevated_check = "(wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('officer')))"
    can_read = (
        f"(wb.can_access(institution_id, NULL, false) OR wb.manages(institution_id) "
        f"OR {elevated_check})"
    )
    can_write = (
        f"(wb.can_access(institution_id, NULL, true) OR wb.manages(institution_id) "
        f"OR {elevated_check})"
    )

    for tbl in p8_tables:
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


def downgrade() -> None:
    raise RuntimeError("Operational security changes require a reviewed forward migration")
