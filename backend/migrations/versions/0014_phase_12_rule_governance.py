"""Phase 12 rule-change governance, replay, dual control, and remedy scenarios.

Revision ID: 0014_phase_12_rule_governance
Revises: 0013_phase_11_media_spatial
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_phase_12_rule_governance"
down_revision = "0013_phase_11_media_spatial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. rule_candidates (draft candidate releases, four gates, dual control)
    op.create_table(
        "rule_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_code", sa.String(60), nullable=False, unique=True),
        sa.Column("target_academic_cycle", sa.String(50), nullable=False),
        sa.Column("numeric_academic_year", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.String(30), nullable=False),
        sa.Column("submission_date", sa.String(30), nullable=False),
        sa.Column("evaluation_time", sa.String(40), nullable=False),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("author_identity", sa.String(100), nullable=False),
        sa.Column("approver_id", sa.String(36)),
        sa.Column("approver_identity", sa.String(100)),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("four_gates", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "candidate_rules", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("release_manifest", sa.JSON()),
        sa.Column("manifest_hash", sa.String(64)),
        sa.Column("published_release_id", sa.String(36)),
        sa.Column("superseded_candidate_id", sa.String(36)),
        sa.Column(
            "conflicts_detected",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("what_if_banner", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_hypothetical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.CheckConstraint(
            "author_id != approver_id OR approver_id IS NULL",
            name="chk_candidate_dual_control",
        ),
    )

    # 2. published_rule_releases (immutable published releases, rollback creates new release)
    op.create_table(
        "published_rule_releases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("release_code", sa.String(60), nullable=False, unique=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("rule_candidates.id", name="fk_pub_release_candidate"),
        ),
        sa.Column("numeric_academic_year", sa.Integer(), nullable=False),
        sa.Column("academic_cycle", sa.String(50), nullable=False),
        sa.Column("effective_date", sa.String(30), nullable=False),
        sa.Column("submission_date", sa.String(30), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("release_manifest", sa.JSON(), nullable=False),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("author_identity", sa.String(100), nullable=False),
        sa.Column("approver_id", sa.String(36), nullable=False),
        sa.Column("approver_identity", sa.String(100), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="PUBLISHED"),
        sa.Column("superseded_by_release_id", sa.String(36)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "adverse_action_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("author_id != approver_id", name="chk_published_dual_control"),
    )

    # 3. rule_impact_simulations (simulation outcomes against frozen runs with what_if banner)
    op.create_table(
        "rule_impact_simulations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("rule_candidates.id", name="fk_sim_candidate"),
            nullable=False,
        ),
        sa.Column("simulated_by", sa.String(36), nullable=False),
        sa.Column(
            "total_runs_simulated",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("what_if_banner", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("diff_summary", sa.JSON(), nullable=False),
        sa.Column("run_diffs", sa.JSON(), nullable=False),
        sa.Column("is_hypothetical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 4. rule_remedies (transparent arithmetic remedies, stage restrictions, advisory only)
    op.create_table(
        "rule_remedies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("finding_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("clause", sa.String(100), nullable=False),
        sa.Column("remedy_type", sa.String(50), nullable=False),
        sa.Column("is_advisory", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "guarantees_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("advisory_wording", sa.Text(), nullable=False),
        sa.Column("calculation_trace", sa.JSON(), nullable=False),
        sa.Column("proposed_remedy_facts", sa.JSON(), nullable=False),
        sa.Column("re_evaluation_result", sa.JSON(), nullable=False),
        sa.Column("findings_closed", sa.JSON(), nullable=False),
        sa.Column("findings_remaining", sa.JSON(), nullable=False),
        sa.Column(
            "allowed_at_current_stage",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("stage_restriction_reason", sa.String(255)),
        sa.Column("is_simulated", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_rule_remedies_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_rule_remedies_application",
        ),
    )

    # 5. replay_bundles (frozen input snapshots, manifests, offline verification files)
    op.create_table(
        "replay_bundles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), nullable=False),
        sa.Column("application_id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("bundle_hash", sa.String(64), nullable=False),
        sa.Column("evaluator_version", sa.String(50), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("files", sa.JSON(), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name="fk_replay_bundles_institution",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name="fk_replay_bundles_application",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            name="fk_replay_bundles_run",
        ),
    )

    # Indexes
    op.create_index(
        "ix_rule_candidates_code",
        "rule_candidates",
        ["candidate_code"],
        unique=True,
    )
    op.create_index(
        "ix_published_rule_releases_code",
        "published_rule_releases",
        ["release_code"],
        unique=True,
    )
    op.create_index(
        "ix_rule_impact_simulations_cand",
        "rule_impact_simulations",
        ["candidate_id"],
    )
    op.create_index(
        "ix_rule_remedies_app_finding",
        "rule_remedies",
        ["application_id", "finding_id"],
    )
    op.create_index(
        "ix_replay_bundles_run",
        "replay_bundles",
        ["run_id"],
    )
    op.create_index(
        "ix_rule_remedies_owner_time",
        "rule_remedies",
        ["institution_id", "created_at", "id"],
    )
    op.create_index(
        "ix_replay_bundles_owner_time",
        "replay_bundles",
        ["institution_id", "created_at", "id"],
    )

    # Triggers for immutable published releases and dual control / alias rejection
    op.execute(
        """
        CREATE OR REPLACE FUNCTION wb.block_published_releases_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'Published rule releases are immutable. '
                'Updates and deletes are prohibited. '
                'Rollback requires a new superseding release.';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_block_published_rule_releases_mutation
        BEFORE UPDATE OR DELETE ON published_rule_releases
        FOR EACH ROW EXECUTE FUNCTION wb.block_published_releases_mutation();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION wb.validate_candidate_approval()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.approver_id IS NOT NULL THEN
                IF NEW.author_id = NEW.approver_id THEN
                    RAISE EXCEPTION
                        'Dual control violation: '
                        'author and approver cannot be the same identity';
                END IF;
                IF NEW.author_identity IS NOT NULL AND NEW.approver_identity IS NOT NULL
                   AND LOWER(TRIM(NEW.author_identity)) = LOWER(TRIM(NEW.approver_identity)) THEN
                    RAISE EXCEPTION
                        'Dual control violation: '
                        'author and approver alias/identity cannot be the same';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_validate_candidate_approval
        BEFORE INSERT OR UPDATE ON rule_candidates
        FOR EACH ROW EXECUTE FUNCTION wb.validate_candidate_approval();
        """
    )

    # RLS Policies on global governance tables
    global_tables = [
        "rule_candidates",
        "published_rule_releases",
        "rule_impact_simulations",
    ]
    elevated_global = (
        "wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('officer') "
        "OR wb.has_role('admin'))"
    )
    for tbl in global_tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {tbl}_read ON {tbl} FOR SELECT "
            "TO wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner "
            "USING (true)"
        )
        op.execute(
            f"CREATE POLICY {tbl}_write ON {tbl} FOR ALL TO wb_app "
            f"USING ({elevated_global}) WITH CHECK ({elevated_global})"
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

    # RLS Policies on tenant-scoped tables
    tenant_tables = [
        "rule_remedies",
        "replay_bundles",
    ]
    elevated_check = "(wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('officer')))"

    for tbl in tenant_tables:
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
