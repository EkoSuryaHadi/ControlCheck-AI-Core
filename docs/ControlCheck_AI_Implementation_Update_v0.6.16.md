# ControlCheck AI Implementation Update v0.6.16

**Version:** v0.6.16  
**Date:** 2026-08-23  
**Owner:** ControlCheck AI

## Objective
Upgrade Reports from browser-local snapshots into server-persisted, cross-device report packages with immutable analysis snapshots, evidence appendix, and persisted PDF binaries.

## Changes

### 1. Server-side report history
Added `report_packages` persistence with organization/project/run ownership.

Stored fields:
- report ID
- organization ID
- project ID
- analysis run ID
- generated-by user ID
- report name/type/period
- immutable JSON snapshot
- persisted PDF binary
- PDF size
- creation timestamp

### 2. Immutable report snapshot
A report freezes the selected analysis-run state at generation time.

Snapshot contents include:
- project identity
- analysis run identity and engine metadata
- workbook SHA-256
- health scores
- active/resolved finding counts
- full finding snapshot
- supporting evidence records
- source sheets
- source row lineage
- record IDs
- evidence fields and aggregation metadata

Later finding updates do not rewrite a historical report.

### 3. Evidence appendix
Every finding in the report captures its linked server evidence. The generated PDF includes an Evidence Appendix containing source sheet, source rows and selected field values.

### 4. Persisted PDF
Added a dependency-free deterministic PDF renderer using built-in PDF/Helvetica primitives. The generated binary is stored in PostgreSQL `BYTEA` so the same report can be opened again from another browser/device.

No browser-local PDF generation is authoritative in v0.6.16.

### 5. Report API
New authenticated JWT-scoped endpoints:
- `GET /v1/projects/{project_id}/reports`
- `POST /v1/projects/{project_id}/reports`
- `GET /v1/reports/{report_id}`
- `GET /v1/reports/{report_id}/pdf`

Tenant scope is derived from JWT `org_id`; generated-by identity is derived from JWT `sub`.

### 6. Frontend Reports workflow
Reports page now:
- loads server report history
- generates only from a completed server analysis run
- persists report package through API
- previews immutable snapshot metrics/findings/evidence count
- opens persisted PDF from the server
- no longer relies on localStorage as the report system of record

## Database Migration
New Alembic migration:

`20260823_0008_report_packages.py`

Revision chain:

`20260823_0007 -> 20260823_0008`

Apply with:

```powershell
python -m alembic upgrade head
```

The local environment must point `DATABASE_URL` to the intended Supabase database before migration.

## Security / Integrity Rules
- report tenant = JWT organization
- generated_by = JWT user
- analysis run must belong to the same project and organization
- only completed/succeeded analysis runs are reportable
- report snapshot is immutable after creation
- persisted PDF is generated from the same stored snapshot

## Acceptance Criteria
- [x] Browser-local report history is no longer authoritative.
- [x] Report generation requires a real completed analysis run.
- [x] Report snapshot stores current finding statuses.
- [x] Evidence lineage is frozen into the report snapshot.
- [x] PDF binary is persisted server-side.
- [x] PDF can be retrieved using report ID after generation.
- [x] Report history is project and tenant scoped.
- [x] Deterministic PDF renderer has a regression test.
- [ ] Migration `0008` applied to Preview Supabase database.
- [ ] Preview runtime generation verified after migration.

## Definition of Done
v0.6.16 is fully operational when:
1. frontend/backend build passes;
2. migration `0008` is applied to Preview database;
3. authenticated user generates a report from a completed run;
4. report remains visible after browser refresh;
5. persisted PDF opens from the report history;
6. evidence appendix is present for findings with evidence.

## Follow-up
Recommended next reporting improvements:
1. branded cover / richer PDF layout;
2. report version sequence and superseded status;
3. digital checksum/signature per report package;
4. controlled deletion/retention policy;
5. optional object-storage migration if PDF volume grows beyond database-friendly limits.
