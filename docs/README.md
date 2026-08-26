# ControlCheck documentation artifacts

The files below are immutable v0.1 historical references copied into this project. Their byte-level SHA-256 values are recorded in `reference_artifacts_v0.1.sha256.json`:

- `001_controlcheck_core_schema.sql`
- `ControlCheck_AI_Control_Rule_Catalogue_v0.1.docx`
- `ControlCheck_AI_ERD_Database_Spec_v0.1.docx`
- `ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx`
- `controlcheck_expected_findings_v0.1.json`
- `controlcheck_rule_catalogue_v0.1.json`

Runtime catalogues and validation fixtures under `data/` remain the canonical execution inputs. Versioned documents under `docs/` describe product and architecture history; they do not override runtime JSON artifacts or executable Alembic migrations.

## Current aligned specifications

- `ControlCheck_AI_PRD_v0.3.docx` — product scope updated for Phase 4A persistence, Phase 4B sequencing, and deferred authentication/RBAC.
- `ControlCheck_AI_ERD_Database_Spec_v0.2.docx` — database specification aligned to the Phase 4A persistence contract.
- `ControlCheck_AI_Control_Rule_Catalogue_v0.2.docx` — governed 20-rule runtime alignment and active thresholds.
- `002_controlcheck_persistence_schema_v0.2.sql` — readable PostgreSQL schema reference. Alembic migration `20260817_0001` is the executable schema authority.

Rendered visual-QA previews are stored under `validation/previews/phase4a-docs/`.

## Consolidated public-beta baseline

`ControlCheck_AI_Implementation_Update_v0.6.19.md` records the verified PR 1 consolidation baseline: the accepted v0.6.x product behavior plus governed canonical ingestion, immutable snapshots, database-backed deterministic analysis, production failure hardening, and restored CI gates.

The active public-beta release candidate uses **Vercel React + FastAPI** with the topology **browser → Vercel React frontend → Vercel FastAPI Function → Supabase PostgreSQL + private Cloudflare R2**. The initial workbook boundary is **4 MiB**, database migration is an **explicit release step**, and the hosted acceptance flow is **register/login → create project → upload workbook** through findings persistence. Full authentication/RBAC hardening, payment/subscription, enterprise SSO, and production-scale HA/DR remain deferred.

`ControlCheck_AI_PRD_v1.2.docx` is the current product requirement authority for this deployment. Earlier versioned PRDs remain immutable historical references.
