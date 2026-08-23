# ControlCheck AI Implementation Update v0.6.15

**Version:** v0.6.15  
**Date:** 2026-08-23  
**Owner:** ControlCheck AI

## Objective
Replace the Reports placeholder experience with a functional project-control reporting workflow based on the current project, real analysis run, health snapshot, and live finding statuses.

## Previous Problem
The Reports page previously:
- displayed hardcoded sample reports;
- generated new rows only in React state;
- used fixed October 2024 sample values;
- used `window.print()` on the whole application shell for both Preview and Download;
- could imply a report existed without a real analysis run.

## Changes

### 1. Real report snapshot source
A generated report now captures the current workspace state:
- project name and code;
- real analysis run ID;
- project health score/status;
- data quality score;
- active Critical and Warning finding counts;
- resolved finding count;
- total finding count;
- top active findings with ID, title, severity, status, and impact.

### 2. Fail-closed generation
Report generation is disabled until a real project and analysis run are present.

No synthetic report is created when analysis data is unavailable.

### 3. Removed hardcoded report catalogue
The seeded sample report list was removed from the active Reports experience.

Generated snapshots are stored per project in browser storage as a temporary persistence layer until server-side report persistence is introduced.

### 4. Functional preview
Preview now opens a dedicated printable report document rather than printing the full application UI.

### 5. Functional Print / Save as PDF
The report document contains a browser print action and supports the browser's **Save as PDF** workflow.

### 6. Status-aware finding summary
Resolved findings are separated from active Critical/Warning counts so closure changes are reflected in subsequent report snapshots.

### 7. Truthful reporting copy
The page now identifies the output as a **report snapshot** generated from current analysis state. It does not claim backend PDF persistence or historical server storage that does not yet exist.

## Active Workflow

`Real Analysis Run -> Reports -> Generate Report -> Snapshot -> Preview -> Print / Save as PDF`

## Acceptance Criteria
- [x] Generate Report is disabled without a real analysis run.
- [x] No hardcoded report rows are shown as real output.
- [x] Generated report contains current project and run identity.
- [x] Active Critical/Warning counts exclude resolved findings.
- [x] Resolved finding count is included.
- [x] Preview opens a dedicated report document.
- [x] Print / Save as PDF does not print the entire ControlCheck application shell.
- [x] Generated snapshots are isolated per project in browser storage.

## Current Limitation
Report metadata and generated snapshots are currently browser-persisted. They are not yet server-persisted documents and no PDF binary is stored in the database/object storage.

## Follow-up
Recommended next reporting iterations:
1. server-side report persistence and report history;
2. PDF generation service/object storage;
3. report templates by Monthly / Executive / Cost / Schedule;
4. chart embedding for Cost, Schedule, Progress, and health drivers;
5. evidence appendix and finding/action closure history;
6. signed report metadata and immutable report-run traceability.

## Definition of Done
- Reports UI uses current workspace data rather than mock report rows.
- Preview and PDF workflow are operational in-browser.
- Change is documented in the same change set.
- Frontend build and Preview deployment must pass before release sign-off.
