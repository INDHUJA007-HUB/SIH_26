from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, throttle
from .. import serializers as ser
from ..auth import (
    OFFICIAL_ROLES,
    ROLES,
    check_password,
    current_session,
    current_user,
    end_session,
    require_roles,
    start_session,
)
from ..config import get_settings
from ..db import get_db
from ..history.watch import dashboard_alerts as watch_alerts
from ..insights.proof import dashboard_alerts as session_alerts
from ..models import Application, AuditEvent, Finding, Institution, User, ValidationRun, VerificationAttempt
from ..rules.engine import active_ruleset
from ..sim import issuers as sim
from .applications import latest_run

router = APIRouter(prefix="/api", tags=["platform"])


class Login(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    throttle.check(db, request, body.username)
    u = db.scalars(select(User).where(User.username == body.username)).first()
    if not u or not u.active or not check_password(u.password_hash, body.password):
        throttle.failed(body.username)
        audit.record(db, actor=body.username[:80], actor_role="anonymous", action="auth.login_failed",
                     object_type="user", object_id=None)
        db.commit()
        raise HTTPException(401, "invalid username or password")
    throttle.succeeded(body.username)
    sess = start_session(db, u, response)
    audit.record(db, actor=u.username, actor_role=u.role, action="auth.login", object_type="user", object_id=u.id)
    db.commit()
    return {"user": ser.user(u), "csrf_token": sess.csrf_token, "role_label": ROLES[u.role]}


@router.post("/auth/logout")
def logout(request: Request, response: Response, user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    end_session(db, request, response)
    audit.record(db, actor=user.username, actor_role=user.role, action="auth.logout", object_type="user",
                 object_id=user.id)
    db.commit()
    return {"ok": True}


@router.get("/auth/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    s = get_settings()
    if not s.demo_mode:
        raise HTTPException(404, "not found")
    users = db.scalars(select(User).where(User.active.is_(True)).order_by(User.role, User.username)).all()
    return {"password": s.demo_password, "notice": "Synthetic demo data only", "accounts": [
        {**ser.user(u), "role_label": ROLES[u.role],
         "institution": db.get(Institution, u.institution_id).name if u.institution_id else None} for u in users]}


@router.get("/auth/me")
def me(sess=Depends(current_session), db: Session = Depends(get_db)):
    u = db.get(User, sess.user_id)
    return {"user": ser.user(u), "csrf_token": sess.csrf_token, "role_label": ROLES[u.role]}


@router.get("/dashboard")
def dashboard(user: User = Depends(require_roles(*OFFICIAL_ROLES)), db: Session = Depends(get_db)):
    apps = db.scalars(select(Application)).all()
    rows, alerts = [], []
    status_counts: dict[str, int] = {}
    ver_counts: dict[str, int] = {}
    cat_counts: dict[str, int] = {}
    open_total = 0
    for a in apps:
        status_counts[a.status] = status_counts.get(a.status, 0) + 1
        run = latest_run(db, a.id)
        open_f = []
        if run:
            fs = db.scalars(select(Finding).where(Finding.run_id == run.id)).all()
            open_f = [f for f in fs if f.review_status in ("open", "acknowledged", "evidence_requested")]
            open_total += len(open_f)
            for f in open_f:
                cat_counts[f.category] = cat_counts.get(f.category, 0) + 1
                if f.severity in ("critical", "high") and f.review_status == "open":
                    alerts.append({"application_id": a.id, "institution": a.institution.name, "finding_id": f.id,
                                   "severity": f.severity, "category": f.category, "title": f.title,
                                   "kind": "high_severity_finding"})
            for v in db.scalars(select(VerificationAttempt).where(VerificationAttempt.run_id == run.id)):
                ver_counts[v.status] = ver_counts.get(v.status, 0) + 1
                if v.status in ("source_unavailable", "verification_pending"):
                    alerts.append({"application_id": a.id, "institution": a.institution.name, "finding_id": None,
                                   "severity": "medium", "category": "verification",
                                   "title": f"{v.source_name}: {v.status.replace('_', ' ')}", "kind": v.status,
                                   "attempt_id": v.id})
        rows.append({**ser.application(a, run), "open_findings": len(open_f),
                     "open_high": sum(1 for f in open_f if f.severity in ("critical", "high"))})
    watch_alerts(db, alerts)
    rows.sort(key=lambda r: -((r["latest_run"] or {}).get("review_priority") or 0))
    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda x: sev_rank.get(x["severity"], 9))
    session_alerts(db, alerts)
    return {"applications": rows, "status_counts": status_counts, "verification_counts": ver_counts,
            "open_findings_by_category": cat_counts, "open_findings": open_total, "alerts": alerts[:50]}


@router.get("/rulesets/active")
def ruleset(user: User = Depends(current_user)):
    rs = active_ruleset()
    return {"id": rs.id, "title": rs.title, "version": rs.version, "sha256": rs.sha256,
            "sources": list(rs.sources.values()), "rules": rs.rules, "document_types": {
                k: {kk: vv for kk, vv in v.items() if kk not in ("fields", "classify", "table")} |
                {"fields": [f["name"] for f in v.get("fields", [])]} for k, v in rs.doc_types.items()},
            "checklists": rs.checklists}


@router.get("/rulesets/impact")
def rule_impact(user: User = Depends(require_roles("officer", "admin")), db: Session = Depends(get_db)):
    """Which applications would change outcome under the active ruleset versus the one their last run used."""
    from ..pipeline.facts_builder import build_facts
    from ..pipeline.validate import as_of_date, ruleset_by_hash
    from ..rules.engine import evaluate

    rs = active_ruleset()
    out = []
    for a in db.scalars(select(Application)):
        run = latest_run(db, a.id)
        if not run or run.status != "complete" or run.ruleset_hash == rs.sha256:
            continue
        old_rs = ruleset_by_hash(run.ruleset_hash)
        if old_rs is None:
            continue
        docs = [d for d in a.documents if not d.superseded]
        facts = build_facts(db, a, docs)
        as_of = date.fromisoformat(run.summary.get("as_of")) if run.summary.get("as_of") else as_of_date(a)
        old = {r.rule["id"]: r.outcome for r in evaluate(old_rs, facts, category=a.category, as_of=as_of)}
        new = {r.rule["id"]: r.outcome for r in evaluate(rs, facts, category=a.category, as_of=as_of)}
        changes = [{"rule_id": k, "before": old.get(k), "after": new.get(k)} for k in sorted(old.keys() | new.keys())
                   if old.get(k) != new.get(k)]
        if changes:
            out.append({"application_id": a.id, "institution": a.institution.name, "changes": changes})
    return {"active_ruleset": f"{rs.id}@{rs.version}", "active_hash": rs.sha256, "affected": out}


@router.get("/audit")
def audit_log(limit: int = 200, user: User = Depends(require_roles("admin", "officer")),
              db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(min(limit, 1000)))
    return [ser.audit_event(e) for e in rows]


@router.get("/audit/verify")
def audit_verify(user: User = Depends(require_roles("admin", "officer")), db: Session = Depends(get_db)):
    return audit.verify_chain(db)


@router.post("/audit/checkpoint")
def audit_checkpoint(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    cp = audit.checkpoint(db)
    db.commit()
    return {"seq": cp.seq, "head_hash": cp.head_hash, "signature": cp.signature} if cp else {}


@router.get("/sim/issuers")
def sim_issuers(user: User = Depends(current_user)):
    return sim.list_issuers()


class Availability(BaseModel):
    available: bool


@router.post("/sim/issuers/{code}/availability")
def sim_availability(code: str, body: Availability, user: User = Depends(require_roles("admin")),
                     db: Session = Depends(get_db)):
    try:
        out = sim.set_availability(code, body.available)
    except KeyError as e:
        raise HTTPException(404, "unknown issuer") from e
    audit.record(db, actor=user.username, actor_role=user.role, action="sim.availability_changed",
                 object_type="issuer", object_id=code, details={"available": body.available})
    db.commit()
    return out


@router.get("/sim/issuers/{code}/lookup")
def sim_lookup(code: str, ref: str, user: User = Depends(require_roles(*OFFICIAL_ROLES))):
    """The simulated issuer's own lookup page, as a verifier would use it by hand."""
    try:
        return sim.lookup(code, ref)
    except KeyError as e:
        raise HTTPException(404, "unknown issuer") from e
    except sim.SourceUnavailable as e:
        raise HTTPException(503, str(e)) from e


@router.post("/tools/verify-pdf")
def verify_pdf(file: UploadFile = File(...), user: User = Depends(require_roles(*OFFICIAL_ROLES)),
               db: Session = Depends(get_db)):
    """Check any PDF's signatures and structure without filing it. Nothing is stored except an audit entry."""
    from dataclasses import asdict

    from .. import sandbox
    from ..pipeline.intake import UploadRejected, validate_upload
    from ..verification.signature import validate_signatures

    data = file.file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    name = (file.filename or "upload.pdf").rsplit("/", 1)[-1][:120]
    try:
        res = validate_upload(name if name.lower().endswith(".pdf") else name + ".pdf", data)
    except UploadRejected as e:
        raise HTTPException(422, str(e)) from e
    if res.mime != "application/pdf":
        raise HTTPException(422, "only PDF files can be checked here")
    sigs = validate_signatures(data)
    try:
        signals, facts = sandbox.forensics(data, "application/pdf", None, None)
    except sandbox.SandboxError as e:
        raise HTTPException(422, f"the file could not be read safely: {e}") from e
    import hashlib

    sha = hashlib.sha256(data).hexdigest()
    audit.record(db, actor=user.username, actor_role=user.role, action="tool.verify_pdf", object_type="file",
                 object_id=sha[:16], details={"sha256": sha, "signatures": [r.status for r in sigs]})
    db.commit()
    return {"filename": name, "sha256": sha, "pages": res.page_count, "active_content": res.active_content,
            "signatures": [{"status": r.status, "simulated": r.simulated, "detail": r.detail, "claim": r.claim,
                            "response": r.response} for r in sigs],
            "forensic_signals": [asdict(x) for x in signals],
            "revisions": facts.get("revisions"), "metadata": facts.get("metadata", {}).get("info", {})}


@router.get("/metrics/runs")
def run_metrics(user: User = Depends(require_roles(*OFFICIAL_ROLES)), db: Session = Depends(get_db)):
    runs = db.scalars(select(ValidationRun).where(ValidationRun.status == "complete")).all()
    durs = [(r.finished_at - r.started_at).total_seconds() for r in runs if r.finished_at]
    return {"runs": len(runs), "mean_seconds": round(sum(durs) / len(durs), 2) if durs else None,
            "max_seconds": round(max(durs), 2) if durs else None}

