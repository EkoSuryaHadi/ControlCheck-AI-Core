# ControlCheck AI — Implementation Update v0.6.9

**Date:** 2026-08-23  
**Owner:** ControlCheck AI  
**Scope:** Real analysis progress state

## Objective
Replace timer-driven simulated analysis progress with server-authoritative analysis-run status polling.

## Changes

### Removed simulated timers
The previous page automatically advanced through stages after fixed browser timers and declared findings ready after approximately 3.4 seconds.

Those timers are removed.

### Real run identification
The page resolves the target analysis run from:
1. current server-backed run in ProjectContext; or
2. the last accepted analysis-run ID stored after upload.

If no real run exists, the page directs the user back to Data Import.

### Server polling
While a run is not terminal, the page polls the project analysis-run list every 2.5 seconds and locates the specific run ID.

Terminal states:
- `completed`
- `failed`

Other states are treated as active/in-progress without inventing percentage completion.

### No fake granular stages
The current API exposes run status but not a server-side granular stage field. The UI therefore displays the processing pipeline only as explanatory reference and explicitly states that it is not a simulated progress meter.

### Real result metrics
Rules, findings, duration and status are displayed only when returned by the analysis-run record. Missing values are shown as `—`, not substituted with demo defaults.

### Completion behavior
Only a server-confirmed `completed` run enables the Findings/Dashboard completion actions.

A server-confirmed `failed` run provides a return-to-import path.

## Acceptance Criteria
- [x] No fixed progress timers remain.
- [x] Page requires a real analysis-run ID.
- [x] Run status is refreshed from the backend.
- [x] Completed UI only appears for server status `completed`.
- [x] Failed UI appears for server status `failed`.
- [x] Rule/finding counts are never defaulted to demo values.
- [x] API limitations are represented truthfully.

## Definition of Done
1. TypeScript/Vite build passes.
2. Preview deployment reaches READY.
3. Data Import creates a real run before Analysis Progress can represent success.
4. Analysis Progress cannot become complete through browser timers alone.

## Follow-up
Next hardening targets:
1. remove UUID finding demo evidence fallback;
2. derive corrective-action actor identity from JWT;
3. strengthen 401/session expiry behavior;
4. reduce remaining authenticated-workspace demo fallbacks.
