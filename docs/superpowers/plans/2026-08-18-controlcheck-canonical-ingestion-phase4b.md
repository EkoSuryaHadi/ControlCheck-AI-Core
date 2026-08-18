# ControlCheck Canonical Ingestion Phase 4B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PostgreSQL canonical snapshot data the durable source of truth for deterministic ControlCheck analysis, while preserving exact Golden/Boundary outcomes and stateless workbook compatibility.

**Architecture:** Ingest each governed workbook once into immutable snapshot-scoped raw and canonical tables. A database dataset loader rebuilds the existing `ProjectDataset`; domain status gates only rules whose declared inputs are blocked. Snapshot analysis persists findings with raw-row lineage and never reopens the source workbook.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, openpyxl, SQLAlchemy 2, Alembic, psycopg 3, PostgreSQL 15+, pytest, python-docx.

## Global Constraints

- PostgreSQL is the canonical source after ingestion; snapshot analysis must not read workbook bytes.
- Every accepted upload creates an immutable snapshot unless the same organization, project, file SHA-256, and mapping-profile hash already exist and `force_new=false`.
- `force_new=true` creates a separate snapshot with a nullable dedupe key; it never mutates the prior snapshot.
- Retain every non-empty governed-domain row in `raw_rows`, including invalid rows.
- Persist valid/warning rows canonically. Hard-invalid rows remain raw-only and block only their affected domain.
- Keep `ProjectDataset`, the 20 deterministic rule implementations, thresholds, finding IDs, and stateless `POST /v1/audits` behavior compatible.
- Add structured `required_domains` to rule catalogue v0.3; never infer gating from human-readable `inputs` text.
- Keep v0.2 threshold/runtime values byte-for-byte equivalent except for the new structured dependency field and version.
- WBS and all facts are snapshot-scoped. No fact row may reference a WBS node from another snapshot.
- Duplicate detection and project-code validation happen before binary storage.
- File and database failures compensate cleanly: no orphan file after DB failure and no committed snapshot without its source object.
- Authentication, complete RBAC, frontend, AI reasoning, queueing, generic column mapping, deployment, and expanded health endpoints remain excluded.
- Runtime artifacts in `data/` are executable authority. Versioned files under `docs/` describe the implemented contract.
- Use TDD per production behavior: RED, inspect expected failure, GREEN, refactor, commit.
- Never modify immutable v0.1 reference artifacts.

---

### Task 1: Version the mapping profile and rule-domain contract

**Files:**
- Create: `data/controlcheck_mapping_profile_v0.1.json`
- Create: `data/controlcheck_rule_catalogue_v0.3.json`
- Modify: `src/controlcheck/config.py`
- Create: `src/controlcheck/ingestion/__init__.py`
- Create: `src/controlcheck/ingestion/profile.py`
- Test: `tests/ingestion/test_mapping_profile.py`
- Test: `tests/test_catalogue_v03.py`

**Interfaces:**
- Produces `MappingProfileV1`, `DomainProfile`, and `ColumnProfile` Pydantic models.
- Produces `load_mapping_profile(path) -> MappingProfileV1` and `mapping_profile_sha256(profile) -> str` using sorted compact JSON.
- Extends `RuleRuntimeV2` with `required_domains: list[Literal["wbs", "budget", "actual_cost", "commitments", "schedule", "progress"]]`.
- Makes `load_catalogue` accept v0.3 through `RuleCatalogueV2` without changing v0.1/v0.2 support.

- [ ] **Step 1: Write failing profile and catalogue tests**

```python
def test_governed_profile_declares_exact_domains_and_columns(project_root):
    profile = load_mapping_profile(project_root / "data/controlcheck_mapping_profile_v0.1.json")
    assert profile.version == "0.1"
    assert set(profile.domains) == {"wbs", "budget", "actual_cost", "commitments", "schedule", "progress"}
    assert profile.domains["actual_cost"].sheet_name == "Actual_Cost"
    assert profile.domains["actual_cost"].columns["transaction_id"].required is True


def test_catalogue_v03_has_explicit_dependencies_for_all_rules(project_root):
    catalogue = load_catalogue(project_root / "data/controlcheck_rule_catalogue_v0.3.json")
    assert len(catalogue.rules) == 20
    assert all(rule.runtime.required_domains for rule in catalogue.rules)
    assert catalogue.by_id("CST-006").runtime.required_domains == ["wbs", "budget", "actual_cost", "progress"]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/ingestion/test_mapping_profile.py tests/test_catalogue_v03.py -q -p no:cacheprovider`

