# ControlCheck AI Implementation Update v0.6.17

**Version:** 0.6.17  
**Date:** 2026-08-23  
**Owner:** ControlCheck AI  
**Status:** Implemented on `homepage-v3`

## Scope
Latest Successful Analysis Run Selection for Reporting and Workspace Reads.

## Problem
The workspace previously selected `runs[0]` as the active analysis run. This assumed the first run returned by the API was both the newest and successful. If the newest run was queued, running, or failed, the Reports module became disabled even when an earlier successful analysis run existed.

## Change
`ProjectContext` now:
- accepts both `succeeded` and legacy `completed` as terminal-success states;
- filters analysis runs to successful runs only for health/findings/reporting state;
- selects the latest successful run using completion/start/create timestamps;
- clears `currentRun` and live findings when no successful run exists;
- avoids exposing a newly uploaded non-terminal run as the reportable current run.

## Active Reporting Rule
A persisted report may only be generated from a server-confirmed successful analysis run.

Selection rule:
1. list project analysis runs;
2. retain only status `succeeded` or `completed`;
3. sort by `completed_at`, then `started_at`, then `created_at` descending;
4. use the newest successful run as `currentRun`.

## Acceptance Criteria
- [x] A failed latest run does not block reporting when an older successful run exists.
- [x] A running latest run does not replace the latest successful reportable run.
- [x] Reports remains disabled when the project has no successful analysis run.
- [x] Health and findings are loaded from the same successful run used for reporting.
- [x] No synthetic/demo run is created to satisfy report generation.

## Definition of Done
- [x] Frontend run-selection logic updated.
- [x] Versioned implementation document created.
- [ ] Vercel Preview build validated.
- [ ] Manual Reports smoke test completed.
