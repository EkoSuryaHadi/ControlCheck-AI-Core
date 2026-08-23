# ControlCheck AI Implementation Update v0.6.14

**Version:** v0.6.14  
**Date:** 2026-08-23  
**Owner:** ControlCheck AI  
**Scope:** Finding closure status synchronization

## Objective
Ensure a finding closed from Finding Detail is represented correctly in the Findings workspace immediately after the user returns to the list.

## Root Cause
The close operation persisted `resolved` on the backend and updated the local Finding Detail state, while the Findings page could continue rendering the prior `liveFindings` snapshot until another project/run refresh occurred.

## Changes

### Refresh on Findings entry
`FindingsPage` now calls `refreshHealthAndFindings()` when it mounts.

Expected flow:
`Close Finding -> Back to Findings -> Fetch latest server findings -> Resolved badge`

The backend remains authoritative.

### Active summary counters
Critical and Warning counters now exclude statuses `resolved` and `closed`.
A separate `Resolved` counter is shown.

### Resolved presentation
Resolved findings remain available for traceability and now show:
- resolved visual treatment,
- `Resolution complete`,
- `View resolution`,
- no active-risk impact emphasis.

## Acceptance Criteria
- [x] Close remains server-authoritative.
- [x] Returning to Findings triggers fresh server data.
- [x] Closed finding displays as `Resolved` in the list.
- [x] Resolved items do not count as active Critical/Warning findings.
- [x] Resolved findings remain accessible for audit review.
- [x] Governance remains parked.

## Definition of Done
1. Code committed to `homepage-v3`.
2. Versioned documentation committed.
3. Frontend TypeScript/Vite build passes.
4. Preview deployment reaches READY.
5. Manual workflow confirms `Close Finding -> Findings -> Resolved`.
