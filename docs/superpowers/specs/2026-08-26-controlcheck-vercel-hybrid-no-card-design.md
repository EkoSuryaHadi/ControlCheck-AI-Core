# ControlCheck AI Vercel Hybrid Public Beta Design

**Date:** 2026-08-26  
**Status:** Approved for implementation planning  
**Supersedes:** The active Vercel–Render–Supabase–R2 beta deployment topology  

## 1. Decision

ControlCheck AI will run its public beta as one Vercel deployment containing the React/Vite frontend and a single FastAPI Python Function. Supabase remains the PostgreSQL system of record and Cloudflare R2 remains the private workbook object store. Render is removed from the active beta path because its account verification requires a payment card that is unavailable.

This decision optimizes for a no-card public beta that the product owner can operate immediately. It deliberately accepts Vercel Function limits, most importantly the 4.5 MB request-body ceiling, and sets a 4 MiB workbook limit for the first beta release.

## 2. Goals

- Make the existing public beta usable without a paid hosting account or payment card.
- Preserve the deterministic ControlCheck engine and existing FastAPI application contract.
- Keep uploaded workbooks private and durable in R2.
- Keep projects, analysis runs, findings, evidence, usage data, and feedback durable in Supabase.
- Fail closed when production secrets, durable storage, or database connectivity are unavailable.
- Provide a measurable register-to-findings workflow for early product feedback.
- Keep a clear upgrade path to direct-to-R2 uploads for workbooks larger than 4 MiB.

## 3. Non-goals

- Full authentication and RBAC hardening.
- Billing, subscriptions, or paid-tier enforcement.
- Enterprise SSO, HA/DR, background workers, or asynchronous job orchestration.
- Workbooks larger than 4 MiB in the initial beta.
- Automatic database migration during a Vercel Function cold start.
- Replacing Supabase or R2.

## 4. Runtime Architecture

```text
Browser
  -> Vercel CDN: React/Vite static frontend
  -> /api/*: one Vercel FastAPI Python Function
       -> Supabase PostgreSQL through the IPv4 session pooler
       -> private Cloudflare R2 bucket
       -> deterministic ControlCheck engine
```

The browser uses same-origin `/api` URLs. Vercel routes API requests to `api/index.py`, which exports the canonical ASGI application and removes the external `/api` prefix before dispatch. Static assets and SPA fallback remain handled by Vercel.

The function bundle includes only runtime code, the rule catalogue, and required Python packages. Frontend source, tests, documentation, generated files, validation artifacts, sample workbooks, local virtual environments, and deployment-only files are excluded.

## 5. Request and Data Flow

### 5.1 Identity and project setup

1. A beta user registers or logs in through the existing application endpoints.
2. The API persists the user, organization membership, and project records in Supabase.
3. The API returns the existing JWT/session contract; no Supabase public client key is required by the browser.

### 5.2 Workbook analysis

1. The frontend rejects files larger than 4 MiB before upload and explains the beta limit.
2. The API independently enforces the same 4 MiB limit and validates extension, MIME type, workbook structure, and content.
3. The API computes the workbook digest and writes the original object to the private R2 bucket.
4. Canonical ingestion and deterministic rules run within the same request, bounded by the Vercel Hobby execution limit.
5. The API persists the source file, snapshot, analysis run, findings, evidence, health score, and usage measurements in one governed workflow.
6. The frontend renders the persisted result returned by the API and can retrieve it later from Supabase-backed endpoints.

If persistence or R2 storage fails, the request must not report a successful durable analysis. Error responses use stable safe error codes and never expose credentials, connection strings, stack traces, or workbook contents.

## 6. Vercel Runtime Contract

- Python runtime: a Vercel-supported Python 3.11 version selected through project metadata.
- Entry point: `api/index.py` exporting one ASGI `app`.
- API route: `/api/*` to the Python Function.
- Frontend API base URL: same-origin `/api`; no Render hostname.
- Maximum workbook size: 4 MiB at frontend and backend boundaries.
- Maximum analysis target: 240 seconds, leaving operational margin below the 300-second Hobby maximum.
- Temporary files: writable `/tmp` only, with per-request cleanup; no durability assumption.
- Function bundle: must remain below the 500 MB uncompressed Python limit.
- Migrations: executed as an explicit release step before deployment, never in Function startup.

## 7. Production Configuration

The following values live only in Vercel Environment Variables:

