CREATE TABLE approval_process_packs (
 id text PRIMARY KEY, state text NOT NULL CHECK(state IN ('DRAFT','PUBLISHED')),
 content json NOT NULL, sha256 text NOT NULL, author_id text NOT NULL REFERENCES actor_identities(id),
 approver_id text REFERENCES actor_identities(id), created_at timestamptz NOT NULL DEFAULT now(),
 published_at timestamptz,
 CHECK(state <> 'PUBLISHED' OR (approver_id IS NOT NULL AND approver_id <> author_id AND published_at IS NOT NULL))
);
CREATE TABLE approval_access_grants (
 id text PRIMARY KEY, actor_id text NOT NULL REFERENCES actor_identities(id),
 role text NOT NULL CHECK(role IN ('REGIONAL','BUREAU','COMMITTEE','AUTHORITY')),
 region text NOT NULL, application_id text REFERENCES applications(id), source_reference text NOT NULL,
 granted_by text NOT NULL REFERENCES actor_identities(id), expires_at timestamptz NOT NULL,
 revoked_at timestamptz, CHECK(actor_id <> granted_by),
 CHECK(role <> 'COMMITTEE' OR application_id IS NOT NULL)
);
GRANT SELECT ON approval_access_grants TO wb_security_owner;
CREATE FUNCTION wb.niyam_role(p_role text,p_region text,p_application text) RETURNS boolean
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
 SELECT wb.elevated() AND EXISTS(SELECT FROM public.approval_access_grants g
 WHERE g.actor_id=wb.actor_id() AND g.role=p_role AND g.revoked_at IS NULL
 AND g.expires_at>statement_timestamp() AND (g.region=p_region OR g.region='*')
 AND (g.application_id IS NULL OR g.application_id=p_application)) $$;