Expected: imports/files fail because profile v0.1 and catalogue v0.3 do not exist.

- [ ] **Step 3: Define the governed template exactly**

The profile must describe the current six domain sheets, their exact header labels, target fields, scalar types, required/null behavior, and date/decimal/boolean normalization. Store the ordered source-to-target mapping as data; do not duplicate header truth in the extractor.

Add these exact rule dependencies:

```text
DQ-001: wbs,budget,actual_cost,schedule,progress
DQ-002: actual_cost
DQ-003: schedule,progress
DQ-004: wbs,budget,actual_cost,commitments,schedule,progress
DQ-005: actual_cost
CST-001: wbs,budget,actual_cost
CST-002: wbs,budget,actual_cost,commitments
CST-003: wbs,budget,actual_cost
CST-004: actual_cost
CST-005: wbs,budget,actual_cost
CST-006: wbs,budget,actual_cost,progress
SCH-001..SCH-005: schedule
PRG-001: wbs,progress
PRG-002: progress,schedule
PRG-003: wbs,budget,actual_cost,progress
XDOM-001: wbs,budget,actual_cost,commitments,schedule,progress
```

- [ ] **Step 4: Verify compatibility and commit**

Run: `python -m pytest tests/ingestion/test_mapping_profile.py tests/test_catalogue_v03.py tests/test_catalogue_contract_v02.py -q -p no:cacheprovider`

```powershell
git add data/controlcheck_mapping_profile_v0.1.json data/controlcheck_rule_catalogue_v0.3.json src/controlcheck/config.py src/controlcheck/ingestion tests/ingestion/test_mapping_profile.py tests/test_catalogue_v03.py
git commit -m "feat: version canonical ingestion contracts"
```

### Task 2: Add the Phase 4B PostgreSQL schema

**Files:**
- Create: `alembic/versions/20260818_0002_phase4b_canonical_ingestion.py`
- Modify: `src/controlcheck/persistence/models.py`
- Test: `tests/persistence/test_phase4b_migration.py`

**Interfaces:**
- Adds `mapping_profile_versions`, `import_batches`, `raw_rows`, `dataset_domain_statuses`, `wbs_nodes`, `budget_records`, `actual_cost_records`, `commitment_records`, `schedule_activities`, and `progress_records`.
- Extends `dataset_snapshots` with `mapping_profile_version_id`, `import_batch_id`, `dedupe_key`, `row_count_raw`, `row_count_canonical`, and expanded status.
- Extends `analysis_runs` with `executed_rule_ids JSONB` and `skipped_rules JSONB`.
- Extends `finding_evidence` with `raw_row_ids JSONB`.

- [ ] **Step 1: Write failing migration tests**

```python
PHASE4B_TABLES = {
    "mapping_profile_versions", "import_batches", "raw_rows",
    "dataset_domain_statuses", "wbs_nodes", "budget_records",
    "actual_cost_records", "commitment_records", "schedule_activities",
    "progress_records",
}

def test_phase4b_upgrade_and_downgrade(postgres_url):
    command.upgrade(alembic_config(postgres_url), "head")
    inspector = inspect(create_engine(postgres_url))
    assert PHASE4B_TABLES <= set(inspector.get_table_names())
    assert {"executed_rule_ids", "skipped_rules"} <= {
        column["name"] for column in inspector.get_columns("analysis_runs")
    }
    command.downgrade(alembic_config(postgres_url), "20260817_0001")
    assert not (PHASE4B_TABLES & set(inspect(create_engine(postgres_url)).get_table_names()))
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/persistence/test_phase4b_migration.py -q -p no:cacheprovider`

Expected: fails because revision `20260818_0002` and new ORM models do not exist.

