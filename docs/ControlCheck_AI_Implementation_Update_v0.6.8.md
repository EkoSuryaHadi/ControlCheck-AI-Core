# ControlCheck AI — Implementation Update v0.6.8

**Date:** 2026-08-23  
**Owner:** ControlCheck AI  
**Scope:** Data ingestion fail-closed hardening

## Objective
Remove all simulated-success paths from the Data Import workflow so users only see a successful ingestion when the backend accepts a real source file and returns a valid analysis-run ID.

## Changes

### 1. Wizard starts at Upload File
`DataImportWizard` now starts at Step 1 instead of Step 2.

### 2. File is mandatory
The wizard blocks progression unless a non-empty `.xlsx`, `.xls`, or `.csv` file is selected.

Preflight checks:
- accepted extension
- non-empty file
- maximum file size 25 MB

### 3. Step navigation is gated
Users cannot click ahead into Mapping, Preflight, or Result without satisfying earlier steps.

### 4. Removed simulated ingestion
Deleted the previous fallback that generated synthetic values such as:
- 20 control rules
- 17 findings
- 156 written records
- simulated duration

No import success screen is shown without a real API response.

### 5. Validation copy is now truthful
The previous UI stated `Schema & Data Quality Validation Passed` before server execution.

It is replaced with **Ready for Server Validation**. The UI now distinguishes local preflight from deterministic server validation.

### 6. Mapping preview is identified as preset guidance
Preset mappings remain useful for user orientation, but the interface explicitly states that actual workbook parsing and validation occur on the server.

### 7. Server-authoritative upload result
`ProjectContext.uploadWorkbook()` now:
- requires a selected project
- requires a non-empty file
- calls the real upload API
- requires a valid `analysis run id`
- never substitutes demo rule/finding counts
- returns the server result to the wizard

Automatic `window.location.assign()` was removed so the calling workflow can determine the next UI state from the real response.

### 8. Result screen is API-backed only
Step 4 renders only when a valid analysis run exists.

Displayed values originate from the API response:
- run ID
- reported rule count
- reported finding count
- optional duration

## Active Workflow

`Upload File -> Mapping Preview -> Preflight -> Server Ingestion -> Real Analysis Run`

If any required condition fails, the workflow remains open and displays the error instead of reporting success.

## Acceptance Criteria

- [x] Data page initially opens at Upload File.
- [x] No file means Next is disabled.
- [x] Unsupported or empty files are rejected locally.
- [x] File larger than 25 MB is rejected locally.
- [x] Users cannot jump ahead without a selected file.
- [x] Preflight does not claim server validation has passed.
- [x] No synthetic ingestion summary is produced.
- [x] API response must contain an analysis-run ID before success is shown.
- [x] Rule and finding counts are not defaulted to demo values.
- [x] Failed upload remains a failed state.

## Definition of Done

This change is complete when:
1. frontend TypeScript/Vite build passes;
2. Preview deployment is READY;
3. `/data` loads under authenticated workspace routing;
4. a user cannot reach a successful result without a real file and real API analysis-run response.

## Follow-up

Next hardening targets:
1. real analysis-progress polling/state;
2. remove live-finding demo evidence fallback for UUID findings;
3. derive corrective-action actor identity from JWT;
4. session/token expiry handling;
5. remove remaining demo fallbacks from authenticated workspace data views.
