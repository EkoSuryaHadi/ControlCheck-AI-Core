# ControlCheck AI Phase 4B: Canonical Ingestion and Database-Native Analysis

**Status:** Approved design
**Date:** 18 August 2026
**Base:** Phase 4A persistence at commit `65bb48d`

## 1. Objective

Phase 4B makes PostgreSQL the source of truth for analysis data. A workbook becomes an ingestion source, not the runtime database. Each upload produces an immutable, auditable dataset snapshot containing raw source rows, typed canonical project-control facts, validation state, and mapping-version identity. The existing deterministic rule engine then runs from a reconstructed `ProjectDataset` loaded from PostgreSQL without reopening the workbook.

The phase is complete only when database-backed execution reproduces controlled Excel-backed results exactly: Golden produces 59 findings, Boundary produces zero findings, and findings, severities, metrics, and evidence anchors match.

## 2. Approved Approach

Use a snapshot-native, database-first model.

- Every accepted upload creates an immutable dataset snapshot.
- WBS and every canonical fact are scoped to that snapshot.
- Historical snapshots are never updated in place.
- Raw rows are retained even when canonical conversion fails.
- Canonical facts contain only rows that pass typed conversion and hard validation.
- The rule engine remains source-agnostic and receives the existing domain model.
- Excel and PostgreSQL are input adapters around one deterministic engine.
- The initial mapping profile supports the governed ControlCheck workbook template only. Generic mapping UI is deferred.

Rejected alternatives:

1. Project-master facts overwritten by each import: simpler, but breaks reproducibility and weakens evidence history.
2. General temporal master tables: flexible, but adds query and lifecycle complexity beyond MVP needs.

## 3. Scope

### 3.1 Included

- Versioned mapping-profile persistence.
- Import-batch lifecycle and counts.
- Immutable raw-row persistence with validation results.
- Snapshot-scoped WBS, budget, actual cost, commitment, schedule, and progress facts.
- Workbook-to-database ingestion service.
- PostgreSQL-to-`ProjectDataset` loader.
- Database-backed deterministic analysis.
- Domain-aware rule skipping when required data is blocked.
- Dataset snapshot upload, list, detail, and analysis endpoints.
- Duplicate-upload idempotency.
- Source evidence resolution from finding to file, sheet, and row.
- Phase 4B PRD, ERD, and readable SQL updates.

### 3.2 Excluded

- Generic Excel mapping UI or user-authored mappings.
- Authentication and complete RBAC.
- Frontend implementation.
- AI reasoning or conversational features.
- Health scoring.
- Background job queues.
- Production deployment and cloud object storage.

## 4. Architecture

```text
Workbook
  -> Template Validator
  -> Raw Row Writer
  -> Canonical Mapper
  -> Snapshot Validator
  -> PostgreSQL Canonical Dataset
  -> Database Dataset Loader
  -> Existing Deterministic Rule Engine
  -> Persisted Findings and Evidence
```

### 4.1 Component boundaries

`WorkbookExtractor` reads the governed template and produces project metadata plus source rows. It does not write the database.

`MappingProfile` defines required sheets, columns, target types, normalizers, and mapping version. Its serialized definition and SHA-256 are stored for reproducibility.

`IngestionService` owns the transaction. It creates or resolves file metadata, snapshot, import batch, raw rows, domain status, and canonical records. It commits only a coherent result.

`CanonicalWriter` converts validated source rows into typed snapshot-scoped facts. It does not execute rules.

`DatabaseDatasetLoader` reconstructs the existing `ProjectDataset` domain object from one tenant-scoped snapshot. Rules do not depend on SQLAlchemy or workbook libraries.

`AnalysisService` runs the existing engine using a dataset adapter. The canonical path loads PostgreSQL. Existing Excel execution remains as compatibility and parity reference.

## 5. Data Model

### 5.1 Existing tables retained

- `organizations`
- `projects`
- `source_files`
- `dataset_snapshots`
- `rule_catalogue_versions`
- `analysis_runs`
- `findings`
- `finding_evidence`
- `approved_exceptions`
- `audit_logs`

### 5.2 New tables

#### `mapping_profile_versions`

- `id` UUID primary key
- `version` text
- `sha256` char(64)
- `definition` JSONB
- `created_at` timestamptz
- unique `(version, sha256)`

#### `import_batches`

- `id` UUID primary key
- `organization_id`, `project_id`, `dataset_snapshot_id`
- `mapping_profile_version_id`
- `status`: `running`, `succeeded`, `failed`
- `rows_read`, `rows_valid`, `rows_warning`, `rows_rejected`
- `safe_error_code`, `safe_error_message`, `error_summary` JSONB
- `started_at`, `completed_at`
- one successful active import batch per snapshot

