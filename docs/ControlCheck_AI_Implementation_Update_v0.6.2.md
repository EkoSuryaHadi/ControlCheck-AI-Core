# ControlCheck AI — Implementation Update v0.6.2

**Version:** v0.6.2  
**Theme:** Preview Database Connectivity Blocker  
**Branch:** `homepage-v3`

## 1. Problem

Preview registration progressed past the previous 404 routing issue but failed with HTTP 500 when creating a workspace.

## 2. Runtime Evidence

Vercel runtime logs confirm the request reaches `POST /api/v1/auth/register` and fails while SQLAlchemy/psycopg attempts to establish a PostgreSQL connection.

The `/api/health/ready` endpoint reports:

- database: `unreachable`
- storage: `ready`
- catalogue: `loaded`
- PostgreSQL connection on port 5432 fails with `Cannot assign requested address`
- the resolved database endpoint is IPv6

## 3. Root Cause

The current Preview `DATABASE_URL` points to a direct PostgreSQL endpoint that resolves to IPv6. The Vercel serverless runtime used by the Preview cannot establish the direct IPv6 connection.

The application code is now correctly reading both `CONTROLCHECK_DATABASE_URL` and standard `DATABASE_URL`; this incident is no longer an application route-registration issue.

## 4. Required Deployment Fix

Replace the Preview database connection string with an IPv4-compatible PostgreSQL pooler connection string. For Supabase, use the project Connection Pooler / Session Pooler connection string rather than the Direct Connection string.

Recommended runtime configuration:

- Vercel Preview environment: `DATABASE_URL=<pooler connection string>`
- Optionally also set `CONTROLCHECK_DATABASE_URL` to the same value for explicit ControlCheck naming
- Preserve SSL parameters required by the database provider
- Redeploy the `homepage-v3` Preview after the environment variable change

Do not commit database passwords or connection strings into GitHub.

## 5. Verification

After updating the environment variable and redeploying:

1. Open `/api/health/ready`.
2. Expected: HTTP 200.
3. Expected database check: `connected`.
4. Register with a new email and organization.
5. Expected: HTTP 201 from `/api/v1/auth/register`.
6. Expected: automatic redirect to `/onboarding`.
7. Create the first project.
8. Verify login with the same credentials after logout.

## 6. Release Gate

v0.7 development should remain behind this release gate until Preview database readiness returns HTTP 200 and the real Create Workspace flow completes successfully.
