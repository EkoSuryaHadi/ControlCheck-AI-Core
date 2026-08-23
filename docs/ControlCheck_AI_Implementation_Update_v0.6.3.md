# ControlCheck AI — Implementation Update v0.6.3

**Version:** v0.6.3  
**Date:** 23 Aug 2026  
**Theme:** Preview Database Schema Migration Readiness  
**Branch:** `homepage-v3`

## 1. Problem

Vercel Preview database connectivity is now healthy, but workspace registration still returned HTTP 500.

Runtime log root cause:

`psycopg.errors.UndefinedTable: relation "users" does not exist`

This confirms that the Supabase database connection is reachable, but the application schema has not yet been migrated into the Preview database.

## 2. Root Cause

The Preview database is effectively empty. Core tables such as `users`, `organizations`, `projects`, findings, actions, governance approvals, and escalation tables are created through the repository Alembic migration chain.

The repository Alembic configuration previously defaulted to a local PostgreSQL URL in `alembic.ini`, and `alembic/env.py` did not override that value from the hosted deployment environment.

## 3. Code Changes

### 3.1 Hosted database URL support

`alembic/env.py` now resolves migration target URL from:

1. `CONTROLCHECK_DATABASE_URL`
2. `DATABASE_URL`
3. fallback to `alembic.ini` only when neither environment variable is present.

### 3.2 psycopg v3 normalization

Hosted connection strings beginning with:

- `postgresql://`
- `postgres://`

are normalized to:

`postgresql+psycopg://`

This matches the application's psycopg v3 runtime and avoids implicit psycopg2 driver resolution.

## 4. Migration Chain

The active schema migration chain on `homepage-v3` includes:

- `20260817_0001_phase4a_persistence.py`
- `20260821_0002_phase4b_canonical_facts.py`
- `20260822_0003_phase5c_health_scoring.py`
- `20260904_0004_phase4c_auth_rbac.py`
- `20260905_0005_phase6_ai_layer.py`
- `20260823_0006_actions_closure_governance.py`
- `20260823_0007_approval_escalation_governance.py`

`alembic upgrade head` must complete successfully before live workspace registration is accepted.

## 5. Required Preview Migration

From a local checkout of branch `homepage-v3`, set the Supabase Pooler URL as `DATABASE_URL`, then execute:

```bash
alembic upgrade head
```

The command must target the same Supabase database used by Vercel Preview.

## 6. Acceptance Criteria

- [ ] `alembic upgrade head` completes without error.
- [ ] `alembic_version` exists and is at head revision.
- [ ] `users` table exists.
- [ ] `organizations` and `organization_members` exist.
- [ ] Project persistence tables exist.
- [ ] Findings/evidence tables exist.
- [ ] Corrective action tables exist.
- [ ] Governance policy, approval, and escalation tables exist.
- [ ] Vercel `/api/health/ready` reports `database: connected`.
- [ ] New workspace registration returns HTTP 201.
- [ ] New account redirects to `/onboarding`.
- [ ] First project creation succeeds.

## 7. Testing Status

Current status at time of this document:

- Vercel Preview deployment: Ready
- Supabase Pooler connectivity: Connected
- Backend route `/v1/auth/register`: Active
- Preview database schema: **Not yet migrated**
- Create Workspace: **Blocked until migration completes**

## 8. Governance Note

Migration execution is intentionally not exposed as an unauthenticated HTTP endpoint. Database schema mutation should remain an explicit deployment/operations action rather than a public runtime capability.