- `CONTROLCHECK_ENV=production`
- `CONTROLCHECK_DATABASE_URL`: Supabase IPv4 session-pooler URI on port 5432
- `CONTROLCHECK_JWT_SECRET`: generated high-entropy secret
- `CONTROLCHECK_STORAGE_BACKEND=s3`
- `CONTROLCHECK_S3_BUCKET=controlcheck-beta-workbooks`
- `CONTROLCHECK_S3_REGION=auto`
- `CONTROLCHECK_S3_ENDPOINT_URL`: account-specific R2 S3 endpoint
- `AWS_ACCESS_KEY_ID`: bucket-scoped R2 credential
- `AWS_SECRET_ACCESS_KEY`: bucket-scoped R2 secret
- `CONTROLCHECK_CORS_ORIGINS`: exact public beta Vercel origin
- `CONTROLCHECK_TRUSTED_HOSTS`: exact production and approved preview hosts

Secrets are never committed, exposed through Vite variables, printed in deployment logs, or copied into documentation. Preview deployments receive separate or deliberately shared values only through Vercel's environment scoping.

## 8. Security Boundaries

- All 42 application tables in Supabase have Row Level Security enabled; the server connection remains the only application data path for this beta.
- The R2 bucket is private. Objects are never exposed through public bucket URLs.
- Upload validation occurs before analysis and before a success response.
- The backend uses exact trusted hosts and exact allowed origins; wildcard production values are rejected.
- Production startup fails when database, durable object storage, or JWT configuration is missing.
- Local filesystem storage is forbidden in the Vercel production runtime.
- Existing beta authentication is retained, while complete RBAC hardening remains explicitly deferred.

## 9. Failure Handling

- Files above 4 MiB return HTTP 413 with user-facing guidance.
- Invalid workbook structure returns a stable validation response with actionable sheet/field details.
- Database unavailability returns service-unavailable semantics and a safe error code.
- R2 write or readiness failure prevents a durable-success result.
- Analysis timeout or unexpected engine failure records a failed run when the database is available and returns a safe failure response.
- Cold-start health checks distinguish liveness from readiness; readiness includes database and object-store checks.
- Retry behavior must not duplicate source files, snapshots, or findings for the same governed operation.

## 10. Verification Strategy

Implementation is accepted only when all of the following pass:

1. Unit tests for API prefix routing, production configuration, storage failure behavior, and the 4 MiB limit.
2. Packaging tests proving runtime metadata is present and non-runtime assets are excluded.
3. A local clean install and full automated test suite.
4. A Vercel production build with the Python bundle below 500 MB.
5. Hosted liveness and readiness checks against Supabase and R2.
6. Hosted register/login, project creation, workbook upload, deterministic analysis, findings display, and later retrieval.
7. Persistence verification after a Function cold start.
8. Negative hosted tests for oversized upload, invalid workbook, database failure, and R2 failure.
9. Confirmation that no secret is present in frontend assets, browser storage, API responses, or deployment logs.

## 11. Documentation and Operational Changes

- Update the PRD to record the Vercel hybrid beta topology and 4 MiB workbook constraint.
- Update the production runbook with Vercel environment variables, explicit migration order, deployment verification, and rollback.
- Replace the active Render instructions. `render.yaml` may remain only as a clearly labeled legacy/self-hosting reference if tests and documentation cannot misidentify it as the beta path; otherwise remove it.
- Record the no-card constraint as the reason for the hosting decision, without treating it as a permanent product limitation.

## 12. Rollback and Upgrade Path

Rollback promotes the previous frontend-only Vercel deployment. Supabase migrations remain backward compatible and R2 objects are not deleted. No destructive database rollback is part of deployment rollback.

When real usage shows that 4 MiB is restrictive, add a short-lived presigned upload flow: the browser uploads directly to R2, then sends the object key and digest to the API for validation and analysis. If synchronous execution time becomes restrictive, move analysis behind a durable queue or paid container runtime without changing the engine or persistence contracts.

## 13. Acceptance Criteria

- The public beta runs without Render or any payment-card-dependent runtime.
- The exact public Vercel URL serves both frontend and `/api` endpoints.
- A valid workbook up to 4 MiB completes the register-to-findings flow and remains retrievable.
- An oversized workbook is rejected consistently in the browser and API.
- Workbook objects remain private in R2 and analysis records remain durable in Supabase.
- Production configuration fails closed and no secret reaches the client.
- PRD and operational documentation match the deployed topology.

