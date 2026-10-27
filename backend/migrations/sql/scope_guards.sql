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
ALTER FUNCTION wb.admin_scope_guard() OWNER TO wb_security_owner;
REVOKE ALL ON FUNCTION wb.admin_scope_guard() FROM PUBLIC;
CREATE TRIGGER scoped_membership BEFORE INSERT OR UPDATE ON memberships FOR EACH ROW EXECUTE FUNCTION wb.admin_scope_guard();
CREATE TRIGGER scoped_identity BEFORE UPDATE ON actor_identities FOR EACH ROW EXECUTE FUNCTION wb.admin_scope_guard();

CREATE OR REPLACE FUNCTION wb.intake_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='evidence_versions' AND TG_OP='INSERT' THEN
  IF NEW.status<>'QUARANTINED' OR NEW.clean_key IS NOT NULL OR NEW.clean_version IS NOT NULL
  THEN RAISE EXCEPTION 'intake begins in quarantine' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='evidence_versions' THEN
  IF OLD.status IN ('ACCEPTED','REJECTED') AND to_jsonb(NEW)<>to_jsonb(OLD)
  THEN RAISE EXCEPTION 'terminal evidence is immutable' USING ERRCODE='23514'; END IF;
  IF NEW.status NOT IN ('QUARANTINED','SCANNING','SCAN_FAILED','ACCEPTED','REJECTED')
   OR (NEW.status='ACCEPTED' AND (NEW.clean_key IS NULL OR NEW.clean_version IS NULL))
  THEN RAISE EXCEPTION 'invalid evidence state' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='evidence_slots' THEN
  IF NOT EXISTS(SELECT FROM public.applications a WHERE a.id=NEW.application_id AND a.stage='DRAFT')
  THEN RAISE EXCEPTION 'slots require draft authority' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION wb.intake_guard() FROM PUBLIC;
CREATE TRIGGER intake_state BEFORE INSERT OR UPDATE ON evidence_versions FOR EACH ROW EXECUTE FUNCTION wb.intake_guard();
CREATE TRIGGER draft_slot BEFORE INSERT ON evidence_slots FOR EACH ROW EXECUTE FUNCTION wb.intake_guard();

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
$$;
ALTER FUNCTION wb.can_access(text,text,boolean) OWNER TO wb_security_owner;
