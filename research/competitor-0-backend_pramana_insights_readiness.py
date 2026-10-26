"""Pre-submission readiness check for institutions (docs/features/insight-ready.md).

A dry run of the handbook rules an institution is allowed to read about: completeness (including conditional
documents), validity of certificates, compliance with handbook norms, and whether each file could be read and
looks like the document its slot asks for. It never creates a validation run, never changes the application's
status, and never stores processing results on the documents: drafts are read into a cache keyed by the file's
hash, so officers see exactly what they would have seen without the check.

Kept out on purpose: forensic indicators, cross-application and consistency checks, issuer and signature
verification, and rules that read AICTE's own reference records. None of them is computed here, so none can
leak, and the output carries no rule or detector codes.
"""

import json
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, sandbox
from ..auth import load_application, require_roles
from ..crypto import cache_get, cache_put, load_document, sha256_hex
from ..db import get_db
from ..models import Application, Document, RectificationRequest, User, utcnow
from ..officer.common import RECTIFIABLE_CATEGORIES, presence_rule
from ..pipeline.extract import classify, extract_fields, extract_table
from ..pipeline.facts_builder import build_facts, latest_by_type
from ..pipeline.llm_extract import fill_missing
from ..rules.engine import ERROR, FAIL, INSUFFICIENT, NOT_APPLICABLE, PASS, Ruleset, active_ruleset, evaluate
from ..rules.facts import FactStore

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["readiness"])

EDITABLE = {"draft", "rectification_requested"}
READER_VERSION = "1"
FIVE_YEARS = 1826
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_PATH = re.compile(r"\b(app|doc|ref|ver|derived|inst)\.([a-z0-9_]+)(?:\.([a-z0-9_]+))?")
_MEM: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_MEM_MAX = 512

GROUPS = [("documents", "Documents"), ("validity", "Validity"), ("norms", "Norms")]
FIGURES = {
    "faculty_count": "Faculty count",
    "built_up_area_sqm": "Built-up area",
    "land_area_acres": "Land area",
    "administrative_area_sqm": "Administrative area",
    "amenities_area_sqm": "Amenities area",
    "internet_bandwidth_mbps": "Internet bandwidth",
    "building_age_years": "Building age",
    "programmes": "Programmes",
}
# Figures computed from the programmes table
PROGRAMME_FACTS = {"total_proposed_intake", "total_approved_intake_claimed", "programme_count", "programme_codes",
                   "intake_increase_requested", "required_faculty", "required_bandwidth_mbps",
                   "core_branch_count", "non_cs_core_count"}
FIELD_WORDS = {"valid_until": "validity date", "issue_date": "date of issue", "stamp_value": "stamp value",
               "attested_by": "officer it was sworn before", "row_count": "faculty list rows",
               "built_up_area_sqm": "built-up area"}
SOURCE_NAMES = {"APH": "Approval Process Handbook", "ADD26": "Addendum to the handbook, 2026-27",
                "PN2627": "AICTE public notice for 2026-27"}

