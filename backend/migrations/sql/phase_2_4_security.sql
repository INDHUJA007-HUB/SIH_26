-- Versioned security kernel. Runtime logins are neither table owners nor BYPASSRLS roles.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS wb;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='wb_security_owner') THEN
    CREATE ROLE wb_security_owner NOLOGIN BYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='wb_app') THEN CREATE ROLE wb_app NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='wb_delivery') THEN CREATE ROLE wb_delivery NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='wb_relay') THEN CREATE ROLE wb_relay NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='wb_scanner') THEN CREATE ROLE wb_scanner NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='wb_worker') THEN CREATE ROLE wb_worker NOLOGIN; END IF;
END $$;
GRANT USAGE ON SCHEMA public,wb TO wb_app,wb_delivery,wb_relay,wb_scanner,wb_worker,wb_security_owner;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO wb_security_owner;
GRANT INSERT ON audit_events,access_events TO wb_security_owner;

CREATE OR REPLACE FUNCTION wb.actor_id() RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
 SELECT a.id FROM public.actor_identities a
 WHERE a.issuer=current_setting('wb.issuer',true) AND a.subject=current_setting('wb.subject',true)
 AND NOT a.disabled
 AND a.valid_after<=to_timestamp(NULLIF(current_setting('wb.iat',true),'')::double precision)
 AND to_timestamp(NULLIF(current_setting('wb.exp',true),'')::double precision)>statement_timestamp()
 AND NOT EXISTS(SELECT FROM public.revoked_sessions s WHERE s.issuer=a.issuer
   AND s.session_id=current_setting('wb.sid',true))
$$;
CREATE OR REPLACE FUNCTION wb.elevated() RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT coalesce(current_setting('wb.mfa',true)='true'
 AND to_timestamp(NULLIF(current_setting('wb.auth_time',true),'')::double precision)
 BETWEEN statement_timestamp()-interval '5 minutes' AND statement_timestamp()+interval '30 seconds',false)
$$;
CREATE OR REPLACE FUNCTION wb.has_role(p_role text) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT FROM public.memberships m WHERE m.actor_id=wb.actor_id() AND m.role=p_role
   AND m.revoked_at IS NULL AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp()))
$$;
CREATE OR REPLACE FUNCTION wb.manages(p_institution text) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT FROM public.memberships m JOIN public.institutions i ON i.id=p_institution
 WHERE m.actor_id=wb.actor_id() AND m.role IN ('supervisor','identity_admin')
 AND m.jurisdiction=i.jurisdiction AND m.revoked_at IS NULL
 AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp()))
$$;
CREATE OR REPLACE FUNCTION wb.can_access(p_institution text,p_application text,p_write boolean DEFAULT false)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS(SELECT FROM public.memberships m WHERE m.actor_id=wb.actor_id()
   AND m.institution_id=p_institution AND m.role IN ('institution_editor','institution_viewer')
   AND (NOT p_write OR m.role='institution_editor') AND m.revoked_at IS NULL
   AND (m.expires_at IS NULL OR m.expires_at>statement_timestamp()))
 OR EXISTS(SELECT FROM public.case_assignments a WHERE a.actor_id=wb.actor_id()
   AND a.institution_id=p_institution AND (a.application_id IS NULL OR p_application IS NULL OR a.application_id=p_application)
   AND (NOT p_write OR a.access_role='officer') AND a.revoked_at IS NULL AND a.expires_at>statement_timestamp()
   AND wb.has_role(a.access_role))
 OR (NOT p_write AND wb.elevated() AND EXISTS(SELECT FROM public.emergency_grants e
   WHERE e.requested_by=wb.actor_id() AND e.institution_id=p_institution AND e.application_id=p_application
   AND e.approved_by IS NOT NULL AND e.revoked_at IS NULL AND e.expires_at>statement_timestamp()))
$$;