- [ ] **Step 3: Implement exact constraints and indexes**

Use PostgreSQL UUID/JSONB and enforce:

- snapshot status: `ingesting|validated|validated_with_errors|failed`;
- domain status: `valid|warning|blocked`;
- import batch status: `ingesting|completed|failed`;
- raw validation state: `valid|warning|invalid`;
- unique non-null `dataset_snapshots.dedupe_key`;
- unique `(snapshot_id, domain, source_row_number)` raw rows;
- unique `(snapshot_id, source_key)` per canonical table;
- canonical `raw_row_id` unique and snapshot-aligned through composite foreign keys;
- snapshot-scoped WBS foreign keys from all dependent fact tables;
- non-negative snapshot row counts and import error/warning counts.

The migration must transform existing `validated` snapshots safely, add defaults for existing runs, and restore the Phase 4A shape on downgrade.

- [ ] **Step 4: Verify ORM/migration parity and commit**

Run: `python -m pytest tests/persistence/test_migrations.py tests/persistence/test_phase4b_migration.py -q -p no:cacheprovider`

```powershell
git add alembic/versions/20260818_0002_phase4b_canonical_ingestion.py src/controlcheck/persistence/models.py tests/persistence/test_phase4b_migration.py
git commit -m "feat: add phase4b canonical schema"
```

### Task 3: Extract every governed workbook row without losing invalid data

**Files:**
- Create: `src/controlcheck/ingestion/types.py`
- Create: `src/controlcheck/ingestion/extractor.py`
- Test: `tests/ingestion/test_extractor.py`

**Interfaces:**
- Produces `ExtractedRow(domain, sheet_name, source_row_number, values, source_key)`.
- Produces `ExtractedWorkbook(project_values, rows_by_domain, template_errors, workbook_sha256)`.
- Produces `extract_workbook(data: bytes, profile: MappingProfileV1) -> ExtractedWorkbook`.

- [ ] **Step 1: Write failing extraction tests**

```python
def test_golden_extractor_retains_all_domain_rows(golden_bytes, mapping_profile):
    extracted = extract_workbook(golden_bytes, mapping_profile)
    assert {name: len(rows) for name, rows in extracted.rows_by_domain.items()} == {
        "wbs": 12, "budget": 9, "actual_cost": 73,
        "commitments": 6, "schedule": 13, "progress": 36,
    }
    assert extracted.template_errors == []


def test_non_empty_invalid_row_is_retained(invalid_progress_workbook, mapping_profile):
    extracted = extract_workbook(invalid_progress_workbook, mapping_profile)
    row = extracted.rows_by_domain["progress"][-1]
    assert row.values["Actual Progress"] == "not-a-percent"
    assert row.source_row_number > 1
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/ingestion/test_extractor.py -q -p no:cacheprovider`

Expected: fails because extractor types and function do not exist.

- [ ] **Step 3: Implement deterministic extraction**

Read workbook bytes from `BytesIO` with `data_only=True`. Extract `Project_Info` key/value rows separately. For each governed sheet, preserve all non-empty data rows as original JSON-safe values. Record missing sheets, duplicate headers, missing required columns, and unexpected headers as deterministic `TemplateIssue` objects. Generate `source_key` from domain, row number, and normalized raw values; never use a random key.

- [ ] **Step 4: Verify malformed and missing-sheet cases, then commit**

Run: `python -m pytest tests/ingestion/test_extractor.py -q -p no:cacheprovider`

```powershell
git add src/controlcheck/ingestion/types.py src/controlcheck/ingestion/extractor.py tests/ingestion/test_extractor.py
git commit -m "feat: extract lossless governed workbook rows"
```

### Task 4: Map raw rows to canonical records and domain status

**Files:**
- Create: `src/controlcheck/ingestion/mapper.py`
- Test: `tests/ingestion/test_mapper.py`

**Interfaces:**
- Produces `RowIssue(code, message, field, severity)`.
- Produces `CanonicalRowResult(domain, source_key, record, issues)` where `record` is a current domain Pydantic model or `None`.
- Produces `MappedSnapshot(project, rows_by_domain, domain_statuses, error_count, warning_count)`.
- Produces `map_extracted_workbook(extracted, profile) -> MappedSnapshot`.