#### `dataset_domain_statuses`

- `id` UUID primary key
- `organization_id`, `project_id`, `dataset_snapshot_id`
- `domain`: `wbs`, `budget`, `actual_cost`, `commitment`, `schedule`, `progress`
- `status`: `valid`, `warning`, `blocked`
- row counts and validation summary JSONB
- unique `(dataset_snapshot_id, domain)`

#### `raw_rows`

- `id` bigint identity primary key
- `organization_id`, `project_id`, `dataset_snapshot_id`, `import_batch_id`
- `source_sheet`, `source_row_number`
- `row_hash` char(64)
- `raw_data` JSONB
- `validation_status`: `valid`, `warning`, `rejected`
- `validation_errors` JSONB
- unique `(dataset_snapshot_id, source_sheet, source_row_number)`

#### Canonical tables

- `wbs_nodes`
- `budget_records`
- `actual_cost_records`
- `commitment_records`
- `schedule_activities`
- `progress_records`

Every canonical table contains:

- UUID primary key
- `organization_id`
- `project_id`
- `dataset_snapshot_id`
- `raw_row_id`
- the source business identifier used by the engine
- typed domain fields matching `src/controlcheck/models.py`
- unique source business identifier per snapshot

`wbs_nodes.parent_id` may reference only a node in the same snapshot. Domain records may retain a nullable source WBS code even when it does not resolve, so data-quality rules can detect missing and orphan references. Resolved rows also store nullable `wbs_node_id`.

Money uses `NUMERIC(20,2)`. Canonical progress uses decimal values from zero to one. Dates use PostgreSQL `date`. JSONB is limited to raw source payloads, mappings, validation details, and summaries; canonical query fields remain typed columns.

### 5.3 Existing-table changes

`dataset_snapshots.status` expands to:

- `ingesting`
- `validated`
- `validated_with_errors`
- `failed`

It also records mapping-profile identity, raw/canonical counts, and validation summary.

It gains a nullable `dedupe_key`. Normal uploads set a deterministic SHA-256 derived from organization, project, workbook SHA-256, and mapping-profile SHA-256; a unique constraint enforces one normal snapshot for that key. Forced uploads set `dedupe_key` to null, which permits intentional duplicate snapshots while preserving normal-request idempotency.

`analysis_runs` records executed rule count, skipped rule count, and structured skipped-rule reasons. Existing `rule_count` remains the catalogue rule count for backward compatibility unless migration tests prove a safer contract change; explicit executed and skipped counts remove ambiguity.

`finding_evidence` gains optional raw-row references or a resolvable evidence-link structure without removing its current source-sheet/source-row contract.

## 6. Ingestion Semantics

### 6.1 Immutability

A snapshot is mutable only while `ingesting`. After `validated`, `validated_with_errors`, or `failed`, its source identity, raw rows, facts, domain statuses, and mapping version cannot be changed by application services.

### 6.2 Duplicate uploads

For the same organization, project, workbook SHA-256, and mapping-profile SHA-256:

- default behavior returns the existing completed snapshot;
- it does not rewrite rows or create another import batch;
- `force=true` creates a distinct immutable snapshot;
- concurrent duplicate requests are protected by a database uniqueness/idempotency constraint, not only an application check.

Duplicate detection occurs before writing another binary. Normal duplicates return the existing source-file and snapshot identity.

### 6.3 Row validation

- Every non-empty source record is persisted in `raw_rows`.
- Valid rows enter canonical tables.
- Warning rows enter canonical tables and retain warnings.
- Hard-invalid rows remain raw-only with deterministic validation codes.
- Missing required sheets or columns block that domain.
- Workbook/project identity mismatch creates no snapshot, matching the Phase 4A security boundary.

### 6.4 Transaction behavior

File storage and database writes cannot share a transaction. The service therefore:

1. validates project identity before durable snapshot creation;
2. stores the binary atomically;
3. opens one database transaction for snapshot, import, raw, validation, and canonical data;
4. rolls back database writes on ingestion failure;
5. deletes the newly stored binary when database creation fails and no persisted source-file record owns it;
6. records a failed import only when enough safe metadata exists to do so without leaving partial facts.

No failed ingestion may leave canonical rows reachable as a validated snapshot.

## 7. Domain Gating and Analysis