CREATE OR REPLACE FUNCTION wb.immutable_row() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable record'; END $$;
CREATE OR REPLACE FUNCTION wb.frozen_application() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR OLD.stage='SUBMITTED' THEN RAISE EXCEPTION 'submitted application is immutable'; END IF;
 IF NEW.institution_id<>OLD.institution_id OR NEW.id<>OLD.id THEN RAISE EXCEPTION 'ownership is immutable'; END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION wb.evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (to_jsonb(NEW)-ARRAY['status','reason_code','clean_key','clean_version','metadata','scan_started_at'])
 <> (to_jsonb(OLD)-ARRAY['status','reason_code','clean_key','clean_version','metadata','scan_started_at'])
 THEN RAISE EXCEPTION 'original evidence identity is immutable'; END IF;
 IF OLD.status='ACCEPTED' AND to_jsonb(NEW)<>to_jsonb(OLD) THEN RAISE EXCEPTION 'accepted evidence is immutable'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable_revision BEFORE UPDATE OR DELETE ON application_revisions FOR EACH ROW EXECUTE FUNCTION wb.immutable_row();
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION wb.immutable_row();
CREATE TRIGGER immutable_access BEFORE UPDATE OR DELETE ON access_events FOR EACH ROW EXECUTE FUNCTION wb.immutable_row();
CREATE TRIGGER immutable_derivative BEFORE UPDATE OR DELETE ON evidence_derivatives FOR EACH ROW EXECUTE FUNCTION wb.immutable_row();
CREATE TRIGGER freeze_application BEFORE UPDATE OR DELETE ON applications FOR EACH ROW EXECUTE FUNCTION wb.frozen_application();
CREATE TRIGGER preserve_original BEFORE UPDATE ON evidence_versions FOR EACH ROW EXECUTE FUNCTION wb.evidence_guard();

CREATE OR REPLACE FUNCTION wb.append_audit(p_id text,p_institution text,p_application text,p_kind text,p_payload jsonb,p_request text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE stream_id text:=coalesce(p_institution,'SECURITY'); prior text; seq bigint; body jsonb; result text;
BEGIN
 IF NOT (wb.can_access(p_institution,p_application,false) OR wb.manages(p_institution)
   OR (p_institution IS NULL AND wb.actor_id() IS NOT NULL)
   OR pg_has_role(session_user,'wb_scanner','member') OR pg_has_role(session_user,'wb_worker','member'))
 THEN RAISE EXCEPTION 'audit scope denied'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('audit:'||stream_id,0));
 SELECT a.sha256,a.sequence INTO prior,seq FROM public.audit_events a WHERE a.stream=stream_id ORDER BY sequence DESC LIMIT 1;
 prior:=coalesce(prior,repeat('0',64)); seq:=coalesce(seq,0)+1;
 body:=jsonb_build_object('actor',coalesce(wb.actor_id(),session_user),'kind',p_kind,'payload',p_payload,
                         'request_id',p_request,'recorded_at',clock_timestamp());
 result:=encode(public.digest(convert_to(prior||'|'||stream_id||'|'||seq::text||'|'||body::text,'UTF8'),'sha256'),'hex');
 INSERT INTO public.audit_events(id,stream,institution_id,application_id,sequence,previous_hash,sha256,event)
 VALUES(p_id,stream_id,p_institution,p_application,seq,prior,result,body);
 RETURN result;
END $$;
CREATE OR REPLACE FUNCTION wb.access_attempt(p_id text,p_institution text,p_application text,p_evidence text,p_resource text,p_action text,p_request text,p_allowed boolean)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF wb.actor_id() IS NULL THEN RAISE EXCEPTION 'actor unavailable'; END IF;
 IF p_allowed AND NOT wb.can_access(p_institution,p_application,false) THEN RAISE EXCEPTION 'access scope denied'; END IF;
 INSERT INTO public.access_events(id,actor_id,institution_id,application_id,evidence_id,resource_id,action,result,bytes_served,request_id)
 VALUES(p_id,wb.actor_id(),CASE WHEN p_allowed THEN p_institution END,CASE WHEN p_allowed THEN p_application END,
 CASE WHEN p_allowed THEN p_evidence END,p_resource,p_action,CASE WHEN p_allowed THEN 'STARTED' ELSE 'DENIED' END,0,p_request);
END $$;
CREATE OR REPLACE FUNCTION wb.access_finish(p_id text,p_attempt text,p_bytes bigint,p_result text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE source public.access_events;
BEGIN
 IF NOT pg_has_role(session_user,'wb_delivery','member') THEN RAISE EXCEPTION 'delivery role required'; END IF;
 IF p_result NOT IN ('COMPLETED','ABORTED','FAILED') OR p_bytes<0 THEN RAISE EXCEPTION 'invalid access result'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('access:'||p_attempt,0));
 SELECT * INTO source FROM public.access_events WHERE id=p_attempt AND result='STARTED';
 IF source.id IS NULL OR EXISTS(SELECT FROM public.access_events WHERE parent_event_id=p_attempt) THEN RETURN; END IF;
 INSERT INTO public.access_events(id,actor_id,institution_id,application_id,evidence_id,resource_id,action,result,bytes_served,request_id,parent_event_id)
 VALUES(p_id,source.actor_id,source.institution_id,source.application_id,source.evidence_id,source.resource_id,source.action,p_result,p_bytes,source.request_id,p_attempt);
