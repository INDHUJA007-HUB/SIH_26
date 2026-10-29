"""Phase 15 retention policies, legal holds, purge manifests and operations containment.

Revision ID: 0016_phase_15_ops_retention
Revises: 0015_phase_14_pilot_scope
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_phase_15_ops_retention"
down_revision = "0015_phase_14_pilot_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. retention_policies
    op.create_table(
        "retention_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_class", sa.String(50), nullable=False),
        sa.Column("retention_basis", sa.String(50), nullable=False),
        sa.Column("retention_period_days", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_retention_policies_class", "retention_policies", ["data_class"])

    # 2. legal_holds
    op.create_table(
        "legal_holds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("institution_id", sa.String(36), sa.ForeignKey("institutions.id"), nullable=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("evidence_slot_id", sa.String(36), nullable=True),
        sa.Column("matter_reference", sa.String(150), nullable=False),
        sa.Column("legal_basis", sa.Text(), nullable=False),
        sa.Column("placed_by", sa.String(36), nullable=False),
        sa.Column(
            "placed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("released_by", sa.String(36), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_legal_holds_app", "legal_holds", ["application_id"])
    op.create_index("ix_legal_holds_inst", "legal_holds", ["institution_id"])
    op.create_index("ix_legal_holds_active", "legal_holds", ["is_active"])

    # 3. purge_manifests
    op.create_table(
        "purge_manifests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "policy_id", sa.String(36), sa.ForeignKey("retention_policies.id"), nullable=False
        ),
        sa.Column("data_class", sa.String(50), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("purged_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped_held_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "skipped_dependency_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("purged_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("purged_derivative_keys", sa.JSON(), nullable=False),
        sa.Column("bytes_freed", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("executed_by", sa.String(36), nullable=False),
        sa.Column(
            "executed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("sha256_digest", sa.String(64), nullable=False),
        sa.Column("audit_event_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_purge_manifests_policy", "purge_manifests", ["policy_id"])

    # 4. incident_containments
    op.create_table(
        "incident_containments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=False),
        sa.Column("containment_action", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("contained_by", sa.String(36), nullable=False),
        sa.Column(
            "contained_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("released_by", sa.String(36), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_event_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_incident_containments_target",
        "incident_containments",
        ["target_type", "target_id"],
    )

    conn = op.get_bind()
    conn.execute(
        sa.text("""
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE retention_policies, legal_holds, purge_manifests, incident_containments TO wb_app, wb_worker, wb_scanner, wb_relay, wb_security_owner;
        GRANT SELECT, UPDATE ON TABLE outbox_events TO wb_app;

        ALTER TABLE retention_policies ENABLE ROW LEVEL SECURITY;
        ALTER TABLE legal_holds ENABLE ROW LEVEL SECURITY;
        ALTER TABLE purge_manifests ENABLE ROW LEVEL SECURITY;
        ALTER TABLE incident_containments ENABLE ROW LEVEL SECURITY;

        -- legal_holds
        DROP POLICY IF EXISTS legal_hold_read ON legal_holds;
        CREATE POLICY legal_hold_read ON legal_holds FOR SELECT TO wb_app
            USING (institution_id IS NULL OR wb.can_access(institution_id, NULL, false) OR wb.has_role('supervisor') OR wb.has_role('auditor') OR (wb.elevated() AND wb.has_role('supervisor')));
        CREATE POLICY legal_hold_write ON legal_holds FOR ALL TO wb_app
            USING (wb.elevated() AND wb.has_role('supervisor'))
            WITH CHECK (wb.elevated() AND wb.has_role('supervisor'));
        CREATE POLICY worker_legal_holds ON legal_holds FOR ALL TO wb_worker, wb_security_owner
            USING (true) WITH CHECK (true);

        -- retention_policies
        CREATE POLICY retention_policies_read ON retention_policies FOR SELECT TO wb_app
            USING (true);
        CREATE POLICY retention_policies_write ON retention_policies FOR ALL TO wb_app
            USING (wb.elevated() AND wb.has_role('supervisor'))
            WITH CHECK (wb.elevated() AND wb.has_role('supervisor'));
        CREATE POLICY worker_retention_policies ON retention_policies FOR ALL TO wb_worker, wb_security_owner
            USING (true) WITH CHECK (true);

        -- purge_manifests
        CREATE POLICY purge_manifests_read ON purge_manifests FOR SELECT TO wb_app
            USING (true);
        CREATE POLICY purge_manifests_write ON purge_manifests FOR ALL TO wb_app
            USING (wb.elevated() AND wb.has_role('supervisor'))
            WITH CHECK (wb.elevated() AND wb.has_role('supervisor'));
        CREATE POLICY worker_purge_manifests ON purge_manifests FOR ALL TO wb_worker, wb_security_owner
            USING (true) WITH CHECK (true);

        -- Evidence and derivatives purge access for elevated supervisors
        GRANT SELECT, DELETE ON TABLE evidence_versions, evidence_derivatives TO wb_app;

        DROP POLICY IF EXISTS retention_supervisor_derivatives ON evidence_derivatives;
        CREATE POLICY retention_supervisor_derivatives ON evidence_derivatives FOR ALL TO wb_app
            USING (wb.elevated() AND wb.has_role('supervisor'))
            WITH CHECK (wb.elevated() AND wb.has_role('supervisor'));

        CREATE OR REPLACE FUNCTION wb.derivative_retention_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND wb.elevated() AND wb.has_role('supervisor') THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'immutable record';
        END;
        $$;

        DROP TRIGGER IF EXISTS immutable_derivative ON evidence_derivatives;
        CREATE TRIGGER immutable_derivative BEFORE UPDATE OR DELETE ON evidence_derivatives
            FOR EACH ROW EXECUTE FUNCTION wb.derivative_retention_guard();

        DROP POLICY IF EXISTS retention_supervisor_evidence ON evidence_versions;
        CREATE POLICY retention_supervisor_evidence ON evidence_versions FOR ALL TO wb_app
            USING (wb.elevated() AND wb.has_role('supervisor'))
            WITH CHECK (wb.elevated() AND wb.has_role('supervisor'));

        -- incident_containments
        CREATE POLICY incident_containments_read ON incident_containments FOR SELECT TO wb_app
            USING (true);
        CREATE POLICY incident_containments_write ON incident_containments FOR ALL TO wb_app
            USING (wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('operator') OR wb.has_role('platform_admin')))
            WITH CHECK (wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('operator') OR wb.has_role('platform_admin')));
        CREATE POLICY worker_incident_containments ON incident_containments FOR ALL TO wb_worker, wb_security_owner
            USING (true) WITH CHECK (true);

        -- Operations reconciliation and outbox access
        GRANT SELECT, UPDATE(lease_owner, lease_until, attempts, available_at, delivered_at) ON TABLE outbox_events TO wb_app;

        DROP POLICY IF EXISTS app_outbox ON outbox_events;
        CREATE POLICY app_outbox ON outbox_events FOR ALL TO wb_app
            USING (wb.has_role('supervisor') OR wb.has_role('operator'))
            WITH CHECK (wb.has_role('supervisor') OR wb.has_role('operator'));

        DROP POLICY IF EXISTS app_operations_reconcile ON operations;
        CREATE POLICY app_operations_reconcile ON operations FOR ALL TO wb_app
            USING (wb.has_role('supervisor') OR wb.has_role('operator'))
            WITH CHECK (wb.has_role('supervisor') OR wb.has_role('operator'));

        -- Session revocation by elevated supervisors for incident containment
        DROP POLICY IF EXISTS session_supervisor ON revoked_sessions;
        CREATE POLICY session_supervisor ON revoked_sessions FOR ALL TO wb_app
            USING (wb.elevated() AND wb.has_role('supervisor'))
            WITH CHECK (wb.elevated() AND wb.has_role('supervisor'));

        -- Compromised actor isolation and containment release by elevated supervisors
        DROP POLICY IF EXISTS actor_supervisor_contain ON actor_identities;
        CREATE POLICY actor_supervisor_contain ON actor_identities FOR UPDATE TO wb_app
            USING (wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('identity_admin')))
            WITH CHECK (wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('identity_admin')));

        CREATE OR REPLACE FUNCTION wb.admin_scope_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public AS $$
        DECLARE caller text:=wb.actor_id(); person text;
        BEGIN
         IF caller IS NULL THEN RETURN NEW; END IF;
         IF TG_TABLE_NAME='memberships' THEN
          IF NOT wb.elevated() OR NOT EXISTS(SELECT FROM public.memberships m
           WHERE m.actor_id=caller AND m.role='identity_admin' AND m.jurisdiction=NEW.jurisdiction
           AND m.revoked_at IS NULL AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp()))
           OR NEW.role IN ('supervisor','identity_admin')
          THEN RAISE EXCEPTION 'scoped administrator required' USING ERRCODE='23514'; END IF;
          IF NEW.institution_id IS NOT NULL AND NOT EXISTS(SELECT FROM public.institutions i
           WHERE i.id=NEW.institution_id AND i.jurisdiction=NEW.jurisdiction)
          THEN RAISE EXCEPTION 'membership jurisdiction differs' USING ERRCODE='23514'; END IF;
         ELSIF TG_TABLE_NAME='actor_identities' THEN
          IF wb.elevated() AND wb.has_role('supervisor') THEN
           RETURN NEW;
          END IF;
          person:=OLD.person_id;
          IF person=(SELECT person_id FROM public.actor_identities WHERE id=caller)
           OR EXISTS(SELECT FROM public.memberships target JOIN public.actor_identities a ON a.id=target.actor_id
            WHERE a.person_id=person AND target.revoked_at IS NULL
            AND (target.expires_at IS NULL OR target.expires_at>statement_timestamp())
            AND (target.role IN ('supervisor','identity_admin') OR NOT EXISTS(SELECT FROM public.memberships m
              WHERE m.actor_id=caller AND m.role='identity_admin' AND m.jurisdiction=target.jurisdiction
              AND m.revoked_at IS NULL AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp()))))
           OR NOT NEW.disabled OR NOT wb.elevated() OR NOT wb.has_role('identity_admin')
          THEN RAISE EXCEPTION 'scoped disable authority required' USING ERRCODE='23514'; END IF;
         END IF;
         RETURN NEW;
        END $$;

        -- Access assurance sweep policies
        DROP POLICY IF EXISTS assignment_supervisor_read ON case_assignments;
        CREATE POLICY assignment_supervisor_read ON case_assignments FOR SELECT TO wb_app
            USING (wb.has_role('supervisor'));

        DROP POLICY IF EXISTS assignment_sweep ON case_assignments;
        CREATE POLICY assignment_sweep ON case_assignments FOR UPDATE TO wb_app
            USING (wb.has_role('supervisor'))
            WITH CHECK (wb.has_role('supervisor'));

        DROP POLICY IF EXISTS membership_supervisor_read ON memberships;
        CREATE POLICY membership_supervisor_read ON memberships FOR SELECT TO wb_app
            USING (wb.has_role('supervisor'));

        DROP POLICY IF EXISTS membership_sweep ON memberships;
        CREATE POLICY membership_sweep ON memberships FOR UPDATE TO wb_app
            USING (wb.has_role('supervisor'))
            WITH CHECK (wb.has_role('supervisor'));
    """)
    )


def downgrade() -> None:
    raise RuntimeError("Phase 15 schema downgrade is not permitted; forward roll only.")
