# ControlCheck AI Implementation Update v0.6.20

## Automatic source-project identification during upload

The upload flow no longer blocks a valid workbook when `Project_Info.project_id`
differs from the project selected in the application.

The selected project remains the authoritative tenant-scoped destination for the
source file, dataset snapshot, analysis run, findings, and evidence. The workbook
identifier is retained as `source_project_id` and the source name is retained as
`source_project_name` for traceability.

When the two identifiers differ, ingestion records a structured
`source_project_mismatch` warning containing both codes. Missing project metadata,
invalid workbook structure, tenant mismatch, and storage failures remain blocking
errors.

This change supports public-beta users uploading exports from external project
systems without manually editing their source workbook, while preserving project
and organization data isolation.

## Verification

- Existing matching workbook upload remains successful.
- Mismatched source workbook is accepted under the selected target project.
- `source_project_id` is persisted unchanged.
- Target project isolation and tenant authorization are unchanged.