END $$;

-- RLS protects every institution/case relation. Runtime logins cannot own or bypass it.
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['applications','application_revisions','evidence_slots','upload_sessions','evidence_versions','evidence_derivatives','outbox_events'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY owner_read ON %I FOR SELECT TO wb_app,wb_delivery USING (wb.can_access(institution_id,%s,false))',t,
     CASE WHEN t='applications' THEN 'id' ELSE 'application_id' END);
  EXECUTE format('CREATE POLICY owner_write ON %I FOR ALL TO wb_app USING (wb.can_access(institution_id,%s,true)) WITH CHECK (wb.can_access(institution_id,%s,true))',t,
     CASE WHEN t='applications' THEN 'id' ELSE 'application_id' END,
     CASE WHEN t='applications' THEN 'id' ELSE 'application_id' END);
 END LOOP;
END $$;
ALTER TABLE institutions ENABLE ROW LEVEL SECURITY; ALTER TABLE institutions FORCE ROW LEVEL SECURITY;
CREATE POLICY institution_read ON institutions FOR SELECT TO wb_app USING(wb.can_access(id,NULL,false) OR wb.manages(id));
ALTER TABLE actor_identities ENABLE ROW LEVEL SECURITY; ALTER TABLE actor_identities FORCE ROW LEVEL SECURITY;
CREATE POLICY actor_read ON actor_identities FOR SELECT TO wb_app USING(id=wb.actor_id() OR (wb.elevated() AND (wb.has_role('supervisor') OR wb.has_role('identity_admin'))));
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY; ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY membership_read ON memberships FOR SELECT TO wb_app USING(actor_id=wb.actor_id() OR (wb.elevated() AND wb.has_role('identity_admin')));
CREATE POLICY membership_admin ON memberships FOR ALL TO wb_app USING(wb.elevated() AND wb.has_role('identity_admin')) WITH CHECK(wb.elevated() AND wb.has_role('identity_admin'));
ALTER TABLE revoked_sessions ENABLE ROW LEVEL SECURITY; ALTER TABLE revoked_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY session_self ON revoked_sessions FOR ALL TO wb_app USING(issuer=current_setting('wb.issuer',true) AND session_id=current_setting('wb.sid',true)) WITH CHECK(issuer=current_setting('wb.issuer',true) AND session_id=current_setting('wb.sid',true));
ALTER TABLE case_assignments ENABLE ROW LEVEL SECURITY; ALTER TABLE case_assignments FORCE ROW LEVEL SECURITY;
CREATE POLICY assignment_read ON case_assignments FOR SELECT TO wb_app USING(actor_id=wb.actor_id() OR wb.manages(institution_id));
CREATE POLICY assignment_manage ON case_assignments FOR ALL TO wb_app USING(wb.elevated() AND wb.manages(institution_id)) WITH CHECK(wb.elevated() AND wb.manages(institution_id));
ALTER TABLE emergency_grants ENABLE ROW LEVEL SECURITY; ALTER TABLE emergency_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY emergency_read ON emergency_grants FOR SELECT TO wb_app USING(requested_by=wb.actor_id() OR wb.manages(institution_id));
CREATE POLICY emergency_request ON emergency_grants FOR INSERT TO wb_app WITH CHECK(requested_by=wb.actor_id() AND wb.elevated() AND wb.has_role('officer') AND approved_by IS NULL);
CREATE POLICY emergency_manage ON emergency_grants FOR UPDATE TO wb_app USING(wb.elevated() AND wb.manages(institution_id)) WITH CHECK(wb.elevated() AND wb.manages(institution_id));
ALTER TABLE command_receipts ENABLE ROW LEVEL SECURITY; ALTER TABLE command_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY receipt_self ON command_receipts FOR ALL TO wb_app USING(actor_id=wb.actor_id()) WITH CHECK(actor_id=wb.actor_id());
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY; ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_read ON audit_events FOR SELECT TO wb_app USING(wb.can_access(institution_id,application_id,false) OR (institution_id IS NULL AND wb.elevated() AND wb.has_role('supervisor')));
ALTER TABLE access_events ENABLE ROW LEVEL SECURITY; ALTER TABLE access_events FORCE ROW LEVEL SECURITY;
CREATE POLICY access_read ON access_events FOR SELECT TO wb_app USING(actor_id=wb.actor_id() OR (wb.can_access(institution_id,application_id,false) AND (wb.has_role('officer') OR wb.has_role('auditor'))));
ALTER TABLE operations_tasks ENABLE ROW LEVEL SECURITY; ALTER TABLE operations_tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY task_read ON operations_tasks FOR SELECT TO wb_app USING(wb.can_access(institution_id,application_id,false));
ALTER TABLE consumer_receipts ENABLE ROW LEVEL SECURITY; ALTER TABLE consumer_receipts FORCE ROW LEVEL SECURITY;