- [ ] **Step 1: Write failing canonical mapping tests**

```python
def test_golden_mapping_has_exact_canonical_counts(golden_bytes, mapping_profile):
    mapped = map_extracted_workbook(extract_workbook(golden_bytes, mapping_profile), mapping_profile)
    assert {name: len([r for r in rows if r.record is not None]) for name, rows in mapped.rows_by_domain.items()} == {
        "wbs": 12, "budget": 9, "actual_cost": 73,
        "commitments": 6, "schedule": 13, "progress": 36,
    }
    assert set(mapped.domain_statuses.values()) == {DomainStatus.valid}


def test_hard_invalid_progress_is_raw_only_and_blocks_progress(invalid_progress_workbook, mapping_profile):
    mapped = map_extracted_workbook(extract_workbook(invalid_progress_workbook, mapping_profile), mapping_profile)
    result = mapped.rows_by_domain["progress"][-1]
    assert result.record is None
    assert result.issues[0].code == "invalid_decimal"
    assert mapped.domain_statuses["progress"] is DomainStatus.blocked
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/ingestion/test_mapper.py -q -p no:cacheprovider`

Expected: fails because canonical mapper does not exist.

- [ ] **Step 3: Implement normalization and severity rules**

Normalize strings, dates, decimals, booleans, and percentage values with stable reason codes. Valid rows create existing domain models and retain `SourceRef`. Warnings allow a canonical record. Missing required value, impossible scalar conversion, contradictory dates, and invalid WBS master identity make that row raw-only. Missing/invalid WBS domain blocks every WBS-dependent domain; an orphan fact WBS remains canonical so DQ-001/DQ-004 can detect it when the WBS domain itself is valid.

- [ ] **Step 4: Verify Golden, Boundary, warning, invalid, and orphan cases**

Run: `python -m pytest tests/ingestion/test_mapper.py tests/test_loader.py -q -p no:cacheprovider`

- [ ] **Step 5: Commit**

```powershell
git add src/controlcheck/ingestion/mapper.py tests/ingestion/test_mapper.py
git commit -m "feat: map governed rows to canonical domains"
```

### Task 5: Persist immutable snapshots with idempotency and compensation

**Files:**
- Create: `src/controlcheck/persistence/ingestion_repositories.py`
- Create: `src/controlcheck/ingestion/service.py`
- Modify: `src/controlcheck/storage.py`
- Test: `tests/persistence/test_snapshot_ingestion_service.py`

**Interfaces:**
- Produces `SnapshotRepository.find_duplicate`, `create_ingesting`, `persist_raw_rows`, `persist_canonical_rows`, `complete`, `fail`, `list_scoped`, and `get_scoped`.
- Produces `SnapshotIngestionService.ingest(organization_id, project_id, filename, content_type, data, force_new=False) -> DatasetSnapshotRecord`.
- Produces storage `exists(key) -> bool` to verify the source object before snapshot completion.

- [ ] **Step 1: Write failing Golden persistence and idempotency tests**

```python
def test_golden_ingestion_persists_raw_and_canonical_rows(snapshot_service, golden_bytes, golden_project, db_session):
    snapshot = snapshot_service.ingest(ORG_ID, golden_project.id, "golden.xlsx", XLSX_MIME, golden_bytes)
    assert snapshot.status == "validated"
    assert snapshot.row_count_raw == 149
    assert snapshot.row_count_canonical == 149
    assert count_rows(db_session, RawRowRecord, snapshot.id) == 149


def test_duplicate_upload_returns_existing_snapshot(snapshot_service, golden_bytes, golden_project):
    first = snapshot_service.ingest(ORG_ID, golden_project.id, "golden.xlsx", XLSX_MIME, golden_bytes)
    second = snapshot_service.ingest(ORG_ID, golden_project.id, "renamed.xlsx", XLSX_MIME, golden_bytes)
    assert second.id == first.id


def test_force_new_creates_distinct_snapshot(snapshot_service, golden_bytes, golden_project):
    first = snapshot_service.ingest(ORG_ID, golden_project.id, "golden.xlsx", XLSX_MIME, golden_bytes)
    forced = snapshot_service.ingest(ORG_ID, golden_project.id, "golden.xlsx", XLSX_MIME, golden_bytes, force_new=True)
    assert forced.id != first.id
    assert forced.dedupe_key is None
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/persistence/test_snapshot_ingestion_service.py -q -p no:cacheprovider`