Rule catalogue schema v0.3 adds a structured `required_domains` array to every rule runtime definition. Thresholds and finding behavior remain unchanged from catalogue v0.2. Gating never parses the human-readable `inputs` field. Before rule execution:

- required domains `valid` or `warning`: execute rule;
- any required domain `blocked`: skip rule;
- skipped rules produce no findings;
- run metadata records rule ID and deterministic skip reason;
- healthy rules still execute;
- an unexpected engine exception fails the entire run and persists zero findings.

The database loader reconstructs the same ordering, values, `SourceRef`, decimals, dates, and identifiers as the Excel loader. Stable ordering is explicit in queries so repeated runs produce identical finding and evidence order.

## 8. API Contract

### 8.1 Snapshot endpoints

- `POST /v1/projects/{project_id}/dataset-snapshots`
  - multipart workbook
  - optional `force=false`
  - returns snapshot identity, status, counts, domain statuses, and duplicate indicator
- `GET /v1/projects/{project_id}/dataset-snapshots`
- `GET /v1/projects/{project_id}/dataset-snapshots/{snapshot_id}`

### 8.2 Analysis endpoint

- `POST /v1/projects/{project_id}/dataset-snapshots/{snapshot_id}/analysis-runs`
  - no workbook body
  - loads snapshot from PostgreSQL
  - rejects failed or still-ingesting snapshots

The existing multipart durable analysis endpoint remains a compatibility shortcut. It ingests or resolves a snapshot, then executes from PostgreSQL. The stateless `/v1/audits` endpoint remains unchanged.

All endpoints retain Phase 4A request IDs, error envelopes, and `X-Organization-ID` tenant context. Cross-tenant resources return `404`.

## 9. Error Contract

Stable safe codes include:

- `duplicate_snapshot`
- `snapshot_not_ready`
- `snapshot_failed`
- `mapping_profile_incompatible`
- `missing_sheets`
- `missing_columns`
- `canonical_validation_failed`
- `ingestion_failed`
- existing `project_identity_mismatch`
- existing engine failure code

Internal database paths, SQL, stack traces, and source values classified as sensitive never enter public messages.

## 10. Testing Strategy

All production changes use test-driven development.

### 10.1 Migration tests

- Upgrade from Phase 4A to Phase 4B.
- Downgrade to Phase 4A.
- Re-upgrade.
- SQLAlchemy metadata has zero Alembic drift.
- Constraints enforce snapshot scope and idempotency.

### 10.2 Repository and service tests

- Exact raw and canonical counts.
- Tenant predicates on every query.
- Immutable snapshot enforcement.
- Duplicate and forced-upload behavior.
- Warning/rejected row routing.
- Missing sheet/column domain blocking.
- Transaction rollback and storage compensation.
- Deterministic dataset reconstruction.

### 10.3 Parity and E2E tests

- Golden Excel path: 59 findings.
- Golden database path: 59 findings.
- Boundary Excel path: zero findings.
- Boundary database path: zero findings.
- Equality of finding identity, rule, entity, severity, metrics, calculations, and evidence anchors.
- Database analysis does not reopen the workbook.
- Finding evidence resolves to source file, sheet, and row.
- Blocked-domain rules are skipped while healthy-domain rules run.
- Cross-tenant snapshot, raw-row, fact, and run access returns `404`.
- Full Phase 4A regression suite stays green.

## 11. Delivery Sequence

1. Phase 4B migration and SQLAlchemy models.
2. Tenant-scoped repositories and immutability/idempotency guards.
3. Versioned ControlCheck template mapping profile.
4. Rule catalogue v0.3 with structured required-domain metadata and no threshold changes.
5. Raw extraction and validation pipeline.
6. Canonical writer and domain-status computation.
7. PostgreSQL `ProjectDataset` loader.
8. Rule-domain gating and run metadata.
9. Snapshot and database-analysis API endpoints.
10. Golden/Boundary parity E2E tests.
11. PRD v0.4, ERD/database spec v0.3, rule catalogue document v0.3, and readable SQL reference v0.3 updates.

## 12. Definition of Done

Phase 4B is done when:

- PostgreSQL is the analysis source of truth for durable runs.
- Golden database execution produces 59 findings with zero parity differences.
- Boundary database execution produces zero findings.
- Every canonical record links to an immutable raw row and source workbook.
- Invalid data handling and domain blocking are deterministic and visible.
- Duplicate uploads are idempotent and concurrent-safe.
- Historical snapshots remain unchanged after later uploads.
- Tenant-isolation tests fail closed.
- Migration and full regression suites pass.
- Product and database specifications match implemented behavior.
