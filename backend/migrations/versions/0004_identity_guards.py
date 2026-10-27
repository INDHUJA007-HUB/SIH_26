"""Concurrent duty separation and assignment/identity integrity beyond HTTP checks."""

from alembic import op

revision = "0004_identity_guards"
down_revision = "0003_security_kernel"
branch_labels = None
depends_on = None

SQL = r"""
CREATE OR REPLACE FUNCTION wb.membership_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
DECLARE person text; actor_person text;
BEGIN
 SELECT person_id INTO person FROM public.actor_identities WHERE id=NEW.actor_id;
 PERFORM pg_advisory_xact_lock(hashtextextended('person-roles:'||person,0));
 IF NEW.role IN ('rule_author','rule_approver') AND NEW.revoked_at IS NULL THEN
  IF EXISTS(SELECT FROM public.memberships m JOIN public.actor_identities a ON a.id=m.actor_id
   WHERE a.person_id=person AND m.role IN ('rule_author','rule_approver') AND m.role<>NEW.role
   AND m.revoked_at IS NULL AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp()))
  THEN RAISE EXCEPTION 'independent rule author and approver required' USING ERRCODE='23514'; END IF;
 END IF;
 IF wb.actor_id() IS NOT NULL AND TG_OP='INSERT' THEN
  SELECT person_id INTO actor_person FROM public.actor_identities WHERE id=wb.actor_id();
  IF person=actor_person OR NEW.role NOT IN ('institution_editor','institution_viewer','officer','auditor','rule_author','rule_approver')
   THEN RAISE EXCEPTION 'organizational role review required' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION wb.assignment_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.access_role NOT IN ('officer','auditor') OR NOT EXISTS(SELECT FROM public.memberships m
   JOIN public.actor_identities a ON a.id=m.actor_id WHERE a.id=NEW.actor_id AND NOT a.disabled
   AND m.role=NEW.access_role AND m.revoked_at IS NULL AND m.jurisdiction=(SELECT jurisdiction FROM public.institutions WHERE id=NEW.institution_id)
   AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp()))
   THEN RAISE EXCEPTION 'valid scoped reviewer role required' USING ERRCODE='23514'; END IF;
  IF NEW.expires_at>statement_timestamp()+interval '7 days' OR NEW.expires_at<=statement_timestamp()
   THEN RAISE EXCEPTION 'invalid assignment lifetime' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION wb.emergency_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.expires_at>NEW.created_at+interval '1 hour' THEN RAISE EXCEPTION 'emergency access is bounded' USING ERRCODE='23514'; END IF;
 IF NEW.approved_by IS NOT NULL AND (SELECT person_id FROM public.actor_identities WHERE id=NEW.requested_by)
  =(SELECT person_id FROM public.actor_identities WHERE id=NEW.approved_by)
  THEN RAISE EXCEPTION 'independent emergency approver required' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND OLD.approved_by IS NOT NULL AND NEW.approved_by<>OLD.approved_by
  THEN RAISE EXCEPTION 'approval is immutable' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
ALTER FUNCTION wb.membership_guard() OWNER TO wb_security_owner;
ALTER FUNCTION wb.assignment_guard() OWNER TO wb_security_owner;
ALTER FUNCTION wb.emergency_guard() OWNER TO wb_security_owner;
REVOKE ALL ON FUNCTION wb.membership_guard(),wb.assignment_guard(),wb.emergency_guard() FROM PUBLIC;
CREATE TRIGGER membership_integrity BEFORE INSERT OR UPDATE ON memberships FOR EACH ROW EXECUTE FUNCTION wb.membership_guard();
CREATE TRIGGER assignment_integrity BEFORE INSERT OR UPDATE ON case_assignments FOR EACH ROW EXECUTE FUNCTION wb.assignment_guard();
CREATE TRIGGER emergency_integrity BEFORE INSERT OR UPDATE ON emergency_grants FOR EACH ROW EXECUTE FUNCTION wb.emergency_guard();
CREATE POLICY actor_admin_update ON actor_identities FOR UPDATE TO wb_app USING(wb.elevated() AND wb.has_role('identity_admin')) WITH CHECK(wb.elevated() AND wb.has_role('identity_admin'));
GRANT UPDATE(disabled,valid_after) ON actor_identities TO wb_app;
CREATE POLICY scanner_expire_upload ON upload_sessions FOR UPDATE TO wb_scanner USING(status='PENDING' AND expires_at<statement_timestamp()) WITH CHECK(status IN ('EXPIRED','ABORTED'));
GRANT UPDATE(status) ON upload_sessions TO wb_scanner;
GRANT UPDATE(state) ON operations_tasks TO wb_scanner;
"""


def upgrade() -> None:
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(SQL)


def downgrade() -> None:
    raise RuntimeError("Identity security changes require a reviewed forward migration")
