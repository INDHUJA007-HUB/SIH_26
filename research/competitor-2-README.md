# AICTE SmartValidate

> **AI-Powered Technical Institution Application Validation, Document Authentication & Regulatory Compliance Platform**  
> *Developed for Smart India Hackathon (SIH) — Decision-Support Platform for AICTE Institutional Approvals*

---

## 1. Executive Summary & Problem Solved

The All India Council for Technical Education (AICTE) processes thousands of applications annually from technical universities, engineering colleges, polytechnics, and management institutes for **Extension of Approval (EoA)**, changes in approved intake, and new programme additions.

Manual examination of these applications is labor-intensive and prone to bottlenecks due to:
- Missing statutory certificates (Fire NOC, Affiliation, Land Use, Building Safety).
- Expired certificates or dates falling outside the applicable academic review window.
- Inconsistent declarations between institutional forms and supporting PDFs.
- Duplicate file uploads reusing certificates across distinct clearance slots.
- Reliance on external issuing authorities that may experience temporary downtime.

**AICTE SmartValidate** is an AI-powered regulatory decision-support system that:
1. **Validates application parameters & dossiers** using a configurable deterministic rule engine.
2. **Extracts structured text & metadata** from text-based and scanned PDFs using PyMuPDF / pypdf and OCR pipelines.
3. **Detects discrepancies & missing items**, including faculty count mismatches, student-to-faculty ratio violations, and institution name variances.
4. **Performs multi-signal anomaly inspection**, including cryptographic SHA-256 binary hash collision detection and chronological contradiction checks.
5. **Simulates issuing authority verification** through adapter architecture for state universities, fire directorates, and municipal town planning registries.
6. **Maintains an immutable, append-only audit trail**, ensuring complete accountability while keeping final approval decisions firmly in the hands of authorized AICTE officials.

---

## 2. Technology Stack

### Frontend
- **Framework**: React 19 with Vite 8 & TypeScript
- **Styling**: Tailwind CSS v4 with custom Government-Tech SaaS tokens & Inter typography
- **Navigation & State**: React Router DOM v7
- **Icons**: Lucide React
- **Visualizations**: Recharts (Pie/Donut charts, Area trend charts, Horizontal & Vertical Bar charts)
- **Notifications**: Custom contextual toast notification system

### Backend
- **Framework**: Python 3.12 with FastAPI & Starlette
- **Data Validation & Schemas**: Pydantic v2
- **ORM & Database**: SQLAlchemy 2.0 with SQLite (clean schema abstraction ready for PostgreSQL)
- **Document Processing**: `pypdf`, `reportlab`, `Pillow` (PIL), and optional `pytesseract` / Tesseract OCR
- **Security & RBAC**: PBKDF2-SHA256 password hashing, HMAC-SHA256 bearer tokens, Role-Based Access Control

---

## 3. Demo Roles & Test Credentials

The portal includes a clearly labeled login screen with **1-click quick login cards** for testing each role:

| Role | Email | Password | Scope & Permissions |
| :--- | :--- | :--- | :--- |
| **Institution User** | `institution@demo.aicte.gov.in` | `Demo@123` | Create & submit applications, upload supporting documents, view detected deficiencies, submit corrections. |
| **AICTE Reviewer** | `reviewer@aicte.gov.in` | `Reviewer@123` | Scrutinize assigned dossiers, inspect OCR fields, trigger authority verification, record observations, issue notices. |
| **Administrator** | `admin@aicte.gov.in` | `Admin@123` | Global view of all applications, configure compliance rules, inspect full audit trail, reset demo sandbox. |

*Note: You can also switch personas on the fly at any time using the **Role Switcher** in the top navigation header.*

---

## 4. Pre-Seeded Demonstration Scenarios (Scenarios A through G)

The system automatically initializes 7 realistic institutional applications with authentic generated PDF documents in `backend/uploads/`:

### **Scenario A: Application with No Detected Issues**
- **Dossier**: `APP-2026-001` — *Delhi Institute of Technology & Science*
- **Category**: Extension of Approval (EoA)
- **Outcome**: **Checks Passed**
- **Details**: All 5 mandatory documents uploaded; university affiliation and fire clearances verified by simulated authority; no date or faculty mismatches.

### **Scenario B: Missing Mandatory Document**
- **Dossier**: `APP-2026-002` — *National Engineering Academy, Pune*
- **Category**: Change in Approved Intake
- **Outcome**: **Deficiencies Found**
- **Details**: Fails `RULE-DOC-MISSING`. The mandatory *Building Safety Certificate* is absent from the dossier. The system flags the deficiency and guides the user to upload it.

### **Scenario C: Expired Regulatory Certificate**
- **Dossier**: `APP-2026-003` — *Apex Institute of Management & Research, Bengaluru*
- **Category**: New Course Approval
- **Outcome**: **Deficiencies Found**
- **Details**: Fails `RULE-EXP-001`. Extracted affiliation certificate expired on `30-Jun-2025` prior to the active AY 2026-27 approval cycle. Authority adapter confirms expired status.

### **Scenario D: Inconsistent Institutional Information**
- **Dossier**: `APP-2026-004` — *Himalayan Polytechnic, Dehradun*
- **Category**: Extension of Approval (EoA)
- **Outcome**: **Manual Review Required**
- **Details**: Fails `RULE-FAC-003` & `RULE-NAME-002`. Application declares 48 teaching faculty, but extracted roster document confirms only 42 positions. Document also lists name variance (*Himalaya Technical Institute*).

