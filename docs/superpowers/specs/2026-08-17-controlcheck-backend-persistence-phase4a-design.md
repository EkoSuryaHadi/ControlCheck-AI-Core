# ControlCheck Backend Persistence Phase 4A Design

**Status:** Approved
**Date:** 17 August 2026
**Product baseline:** ControlCheck Core Engine v0.2.0

## 1. Objective

Phase 4A adds a durable backend application layer around the validated deterministic engine. A caller can create a project, upload a versioned workbook, run ControlCheck, persist the analysis and its evidence, and retrieve the results through FastAPI.

Authentication and complete RBAC are intentionally deferred. The schema and service boundaries remain organization-scoped so authentication can be added later without redesigning persisted project-control data.

## 2. Scope

### Included

- PostgreSQL 15+ schema and Alembic migrations.
- SQLAlchemy 2 persistence models and repositories.
- Organization and project bootstrap endpoints.
- Tenant context through the `X-Organization-ID` request header.
- Local development file storage behind a replaceable storage adapter.
- Dataset snapshots, rule-catalogue snapshots, analysis runs, findings, evidence, approved exceptions, and minimal audit logs.
- Synchronous workbook analysis orchestration.
- Read APIs for runs, findings, and evidence.
- Finding status changes.
- PostgreSQL integration tests and preservation of all existing engine tests.
- ERD, rule catalogue, PRD sequencing, schema, and developer documentation alignment.

### Excluded

- Login, password management, tokens, authentication, and complete RBAC.
- Frontend or mobile UI.
- Background queues and distributed workers.
- Health scoring and AI reasoning.
- S3-compatible production storage implementation.
- Full raw-row and canonical-fact persistence.
- Actions, reports, conversations, and AI messages.

## 3. Selected Architecture

ControlCheck remains a modular monolith. The deterministic engine continues to accept a workbook and catalogue without knowing about HTTP, SQLAlchemy, PostgreSQL, or file storage. A new application service coordinates storage, engine execution, and persistence.

The end-to-end flow is:

```text
Upload workbook
  -> validate tenant and project
  -> hash and store file
  -> persist source file and dataset snapshot
  -> create analysis run
  -> run deterministic engine
  -> atomically persist findings and evidence
  -> expose the stored result through FastAPI
```

The existing `POST /v1/audits` endpoint remains a stateless compatibility endpoint. New durable endpoints use project and analysis-run resources.

## 4. Component Boundaries

### Deterministic engine

The current `controlcheck.service.run_audit` behavior remains database-independent. It owns workbook loading, artifact compatibility checks, deterministic rule execution, and the `AuditResult` contract.

### Application orchestration

An analysis service owns the state transition from upload to completed or failed run. It depends on repository and storage protocols instead of concrete implementations. It never embeds rule calculations.

### Persistence

Repositories own database queries, transactions, tenant filters, and mapping between persistence records and API response models. Finding and evidence insertion occurs in one transaction.

### File storage

A storage protocol accepts bytes plus a stable storage key. The Phase 4A implementation writes beneath `var/uploads`; tests use an isolated temporary directory. PostgreSQL stores only file metadata and the storage key.

### FastAPI

The API validates transport concerns, resolves tenant context, calls application services, and maps domain failures to a stable error envelope. It does not query SQLAlchemy models directly.

## 5. Persistence Model

### `organizations`

Stores the tenant boundary: UUID, name, slug, status, and timestamps.

### `projects`

Stores organization ownership, unique organization-scoped project code, name, currency, optional dates, status, and timestamps.

### `source_files`

Stores project and organization ownership, original filename, MIME type, byte size, SHA-256, storage key, and upload timestamp.

### `dataset_snapshots`

Represents one complete multi-sheet workbook snapshot. It stores project, source file, dataset version, project data date, status, and creation timestamp. Phase 4A does not split one workbook into independent domain datasets.

### `rule_catalogue_versions`

Stores catalogue version, SHA-256, the structured JSON definition, and creation timestamp. The `(version, sha256)` pair is unique.

### `analysis_runs`

Stores project, dataset snapshot, catalogue version, engine version, workbook hash, status, start/completion timestamps, rule count, finding count, duration, and safe error code/message. Allowed states are `queued`, `running`, `succeeded`, and `failed`.

### `findings`

Uses a database UUID as primary key and retains `engine_finding_id` as the stable deterministic identity. It stores run, project, rule, entity type and textual entity ID, category, severity, lifecycle status, title, description, metrics JSON, calculation JSON, business impact, recommendation, confidence, and detection timestamp. `(analysis_run_id, engine_finding_id)` is unique.

### `finding_evidence`

Stores finding, evidence order, source sheet, source row numbers, record IDs, fields, and optional aggregation. Source identifiers remain textual or JSON values because engine entities may be source-native or composite rather than UUIDs.

### `approved_exceptions`

Stores organization/project scope, rule ID, entity type and entity ID, rationale, approver reference, effective period, evidence reference, status, and timestamps. Phase 4A persists governed exceptions but does not add a public exception-management API.

### `audit_logs`

Stores organization, optional project, event type, entity type/ID, structured metadata, and timestamp for project creation, uploads, run transitions, and finding status changes.

### Deferred v0.1 entities

Raw rows, canonical budget/cost/schedule/progress facts, users, memberships, actions, reports, health snapshots, conversations, and AI messages remain in the long-term ERD but are not migrated as active Phase 4A tables.

## 6. Tenant Isolation

Every durable request requires `X-Organization-ID` containing a UUID. The application resolves the target project, run, or finding through an organization-scoped repository query. A resource owned by another organization is never returned.