Expected: fails because snapshot ingestion service/repository do not exist.

- [ ] **Step 3: Implement ordered ingestion transaction**

Execution order must be:

1. resolve tenant-scoped project;
2. compute workbook SHA-256 and extract `Project_Info`;
3. reject project-code mismatch;
4. resolve/store mapping profile version and check dedupe key;
5. write source object;
6. start DB transaction and create import batch/snapshot;
7. persist raw rows, canonical rows, domain statuses, and counts;
8. verify source object exists and commit completed state;
9. delete the source object if the DB transaction fails.

Serialize normal duplicate races through the unique dedupe key: catch the unique violation, roll back, delete the losing file, and return the winner.

- [ ] **Step 4: Add failure/tenant/immutability tests**

Test DB failure deletes file, storage failure creates no snapshot, mismatch stores nothing, missing sheet yields `validated_with_errors`, cross-tenant lookups return none, and completed snapshot facts cannot be updated through repository methods.

Run: `python -m pytest tests/persistence/test_snapshot_ingestion_service.py -q -p no:cacheprovider`

- [ ] **Step 5: Commit**

```powershell
git add src/controlcheck/storage.py src/controlcheck/ingestion/service.py src/controlcheck/persistence/ingestion_repositories.py tests/persistence/test_snapshot_ingestion_service.py
git commit -m "feat: persist immutable canonical snapshots"
```

### Task 6: Rebuild `ProjectDataset` exclusively from PostgreSQL

**Files:**
- Create: `src/controlcheck/persistence/dataset_loader.py`
- Test: `tests/persistence/test_database_dataset_loader.py`

**Interfaces:**
- Produces `DatabaseDataset(snapshot: ProjectDataset, domain_statuses: dict[str, DomainStatus], raw_row_index: dict[tuple[str, int], UUID])`.
- Produces `DatabaseDatasetLoader.load(organization_id, project_id, snapshot_id) -> DatabaseDataset`.

- [ ] **Step 1: Write failing database-loader parity tests**

```python
def test_db_loader_matches_legacy_loader_exactly(ingested_golden, golden_path, db_loader):
    expected = load_workbook(golden_path).model_dump(mode="json")
    actual = db_loader.load(ORG_ID, ingested_golden.project_id, ingested_golden.id)
    assert actual.snapshot.model_dump(mode="json") == expected


def test_db_loader_never_reads_source_file(ingested_golden, db_loader, storage):
    storage.delete(ingested_golden.source_file.storage_key)
    loaded = db_loader.load(ORG_ID, ingested_golden.project_id, ingested_golden.id)
    assert len(loaded.snapshot.actual_cost) == 75
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/persistence/test_database_dataset_loader.py -q -p no:cacheprovider`

Expected: fails because `DatabaseDatasetLoader` does not exist.

- [ ] **Step 3: Implement deterministic scoped loading**

Query the snapshot with organization/project predicates. Load each canonical table ordered by original source row. Recreate exact domain Pydantic models, including `SourceRef(sheet, row_number)`. Return a `(source_sheet, source_row_number) -> raw_row_id` index for later evidence lineage. Reject `ingesting` and `failed` snapshots with stable application errors.

- [ ] **Step 4: Verify parity, tenant isolation, and no-file behavior**

Run: `python -m pytest tests/persistence/test_database_dataset_loader.py -q -p no:cacheprovider`

- [ ] **Step 5: Commit**

```powershell
git add src/controlcheck/persistence/dataset_loader.py tests/persistence/test_database_dataset_loader.py
git commit -m "feat: load engine datasets from postgres"
```

### Task 7: Gate blocked-domain rules and persist skipped-rule evidence

