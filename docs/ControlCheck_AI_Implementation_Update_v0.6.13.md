# ControlCheck AI Implementation Update v0.6.13

**Version:** v0.6.13  
**Date:** 2026-08-23  
**Owner:** ControlCheck AI

## Objective
Prevent the legacy finding-status endpoint from resolving findings without passing corrective-action and evidence closure gates.

## Changes
- `FindingStatusUpdate` now permits only `open`, `in_review`, and `dismissed`.
- `resolved` is intentionally rejected by the legacy `/v1/findings/{finding_id}/status` endpoint at request validation.
- Finding resolution must use `/v1/findings/{finding_id}/close`.
- Added regression tests for rejected direct resolution and allowed non-closure states.

## Closure Rule
A finding may become `resolved` only through the dedicated close endpoint, which evaluates evidence and corrective-action readiness (and Governance when that feature is re-enabled).

## Acceptance Criteria
- PATCH status with `resolved` returns request validation failure and does not mutate the finding.
- PATCH status with `open`, `in_review`, or `dismissed` remains valid.
- POST close remains the only active API path for resolution.
- Regression tests cover this contract.

## Definition of Done
- Legacy bypass blocked at API model boundary.
- Regression test added.
- Documentation added in the same change set.
- Preview build / CI validation required before release sign-off.
