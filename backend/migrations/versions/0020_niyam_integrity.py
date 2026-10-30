"""Bound post-submission renewal upload authority and policy/booking integrity."""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE approval_upload_permits (
       id text PRIMARY KEY, institution_id text NOT NULL, application_id text NOT NULL,
       obligation_id text NOT NULL REFERENCES approval_obligations(id), slot_id text NOT NULL,
       authorized_by text NOT NULL REFERENCES actor_identities(id), source_reference text NOT NULL,
       expires_at timestamptz NOT NULL, revoked_at timestamptz,
       FOREIGN KEY(institution_id,application_id,slot_id) REFERENCES evidence_slots(institution_id,application_id,id)
      );
      ALTER TABLE approval_upload_permits ENABLE ROW LEVEL SECURITY;
      ALTER TABLE approval_upload_permits FORCE ROW LEVEL SECURITY;
      GRANT SELECT,INSERT ON approval_upload_permits TO wb_app;
      CREATE POLICY permit_read ON approval_upload_permits FOR SELECT TO wb_app USING(
       wb.can_access(institution_id,application_id,false) OR wb.manages(institution_id));
      CREATE POLICY permit_issue ON approval_upload_permits FOR INSERT TO wb_app WITH CHECK(
       wb.elevated() AND (wb.manages(institution_id) OR (wb.has_role('officer') AND wb.can_access(institution_id,application_id,true))
       OR wb.niyam_role('REGIONAL',(SELECT region FROM approval_obligations WHERE id=obligation_id),application_id)
       OR wb.niyam_role('BUREAU',(SELECT region FROM approval_obligations WHERE id=obligation_id),application_id)));
      CREATE FUNCTION wb.niyam_pack_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
       IF OLD.state='PUBLISHED' THEN RAISE EXCEPTION 'published pack is immutable' USING ERRCODE='23514'; END IF;
       IF NEW.content::text<>OLD.content::text OR NEW.sha256<>OLD.sha256 OR NEW.author_id<>OLD.author_id
       THEN RAISE EXCEPTION 'publication cannot replace authored content' USING ERRCODE='23514'; END IF;
       IF NOT wb.distinct_people(NEW.author_id,NEW.approver_id)
       THEN RAISE EXCEPTION 'independent approver required' USING ERRCODE='23514'; END IF;
       RETURN NEW; END $$;
      CREATE TRIGGER pack_integrity BEFORE UPDATE ON approval_process_packs
       FOR EACH ROW EXECUTE FUNCTION wb.niyam_pack_guard();
      CREATE FUNCTION wb.niyam_case_guard() RETURNS trigger LANGUAGE plpgsql AS $$
       DECLARE expected_region text; BEGIN
       SELECT jurisdiction INTO expected_region FROM applications WHERE id=NEW.application_id AND institution_id=NEW.institution_id;
       IF expected_region IS DISTINCT FROM NEW.region THEN
        RAISE EXCEPTION 'case owner/region mismatch' USING ERRCODE='23514'; END IF;
       IF TG_OP='UPDATE' AND (NEW.pack_id<>OLD.pack_id OR NEW.route<>OLD.route OR NEW.received_at<>OLD.received_at
        OR NEW.application_id<>OLD.application_id OR NEW.institution_id<>OLD.institution_id) THEN
        RAISE EXCEPTION 'case lineage is immutable' USING ERRCODE='23514'; END IF;
       RETURN NEW; END $$;
      CREATE TRIGGER case_integrity BEFORE INSERT OR UPDATE ON approval_cases
       FOR EACH ROW EXECUTE FUNCTION wb.niyam_case_guard();
      DROP POLICY alert_read ON approval_deadline_alerts;
      CREATE POLICY alert_read ON approval_deadline_alerts FOR SELECT TO wb_app USING(
       wb.niyam_access(institution_id,application_id,COALESCE((SELECT jurisdiction FROM applications WHERE id=application_id),
        (SELECT jurisdiction FROM institutions WHERE id=institution_id))) AND (
       recipient_role='INSTITUTION'
       OR (recipient_role='OFFICER' AND wb.elevated() AND (wb.has_role('officer') OR wb.has_role('supervisor')))
       OR wb.niyam_role(recipient_role,COALESCE((SELECT jurisdiction FROM applications WHERE id=application_id),
        (SELECT jurisdiction FROM institutions WHERE id=institution_id)),application_id)));
    """)


def downgrade() -> None:
    raise RuntimeError("Preserve renewal authorization history; use a reviewed forward migration")