**Files:**
- Modify: `src/controlcheck/engine.py`
- Modify: `src/controlcheck/persistence/repositories.py`
- Modify: `src/controlcheck/application.py`
- Modify: `src/controlcheck/api_models.py`
- Test: `tests/test_engine_domain_gating.py`
- Test: `tests/persistence/test_snapshot_analysis_service.py`

**Interfaces:**
- Produces immutable `RuleSkip(rule_id, reason_code, blocked_domains)` and `EngineExecution(audit, executed_rule_ids, skipped_rules)`.
- Produces `ControlEngine.run_gated(dataset, context, domain_statuses) -> EngineExecution` while keeping `run(...) -> AuditResult` unchanged.
- Produces `AnalysisService.run_snapshot(organization_id, project_id, snapshot_id) -> AnalysisRunRecord`.

- [ ] **Step 1: Write failing engine-gating tests**

```python
def test_only_progress_dependent_rules_skip_when_progress_blocked(engine, golden_dataset, context):
    execution = engine.run_gated(golden_dataset, context, {"progress": "blocked"})
    skipped = {item.rule_id for item in execution.skipped_rules}
    assert skipped == {"DQ-001", "DQ-003", "DQ-004", "CST-006", "PRG-001", "PRG-002", "PRG-003", "XDOM-001"}
    assert "CST-001" in execution.executed_rule_ids
    assert all(item.reason_code == "blocked_required_domain" for item in execution.skipped_rules)
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_engine_domain_gating.py -q -p no:cacheprovider`

Expected: fails because `run_gated` and execution result types do not exist.

- [ ] **Step 3: Implement structured gating only**

Use `rule_definition.runtime.required_domains`; do not inspect rule code/category/input prose. Sort rules and skips by rule ID. `run()` must still execute all rules for stateless compatibility.

- [ ] **Step 4: Write failing snapshot-analysis persistence test**

```python
def test_snapshot_analysis_uses_db_and_persists_lineage(snapshot_analysis_service, ingested_golden, storage, db_session):
    storage.delete(source_key_for(ingested_golden))
    run = snapshot_analysis_service.run_snapshot(ORG_ID, ingested_golden.project_id, ingested_golden.id)
    assert run.status == "succeeded"
    assert run.finding_count == 59
    assert run.rule_count == 20
    assert run.executed_rule_ids == sorted(run.executed_rule_ids)
    assert run.skipped_rules == []
    assert all(e.raw_row_ids for e in evidence_for_run(db_session, run.id))
```

- [ ] **Step 5: Refactor persisted execution**

`run_snapshot` must load only through `DatabaseDatasetLoader`, create a run against the existing snapshot, call `run_gated`, map evidence source rows to `raw_row_ids`, and atomically persist findings/evidence plus executed/skipped metadata. Change the existing workbook analysis orchestration to `ingest(...)` then `run_snapshot(...)`; do not retain the old direct `BytesIO` audit path for durable endpoints.

- [ ] **Step 6: Verify Golden, Boundary, partial-domain, failure atomicity, and legacy engine**

Run: `python -m pytest tests/test_engine_domain_gating.py tests/persistence/test_snapshot_analysis_service.py tests/persistence/test_analysis_service.py -q -p no:cacheprovider`

- [ ] **Step 7: Commit**

```powershell
git add src/controlcheck/engine.py src/controlcheck/application.py src/controlcheck/api_models.py src/controlcheck/persistence/repositories.py tests/test_engine_domain_gating.py tests/persistence/test_snapshot_analysis_service.py
git commit -m "feat: analyze canonical snapshots with domain gating"
```

### Task 8: Expose snapshot ingestion and analysis APIs

**Files:**
- Modify: `src/controlcheck/api_models.py`
- Modify: `src/controlcheck/api.py`
- Test: `tests/test_snapshot_api.py`
- Modify: `tests/test_persistent_analysis_api.py`

**Interfaces:**
- Adds `POST /v1/projects/{project_id}/dataset-snapshots?force_new=false`.
- Adds `GET /v1/projects/{project_id}/dataset-snapshots`.
- Adds `GET /v1/projects/{project_id}/dataset-snapshots/{snapshot_id}`.
- Adds `POST /v1/projects/{project_id}/dataset-snapshots/{snapshot_id}/analysis-runs`.
- Keeps `POST /v1/projects/{project_id}/analysis-runs` as ingest-and-analyze compatibility endpoint.

