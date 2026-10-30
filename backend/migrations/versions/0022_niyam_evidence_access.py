"""Delegated reviewers use the existing audited evidence delivery boundary."""

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE FUNCTION wb.niyam_delegated_read(p_inst text,p_app text) RETURNS boolean
       LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
       SELECT wb.elevated() AND EXISTS(SELECT FROM public.institutions i WHERE i.id=p_inst AND (
        (wb.has_role('supervisor') AND wb.manages(p_inst))
        OR wb.niyam_role('REGIONAL',i.jurisdiction,p_app)
        OR wb.niyam_role('BUREAU',i.jurisdiction,p_app)
        OR wb.niyam_role('AUTHORITY',i.jurisdiction,p_app)
        OR wb.niyam_role('COMMITTEE',i.jurisdiction,p_app)))
       AND (p_app IS NULL OR EXISTS(SELECT FROM public.applications a WHERE a.id=p_app AND a.institution_id=p_inst)) $$;
      ALTER FUNCTION wb.niyam_delegated_read(text,text) OWNER TO wb_security_owner;
      REVOKE ALL ON FUNCTION wb.niyam_delegated_read(text,text) FROM PUBLIC;
      GRANT EXECUTE ON FUNCTION wb.niyam_delegated_read(text,text) TO wb_app,wb_delivery,wb_security_owner;
      CREATE OR REPLACE FUNCTION wb.can_access(p_institution text,p_application text,p_write boolean DEFAULT false)
       RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
       SELECT EXISTS(SELECT FROM public.memberships m WHERE m.actor_id=wb.actor_id()
        AND m.institution_id=p_institution AND m.role IN ('institution_editor','institution_viewer')
        AND (NOT p_write OR m.role='institution_editor') AND m.revoked_at IS NULL
        AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp()))
       OR EXISTS(SELECT FROM public.case_assignments a JOIN public.institutions i ON i.id=a.institution_id
        WHERE a.actor_id=wb.actor_id() AND a.institution_id=p_institution
        AND (a.application_id IS NULL OR p_application IS NULL OR a.application_id=p_application)
        AND (NOT p_write OR a.access_role='officer') AND a.revoked_at IS NULL AND a.expires_at>statement_timestamp()
        AND EXISTS(SELECT FROM public.memberships m WHERE m.actor_id=wb.actor_id() AND m.role=a.access_role
         AND m.jurisdiction=i.jurisdiction AND m.revoked_at IS NULL
         AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp())))
       OR (NOT p_write AND wb.elevated() AND wb.has_role('officer')
        AND EXISTS(SELECT FROM public.emergency_grants e WHERE e.requested_by=wb.actor_id()
         AND e.institution_id=p_institution AND e.application_id=p_application AND e.approved_by IS NOT NULL
         AND e.revoked_at IS NULL AND e.expires_at>statement_timestamp()))
       OR (NOT p_write AND wb.niyam_delegated_read(p_institution,p_application)) $$;
    """)


def downgrade() -> None:
    raise RuntimeError("Review active delegation and delivery sessions before removing access support")
