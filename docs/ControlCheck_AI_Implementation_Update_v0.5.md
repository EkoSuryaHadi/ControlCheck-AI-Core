# ControlCheck AI — Implementation Update v0.5

**Date:** 23 Aug 2026  
**Status:** In Review  
**Branch:** `homepage-v3`  
**Pull Request:** #2

## Document Change Log

| Version | Date | Change |
|---|---|---|
| 0.4 | 23 Aug 2026 | Browser-local corrective action management and Evidence Completeness |
| 0.5 | 23 Aug 2026 | Server action persistence, action history, overdue monitoring, and governed finding closure |

## 1. Purpose

v0.5 moves corrective actions from browser-only persistence toward production-grade backend persistence and introduces closure governance for project-control findings.

The primary rule is simple: a finding must not be marked resolved merely because a user clicked a button. Closure must satisfy evidence and corrective-action requirements.

## 2. Persistent Corrective Action Model

New table: `finding_actions`

Key fields:

- `id`
- `organization_id`
- `project_id`
- `finding_id`
- `title`
- `owner`
- `due_date`
- `priority`: `high | medium | low`
- `status`: `open | in_review | completed | cancelled`
- `notes`
- `created_by`
- `completed_at`
- `created_at`
- `updated_at`

New table: `finding_action_history`

Key fields:

- `id`
- `organization_id`
- `action_id`
- `event_type`
- `actor`
- `changes` JSONB
- `created_at`

Actions are scoped by organization, project, and finding.

## 3. Database Migration

Migration:

`alembic/versions/20260823_0006_actions_closure_governance.py`

Apply before enabling v0.5 action persistence:

```bash
alembic upgrade head
```

Rollback removes `finding_action_history` and `finding_actions`.

## 4. Action API

New server routes:

- `GET /v1/projects/{project_id}/actions`
- `GET /v1/findings/{finding_id}/actions`
- `POST /v1/findings/{finding_id}/actions`
- `PATCH /v1/actions/{action_id}`
- `GET /v1/findings/{finding_id}/closure-readiness`
- `POST /v1/findings/{finding_id}/close`

Action deletion is intentionally not exposed as a hard-delete workflow. User-facing removal becomes `cancelled` so historical accountability is retained.

## 5. Closure Governance Policy

A finding can close only when all conditions are satisfied:

1. At least one persisted evidence record exists.
2. No corrective action remains `open` or `in_review`.
3. Existing corrective actions are `completed` or `cancelled`.

The server evaluates closure readiness and returns:

- `can_close`
- `evidence_ready`
- `actions_ready`
- `action_count`
- `open_action_count`
- `completed_action_count`
- `blockers[]`

If closure requirements are not satisfied, `POST /v1/findings/{finding_id}/close` returns HTTP `409` with `closure_governance_blocked`.

## 6. Finding Detail UX

Finding Detail now exposes a **Closure Readiness** panel.

It shows:

- Evidence: Ready / Missing
- Actions: Ready / N Open
- Completed Actions
- Total Actions
- Governance blockers

The **Close Finding** button is disabled while closure requirements are incomplete.

For a server-backed finding, the final closure decision is revalidated by the backend; frontend state alone cannot authorize closure.

Demo/non-UUID findings continue to use a local policy approximation so the sample experience remains usable.

## 7. Action Workspace v0.5

The `/actions` workspace now:

- synchronizes project actions with the server when API/database are available;
- retains local browser state only as cache/fallback;
- displays Total, Open/In Review, Overdue, and Completed metrics;
- highlights overdue corrective actions;
- supports `open`, `in_review`, `completed`, and `cancelled` states;
- cancels actions instead of hard-deleting server records.

### Overdue Definition

An action is overdue when:

- `due_date` is earlier than the current date/time; and
- status is not `completed` or `cancelled`.

Overdue status is presentation/monitoring logic in v0.5. Automated escalation is not yet implemented.

## 8. Browser Cache / Fallback Strategy

`frontend/src/lib/actionStore.ts` remains in place as a resilient client cache.

Behavior:

1. Create/update immediately updates local UX.
2. If a server-compatible finding/action ID exists, the client synchronizes with the Action API.
3. Project Action Workspace refreshes from the server and merges local-only fallback records.
4. Server-backed delete requests are converted to `cancelled` status.

The server database is the intended source of truth whenever available.

## 9. Auditability

Action create/update events generate `finding_action_history` records.

Recorded information includes:

- event type;
- actor string;
- field changes;
- timestamp.

### Current identity limitation

`actor` is currently supported as an application-provided string. A future release should derive immutable user identity directly from authenticated token claims instead of trusting a client-supplied actor field.

## 10. Tenant Isolation

Action API calls require organization context via:

- authenticated JWT `org_id`; or
- `X-Organization-ID` fallback.

Repository queries scope actions/findings to the organization.

## 11. Tests Added

New test:

`tests/test_action_closure_governance.py`

Coverage includes:

- closure blocked when evidence is missing;
- closure blocked when an action is still open;
- closure allowed when evidence exists and all actions are completed/cancelled.

The closure rule is extracted into `evaluate_closure_readiness()` so the core policy is unit-testable without UI state.

## 12. Files Added / Modified

Backend:

- `src/controlcheck/persistence/action_models.py`
- `src/controlcheck/persistence/action_repository.py`
- `src/controlcheck/actions_api.py`
- `api/index.py`
- `alembic/versions/20260823_0006_actions_closure_governance.py`
- `tests/test_action_closure_governance.py`

Frontend:

- `frontend/src/lib/api.ts`
- `frontend/src/lib/actionStore.ts`
- `frontend/src/pages/actions/ActionsPage.tsx`
- `frontend/src/pages/findings/FindingDetailV2Page.tsx`

## 13. Deployment Notes

Before production deployment:

1. Apply Alembic migration.
2. Verify `DATABASE_URL` is configured.
3. Deploy backend/serverless API.
4. Verify Action API health using authenticated tenant context.
5. Test create action → update action → complete action → close finding.
6. Confirm HTTP 409 is returned if closure is attempted while blocked.

### Route registration note

The v0.5 Action API is currently registered in the Vercel serverless entry point `api/index.py`, which matches the current ControlCheck deployment path. If a separate Docker/ASGI deployment is introduced, the same `install_action_routes()` hook must be registered in that application entry point before production use.

## 14. Acceptance Criteria

- [ ] Alembic migration applies successfully.
- [ ] Action create persists after browser refresh and cross-device login when server API is available.
- [ ] Project Actions endpoint returns only tenant-scoped project actions.
- [ ] Action status changes create history records.
- [ ] Completed actions store completion timestamp.
- [ ] Overdue actions are visibly flagged.
- [ ] Finding closure is blocked without evidence.
- [ ] Finding closure is blocked with Open/In Review action.
- [ ] Finding closure succeeds when evidence exists and actions are complete/cancelled.
- [ ] Browser fallback does not prevent the demo flow from operating.
- [ ] Existing Dashboard, Findings, Cost, Schedule, Progress, AI Assistant, Reports, and onboarding flows remain functional.

## 15. Definition of Done

v0.5 is ready to merge only after:

- TypeScript/Vite build passes;
- Python test suite including closure governance test passes;
- Alembic migration is validated on a non-production database;
- API endpoints are smoke-tested;
- closure 409/200 paths are verified;
- no regression is found in the existing application modules.

## 16. Next Recommended Update — v0.6

Recommended priorities:

1. Server-derived user identity for action audit history.
2. Action SLA and escalation rules.
3. Notifications for upcoming/overdue due dates.
4. RBAC: who can assign, complete, cancel, or close findings.
5. Closure approval / maker-checker workflow for Critical findings.
6. Action/history timeline in Finding Detail.
7. Action performance KPIs: overdue rate, average closure time, recurring finding rate.

---

This document is the v0.5 implementation baseline. Any change to action persistence, closure rules, evidence requirements, status workflow, API contract, database schema, or deployment behavior must update this documentation in the same change set.
