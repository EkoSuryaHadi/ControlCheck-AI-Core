# ControlCheck AI Implementation Update v0.6.7

**Version:** 0.6.7  
**Date:** 2026-08-23  
**Scope:** Simplified Finding Resolution finalization + workspace route protection

## 1. Objective

Finalize the temporarily governance-free user flow and close an important workspace security gap.

Active user workflow:

`Finding -> Corrective Action -> Evidence -> Close Finding`

Governance remains parked and is not part of the active UI flow.

## 2. Finding Resolution UX Changes

`frontend/src/pages/findings/FindingDetailV2Page.tsx`

Changes:
- Removed Approval as a visible resolution step.
- Removed approval pending/rejected/request state from the active UI.
- Removed Submit for Approval / Approval Pending CTAs.
- Removed Governance explanatory copy from the Resolution panel.
- Resolution progress is now exactly:
  - Review
  - Action
  - Evidence
  - Closed
- Primary CTA is state-driven:
  - Create Action
  - Update Action
  - Review Evidence
  - Close Finding
- Ready state now reads `Ready to close`.
- Closure remains evidence-backed and action-gated.
- Server-backed findings continue to use the persistent closure endpoint.

## 3. Workspace Route Protection

New file:

`frontend/src/components/auth/ProtectedRoute.tsx`

Updated:

`frontend/src/App.tsx`

Protected routes now include:
- `/onboarding`
- `/dashboard`
- `/projects`
- `/data`
- `/analysis-progress`
- `/findings`
- `/findings/:findingId`
- `/actions`
- `/cost`
- `/schedule`
- `/progress`
- `/assistant`
- `/reports`
- `/settings`

Unauthenticated users are redirected to `/login`.

Public routes remain:
- `/`
- `/demo`
- `/login`
- `/register`

The parked `/governance` route remains redirected to `/findings` and is behind the protected workspace shell.

## 4. Acceptance Criteria

1. Finding Detail shows no Approval/Governance step in the active Resolution workflow.
2. Resolution progress contains exactly four stages: Review, Action, Evidence, Closed.
3. A finding cannot be closed while required corrective actions are incomplete.
4. A finding cannot be closed while evidence readiness is false.
5. A ready finding exposes `Close Finding` as the primary CTA.
6. Visiting workspace routes without a stored authenticated session redirects to `/login`.
7. Public landing, demo, login, and register routes remain accessible without authentication.
8. Governance code and schema remain preserved for future reactivation.

## 5. Definition of Done

- [x] Approval/Governance copy removed from active Finding Resolution UI.
- [x] Four-step resolution workflow implemented.
- [x] ProtectedRoute component added.
- [x] Onboarding and workspace routes guarded.
- [x] Governance route remains parked.
- [ ] Vercel Preview build verified after final commit.
- [ ] Manual browser regression: logged-out workspace redirect.
- [ ] Manual browser regression: Finding -> Action -> Evidence -> Close.

## 6. Next Recommended Hardening

After v0.6.7 is stable:
1. Replace local-token-only session check with token validity/expiry handling.
2. Fix Data Import wizard so success cannot be simulated without a real upload/analysis run.
3. Fail closed when server-backed closure readiness cannot be loaded.
4. Remove demo evidence fallback for live UUID findings when API evidence is empty.
5. Derive action actor identity from JWT rather than client-supplied actor fields.