ALTER FUNCTION wb.niyam_role(text,text,text) OWNER TO wb_security_owner;
REVOKE ALL ON FUNCTION wb.niyam_role(text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION wb.niyam_role(text,text,text) TO wb_app;
CREATE FUNCTION wb.niyam_access(p_inst text,p_app text,p_region text) RETURNS boolean
 LANGUAGE sql STABLE AS $$ SELECT wb.can_access(p_inst,p_app,false)
 OR (wb.elevated() AND wb.has_role('supervisor') AND wb.manages(p_inst))
 OR wb.niyam_role('REGIONAL',p_region,p_app) OR wb.niyam_role('BUREAU',p_region,p_app)
 OR wb.niyam_role('COMMITTEE',p_region,p_app) OR wb.niyam_role('AUTHORITY',p_region,p_app) $$;
REVOKE ALL ON FUNCTION wb.niyam_access(text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION wb.niyam_access(text,text,text) TO wb_app;
CREATE FUNCTION wb.distinct_people(a text,b text) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
 SET search_path=pg_catalog,public AS $$ SELECT count(DISTINCT person_id)=2 FROM public.actor_identities WHERE id IN (a,b) $$;
ALTER FUNCTION wb.distinct_people(text,text) OWNER TO wb_security_owner;
REVOKE ALL ON FUNCTION wb.distinct_people(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION wb.distinct_people(text,text) TO wb_app;
CREATE POLICY niyam_institution_read ON institutions FOR SELECT TO wb_app USING(
 wb.niyam_role('REGIONAL',jurisdiction,NULL) OR wb.niyam_role('BUREAU',jurisdiction,NULL) OR wb.niyam_role('AUTHORITY',jurisdiction,NULL));
CREATE POLICY niyam_application_read ON applications FOR SELECT TO wb_app USING(
 wb.niyam_role('REGIONAL',jurisdiction,id) OR wb.niyam_role('BUREAU',jurisdiction,id)
 OR wb.niyam_role('AUTHORITY',jurisdiction,id) OR wb.niyam_role('COMMITTEE',jurisdiction,id));
CREATE POLICY niyam_evidence_read ON evidence_versions FOR SELECT TO wb_app USING(EXISTS(
 SELECT FROM applications a WHERE a.id=application_id AND (
 wb.niyam_role('REGIONAL',a.jurisdiction,a.id) OR wb.niyam_role('BUREAU',a.jurisdiction,a.id)
 OR wb.niyam_role('AUTHORITY',a.jurisdiction,a.id) OR wb.niyam_role('COMMITTEE',a.jurisdiction,a.id))));
CREATE TABLE approval_cases (
 id text PRIMARY KEY, institution_id text NOT NULL REFERENCES institutions(id),
 application_id text NOT NULL UNIQUE, region text NOT NULL,
 pack_id text NOT NULL REFERENCES approval_process_packs(id), route text NOT NULL, stage text NOT NULL,
 status text NOT NULL CHECK(status IN ('ACTIVE','CLOSED')), revision integer NOT NULL CHECK(revision>0),
 generation integer NOT NULL CHECK(generation>0), received_at timestamptz NOT NULL,
 stage_entered_at timestamptz NOT NULL, due_at timestamptz, pauses json NOT NULL DEFAULT '[]',
 milestones json NOT NULL DEFAULT '{}', facts json NOT NULL DEFAULT '{}',
 UNIQUE(institution_id,application_id,id),
 FOREIGN KEY(institution_id,application_id) REFERENCES applications(institution_id,id)
);
CREATE TABLE approval_obligations (
 id text PRIMARY KEY, institution_id text NOT NULL REFERENCES institutions(id), application_id text,
 case_id text, region text NOT NULL, pack_id text NOT NULL REFERENCES approval_process_packs(id),
 kind text NOT NULL CHECK(kind IN ('UNDERTAKING','DOCUMENT_VALIDITY')), code text NOT NULL,
 title text NOT NULL, source_reference text NOT NULL,
 state text NOT NULL CHECK(state IN ('OPEN','SUBMITTED','VERIFIED','RETURNED','CANCELLED')),
 revision integer NOT NULL CHECK(revision>0), generation integer NOT NULL CHECK(generation>0),
 due_at timestamptz NOT NULL, accepted_evidence_id text, submitted_evidence_id text,
 submitted_due_at timestamptz, reviewer_id text REFERENCES actor_identities(id), reason text,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(institution_id,application_id,case_id) REFERENCES approval_cases(institution_id,application_id,id),
 FOREIGN KEY(institution_id,application_id) REFERENCES applications(institution_id,id),
 FOREIGN KEY(institution_id,application_id,accepted_evidence_id) REFERENCES evidence_versions(institution_id,application_id,id),
 FOREIGN KEY(institution_id,application_id,submitted_evidence_id) REFERENCES evidence_versions(institution_id,application_id,id),
 CHECK(case_id IS NULL OR application_id IS NOT NULL),
 CHECK(accepted_evidence_id IS NULL OR application_id IS NOT NULL),
 CHECK(submitted_evidence_id IS NULL OR application_id IS NOT NULL),
 CHECK(state <> 'VERIFIED' OR (accepted_evidence_id IS NOT NULL AND reviewer_id IS NOT NULL))
);
CREATE UNIQUE INDEX approval_obligation_code ON approval_obligations(case_id,code) WHERE case_id IS NOT NULL;
CREATE TABLE evc_rosters (
 id text PRIMARY KEY, region text NOT NULL, source_reference text NOT NULL,
 members json NOT NULL, availability json NOT NULL, conflicts json NOT NULL DEFAULT '[]',
 mode text NOT NULL CHECK(mode IN ('ONLINE','OFFLINE')), expires_at timestamptz NOT NULL
);
CREATE TABLE evc_appointments (
 id text PRIMARY KEY, institution_id text NOT NULL, application_id text NOT NULL, case_id text NOT NULL,
 region text NOT NULL, roster_id text NOT NULL REFERENCES evc_rosters(id),
 state text NOT NULL CHECK(state IN ('PROPOSED','CONFIRMED','CANCELLED','COMPLETED')),
 members json NOT NULL, starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), confirmed_by text REFERENCES actor_identities(id),
 explanation json NOT NULL, CHECK(ends_at>starts_at),
 FOREIGN KEY(institution_id,application_id,case_id) REFERENCES approval_cases(institution_id,application_id,id)
);
CREATE UNIQUE INDEX evc_one_confirmed_case ON evc_appointments(case_id) WHERE state='CONFIRMED';
CREATE TABLE approval_history (
 id text PRIMARY KEY, institution_id text REFERENCES institutions(id), application_id text,
 case_id text, resource_id text NOT NULL, actor_id text REFERENCES actor_identities(id),
 kind text NOT NULL, payload json NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(institution_id,application_id,case_id) REFERENCES approval_cases(institution_id,application_id,id)
);
CREATE TABLE approval_deadline_alerts (
 id text PRIMARY KEY, institution_id text NOT NULL REFERENCES institutions(id), application_id text,
 resource_id text NOT NULL, resource_kind text NOT NULL, generation integer NOT NULL,
 rule_key text NOT NULL, recipient_role text NOT NULL,
 state text NOT NULL CHECK(state IN ('OPEN','ACKNOWLEDGED','SUPERSEDED')),
 trigger_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(resource_id,resource_kind,generation,rule_key),
 FOREIGN KEY(institution_id,application_id) REFERENCES applications(institution_id,id)
);
CREATE INDEX approval_cases_queue ON approval_cases(region,status,due_at);
CREATE INDEX approval_obligations_due ON approval_obligations(due_at,state);
CREATE INDEX approval_history_resource ON approval_history(resource_id,created_at);
CREATE INDEX evc_booking_interval ON evc_appointments(starts_at,ends_at) WHERE state IN ('CONFIRMED','COMPLETED');

ALTER TABLE approval_access_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_access_grants FORCE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE ON approval_access_grants TO wb_app;
CREATE POLICY security_read ON approval_access_grants FOR SELECT TO wb_security_owner USING(true);
CREATE POLICY grants_read ON approval_access_grants FOR SELECT TO wb_app USING(actor_id=wb.actor_id() OR (wb.elevated() AND wb.has_role('supervisor')));
CREATE POLICY grants_write ON approval_access_grants FOR ALL TO wb_app USING(wb.elevated() AND wb.has_role('supervisor')) WITH CHECK(wb.elevated() AND wb.has_role('supervisor'));
ALTER TABLE approval_process_packs ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_process_packs FORCE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE ON approval_process_packs TO wb_app;
CREATE POLICY packs_read ON approval_process_packs FOR SELECT TO wb_app USING(wb.actor_id() IS NOT NULL);
CREATE POLICY packs_insert ON approval_process_packs FOR INSERT TO wb_app WITH CHECK(wb.elevated() AND wb.has_role('rule_author') AND author_id=wb.actor_id());
CREATE POLICY packs_publish ON approval_process_packs FOR UPDATE TO wb_app USING(state='DRAFT' AND wb.elevated() AND wb.has_role('rule_approver')) WITH CHECK(state='PUBLISHED' AND approver_id=wb.actor_id());
ALTER TABLE evc_rosters ENABLE ROW LEVEL SECURITY;
ALTER TABLE evc_rosters FORCE ROW LEVEL SECURITY;
GRANT SELECT,INSERT ON evc_rosters TO wb_app;
CREATE POLICY roster_read ON evc_rosters FOR SELECT TO wb_app USING(wb.elevated() AND (wb.has_role('officer') OR wb.has_role('supervisor') OR wb.niyam_role('REGIONAL',region,NULL) OR wb.niyam_role('BUREAU',region,NULL)));
CREATE POLICY roster_insert ON evc_rosters FOR INSERT TO wb_app WITH CHECK(wb.elevated() AND (wb.niyam_role('REGIONAL',region,NULL) OR wb.niyam_role('BUREAU',region,NULL) OR (wb.has_role('supervisor') AND EXISTS(SELECT FROM memberships m WHERE m.actor_id=wb.actor_id() AND m.jurisdiction=region))));

DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['approval_cases','approval_obligations','evc_appointments'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE ON %I TO wb_app',t);
  EXECUTE format('CREATE POLICY scope ON %I FOR ALL TO wb_app USING(wb.niyam_access(institution_id,application_id,region)) WITH CHECK(wb.niyam_access(institution_id,application_id,region))',t);
 END LOOP;
END $$;
ALTER TABLE approval_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_history FORCE ROW LEVEL SECURITY;
GRANT SELECT,INSERT ON approval_history TO wb_app;
CREATE POLICY history_read ON approval_history FOR SELECT TO wb_app USING(
 (institution_id IS NULL AND wb.elevated() AND (wb.has_role('rule_author') OR wb.has_role('rule_approver') OR wb.has_role('supervisor')))
 OR wb.niyam_access(institution_id,application_id,(SELECT jurisdiction FROM institutions WHERE id=institution_id)));
CREATE POLICY history_insert ON approval_history FOR INSERT TO wb_app WITH CHECK(actor_id=wb.actor_id());
ALTER TABLE approval_deadline_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_deadline_alerts FORCE ROW LEVEL SECURITY;
GRANT SELECT,UPDATE ON approval_deadline_alerts TO wb_app;
CREATE POLICY alert_read ON approval_deadline_alerts FOR SELECT TO wb_app USING(
 wb.niyam_access(institution_id,application_id,(SELECT jurisdiction FROM institutions WHERE id=institution_id))
 AND (recipient_role='INSTITUTION' OR wb.elevated()));
CREATE POLICY alert_ack ON approval_deadline_alerts FOR UPDATE TO wb_app USING(
 wb.niyam_access(institution_id,application_id,(SELECT jurisdiction FROM institutions WHERE id=institution_id))
 AND (recipient_role='INSTITUTION' OR wb.elevated())) WITH CHECK(state='ACKNOWLEDGED');
CREATE POLICY alert_supersede ON approval_deadline_alerts FOR UPDATE TO wb_app USING(
 wb.niyam_access(institution_id,application_id,(SELECT jurisdiction FROM institutions WHERE id=institution_id))) WITH CHECK(state='SUPERSEDED');
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['approval_process_packs','approval_cases','approval_obligations','approval_history','approval_deadline_alerts'] LOOP
  GRANT USAGE ON SCHEMA wb TO wb_worker;
  EXECUTE format('GRANT SELECT ON %I TO wb_worker',t);
  EXECUTE format('CREATE POLICY worker_read ON %I FOR SELECT TO wb_worker USING(true)',t);
 END LOOP;
END $$;
GRANT INSERT ON approval_history,approval_deadline_alerts TO wb_worker;
CREATE POLICY worker_history ON approval_history FOR INSERT TO wb_worker WITH CHECK(actor_id IS NULL);
CREATE POLICY worker_alert ON approval_deadline_alerts FOR INSERT TO wb_worker WITH CHECK(true);
GRANT UPDATE(state) ON approval_deadline_alerts TO wb_worker;
CREATE POLICY worker_supersede ON approval_deadline_alerts FOR UPDATE TO wb_worker USING(true) WITH CHECK(state='SUPERSEDED');

-- Validate overlaps across all institutions and regions, not just rows a planner can see.
GRANT SELECT ON evc_appointments TO wb_security_owner;
CREATE POLICY booking_integrity_read ON evc_appointments FOR SELECT TO wb_security_owner USING(true);
CREATE FUNCTION wb.evc_booking_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,public AS $$ DECLARE member text; BEGIN
 IF NEW.state IN ('CONFIRMED','COMPLETED') THEN
  FOR member IN SELECT json_array_elements_text(NEW.members) ORDER BY 1 LOOP
   PERFORM pg_advisory_xact_lock(hashtextextended('evc-member:'||member,0));
  END LOOP;
  IF EXISTS(SELECT FROM public.evc_appointments a WHERE a.id<>NEW.id
   AND a.state IN ('CONFIRMED','COMPLETED') AND a.starts_at<NEW.ends_at AND a.ends_at>NEW.starts_at
   AND EXISTS(SELECT FROM json_array_elements_text(a.members) m
    WHERE m.value IN (SELECT json_array_elements_text(NEW.members))))
  THEN RAISE EXCEPTION 'committee member booking conflict' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
 END $$;
ALTER FUNCTION wb.evc_booking_guard() OWNER TO wb_security_owner;
REVOKE ALL ON FUNCTION wb.evc_booking_guard() FROM PUBLIC;
CREATE TRIGGER member_booking_integrity BEFORE INSERT OR UPDATE ON evc_appointments
 FOR EACH ROW EXECUTE FUNCTION wb.evc_booking_guard();
