# ControlCheck AI — Enterprise Project Control & Audit Platform

ControlCheck AI is a deterministic project-control audit engine and AI-powered intelligence platform for EPC (Engineering, Procurement, and Construction) cost, schedule, progress, and data-quality governance.

Guided by the foundational principle: **"Deterministic engine calculates, AI explains."**

---

## 🏛️ Platform Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   ControlCheck AI                                      │
├────────────────────────┬───────────────────────────┬───────────────────────────────────┤
│  1. Ingestion Layer    │  2. Deterministic Engine  │  3. Health Scoring Engine         │
│  - Raw-Row Extraction  │  - 20 Catalogue Rules     │  - Formula PRD §13 (30/30/25/15)  │
│  - Lineage Tracking    │  - 100% Deterministic     │  - Cost/Sched/Prog/DQ Score Bands │
│  - Canonical Facts     │  - Evidence Traceability  │  - Historical Trend Snapshots     │
├────────────────────────┼───────────────────────────┼───────────────────────────────────┤
│  4. Persistence Layer  │  5. Auth & RBAC Layer     │  6. AI Intelligence & Safety      │
│  - PostgreSQL 16       │  - JWT Access & Refresh   │  - Controlled Zero-Hallucination  │
│  - 5 Alembic Revisions │  - Salted Bcrypt Hash     │  - Grounded Assistant & Tools     │
│  - Cursor Pagination   │  - Org & Project Roles    │  - Conversation & Message Memory  │
├────────────────────────┴───────────────────────────┴───────────────────────────────────┤
│  7. Executive React Web Application (Vite + React 19 + TypeScript + Tailwind CSS v4)   │
│  - Dark Navy App Shell & Dynamic Project Selector                                      │
│  - Executive Dashboard: 0-100 Health Gauge, Cost Performance, S-Curve Trend, Top Risks │
│  - Findings Register & Finding Detail with 5 Tabs (Overview, Evidence, AI, Actions)   │
│  - 4-Step Ingestion & Mapping Wizard with AI Confidence Badges                         │
│  - Evidence-Grounded AI Assistant with Quick Prompt Chips & Finding Citations          │
│  - Executive Reports Registry with PDF Sample Preview                                  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Modules & Capabilities

### 1. Deterministic Audit Engine (20 Rules)
- Evaluates cost overruns (`CST`), schedule delays (`SCH`), progress discrepancies (`PRG`), and data quality anomalies (`DQ`).
- Every finding includes stable IDs, entity grains, calculations, business impacts, recommendations, and traceable evidence.

### 2. Ingestion & Raw-Row Lineage (Phase 4B)
- Extracts verbatim rows from Excel workbooks (`raw_rows` table).
- Maps raw records to canonical facts (`wbs_nodes`, `budget_records`, `cost_records`, `commitment_records`, `schedule_activities`, `progress_records`) with `raw_row_id` foreign keys for end-to-end auditability.

### 3. Project Health Scoring Engine (Phase 5C)
- Standardized weighted formula:
  $$\text{Health Score} = 0.30 \times \text{Cost} + 0.30 \times \text{Schedule} + 0.25 \times \text{Progress} + 0.15 \times \text{DQ}$$
- Severity penalties: `critical` (-15), `warning` (-5), `observation` (-1).
- Score bands: `Healthy` (80–100), `Needs Attention` (60–79), `At Risk` (40–59), `Critical` (0–39).
- Historical trend tracking via `health_snapshots`.

### 4. Authentication & Multi-Tenant RBAC (Phase 4C)
- Salted `bcrypt` password hashing and JWT token issuance (Access & Refresh tokens).
- Multi-tier role authorization:
  - Organization roles: `org_admin`, `org_member`, `org_viewer`.
  - Project roles: `project_manager`, `project_member`, `project_viewer`.

### 5. AI Intelligence Layer & Safety Guardrails (Phase 6)
- **Zero-hallucination guarantee**: The AI assistant never invents financial figures, dates, or activity IDs.
- **Controlled Tools**: `get_project_health`, `get_top_cost_drivers`, `get_delayed_activities`, `get_finding_evidence`.
- Context-aware natural language assistant for executive summaries, delay root-cause analysis, and cost overrun explanations.