- [ ] **Step 1: Write failing API contract tests**

```python
def test_snapshot_upload_list_detail_and_analysis(snapshot_client, golden_file, project):
    uploaded = upload_snapshot(snapshot_client, project.id, golden_file)
    assert uploaded.status_code == 201
    snapshot = uploaded.json()
    assert snapshot["status"] == "validated"
    assert snapshot["row_count_raw"] == 149
    assert snapshot["domain_statuses"] == {
        "actual_cost": "valid", "budget": "valid", "commitments": "valid",
        "progress": "valid", "schedule": "valid", "wbs": "valid",
    }
    assert list_snapshots(snapshot_client, project.id)[0]["id"] == snapshot["id"]
    run = analyze_snapshot(snapshot_client, project.id, snapshot["id"])
    assert run["finding_count"] == 59 and run["skipped_rules"] == []
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_snapshot_api.py -q -p no:cacheprovider`

Expected: snapshot routes return 404.

- [ ] **Step 3: Implement response contracts and stable errors**

Snapshot response includes IDs, profile version/hash, workbook hash, status, raw/canonical/error/warning counts, domain statuses, and timestamps; it never exposes storage paths. Use stable error codes `snapshot_not_found`, `snapshot_not_ready`, `workbook_project_mismatch`, `unsupported_template`, and `snapshot_ingestion_failed`. Duplicate normal upload returns `200`; newly created snapshot returns `201`; forced upload returns `201`.

- [ ] **Step 4: Verify compatibility and tenant boundaries**

Run: `python -m pytest tests/test_snapshot_api.py tests/test_persistent_analysis_api.py tests/test_persistent_query_api.py tests/test_api.py -q -p no:cacheprovider`

- [ ] **Step 5: Commit**

```powershell
git add src/controlcheck/api.py src/controlcheck/api_models.py tests/test_snapshot_api.py tests/test_persistent_analysis_api.py
git commit -m "feat: add canonical snapshot api"
```

### Task 9: Prove exact Golden/Boundary parity and update product documents

**Files:**
- Create: `tests/persistence/test_phase4b_end_to_end.py`
- Create: `tests/persistence/test_excel_db_parity.py`
- Create: `tests/test_phase4b_documents.py`
- Create: `docs/003_controlcheck_canonical_ingestion_schema_v0.3.sql`
- Create: `docs/ControlCheck_AI_ERD_Database_Spec_v0.3.docx`
- Create: `docs/ControlCheck_AI_Control_Rule_Catalogue_v0.3.docx`
- Create: `docs/ControlCheck_AI_PRD_v0.4.docx`
- Create: `tools/update_phase4b_documents.py`
- Create: `validation/previews/phase4b-docs/`
- Modify: `README.md`

**Interfaces:**
- Establishes Golden 59, Boundary 0, and exact Excel-vs-DB finding parity as release invariants.
- Records implemented Phase 4B changes in PRD v0.4, ERD v0.3, rule catalogue v0.3, SQL reference v0.3, and developer README.

- [ ] **Step 1: Write failing parity tests**

```python
@pytest.mark.parametrize(
    ("workbook", "project_code", "expected_count"),
    [
        ("ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx", "PRJ-CCAI-001", 59),
        ("ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx", "PRJ-CCAI-BND-001", 0),
    ],
)
def test_excel_and_database_paths_are_exactly_equal(workbook, project_code, expected_count, harness):
    excel = harness.run_stateless(workbook)
    database = harness.ingest_and_run_snapshot(workbook, project_code)
    assert len(database.findings) == expected_count
    assert [f.model_dump(mode="json") for f in database.findings] == [
        f.model_dump(mode="json") for f in excel.findings
    ]
```

- [ ] **Step 2: Run RED and fix only parity defects**

Run: `python -m pytest tests/persistence/test_excel_db_parity.py tests/persistence/test_phase4b_end_to_end.py -q -p no:cacheprovider`