# Plain wording per rule; anything not listed falls back to the rule's own title and message
WORDING: dict[str, dict[str, str]] = {
    "APH-617I-FIRE-VALID": {
        "topic": "Fire Safety Certificate validity","met": "Fire Safety Certificate is valid", "fix": "Fire Safety Certificate has expired"},
    "APH-A31D-FIRE-BEFORE": {
        "topic": "Fire Safety Certificate date",
        "met": "Fire Safety Certificate was issued before applying",
        "fix": "Fire Safety Certificate is dated after the submission date",
        "action": "Upload the Fire Safety Certificate you held before applying, dated on or before {as_of}."},
    "APH-617H-SSC-VALID": {
        "topic": "Structural Stability Certificate validity",
        "met": "Structural Stability Certificate is within its five years",
        "fix": "Structural Stability Certificate is older than five years"},
    "APH-AFF2-FORM": {
        "topic": "Affidavit 2 form",
        "met": "Affidavit 2 is on Rs 100 e-stamp paper and duly sworn",
        "fix": "Affidavit 2 is not in the prescribed form",
        "action": "Upload Affidavit 2 on e-stamp paper of at least Rs 100, sworn before a First Class Judicial "
                  "Magistrate, a Notary or an Oath Commissioner."},
    "APH-ANX5-FSR": {
        "topic": "Faculty-student ratio",
        "met": "Faculty-student ratio meets Annexure 5",
        "fix": "Fewer faculty than Annexure 5 requires",
        "action": "List at least {required_faculty} faculty on the faculty roster, or check the approved intake "
                  "and duration of each programme."},
    "APH-ANX41-BANDWIDTH": {
        "topic": "Internet bandwidth tier",
        "met": "Internet bandwidth meets the tier for your intake",
        "fix": "Internet bandwidth is below the tier for your intake",
        "action": "Raise the campus connection to at least {required_bandwidth_mbps} Mbps, then update Internet "
                  "bandwidth."},
    "APH-ANX33-ADMIN-AREA": {
        "topic": "Administrative and amenities areas",
        "met": "Administrative and amenities areas meet the minimums",
        "fix": "Administrative or amenities area is below the minimum",
        "action": "Check the areas you declared: at least 750 sq m administrative and 500 sq m amenities for an "
                  "approved intake up to 300."},
    "ADD26-26C-CORE-BRANCHES": {
        "topic": "Core branches for an increase in intake",
        "met": "Three core branches, two outside Computer Science",
        "fix": "Too few core branches for an increase in intake",
        "action": "An increase needs at least three core branches, two of them outside Computer Science and "
                  "allied disciplines. Check how each programme is marked."},
    "PN2627-DEADLINE": {
        "topic": "Application window",
        "met": "Within the 2026-27 application window",
        "fix": "The 2026-27 application window has closed",
        "detail": "The last date for 2026-27, with the late fee, was 20 January 2026.",
        "action": "Contact AICTE before submitting, or start an application for the next academic year."},
}


# ------------------------------------------------------------------ reading documents without storing results


@dataclass
class _Field:
    name: str
    raw: str | None
    value: str | None
    value_type: str
    page: int | None
    bbox: list[float] | None
    method: str
    status: str
    id: None = None


@dataclass
class _Doc:
    """A stand-in for a Document, carrying what the fact builder reads, so a draft file is never altered."""

    id: str
    declared_type: str
    original_filename: str
    round: int
    uploaded_at: datetime
    processing_status: str
    processing_error: str | None = None
    classification: dict[str, Any] = field(default_factory=dict)
    fields: list[_Field] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)


def _read_file(doc: Document, rs: Ruleset) -> dict[str, Any]:
    """Text, type and field values of one file, the way the pipeline reads them, without forensics."""
    spec_declared = rs.doc_types.get(doc.declared_type, {})
    if doc.mime != "application/pdf" and not spec_declared.get("fields") \
            and not (spec_declared.get("classify") or {}).get("keywords"):
        # Photographs carry no values to check; reading them would only spend OCR time
        return {"status": "processed", "classification": {}, "fields": [], "rows": None,
                "unreadable_pages": [], "scripts_not_read": []}
    try:
        pages = sandbox.read_pages(load_document(doc.storage_name), doc.mime)
    except Exception as e:  # noqa: BLE001  any failure to read is reported as an unreadable file
        log.info("readiness: %s could not be read: %s", doc.id, e)
        return {"status": "failed"}
    cls = classify(pages, rs.doc_types)
    use_type = doc.declared_type if doc.declared_type in rs.doc_types else cls["type"]
    spec = rs.doc_types.get(use_type or "", {})
    extracted = extract_fields(pages, spec)
    extracted, _ = fill_missing(pages, spec, spec.get("label", use_type or "document"), extracted)
    fields = [{"name": e.name, "raw": e.raw, "value": e.value.isoformat() if hasattr(e.value, "isoformat") else
               (str(e.value) if e.value is not None else None), "value_type": e.value_type, "page": e.page,
               "bbox": e.bbox, "method": e.method, "status": e.status} for e in extracted]
    return {
        "status": "processed",
        "classification": {"type": cls.get("type")},
        "fields": fields,
        "rows": extract_table(pages, spec["table"]) if spec.get("table") else None,
        "unreadable_pages": [p.page_no for p in pages if p.source == "unreadable"],
        "scripts_not_read": [p.page_no for p in pages if (p.ocr or {}).get("script") == "devanagari"
                             and (p.ocr or {}).get("read") is False],
    }