### 6. Executive React Web Application
- Built in `frontend/` using **React 19**, **TypeScript**, **Tailwind CSS v4**, **Recharts**, **Lucide**, and **TanStack Query**.
- 10 complete route views matching approved [UI/UX Design Spec v0.1](docs/ControlCheck_AI_UI_UX_Design_Spec_v0.1.docx) visual mockup.

---

## 🛠️ Quickstart & Setup

### Prerequisites
- Python 3.11+
- Node.js 20+ & npm
- Docker or Podman (for PostgreSQL database)

### 1. Backend Setup & Run
```powershell
# Install Python dependencies
python -m pip install -e ".[dev]"

# Start PostgreSQL database
podman compose up -d postgres
$env:CONTROLCHECK_DATABASE_URL = "postgresql+psycopg://controlcheck:controlcheck@127.0.0.1:54329/controlcheck"
alembic upgrade head

# Launch FastAPI Backend
$env:CONTROLCHECK_CATALOGUE = "data\controlcheck_rule_catalogue_v0.2.json"
$env:CONTROLCHECK_UPLOAD_ROOT = "var\uploads"
uvicorn controlcheck.api:app --app-dir src --host 127.0.0.1 --port 8000
```

### 2. Frontend React Web Application Setup
```powershell
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite Development Server with live API proxy
npm run dev

# Open in browser
# http://127.0.0.1:5173/
```

### 3. Production Single-Container Build
```powershell
# Build frontend bundle
cd frontend
npm run build

# Run all backend tests
cd ..
python -m pytest -q -p no:cacheprovider
```

---

## 📡 REST API Reference

| Domain | Method | Endpoint | Description |
|---|---|---|---|
| **Auth** | `POST` | `/v1/auth/register` | Register user & initialize organization |
| | `POST` | `/v1/auth/login` | Obtain JWT access and refresh tokens |
| **Projects** | `POST` | `/v1/organizations/{org_id}/projects` | Create a new scoped project |
| | `GET` | `/v1/organizations/{org_id}/projects` | List projects with pagination |
| **Audits & Runs** | `POST` | `/v1/projects/{project_id}/analysis-runs` | Upload workbook & trigger audit (Supports `X-Idempotency-Key`) |
| | `GET` | `/v1/projects/{project_id}/analysis-runs` | List analysis runs |
| | `GET` | `/v1/analysis-runs/{run_id}/findings` | List findings with severity/category filters |
| **Findings** | `PATCH` | `/v1/findings/{finding_id}/status` | Update finding status (`open`, `in_review`, `resolved`) |
| | `GET` | `/v1/findings/{finding_id}/evidence` | Retrieve verbatim raw-row evidence records |
| **Health** | `GET` | `/v1/analysis-runs/{run_id}/health` | Retrieve health score breakdown & key drivers |
| | `GET` | `/v1/projects/{project_id}/health-trend` | Retrieve project historical health trend |
| **AI Assistant**| `POST` | `/v1/projects/{project_id}/ai/ask` | Ask grounded AI questions about project performance |
| | `GET` | `/v1/projects/{project_id}/ai/conversations` | List conversation threads |
| | `GET` | `/v1/ai/conversations/{conv_id}/messages` | View chat message history |

---

## 🧪 Testing & Verification

Run the entire suite of 128 unit, schema, and API verification tests:
```powershell
python -m pytest -q -p no:cacheprovider
```

---

## 📚 Document Governance
- **PRD v1.0**: `docs/ControlCheck_AI_PRD_v1.0.docx`
- **UI/UX Design Spec v0.1**: `docs/ControlCheck_AI_UI_UX_Design_Spec_v0.1.docx`
- **ERD & Database Spec v0.3**: `docs/ControlCheck_AI_ERD_Database_Spec_v0.3.docx`
- **SQL Canonical Schema**: `docs/003_controlcheck_canonical_schema_v0.3.sql`
