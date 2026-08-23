# ControlCheck AI — Implementation Update v0.6.6

**Date:** 2026-08-23  
**Owner:** ControlCheck AI  
**Status:** Governance temporarily parked

## Summary
Governance is temporarily removed from the active user workflow while the product focuses on the core Project Control resolution experience.

The active workflow is now:

**Finding → Corrective Action → Evidence → Close Finding**

Governance code, database tables, migration history, approval records, escalation records, and API implementation are retained so the module can be re-enabled later without rebuilding it.

## Product Changes

### Navigation
- Governance Center is removed from the primary workspace navigation.
- Direct frontend access to `/governance` redirects to `/findings`.
- Governance page source remains in the codebase for future reactivation.

### Finding Closure
When Governance is disabled:
- closure approval is not required;
- approval state does not block closure readiness;
- manager-only closure authority is not enforced;
- a finding can close when its evidence and corrective-action requirements are satisfied.

### Backend Feature Flag
Governance participation in closure is controlled by:

`CONTROLCHECK_GOVERNANCE_ENABLED`

Default behavior:

`false`

To reactivate Governance in a future release:

`CONTROLCHECK_GOVERNANCE_ENABLED=true`

When enabled, the existing approval policy, maker-checker authority, SLA escalation, and governed closure logic participate again.

## Scope Retained but Inactive
The following are intentionally preserved:
- Project Governance Policy
- Closure Approval records
- Governance Escalations
- Maker-checker approval rules
- SLA scanning
- Governance API routes
- Governance database tables and migrations

No governance data is deleted by this change.

## Acceptance Criteria
1. Governance Center does not appear in the workspace navigation.
2. `/governance` redirects to `/findings` in the frontend.
3. Closure readiness returns `approval_required=false` while the feature flag is disabled.
4. Approval state cannot block a finding from closing while Governance is disabled.
5. Evidence remains required for closure.
6. Corrective actions must still be completed or cancelled before closure.
7. Existing governance schema and code remain available for future reactivation.

## Definition of Done
- [x] Governance removed from active navigation.
- [x] Governance route parked via frontend redirect.
- [x] Closure backend made governance-optional.
- [x] Default governance state set to disabled.
- [x] Reactivation flag documented.
- [x] No database migration required.
- [ ] Full Finding Detail wording cleanup to remove residual governance terminology from presentation copy, if any remains after runtime state refresh.
- [ ] Preview deployment validation.

## Notes
This is a temporary product-scope decision, not deletion of Governance. The module should remain dormant until the core Finding → Action → Evidence → Close workflow is validated with users.
