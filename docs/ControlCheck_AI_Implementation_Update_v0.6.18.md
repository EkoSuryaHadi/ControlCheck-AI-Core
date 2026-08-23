# ControlCheck AI — Implementation Update v0.6.18

**Version:** 0.6.18  
**Date:** 2026-08-23  
**Status:** Implemented on `homepage-v3`  
**Scope:** Workbook project identity validation diagnostics

## Objective
Keep project-boundary validation fail-closed while making ingestion errors actionable for users.

## Rule
A workbook may only be ingested into a ControlCheck project when the workbook `Project.PROJECT_ID` value exactly matches the active ControlCheck `project.code`.

This rule is intentionally strict to prevent project A data from being imported into project B.

## Change
When the workbook project identity does not match the active project, the API now returns a diagnostic message containing:

- the workbook Project ID received;
- the active ControlCheck project code expected;
- an instruction to select the matching project or update the workbook Project sheet.

The error code remains:

`workbook_project_mismatch`

HTTP status remains `422`.

## Security / Assurance
The change does **not** relax project identity matching, auto-remap a workbook to another project, or silently rewrite workbook metadata.

## Acceptance Criteria
- A workbook whose Project ID matches the active project code can proceed to ingestion.
- A workbook whose Project ID differs is rejected with HTTP 422.
- The mismatch error identifies both received and expected project codes.
- No analysis run is reported successful for a mismatched workbook.
- Uploaded mismatched workbook storage is deleted by the existing failure path.

## Definition of Done
- [x] Fail-closed identity validation retained.
- [x] Actionable mismatch diagnostic implemented.
- [x] No schema migration required.
- [x] Documentation created.
- [ ] Preview build validated.
- [ ] Manual mismatch and matching-workbook smoke tests completed.
