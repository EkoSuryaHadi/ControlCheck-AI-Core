# ControlCheck AI — Enterprise Project Control & Audit Platform

ControlCheck AI is a deterministic project-control audit engine and AI-powered intelligence platform for EPC (Engineering, Procurement, and Construction) cost, schedule, progress, and data-quality governance.

Guided by the foundational principle: **"Deterministic engine calculates, AI explains."**

---

## Consolidated Baseline Status

This repository currently represents the verified PR 1 consolidation baseline for the planned public beta. It preserves the accepted v0.6.x homepage, Actions, Governance, Finding Closure, reporting, deterministic engine, controlled validation fixtures, and existing custom JWT/RBAC behavior. It also adds governed, lossless workbook extraction; immutable PostgreSQL snapshots; database-backed deterministic analysis; domain-readiness gating; and tenant-scoped snapshot APIs.

This baseline is **not the public-beta implementation and is not public-launch ready**. Clerk identity, private Vercel Blob storage, fair-use quota, product telemetry, user feedback, billing, and the public-beta UI are explicitly deferred to later governed PRs. The approved product direction remains an implementation-pending design in [`docs/superpowers/specs/2026-08-24-controlcheck-vercel-public-beta-ui-design.md`](docs/superpowers/specs/2026-08-24-controlcheck-vercel-public-beta-ui-design.md).

---

## Public Beta Cloud Deployment Contract

The public-beta architecture is **browser → Vercel frontend → Render Free FastAPI → Supabase Free PostgreSQL plus private Cloudflare R2 Standard object storage**. Vercel is frontend-only and receives the Render API base URL through `VITE_API_BASE_URL`; it does not host the FastAPI service.

Provider responsibilities are deliberately narrow:

- **Vercel:** builds and serves the React frontend using the exact beta origin `https://control-check-ai-git-codex-public-8a91d7-ekosuryahadis-projects.vercel.app`.
- **Render Free FastAPI:** runs the Singapore `controlcheck-api` service, performs migrations before startup, and exposes `/health/ready` at the trusted host `controlcheck-api.onrender.com`.
- **Supabase Free PostgreSQL:** stores accounts, projects, analysis runs, findings, evidence, and measurement records through the `CONTROLCHECK_DATABASE_URL` Session Pooler connection on port 5432.
- **Cloudflare R2 Standard:** retains uploaded workbooks in the private `controlcheck-beta-workbooks` bucket (region `auto`) using dashboard-only endpoint and scoped credential secrets.

Hosted data flow is **register/login → create project → upload workbook → persist workbook in R2 → canonical ingestion and deterministic analysis on Render → persist run/findings/evidence in Supabase → display results in Vercel**. Provision in that order: Supabase database, private R2 bucket and scoped credentials, Render service plus secrets, then Vercel `VITE_API_BASE_URL` and redeploy. Keep all connection strings, keys, and endpoints that identify an account in provider dashboards or deployment secrets only: no secrets appear in source/logs/docs.

The beta must demonstrate that the hosted register-to-findings flow passes and that uploaded files and results persist across Render restart/cold start. Render cold start after idle and Supabase Free may pause after low activity; a readiness failure should be retried after the service wakes, then verified by logging in, opening a project, and loading prior findings. Supabase Free has limited capacity/no managed downloadable backups. Upgrade if cold starts materially affect user experience, the Supabase database approaches 400 MB, R2 approaches 8 GB, or routine usage warrants an always-on backend. Full authentication/RBAC hardening, payment/subscription, enterprise SSO, and production-scale HA/DR remain deferred.

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
│  - 10 Alembic revs     │  - Salted Bcrypt Hash     │  - Grounded Assistant & Tools     │
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

### 2. Governed Ingestion & Raw-Row Lineage
- Extracts every non-empty governed workbook row without lossy header collision or scalar coercion.
- Persists immutable governed snapshots, raw rows, six canonical domains, mapping-profile provenance, source coordinates, and domain readiness in PostgreSQL.
- Loads deterministic analysis datasets from persisted governed facts and records stable skip metadata when a rule's required domain is blocked.
- Keeps earlier simplified snapshots readable as a compatibility contract; new snapshot writes use governed storage.

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
uvicorn controlcheck.asgi:app --app-dir src --host 127.0.0.1 --port 8000
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

### 3. Consolidated Baseline Verification
```powershell
# Backend syntax, production configuration, and full suite
python -m compileall -q api src tests tools alembic
python -m pytest -q tests/test_production_configuration.py tests/test_serverless_entrypoint.py -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
python -m pytest -q tests/persistence/test_migrations.py::test_alembic_metadata_has_no_drift -p no:cacheprovider

# Frontend clean install, typecheck/build, and lint
cd frontend
npm ci
npm run build
npm run lint
```

Persistence and migration gates require a PostgreSQL 16 admin URL in `CONTROLCHECK_TEST_POSTGRES_URL`. The test harness creates and drops only a disposable `controlcheck_test_<uuid>` database; it never migrates or drops the configured shared database.

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
| **Health** | `GET` | `/v1/analysis-runs/{run_id}/health` | Retrieve health score, computation status, rule coverage, unavailable domains, and key drivers |
| | `GET` | `/v1/projects/{project_id}/health-trend` | Retrieve project historical health trend |
| **AI Assistant**| `POST` | `/v1/projects/{project_id}/ai/ask` | Ask grounded AI questions about project performance |
| | `GET` | `/v1/projects/{project_id}/ai/conversations` | List conversation threads |
| | `GET` | `/v1/ai/conversations/{conv_id}/messages` | View chat message history |

---

## 🧪 Testing & Verification

Run the complete backend suite:
```powershell
python -m pytest -q -p no:cacheprovider
```

CI additionally performs Python bytecode compilation, strict production-configuration tests, live PostgreSQL migration-drift verification, and frontend `npm ci`, behavior-test, typecheck/build, and lint gates. Runtime modes are trimmed, case-normalized, and restricted to the documented development/test/production set; Vercel, Lambda, and Render production signals cannot be overridden by a weaker application mode. Production startup fails closed when its JWT secret, database URL, exact CORS origins, exact trusted hosts, durable storage configuration, or catalogue is absent, and no diagnostic endpoint exposes import traces, paths, or environment-variable names. The accepted S3 SDK is a base runtime dependency across package, requirements, lockfile, container, Render, and Vercel installation paths; readiness verifies actual local-directory or S3-bucket access before reporting storage ready, and provider failures return a safe `503` envelope. Governed health is reported as `Partial` or `Not Computed`, with nullable scores and explicit coverage/unavailable-domain metadata, whenever domain gates prevent complete analysis; unavailable data is never labeled Healthy.

---

## 📚 Document Governance
- **PRD v1.0**: `docs/ControlCheck_AI_PRD_v1.0.docx`
- **UI/UX Design Spec v0.1**: `docs/ControlCheck_AI_UI_UX_Design_Spec_v0.1.docx`
- **ERD & Database Spec v0.3**: `docs/ControlCheck_AI_ERD_Database_Spec_v0.3.docx`
- **SQL Canonical Schema**: `docs/003_controlcheck_canonical_schema_v0.3.sql`
- **Latest implementation status**: `docs/ControlCheck_AI_Implementation_Update_v0.6.19.md`
