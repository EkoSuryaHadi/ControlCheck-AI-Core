# ControlCheck AI Public Beta Cloud Deployment Plan

**Goal:** Deploy the public beta with Vercel serving only the frontend, Render Free hosting FastAPI, Supabase Free providing PostgreSQL, and Cloudflare R2 storing uploaded workbooks.

**Architecture:** The browser calls the Render API directly through `VITE_API_BASE_URL`. Render connects to Supabase through the IPv4-compatible session pooler and stores uploaded workbooks in a private R2 Standard bucket. Production settings fail closed when durable services or exact origins/hosts are missing.

**Global constraints:** Preserve the stable backend baseline at `22fff4d`; remove only the three Vercel Python packaging experiments; keep full authentication/RBAC and payments out of scope; never commit or log secrets; use exact CORS origins and trusted hosts; update PRD/operations documentation for every architecture change; do not merge until the hosted register-to-findings flow passes.

## Task 1: Restore Vercel to frontend-only hosting

- Revert commits `14ae1c7`, `d18d599`, and `e864544` without rewriting history.
- Remove Python-function routing and packaging from the Vercel deployment.
- Keep SPA fallback routing and the existing frontend build.
- Add or update tests that prove Vercel no longer packages `api/index.py` and frontend API configuration remains environment-driven.
- Run focused packaging/configuration tests plus frontend test, build, and lint.
- Commit the task.

## Task 2: Prepare Render, Supabase, and R2 runtime configuration

- Update `render.yaml` for Render Free in Singapore.
- Configure Supabase through secret `CONTROLCHECK_DATABASE_URL`; runtime value will use Session Pooler port 5432.
- Configure private Cloudflare R2 Standard storage with bucket `controlcheck-beta-workbooks`, region `auto`, endpoint URL, and scoped access credentials supplied only through Render secrets.
- Use exact public-beta Vercel origin and exact Render hostname; no wildcard CORS or trusted hosts.
- Preserve automatic Alembic migration followed by FastAPI startup and `/health/ready` health checking.
- Add configuration contract tests and run focused backend production-setting tests.
- Commit the task.

## Task 3: Update PRD and operations documentation

- Record the Vercel–Render–Supabase–R2 architecture, free-tier limitations, secret-handling rules, deployment order, recovery procedure, and upgrade triggers.
- Record that full authentication/RBAC and payments remain deferred.
- Update developer/production documentation and the tracked PRD source/document according to the repository's established document-generation workflow.
- Run document consistency tests and commit the task.

## Task 4: Provision and connect hosted services

- Create Supabase project `controlcheck-ai-beta` in Singapore and obtain its Session Pooler connection string.
- Create or select private R2 Standard bucket `controlcheck-beta-workbooks` and a bucket-scoped read/write token.
- Deploy the Render Blueprint, enter secrets in the provider dashboards, and verify migrations and readiness.
- Set Vercel `VITE_API_BASE_URL` to the Render public URL and redeploy the frontend.
- Never place secret values in repository files, logs, reports, or chat.

## Task 5: End-to-end verification and handoff

- Verify `/health`, `/health/live`, and `/health/ready`.
- Verify register, login, project creation, workbook upload, deterministic analysis, findings/evidence, refresh persistence, and expected failure paths.
- Confirm records persist in Supabase and objects persist in R2 after Render restart/cold start.
- Run the full backend suite, migration-drift tests, frontend test/build/lint, and hosted browser smoke test.
- Update the pull request only after all gates pass; do not merge without explicit user approval.