### **Scenario E: Potential File Duplicate (SHA-256 Collision)**
- **Dossier**: `APP-2026-005` — *Vanguard Institute of Computer Applications, Hyderabad*
- **Category**: Extension of Approval (EoA)
- **Outcome**: **Deficiencies Found (High Anomaly Score)**
- **Details**: Fails `RULE-DUP-005`. The file uploaded for *Land Use Certificate* and *Building Safety Certificate* share an identical SHA-256 binary hash (`ANOM-HASH-DUP`).

### **Scenario F: Authority Verification Mismatch**
- **Dossier**: `APP-2026-006` — *Konkan Coast Engineering College, Ratnagiri*
- **Category**: Programme Expansion
- **Outcome**: **Manual Review Required**
- **Details**: The application requests 360 approved intake including Computer Science & AI. Querying the simulated university authority returns only 240 approved intake (Civil & Mechanical sanctioned only).

### **Scenario G: Manual Review Required (Source Unavailable & Low OCR)**
- **Dossier**: `APP-2026-007` — *Saraswati Technical Campus, Lucknow*
- **Category**: Extension of Approval (EoA)
- **Outcome**: **Manual Review Required**
- **Details**: Fails `RULE-OCR-006`. Scanned document yields low machine readability confidence (42%). Simulated state fire service gateway returns `HTTP 503 Source Unavailable`. The dossier routes to human inspection without falsely flagging forgery.

---

## 5. System Architecture & Features

```
┌────────────────────────────────────────────────────────┐
│               React + Vite Frontend (UI/UX)            │
│  Overview • Applications • Verification • Compliance   │
│   Anomaly Detection • Reports & Dossier • Audit Trail  │
└───────────────────────────▲────────────────────────────┘
                            │ REST APIs / JWT Bearer
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
│  Auth Router • Apps Router • Docs Router • Audit Log   │
└───────┬──────────────┬──────────────┬───────────┬──────┘
        │              │              │           │
┌───────▼──────┐┌──────▼───────┐┌─────▼─────┐┌────▼──────┐
│  Document    ││ Deterministic││  Anomaly  ││ Simulated │
│  Processor   ││ Rule Engine  ││ Detection ││ Authority │
│  (pypdf/OCR) ││  (Validation)││ (SHA-256) ││  Adapter  │
└──────────────┘└──────────────┘└───────────┘└───────────┘
```

### Main Application Tabs
1. **Overview Dashboard**: Live metric summary cards, status distributions, monthly trends, and recent applications table.
2. **Applications Directory**: Complete multi-step creation form, category/status filters, CSV export, and quick scenario navigator.
3. **Application Detail Dossier**: 6 connected tabs:
   - *Tab 1: Overview*: Profile, declared capacities, programmes table, activity timeline.
   - *Tab 2: Documents & OCR*: File size, SHA-256 hash, OCR confidence badge, field corrections modal, download scan link.
   - *Tab 3: Validation Results*: Evidence-linked finding cards with expected vs found values and reviewer observation modal.
   - *Tab 4: Issuing Authority Verif*: Authority records, status badges, one-click verify, and JSON payload inspector.
   - *Tab 5: Regulatory Compliance*: AICTE Approval Process Handbook checklist (FSR, Land, Fire, Built-up area norms).
   - *Tab 6: Review History*: Chronological audit trail specific to this dossier.
4. **Document Verification Gateway**: Central table of all statutory clearance records, verification status, and manual retry options.
5. **Compliance Review Engine**: Scrutiny matrix + Configurable Rule Manager allowing administrators to publish new rules.
6. **Multi-Signal Anomaly Detection**: Explanatory anomaly scoring (0-100) based on SHA-256 duplicates, chronological date conflicts, and scan legibility.
7. **Reports & Analytics**: Status breakdowns, deficiency frequencies, processing latency metrics, and printable formal validation dossier.
8. **Audit Trail**: Append-only tamper-evident regulatory ledger with actor, role, timestamp, action type, and IP address.
9. **Settings & Demo Reset**: OCR status, active authority adapters, and 1-click confirmation dialog to reset demo records.

---

## 6. Local Setup and Execution Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### Step 1: Start the Backend Server
```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
*The backend will automatically create SQLite tables and seed demo accounts and Scenarios A–G on first run.*

### Step 2: Start the Frontend Application
```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### Step 3: Access the Application
Open your browser and navigate to:
```
http://127.0.0.1:5173/login
```
Click any of the **1-Click Demo Evaluation Roles** on the login screen to start exploring.

---

## 7. Scope & Boundaries (Implemented vs Simulated)

| Feature | Implementation Details |
| :--- | :--- |
| **PDF Text Extraction** | Fully functional using `pypdf` reading embedded PDF streams, character encoding, and document metadata. |
| **OCR for Scans & Images** | Functional image preprocessing via `Pillow` and `pytesseract` (with automatic fallback to pure Python extraction if Tesseract binary is uninstalled). |
| **Cryptographic Hashing** | Real SHA-256 checksums calculated across uploaded file contents to detect duplicates. |
| **Deterministic Validation** | Real rule engine evaluating required checklists, expiry dates, faculty counts, and name similarities. |
| **Issuing Authority Verification** | Built on an **adapter pattern** returning deterministic synthetic payloads for demonstration purposes. *Does not make live calls to real government databases.* |
| **Database Persistence** | Real SQLite database (`aicte_smartvalidate.db`) managed via SQLAlchemy ORM. |
| **Immutable Audit Trail** | Real database-persisted append-only audit event log. |

---

## 8. License & Attribution
Developed for the **Smart India Hackathon (SIH)**. Fictional institutional identities are used for demonstration purposes only.