Expected: fails on the first serialization, ordering, source-lineage, API, or transaction mismatch.

- [ ] **Step 3: Write failing document assertions**

Assert PRD v0.4 names immutable snapshots, governed template scope, partial-domain execution, deferred auth/RBAC, and workbook compatibility. Assert ERD v0.3 names all Phase 4B tables and snapshot-scoped foreign keys. Assert catalogue v0.3 contains 20 rules and structured required domains. Assert SQL v0.3 states Alembic is executable authority.

- [ ] **Step 4: Generate and visually inspect versioned docs**

Follow the documents skill before editing DOCX. Preserve existing visual systems. Render every output and inspect every page for clipping, overlap, table overflow, and missing glyphs. Keep v0.1-v0.3 source documents unchanged. Store preview evidence under `validation/previews/phase4b-docs/`.

- [ ] **Step 5: Update developer README**

Document migration, profile/catalogue environment settings, snapshot routes, compatibility route, idempotency/force behavior, partial-domain semantics, and these commands:

```powershell
podman compose up -d postgres
$env:CONTROLCHECK_DATABASE_URL = "postgresql+psycopg://controlcheck:controlcheck@127.0.0.1:54329/controlcheck"
alembic upgrade head
$env:CONTROLCHECK_CATALOGUE = "data\controlcheck_rule_catalogue_v0.3.json"
uvicorn controlcheck.api:app --app-dir src --host 127.0.0.1 --port 8000
```

- [ ] **Step 6: Verify docs/parity and commit**

Run: `python -m pytest tests/persistence/test_excel_db_parity.py tests/persistence/test_phase4b_end_to_end.py tests/test_phase4b_documents.py -q -p no:cacheprovider`

```powershell
git add README.md docs data/controlcheck_rule_catalogue_v0.3.json tools/update_phase4b_documents.py tests/persistence/test_excel_db_parity.py tests/persistence/test_phase4b_end_to_end.py tests/test_phase4b_documents.py validation/previews/phase4b-docs
git commit -m "docs: align phase4b canonical ingestion"
```

### Task 10: Run release gates and prepare branch handoff

**Files:**
- Modify only files needed to fix a reproducing release-gate failure.

**Interfaces:**
- Produces a clean, reviewable `codex/canonical-ingestion-phase4b` branch with migration head `20260818_0002`.

- [ ] **Step 1: Start PostgreSQL and run fresh migration verification**

Run: `podman compose up -d postgres`

Run: `alembic upgrade head`

Run: `alembic current`

Run: `alembic check`

Expected: current/head is `20260818_0002`, and Alembic reports no new upgrade operations.

- [ ] **Step 2: Run focused integration gates**

Run: `python -m pytest tests/persistence/test_phase4b_migration.py tests/persistence/test_snapshot_ingestion_service.py tests/persistence/test_database_dataset_loader.py tests/persistence/test_snapshot_analysis_service.py tests/persistence/test_excel_db_parity.py tests/persistence/test_phase4b_end_to_end.py tests/test_snapshot_api.py -q -p no:cacheprovider`

Expected: Golden DB analysis returns 59 findings, Boundary returns 0, all Golden evidence has raw-row lineage, missing-domain snapshot skips only dependent rules, duplicate upload is idempotent, and tenant isolation passes.

- [ ] **Step 3: Run full regression and static gates**

Run: `python -m pytest -q -p no:cacheprovider`

Run: `python -m compileall -q src`

Run: `git diff --check`

Expected: all tests pass, compilation is clean, and no whitespace errors exist.

- [ ] **Step 4: Inspect final repository state**

Run: `git status --short`

Run: `git log --oneline --decorate -15`

Confirm no upload bytes, temporary databases, secrets, rendered scratch files, or unrelated user changes are staged.

- [ ] **Step 5: Apply completion skills and hand off**

Use `superpowers:verification-before-completion`, then `superpowers:requesting-code-review`, then `superpowers:finishing-a-development-branch`. Report exact test count, migration revision, Golden/Boundary counts, parity result, document page counts, branch, commits, and remote availability. Do not merge or push without the user's explicit choice.
