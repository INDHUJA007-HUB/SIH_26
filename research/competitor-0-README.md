# Pramana

Evidence-linked application validation, document authentication and compliance assistance for AICTE approval processing. Built for Smart India Hackathon 2026, problem statement **26261** (AICTE, Regulation Bureau).

> Decision support only. Findings are preliminary indicators for review by competent authorities. Pramana does not approve, reject or penalise any institution. The demo runs on test records, as the problem statement specifies. Issuer registries connect through adapters, simulated until access is authorised.

**Demo video (under 5 minutes):** [watch on Google Drive](https://drive.google.com/file/d/1EWt5FSUE9omqn0tEgNDzp0GsQ5wujE_l/view?usp=sharing)

## What it does

- **Validates** an application against a versioned, cited ruleset built from the Approval Process Handbook 2024-27 and its 2025-26 and 2026-27 addenda.
  - 29 rules across the Annexure 2.1 documents, certificate validity, Affidavit 2 form and DSC, TER ledger status, approval-record consistency, faculty-student ratio, bandwidth, areas, NBA claims and core-branch conditions.
  - Validation runs in the background. The officer watches each document being read and each check returning, with real durations; the institution sees only the stages.
- **Reads documents** from their text layer, or by OCR for scanned pages. Pages in Hindi (Devanagari script) are read with a second, Devanagari recogniser. Every extracted value is tied to the page region it came from.
- **Verifies:**
  - PDF digital signatures against the **CCA India root certificates**, a real check that works offline (online OCSP and CRL checks are optional);
  - issuer-signed QR codes, also on a public scan-to-verify page that needs no login;
  - Content Credentials (C2PA) embedded in photos, against a DEMO capture CA;
  - issuer registries through an adapter interface (simulated registries in the prototype, clearly labelled).
- **Separates who signed:** the applicant's own DSC never counts as issuer authentication.
- **Finds tampering evidence:**
  - text changed in a later PDF revision ("added '30-06-2027' over existing text '30-06-2025'"), and a time machine that shows the page as saved at each revision;
  - overwritten fields, overlaid glyphs, white boxes;
  - a value drawn in a font that no other value on the document uses;
  - a seal image that also appears on another issuer's certificate;
  - photo metadata, geotag distance, and photos modified after their Content Credentials were signed;
  - edits made with everyday tools: a text box or white box drawn over a value in Edge or a PDF reader, a Word round trip, a print to PDF, or a photo of a printout, including an issuer document that arrives without the issuer's signature or only as an image.
- **Shows the evidence at a glance:**
  - a proof-strength ladder per requirement, from the institution's own word up to the issuer's signature, with contradictions marked;
  - a certificate coverage calendar that catches a certificate valid on the submission date but lapsing during the academic session;
  - a document life story: when a file was created, signed, edited, uploaded and checked.
- **Links applications** through shared faculty IDs, certificate numbers, file hashes, reused photos and seals, and identical certificate details. These contradictions are invisible when one document is reviewed at a time. The Integrity page draws them as a network of clusters, and a faculty-overlap timeline shows one faculty ID listed full-time by two institutions at once, and since when.
- **Compares with last year:** land and built-up area, intake, the faculty roster and certificate numbers against the institution's previous application. Only changes that are hard to explain become indicators.
- **Shows the campus:** a map with the campus on record, the declared map point and each photo's geotag, and a low-weight indicator when a lab photo shows far fewer workstations than declared.
- **Supports reviewers:**
  - an evidence viewer and review actions that need reasons;
  - rectification rounds that flag changes outside the requested scope, with a deficiency letter drafted from the findings and quoting the cited clauses;
  - manual confirmation when a source is unavailable;
  - Ask why: questions about an application answered only from Pramana's own findings, with every sentence citing its evidence;
  - an evidence pack: a signed ZIP with the report, the data and an audit extract, checkable offline;
  - a re-verification watch that re-queries issuer-confirmed certificates after the scrutiny outcome and raises an alert when one changes;
  - an inspection brief for the visiting committee: where to go, what to count and what to ask, as a PDF;
  - a hash-chained audit trail and replayable validation runs.
- **Analyses any document** an official drops in, PDF or photo, with the same checks as a validation run and without storing it. Tested on real DSC-signed Government e-Gazettes.
- **Helps institutions before they submit:** a readiness check lists what the handbook rules will raise, each with its clause and where to fix it.
- **Hardened for deployment:** sign-in throttling, a `__Host-` session cookie with HSTS behind HTTPS, untrusted files parsed in sandboxed worker processes, per-document envelope encryption with key rotation, a retention policy with an audited purge, and PostgreSQL support.

Start with `docs/usp-and-demo.md`. Research, requirements mapping, design decisions, security and measured results are in `docs/`. Each feature added in the October sprint has its own document:

| Document | Covers |
|---|---|
| [docs/features/platform.md](docs/features/platform.md) | Background validation with live progress, sign-in throttling, secure cookies, parser sandbox, envelope encryption, retention, PostgreSQL, optional OCSP and CRL |
| [docs/features/forensics.md](docs/features/forensics.md) | Font check, seal reuse, Hindi OCR, public scan-to-verify page |
| [docs/features/officer.md](docs/features/officer.md) | Deficiency letter, evidence pack, Ask why |
| [docs/features/history.md](docs/features/history.md) | Revision time machine, re-verification watch, year-over-year comparison |
| [docs/features/photos.md](docs/features/photos.md) | Campus tab with map, Content Credentials (C2PA), room and seat indicator, photo attributions |
| [docs/features/model-v2.md](docs/features/model-v2.md) | Version 2 of the fine-tuned extractor: training data changes, Kaggle run, comparison with version 1, A11 check |
| [docs/features/edits.md](docs/features/edits.md) | Edits made with everyday tools (Word, Edge, PDF readers, print to PDF, printout photos) and the 18-method test |
| [docs/features/random-eval.md](docs/features/random-eval.md) | Randomised blind evaluation: hundreds of generated applications, scored blind, rerunnable with any seed |
| [docs/features/analyse.md](docs/features/analyse.md) | Analyse a document, including real signed Government e-Gazettes |
| [docs/features/scan-link.md](docs/features/scan-link.md) | QR codes as links: verify a certificate from any phone camera |
| [docs/features/insight-proof.md](docs/features/insight-proof.md) | Proof-strength ladder and certificate coverage calendar |
| [docs/features/insight-network.md](docs/features/insight-network.md) | Integrity network and faculty overlaps |
| [docs/features/insight-story.md](docs/features/insight-story.md) | Document life story and inspection brief |
| [docs/features/insight-ready.md](docs/features/insight-ready.md) | Readiness check for institutions before they submit |

## Quick start (Windows, macOS or Linux)

Prerequisites: Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 22 with pnpm. The first setup needs network access once, for model weights, fonts and sample photos. After that the demo runs offline; without network the campus map shows a plain plot instead of map tiles.

The commands use the Windows path `.venv/Scripts/python`; on macOS and Linux use `.venv/bin/python`.

```bash
# Backend
cd backend
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"          # uv installs into ./.venv

# Third-party assets, once, with network. Each file is checked against a pinned SHA-256; none is committed.
.venv/Scripts/python scripts/fetch_assets.py         # Devanagari OCR model; Noto Sans Devanagari for the Hindi fixture
.venv/Scripts/python scripts/fetch_photo_assets.py   # YOLOX-M detector; three openly licensed lab photos
.venv/Scripts/python scripts/fetch_real_samples.py   # optional: a real DSC-signed e-Gazette PDF

# Synthetic world and demo database (a few minutes on a laptop CPU)
.venv/Scripts/python scripts/make_fixtures.py
.venv/Scripts/python scripts/seed.py

# Frontend
cd ../frontend
pnpm install
pnpm build

# Run (serves the UI and the API)
cd ../backend
.venv/Scripts/python -m uvicorn pramana.main:app --port 8000
```

Open http://127.0.0.1:8000. For frontend development run `pnpm dev` in `frontend/`; it proxies `/api` to port 8000.

To open the public scan page (`/scan`) on a phone, start the server with `--host 0.0.0.0` and open `http://<laptop address>:8000/scan` on the same Wi-Fi; `docs/features/forensics.md` has the steps. The printable QR samples are written to `fixtures/out/scan/` by `make_fixtures.py`; the demo issuer keys change on every fixture run, so print them after the last `make_fixtures.py` and `seed.py`.

Demo accounts (password `Pramana@2026`):

| User | Role |
|---|---|
| officer | AICTE scrutiny officer |
| verifier | Verification cell |
| admin | Administrator / auditor |
| inst1 ... inst11 | Applicant institution for application A1 ... A11 |

## Tests and evaluation

```bash
cd backend
.venv/Scripts/python -m pytest              # 162 tests: rules, forensics, signatures, QR, uploads, workflow, platform, officer tools, history, photos, edits, insights
.venv/Scripts/python scripts/evaluate.py    # planted conditions, fields, verification outcomes, controls
.venv/Scripts/python scripts/eval_hindi.py  # Hindi OCR accuracy
.venv/Scripts/python scripts/eval_ask.py    # Ask why: kept sentences, citations, latency
.venv/Scripts/python scripts/bench_sandbox.py
```

Current results, measured on 24 Oct 2026 on the merged code:
- **Test applications:** 54 of 54 planted problems found across 11 test applications (83 documents), with 0 false alarms, in deterministic mode. With the fine-tuned model switched on: 50 of 50 (in model mode A11 expects only its instruction-line finding), with 0 false alarms.
- **Fields:** deterministic patterns read 323 of 328 printed fields; the 5 misses are A11's unfamiliar layout, which goes to manual review without a model. With the model, 328 of 328.
- **Randomised blind test:** 300 generated applications over three seeds gave 99.2% recall and 91.6% precision. After the fixes, two fresh seeds (200 applications) gave 100% recall and precision, with 0 false alarms on 55 clean applications. Anyone can rerun it with their own seed; see `docs/features/random-eval.md`.
- **Everyday-editor test:** 18 of 18 edit methods caught (Word, Edge, Acrobat comment tools, print to PDF, photo of a printout); see `docs/features/edits.md`.
- **Real documents:** 9 of 9 real DSC-signed Government e-Gazettes verified against the CCA India roots, with 0 false indicators.
- **Our model (version 2):** the fine-tuned Qwen3 1.7B extractor gets 94.7% of fields fully correct on held-out layouts, against 82.5% for a general 4B model and 89.1% for a 20B model on a cloud service. It followed 0 of 30 planted instructions, against 9 and 3, at about 1.1 s per document.
- **Speed:** a validation run takes about 1.1 to 1.8 s per application on a laptop CPU, once documents are read.
- **Tests:** 162 automated tests pass on SQLite. On the platform branch, the full suite at that point (35 tests) also passed on PostgreSQL 16.2.

Method, controls and limitations: `docs/evaluation-results.md`.

## Optional models

- **Local extractor** (used in the demo setting):
  1. Install Ollama.
  2. Build `pramana-extract-v2` with `backend/training` (Kaggle notebook or script, `merge_adapter.py`, Q8_0 conversion).
  3. Set `PRAMANA_LLM_PROVIDERS=ollama` in `backend/.env`.
  A model value is kept only when it is found on the page.
- **Ask why** uses `qwen3:4b-instruct-2507-q4_K_M` through Ollama by default. Without a reachable model it answers from templates built from the same evidence.
- **No cloud models.** Every model runs on this machine, so document text never leaves it. A cloud model (GPT-OSS 20B via Groq) was measured once for comparison and scored below our fine-tuned extractor; see docs/evaluation-results.md.

## Layout

```
backend/
  pramana/            FastAPI app
    pipeline/         intake, text and OCR (including Devanagari), extraction, facts, validation runs
    rules/            expression language, facts with provenance, rule engine
    verification/     PDF signatures (pyHanko), signed QR, issuer adapters, demo PKI
    forensics/        PDF structure, fonts, seal images, photo metadata, fingerprints
    consistency/      cross-application links, seal reuse, relationship graph
    history/          revision time machine, re-verification watch, year-over-year comparison
    officer/          deficiency letter, evidence pack and its checker, Ask why
    photos/           campus map data, Content Credentials, room and seat indicator
    api/              routes, including live run progress and the public scan endpoint
    jobs.py           background validation queue
    sandbox.py        parser sandbox (workers in sandbox_worker.py)
    keyring.py        per-document envelope encryption
    retention.py      retention policy and purge
    sim/              SIMULATED issuer registries
  rulesets/           APH 2024-27 ruleset (YAML, cited, with Hindi label patterns)
  trust/              CCA India roots (india-pki), DEMO PDF root, DEMO capture CA for C2PA
  models/             downloaded model weights (gitignored)
  scripts/            asset fetch, fixtures, seed, evaluation, benchmarks, key rotation, purge
  training/           extractor fine-tuning and evaluation
  tests/
frontend/             React + Vite + TypeScript UI (Cytoscape.js for the integrity network, Leaflet for the campus map)
docs/                 research, requirements matrix, decisions, USP and demo, security, evaluation
docs/features/        one document per feature area
```

## Configuration

Environment variables, prefix `PRAMANA_`, in `backend/.env` (see `.env.example`). The settings most worth knowing:

| Variable | Default | Purpose |
|---|---|---|
| `DATA_DIR` | `var/` | Runtime data directory |
| `DATABASE_URL` | SQLite in `DATA_DIR` | PostgreSQL with `postgresql+psycopg://...` and the `postgres` extra |
| `MASTER_KEY` | generated into `var/keys/master` | Base64 256-bit key that wraps the per-document data keys |
| `STORAGE_KEY` | unset | Fernet key, only to open files stored before envelope encryption |
| `DEMO_MODE` | `true` | Show demo accounts; never with real data |
| `COOKIE_SECURE` | `false` | Behind HTTPS: `__Host-` cookie and HSTS |
| `BACKGROUND_RUNS` | `true` | Validate in the background with live progress |
| `PARSER_SANDBOX` | `true` | Parse untrusted files in worker processes |
| `SANDBOX_TIMEOUT_S`, `SANDBOX_MEMORY_MB` | `120`, `1536` | Limits per parser operation and per worker |
| `LOGIN_MAX_PER_IP`, `LOGIN_MAX_FAILURES_PER_USER` | `60`, `5` | Sign-in throttling per 15-minute window |
| `RETENTION_DOCUMENT_DAYS` | `730` | Days to keep document files after an application is closed or withdrawn |
| `PKI_FETCH_REVOCATION` | `false` | Check OCSP and CRL online |
| `MODELS_DIR`, `FETCH_MODELS` | `backend/models`, `true` | Where model weights live, and whether the Devanagari model may be fetched on first use |
| `MAP_TILE_URL` | OpenStreetMap | Campus map tiles; empty shows a plain plot only |
| `WATCH_INTERVAL_HOURS` | `24` | Re-verification watch interval |
| `LLM_PROVIDERS`, `OLLAMA_MODEL` | empty, `pramana-extract-v2` | `ollama` turns on the fine-tuned extractor for fields the patterns miss |
| `ASK_PROVIDERS` | `ollama` | Ask why providers; empty uses templates only |

The full lists are in the settings section of each feature document.

## Open source

Pramana is released under the MIT licence. Every dependency is free and open source, and model weights use permissive licences:
- **Backend:** FastAPI, SQLAlchemy, pyHanko, pikepdf, pdfplumber, pypdfium2, RapidOCR with PP-OCR ONNX weights including the PP-OCRv5 Devanagari recogniser (Apache-2.0), onnxruntime, YOLOX-M ONNX weights (Apache-2.0), c2pa-python (MIT or Apache-2.0), OpenCV, Pillow, imagehash, networkx, rapidfuzz, reportlab, segno, cryptography, argon2-cffi; optional psycopg 3 (LGPL-3.0) for PostgreSQL.
- **Frontend:** React, Vite, Tailwind CSS, TanStack Query, Cytoscape.js and three.js (MIT), and Leaflet (BSD-2-Clause). Map data and tiles are from OpenStreetMap contributors (ODbL), with the attribution always shown.
- **Fixtures only:** Noto Sans Devanagari (SIL Open Font License), uharfbuzz and fontTools, and three Wikimedia Commons photos under CC BY-SA 3.0, CC BY-SA 4.0 and CC0. The photos and fonts are downloaded, not committed; attributions are in `docs/features/photos.md`.

We deliberately avoided AGPL PDF libraries and detection, OCR or forensics models with non-commercial or AGPL weight licences; `docs/architecture-decisions.md` explains why.