CREATE POLICY scanner_evidence ON evidence_versions FOR ALL TO wb_scanner USING(true) WITH CHECK(true);
CREATE POLICY scanner_uploads ON upload_sessions FOR SELECT TO wb_scanner USING(true);
CREATE POLICY scanner_derivatives ON evidence_derivatives FOR ALL TO wb_scanner USING(true) WITH CHECK(true);
CREATE POLICY scanner_outbox ON outbox_events FOR SELECT TO wb_scanner USING(true);
CREATE POLICY relay_outbox ON outbox_events FOR ALL TO wb_relay USING(true) WITH CHECK(true);
CREATE POLICY worker_outbox ON outbox_events FOR SELECT TO wb_worker USING(true);
CREATE POLICY worker_receipts ON consumer_receipts FOR ALL TO wb_worker,wb_scanner USING(true) WITH CHECK(true);
CREATE POLICY worker_tasks ON operations_tasks FOR ALL TO wb_worker,wb_scanner USING(true) WITH CHECK(true);

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM wb_app,wb_delivery,wb_relay,wb_worker,wb_scanner;
GRANT SELECT ON institutions,actor_identities,memberships,case_assignments,emergency_grants,applications,application_revisions,evidence_slots,upload_sessions,evidence_versions,evidence_derivatives,command_receipts,audit_events,access_events,operations_tasks TO wb_app;
GRANT INSERT ON memberships,case_assignments,emergency_grants,revoked_sessions,applications,application_revisions,evidence_slots,upload_sessions,evidence_versions,command_receipts,outbox_events TO wb_app;
GRANT UPDATE(revoked_at) ON memberships,case_assignments TO wb_app;
GRANT UPDATE(approved_by,revoked_at) ON emergency_grants TO wb_app;
GRANT UPDATE(stage,revision,declared_facts) ON applications TO wb_app;
GRANT UPDATE(status,object_version,multipart_id) ON upload_sessions TO wb_app;
GRANT SELECT ON evidence_versions,evidence_derivatives TO wb_delivery;
GRANT SELECT ON outbox_events TO wb_relay;
GRANT UPDATE(lease_owner,lease_until,attempts,available_at,delivered_at) ON outbox_events TO wb_relay;
GRANT SELECT ON outbox_events,consumer_receipts,operations_tasks TO wb_worker;
GRANT INSERT ON consumer_receipts,operations_tasks TO wb_worker;
GRANT SELECT ON outbox_events,consumer_receipts,evidence_versions,upload_sessions,evidence_derivatives,operations_tasks TO wb_scanner;
GRANT INSERT ON consumer_receipts,evidence_derivatives,operations_tasks TO wb_scanner;
GRANT UPDATE(status,reason_code,clean_key,clean_version,metadata,scan_started_at) ON evidence_versions TO wb_scanner;

DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT p.oid::regprocedure AS signature FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid WHERE n.nspname='wb' AND p.prosecdef LOOP
   EXECUTE format('ALTER FUNCTION %s OWNER TO wb_security_owner',f.signature);
 END LOOP;
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA wb FROM PUBLIC;
GRANT EXECUTE ON FUNCTION wb.actor_id(),wb.elevated(),wb.has_role(text),wb.manages(text),wb.can_access(text,text,boolean) TO wb_app,wb_delivery,wb_security_owner;
GRANT EXECUTE ON FUNCTION wb.append_audit(text,text,text,text,jsonb,text) TO wb_app,wb_scanner,wb_worker;
GRANT EXECUTE ON FUNCTION wb.access_attempt(text,text,text,text,text,text,text,boolean) TO wb_app,wb_delivery;
GRANT EXECUTE ON FUNCTION wb.access_finish(text,text,bigint,text) TO wb_delivery;