def _cached_read(doc: Document, rs: Ruleset) -> tuple[dict[str, Any], bool]:
    """(result, fresh). Cached per file hash, slot and ruleset, in memory and encrypted on disk."""
    key = sha256_hex(f"{doc.sha256}|{doc.declared_type}|{doc.mime}|{rs.sha256}|{READER_VERSION}".encode())[:40]
    if key in _MEM:
        _MEM.move_to_end(key)
        return _MEM[key], False
    name = f"readiness-{key}.json"
    raw = cache_get(name)
    if raw is not None:
        try:
            out = json.loads(raw)
            _remember(key, out)
            return out, False
        except ValueError:
            pass
    out = _read_file(doc, rs)
    try:
        cache_put(name, json.dumps(out).encode())
    except OSError as e:
        log.warning("readiness cache write failed: %s", e)
    _remember(key, out)
    return out, True


def _remember(key: str, value: dict[str, Any]) -> None:
    _MEM[key] = value
    _MEM.move_to_end(key)
    while len(_MEM) > _MEM_MAX:
        _MEM.popitem(last=False)


def _stand_in(doc: Document, rs: Ruleset) -> tuple[Any, bool]:
    """The document itself when the pipeline already processed it; otherwise a read-only stand-in."""
    if doc.processing_status in ("processed", "failed"):
        return doc, False
    got, fresh = _cached_read(doc, rs)
    sd = _Doc(id=doc.id, declared_type=doc.declared_type, original_filename=doc.original_filename,
              round=doc.round, uploaded_at=doc.uploaded_at, processing_status=got["status"],
              processing_error="unreadable" if got["status"] == "failed" else None,
              classification=got.get("classification") or {},
              fields=[_Field(**f) for f in got.get("fields") or []],
              analysis={"rows": got.get("rows"), "unreadable_pages": got.get("unreadable_pages") or [],
                        "scripts_not_read": got.get("scripts_not_read") or []})
    return sd, fresh


# ------------------------------------------------------------------ wording helpers


def fmt_day(d: date | str | None) -> str:
    if not d:
        return "not given"
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{d.day} {d.strftime('%B %Y')}"


def _readable(text: str) -> str:
    out = _ISO.sub(lambda m: fmt_day(m.group(0)), text)
    return re.sub(r"\b(\d{2})-(\d{2})-(\d{4})\b",
                  lambda m: fmt_day(f"{m.group(3)}-{m.group(2)}-{m.group(1)}"), out)


def session_end(academic_year: str) -> date:
    """The academic session ends on 30 June of its second year (configuration, not a handbook clause)."""
    return date(int(academic_year[:4]) + 1, 6, 30)


def _label(rs: Ruleset, doc_type: str) -> str:
    """The slot's name without its parenthetical gloss: "Affidavit 2", "Faculty roster"."""
    label = rs.doc_types.get(doc_type, {}).get("label", doc_type.replace("_", " "))
    return re.sub(r"\s*\([^)]*\)", "", label).strip() or label


def _lower_first(s: str) -> str:
    """Sentence-case labels read naturally mid-sentence; names in title case and acronyms stay as they are."""
    words = s.split()
    if len(words) > 1 and words[1][:1].islower() and not words[0].isupper():
        return s[:1].lower() + s[1:]
    return s


def _the(label: str) -> str:
    """The label with its article: the Fire Safety Certificate, but Affidavit 2 (numbered forms take none)."""
    return label if re.search(r"\d$", label) else f"the {_lower_first(label)}"