This header is a temporary development context, not proof of identity and not a security claim. Authentication, role assignment, authorization policy, and PostgreSQL row-level security remain a later phase. The interim implementation still fails closed on missing, malformed, or mismatched tenant context.

## 7. API Contract

### Project endpoints

- `POST /v1/organizations/{organization_id}/projects`
- `GET /v1/organizations/{organization_id}/projects`

The path organization must match `X-Organization-ID`.

### Analysis endpoints

- `POST /v1/projects/{project_id}/analysis-runs`
- `GET /v1/projects/{project_id}/analysis-runs`
- `GET /v1/analysis-runs/{run_id}`

The POST accepts one `.xlsx` multipart upload. Phase 4A executes synchronously and returns the stored run resource after success. If execution fails after the run has been created, the API returns the error envelope with `analysis_run_id` so the persisted failure can be inspected.

### Finding endpoints

- `GET /v1/analysis-runs/{run_id}/findings`
- `GET /v1/findings/{finding_id}`
- `GET /v1/findings/{finding_id}/evidence`
- `PATCH /v1/findings/{finding_id}/status`

Finding lists support exact filters for rule ID, severity, category, entity ID, and lifecycle status. Initial lifecycle states are `open`, `acknowledged`, `resolved`, and `dismissed`.

### Compatibility endpoint

- `POST /v1/audits`

This endpoint remains stateless and preserves the current `AuditResult` response contract.

## 8. Execution and Transaction Semantics

1. Validate tenant context, project ownership, extension, MIME type, and upload-size limit.
2. Read the bounded upload, calculate SHA-256, and persist it through the storage adapter.
3. In a short transaction, create source-file metadata, dataset snapshot, catalogue snapshot if absent, and a `running` analysis run.
4. Execute the deterministic engine outside a long-lived database transaction.
5. On success, start a new transaction and insert every finding and evidence row, then mark the run `succeeded` with counts and timing.
6. On engine failure, mark the run `failed` with a stable safe error code. No finding or evidence rows may remain for the failed run.
7. Re-uploading identical bytes is allowed as a new dataset snapshot and remains auditable through the repeated SHA-256.

Phase 4A does not retry engine failures automatically and does not deduplicate uploads across projects.

## 9. Error Contract

All new durable endpoints use:

```json
{
  "error": {
    "code": "project_not_found",
    "message": "Project was not found for this organization",
    "request_id": "opaque-request-id",
    "analysis_run_id": null
  }
}
```

`analysis_run_id` is optional and is populated only when a failed run was persisted before the response was returned.

Required stable codes are:

- `missing_tenant_context`
- `invalid_tenant_context`
- `tenant_scope_violation`
- `project_not_found`
- `analysis_run_not_found`
- `finding_not_found`
- `unsupported_file_type`
- `file_too_large`
- `workbook_schema_error`
- `incompatible_artifact_versions`
- `analysis_failed`
- `persistence_error`
- `invalid_finding_status`

Messages must not expose SQL, filesystem paths, stack traces, or workbook internals that are not already part of the public validation contract.

## 10. Testing Strategy

Unit tests cover repository behavior, tenant filters, storage-key safety, state transitions, response mapping, and error translation.

API tests cover project creation/listing, Golden upload, Boundary upload, run history, finding filters, detail, evidence, status changes, invalid files, version mismatch, missing tenant context, and cross-tenant access.

PostgreSQL 15+ is the only integration database. Tests do not substitute SQLite because UUID, JSONB, constraints, and transaction behavior must match production. A local container definition provides the integration database.

The primary end-to-end acceptance scenarios are:

- Golden Positive workbook persists a successful run with 59 findings and complete evidence.
- Boundary / Negative workbook persists a successful run with zero findings.
- A failed engine execution persists a failed run and zero partial findings.
- Every cross-tenant project, run, finding, and evidence request fails closed.
- All existing 77 engine and documentation tests continue to pass.
- Alembic upgrades an empty PostgreSQL database to head without errors.

## 11. Documentation and Version Alignment

- Preserve `ControlCheck_AI_ERD_Database_Spec_v0.1.docx` and create v0.2.
- Preserve the v0.1 SQL schema and create a v0.2 schema/migration aligned with this design.
- Preserve the v0.1 rule-catalogue document and create v0.2 aligned with the 20-rule runtime catalogue.
- Update the PRD to record Phase 4A persistence sequencing, Phase 4B raw/canonical ingestion, and deferred authentication/RBAC when those statements differ from the current PRD.
- Update the developer README with PostgreSQL startup, migrations, environment variables, storage directory, and API examples.
- Treat files copied into `docs/` as historical/reference sources. Runtime catalogues and fixtures under `data/` remain canonical for execution.

## 12. Definition of Done

- Alembic upgrades an empty PostgreSQL 15+ database to head.
- The Golden Positive workflow persists 59 findings with evidence and retrieves them through the API.
- The Boundary / Negative workflow persists a successful zero-finding run.
- Tenant mismatch is rejected for every durable resource type.
- Failed analysis never leaves partial findings or evidence.
- File bytes remain outside PostgreSQL and metadata contains a verified SHA-256.
- All existing and new automated tests pass.
- ERD, SQL, rule catalogue, PRD sequencing, and README agree with implemented behavior.

## 13. Sequencing After Phase 4A

Phase 4B adds raw-row and canonical-fact persistence plus import/mapping history. Authentication and complete RBAC follow after the tenant-scoped persistence contract is stable. Health scoring, AI reasoning, production UI, and pilot deployment remain subsequent phases.