def _clause(rs: Ruleset, rule: dict[str, Any] | None, fallback: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The handbook clause, verbatim from the ruleset, with the source named in words."""
    src = dict((rule or {}).get("source") or fallback or {})
    if not src:
        return None
    doc = src.get("doc", "")
    return {"source": SOURCE_NAMES.get(doc) or rs.sources.get(doc, {}).get("title") or doc,
            "section": src.get("section"), "page": src.get("page"), "quote": src.get("quote")}


def _paths(rule: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    chk = rule.get("check") or {}
    text = " ".join(str(x) for x in (chk.get("expr"), (rule.get("applies_to") or {}).get("when")) if x)
    return [(m.group(1), m.group(2), m.group(3)) for m in _PATH.finditer(text)]


def _allowed(rule: dict[str, Any]) -> bool:
    """Only rules an institution may read about, and only those that need nothing beyond its own submission."""
    if rule.get("category") not in RECTIFIABLE_CATEGORIES:
        return False
    return not any(kind in ("ref", "ver") for kind, _, _ in _paths(rule))


def _targets(rs: Ruleset, rule: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []

    def add(kind: str, key: str, label: str) -> None:
        if not any(t["key"] == key for t in out):
            out.append({"kind": kind, "key": key, "label": label})

    for kind, a, _b in _paths(rule):
        if kind == "doc" and a in rs.doc_types:
            add("document", a, _label(rs, a))
    for kind, a, _b in _paths(rule):
        if kind == "app" and a in FIGURES:
            add("figure", a, FIGURES[a])
        elif kind in ("app", "derived") and a in PROGRAMME_FACTS:
            add("figure", "programmes", FIGURES["programmes"])
    for t in (rule.get("applies_to") or {}).get("requires_docs", []):
        add("document", t, _label(rs, t))
    return out[:2]


def _years(age: float) -> str:
    # Whole years, except near the 30-year line where the decimal decides
    return f"{age:.1f}" if 29.5 <= age < 31.5 else f"{age:.0f}"


def _num(facts: FactStore, path: str) -> Any:
    f = facts.get(path)
    return f.value if f else None


# ------------------------------------------------------------------ the check


@dataclass
class _Item:
    id: str
    group: str
    status: str  # met, fix, waiting
    title: str
    detail: str | None = None
    action: str | None = None
    advice: dict[str, str] | None = None
    clause: dict[str, Any] | None = None
    targets: list[dict[str, str]] = field(default_factory=list)
    requested: bool = False
    conditional: str | None = None
    _doc_types: set[str] = field(default_factory=set)
    _rule_id: str | None = None

    def out(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


def _rule_item_id(rule_id: str) -> str:
    return "r-" + sha256_hex(rule_id.encode())[:10]


def _document_items(rs: Ruleset, app: Application, docs: dict[str, Any], facts: FactStore,
                    results: dict[str, Any], as_of: date) -> tuple[list[_Item], list[str]]:
    """One item per document slot that is required now: present, readable and the right document."""
    cl = rs.checklists.get(app.category, {})
    required = list(cl.get("required", []))
    notes: list[str] = []
    conditional: dict[str, str] = {}
    ssc_rule = next((r for r in rs.rules if (r.get("check") or {}).get("doc_type") == "structural_stability"
                     and (r.get("applies_to") or {}).get("when")), None)
    if ssc_rule and "structural_stability" not in required:
        res = results.get(ssc_rule["id"])
        age = _num(facts, "derived.years_since_completion")
        basis = ("from the date of your completion certificate"
                 if facts.get("derived.years_since_completion")
                 and facts.get("derived.years_since_completion").source == "derived" else "as you declared it")
        if res is not None and res.outcome in (PASS, FAIL):
            required.append("structural_stability")
            conditional["structural_stability"] = (f"Required because the building is {_years(age)} years old, {basis}; "
                                                   "the handbook asks for it above 30 years.")
        elif res is not None and res.outcome == NOT_APPLICABLE and age is not None:
            notes.append(f"A Structural Stability Certificate is not needed: the building is {_years(age)} years old, "
                         f"{basis}, and the handbook asks for it only above 30 years.")
        elif res is not None and res.outcome == INSUFFICIENT:
            notes.append("Upload the Occupancy / Completion Certificate, or declare the building age, to find out "
                         "whether a Structural Stability Certificate is needed.")
    optional_uploaded = [t for t in cl.get("optional", []) if t in docs and t not in required]
    items = []
    for t in required + optional_uploaded:
        label = _label(rs, t)
        spec = rs.doc_types.get(t, {})
        rule = presence_rule(rs, t) if t != "structural_stability" or not ssc_rule else ssc_rule
        it = _Item(id=f"doc-{t}", group="documents", status="met", title=f"{label} uploaded",
                   clause=_clause(rs, rule, cl.get("source")),
                   targets=[{"kind": "document", "key": t, "label": label}], conditional=conditional.get(t),
                   _doc_types={t})
        d = docs.get(t)
        if d is None:
            it.status, it.title = "fix", f"{label} not uploaded"
            # The handbook quote says what the document is; the slot's own description is the fallback
            it.detail = None if (it.clause or {}).get("quote") else spec.get("description")
            it.action = f"Upload {_the(label)}."
        elif d.processing_status == "failed":
            it.status, it.title = "fix", f"{label} could not be read"
            it.detail = f"The file {d.original_filename} could not be opened or read."
            it.action = "Upload a clearer copy as a PDF, JPG or PNG."
        else:
            seen = (d.classification or {}).get("type")
            an = d.analysis or {}
            if seen and seen != t and t in rs.doc_types:
                it.status, it.title = "fix", f"The {_lower_first(label)} slot holds a different document"
                it.detail = f"{d.original_filename} reads like {_the(_label(rs, seen))}."
                it.action = f"Check the file, then upload {_the(label)} in this slot."
            unread = an.get("unreadable_pages") or []
            hindi = an.get("scripts_not_read") or [s.get("page") for s in an.get("ocr_scripts") or []
                                                   if s.get("read") is False]
            if it.status == "met" and (unread or hindi):
                pages = unread or hindi
                which = ", ".join(str(p) for p in pages)
                what = ("have no readable text" if unread else "carry Hindi text that was not read")
                it.advice = {"text": f"Page{'s' if len(pages) > 1 else ''} {which} {what}, so values on "
                                     f"{'them' if len(pages) > 1 else 'it'} were not checked.",
                             "action": "Upload a clearer scan if those pages carry dates or figures."}
        items.append(it)
    return items, notes


def _rule_item(rs: Ruleset, app: Application, r: Any, facts: FactStore, as_of: date, end: date,
               required: set[str]) -> _Item | None:
    rule = r.rule
    words = WORDING.get(rule["id"], {})
    group = "validity" if rule.get("category") == "validity" else "norms"
    targets = _targets(rs, rule)
    it = _Item(id=_rule_item_id(rule["id"]), group=group, status="met", title=words.get("met", rule["title"]),
               clause=_clause(rs, rule), targets=targets,
               _doc_types={t["key"] for t in targets if t["kind"] == "document"}, _rule_id=rule["id"])
    values = {"as_of": fmt_day(as_of), "session_end": fmt_day(end),
              "required_faculty": _num(facts, "derived.required_faculty"),
              "required_bandwidth_mbps": _num(facts, "derived.required_bandwidth_mbps")}
    if r.outcome == PASS:
        return it
    if r.outcome == NOT_APPLICABLE:
        if not r.missing or not set(r.missing) <= required:
            return None  # the rule does not apply, or rests on an optional document that was not uploaded
        names = [_the(_label(rs, t)) for t in r.missing]
        it.status, it.detail = "waiting", f"Checked once {' and '.join(names)} {'is' if len(names) == 1 else 'are'} uploaded."
        return it
    if r.outcome == FAIL:
        it.status, it.title = "fix", words.get("fix", rule["title"])
        it.detail = words.get("detail") or _readable(r.message)
        if it.detail:
            # Judged as of today, the date the institution would submit or resubmit
            it.detail = re.sub(r"the submission date (\d{1,2} \w+ \d{4})", lambda m: f"today, {m.group(1)}",
                               it.detail)
        if rule["id"] == "APH-617I-FIRE-VALID":
            it.action = f"Upload a Fire Safety Certificate valid until at least {fmt_day(end)}."
        elif rule["id"] == "APH-617H-SSC-VALID":
            it.action = ("Upload a Structural Stability Certificate from a registered structural engineer, issued "
                         f"on or after {fmt_day(end - timedelta(days=FIVE_YEARS))} so it stays valid through the "
                         "session.")
        else:
            it.action = words.get("action", "Correct this before submitting.").format(**values)
        return it
    # Could not decide: say which value is missing and where to give it
    missing = r.missing[0] if r.missing else ""
    m = _PATH.match(missing)
    kind, a, b = (m.group(1), m.group(2), m.group(3)) if m else ("", "", None)
    it.status, it.title = "fix", f"{words['topic']} cannot be checked yet" if "topic" in words else rule["title"]
    if r.outcome == ERROR:
        it.detail = "A value needed for this rule could not be understood."
        it.action = "Check the figures and the documents this rule reads."
    elif kind == "doc" and a in rs.doc_types:
        label = _label(rs, a)
        what = FIELD_WORDS.get(b or "", (b or "value").replace("_", " "))
        it.detail = f"The {what} could not be read from {_the(label)}."
        it.action = f"Upload a clearer copy of {_the(label)}."
        it.targets = [{"kind": "document", "key": a, "label": label}]
    elif kind == "app" and a in FIGURES:
        it.detail = f"{FIGURES[a]} is not filled in, so this cannot be checked."
        it.action = f"Enter {_lower_first(FIGURES[a])} under Declared figures."
        it.targets = [{"kind": "figure", "key": a, "label": FIGURES[a]}]
    elif a in PROGRAMME_FACTS or kind == "derived":
        it.detail = "Your programmes are not filled in, so this cannot be checked."
        it.action = "Add each programme with its level, duration and approved intake."
        it.targets = [{"kind": "figure", "key": "programmes", "label": FIGURES["programmes"]}]
    else:
        it.detail = "A value needed for this rule is missing."
        it.action = "Check the figures and documents this rule reads."
    return it


def _validity_advice(rs: Ruleset, items: list[_Item], facts: FactStore, as_of: date, end: date,
                     year: str) -> None:
    """A certificate valid today that lapses before the session ends: met, with a note to renew."""
    lapses: dict[str, date] = {}
    for t in rs.doc_types:
        f = facts.get(f"doc.{t}.valid_until")
        if f and isinstance(f.value, date):
            lapses[t] = f.value
    issued = facts.get("doc.structural_stability.issue_date")
    if issued and isinstance(issued.value, date):
        lapses["structural_stability"] = issued.value + timedelta(days=FIVE_YEARS)
    for t, until in lapses.items():
        if not (as_of <= until < end):
            continue
        label = _label(rs, t)
        host = next((i for i in items if i.group == "validity" and t in i._doc_types and i.status == "met"), None) \
            or next((i for i in items if i.id == f"doc-{t}" and i.status == "met"), None)
        if host is None:
            continue
        when = (f"before the {year} session begins" if until < date(end.year - 1, 7, 1)
                else f"before the {year} session ends on {fmt_day(end)}")
        host.advice = {"text": f"Valid when you submit, but it lapses on {fmt_day(until)}, {when}.",
                       "action": f"Plan the renewal, or upload a {_lower_first(label)} valid until at least "
                                 f"{fmt_day(end)}."}


def _requested(db: Session, app: Application) -> tuple[set[str], set[str], set[str]] | None:
    """Rule ids, document types and declared fields the open rectification request names."""
    req = db.scalars(select(RectificationRequest).where(RectificationRequest.application_id == app.id,
                                                        RectificationRequest.status == "open")
                     .order_by(RectificationRequest.created_at.desc())).first()
    if req is None:
        return None
    codes, doc_types, fields = set(), set(), set()
    for i in req.items or []:
        if i.get("code"):
            codes.add(i["code"])
        if i.get("document_type"):
            doc_types.add(i["document_type"])
        for p in i.get("fact_paths") or []:
            parts = p.split(".")
            if parts[0] == "doc" and len(parts) > 1:
                doc_types.add(parts[1])
            elif parts[0] == "app" and len(parts) > 1:
                fields.add("programmes" if parts[1] in PROGRAMME_FACTS else parts[1])
    return codes, doc_types, fields


def check(db: Session, app: Application, *, today: date | None = None) -> dict[str, Any]:
    """The readiness check for one application. Reads only; the caller records the audit event."""
    t0 = time.perf_counter()
    rs = active_ruleset()
    as_of = today or utcnow().date()
    end = session_end(app.academic_year)
    current = list(db.scalars(select(Document).where(Document.application_id == app.id,
                                                     Document.superseded.is_(False))))
    fresh = 0
    stand_ins = []
    for d in current:
        sd, was_fresh = _stand_in(d, rs)
        fresh += was_fresh
        stand_ins.append(sd)
    docs = latest_by_type(stand_ins)
    facts = build_facts(db, app, stand_ins, rs, None, as_of)
    if not facts.get("app.submitted_on"):
        # A draft is judged as if it were submitted today
        facts.add("app.submitted_on", as_of, "declared", form_field="submitted_at")
    if not facts.get("derived.years_since_completion") and isinstance((app.declared or {}).get("building_age_years"),
                                                                      int | float):
        # Before the completion certificate is read, the declared building age decides the conditional document
        facts.add("derived.years_since_completion", float(app.declared["building_age_years"]), "declared",
                  form_field="building_age_years")
    results = {r.rule["id"]: r for r in evaluate(rs, facts, category=app.category, as_of=as_of)}

    items, notes = _document_items(rs, app, docs, facts, results, as_of)
    required = {i.id[4:] for i in items}
    for r in results.values():
        rule = r.rule
        chk = rule.get("check") or {}
        if not _allowed(rule) or chk.get("type") == "document_present":
            continue
        it = _rule_item(rs, app, r, facts, as_of, end, required)
        if it is not None:
            items.append(it)
    _validity_advice(rs, items, facts, as_of, end, app.academic_year)

    asked = _requested(db, app)
    if asked:
        codes, doc_types, fields = asked
        for it in items:
            figs = {t["key"] for t in it.targets if t["kind"] == "figure"}
            it.requested = bool((it._rule_id and it._rule_id in codes) or (it._doc_types & doc_types)
                                or (figs & fields))

    counts = {"total": len(items),
              "met": sum(1 for i in items if i.status == "met"),
              "fix": sum(1 for i in items if i.status == "fix"),
              "waiting": sum(1 for i in items if i.status == "waiting"),
              "advice": sum(1 for i in items if i.advice),
              "requested": sum(1 for i in items if i.requested),
              "requested_fix": sum(1 for i in items if i.requested and i.status == "fix")}
    return {
        "application_id": app.id,
        "status": app.status,
        "round": app.round,
        "resubmission": app.status == "rectification_requested",
        "checked_at": utcnow().isoformat(),
        "as_of": as_of.isoformat(),
        "session": {"year": app.academic_year, "ends": end.isoformat()},
        "state": "fix" if counts["fix"] else "ready",
        "counts": counts,
        "groups": [{"id": g, "label": label, "items": [i.out() for i in items if i.group == g]} for g, label in GROUPS],
        "notes": notes,
        "fresh_reads": fresh,
        "duration_ms": round((time.perf_counter() - t0) * 1000),
    }


@router.post("/applications/{app_id}/readiness")
def readiness(app_id: str, user: User = Depends(require_roles("institution")), db: Session = Depends(get_db)):
    """Dry run of the handbook rules an institution may see. No validation run, no status change; one audit
    event with counts only."""
    app = load_application(db, user, app_id)
    if app.status not in EDITABLE:
        raise HTTPException(409, f"application is {app.status}; the readiness check runs on drafts and "
                                 "rectification rounds")
    out = check(db, app)
    c = out["counts"]
    audit.record(db, actor=user.username, actor_role=user.role, action="readiness.checked",
                 object_type="application", object_id=app.id, application_id=app.id,
                 details={"met": c["met"], "to_fix": c["fix"], "waiting": c["waiting"], "advice": c["advice"],
                          "files_read": out["fresh_reads"]})
    db.commit()
    return out

