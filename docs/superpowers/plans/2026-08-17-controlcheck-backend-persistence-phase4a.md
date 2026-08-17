# ControlCheck Backend Persistence Phase 4A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PostgreSQL-backed application layer that persists projects, uploaded workbook snapshots, analysis runs, deterministic findings, and evidence while preserving the stateless v0.2 engine API.

**Architecture:** Keep the rule engine database-independent and place orchestration in a synchronous application service. FastAPI resolves an explicit tenant context, local storage retains workbook bytes, SQLAlchemy repositories own organization-scoped queries, and Alembic owns the PostgreSQL 15+ schema.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, psycopg 3, PostgreSQL 15+, pytest, Podman/Docker Compose, python-docx.

## Global Constraints

- Authentication and complete RBAC are excluded; every durable request requires `X-Organization-ID`.
- PostgreSQL 15+ is the only integration database; do not substitute SQLite.
- `Project_Info.project_id` must equal the target `projects.code` before rule execution.
- Keep `controlcheck.service.run_audit` independent of HTTP, SQLAlchemy, PostgreSQL, and file storage.
- Preserve `POST /v1/audits` and its current stateless response contract.
- Store file bytes outside PostgreSQL beneath a configured storage root.
- Persist findings and all evidence atomically; failed runs contain no partial findings.
- Runtime artefacts under `data/` remain canonical; copies under `docs/` are historical references.
- Use TDD for every production behavior: RED, verify the expected failure, GREEN, refactor, then commit.
- Do not modify the six user-supplied v0.1 reference files; record and verify their exact SHA-256 values.

---

### Task 1: Preserve reference artefacts and add Phase 4 runtime configuration

**Files:**
- Create: `docs/reference_artifacts_v0.1.sha256.json`
- Create: `docs/README.md`
- Create: `src/controlcheck/settings.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Test: `tests/test_phase4_settings.py`
- Test: `tests/test_reference_artifacts_phase4.py`

**Interfaces:**
- Produces: `PersistenceSettings.from_env() -> PersistenceSettings`.
- Produces: exact checksum manifest consumed by the documentation regression test.
- Adds dependencies: `SQLAlchemy>=2.0`, `alembic>=1.13`, and `psycopg[binary]>=3.1`.

- [ ] **Step 1: Write failing settings and checksum tests**

```python
def test_persistence_settings_require_database_url(monkeypatch):
    monkeypatch.delenv("CONTROLCHECK_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="CONTROLCHECK_DATABASE_URL"):
        PersistenceSettings.from_env()


def test_reference_artifact_hashes(project_root):
    manifest = json.loads((project_root / "docs/reference_artifacts_v0.1.sha256.json").read_text())
    for name, expected in manifest.items():
        actual = hashlib.sha256((project_root / "docs" / name).read_bytes()).hexdigest().upper()
        assert actual == expected
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_phase4_settings.py tests/test_reference_artifacts_phase4.py -q -p no:cacheprovider`

Expected: collection fails because `controlcheck.settings` and the checksum manifest do not exist.

- [ ] **Step 3: Add exact configuration and manifest**

```python
@dataclass(frozen=True)
class PersistenceSettings:
    database_url: str
    upload_root: Path

    @classmethod
    def from_env(cls) -> "PersistenceSettings":
        database_url = os.environ.get("CONTROLCHECK_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("CONTROLCHECK_DATABASE_URL is required for durable API endpoints")
        return cls(
            database_url=database_url,
            upload_root=Path(os.environ.get("CONTROLCHECK_UPLOAD_ROOT", "var/uploads")),
        )
```

The checksum manifest must contain these exact entries:

```json
{
  "001_controlcheck_core_schema.sql": "FACD12E317976A61FA4927DBE04F1CF6CBDB54D1C7013404FE524BD97446F46A",
  "ControlCheck_AI_Control_Rule_Catalogue_v0.1.docx": "69A9980179ED2040A224CA6B75CD621892EAD6BD53207F2DD2316BEA6127F1BB",
  "ControlCheck_AI_ERD_Database_Spec_v0.1.docx": "E2744A36A32754AEC6F90B0FEF8C30B5FFE9CEC8945D648AF8AD2EF3087B0D38",
  "ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx": "341ABFA2B80D3199F625782007F880F20EC9DA4C92CDD335B9635EFD112574F8",
  "controlcheck_expected_findings_v0.1.json": "D4C562495625B68C77B0579A10274548AA92EBA8DC9C0C87143BCAF3580F032C",
  "controlcheck_rule_catalogue_v0.1.json": "B95B25AFC99FC38D38F756225F45B3662C47E27D6DE69A1E1655418F534D616A"
}
```

Add `var/` to `.gitignore`. In `docs/README.md`, label the six root-level files as immutable v0.1 references and `data/` as runtime authority.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_phase4_settings.py tests/test_reference_artifacts_phase4.py -q -p no:cacheprovider`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add .gitignore pyproject.toml docs/README.md docs/reference_artifacts_v0.1.sha256.json docs/001_controlcheck_core_schema.sql docs/ControlCheck_AI_Control_Rule_Catalogue_v0.1.docx docs/ControlCheck_AI_ERD_Database_Spec_v0.1.docx docs/ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx docs/controlcheck_expected_findings_v0.1.json docs/controlcheck_rule_catalogue_v0.1.json src/controlcheck/settings.py tests/test_phase4_settings.py tests/test_reference_artifacts_phase4.py
git commit -m "chore: preserve phase4 reference artifacts"
```

### Task 2: Create PostgreSQL models and Alembic migration

**Files:**
- Create: `compose.yaml`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/20260817_0001_phase4a_persistence.py`
- Create: `src/controlcheck/persistence/__init__.py`
- Create: `src/controlcheck/persistence/database.py`
- Create: `src/controlcheck/persistence/models.py`
- Test: `tests/persistence/conftest.py`
- Test: `tests/persistence/test_migrations.py`

**Interfaces:**
- Produces: `Base`, `create_session_factory(database_url) -> sessionmaker[Session]`.
- Produces ORM records `OrganizationRecord`, `ProjectRecord`, `SourceFileRecord`, `DatasetSnapshotRecord`, `RuleCatalogueVersionRecord`, `AnalysisRunRecord`, `FindingRecord`, `FindingEvidenceRecord`, `ApprovedExceptionRecord`, and `AuditLogRecord`.

- [ ] **Step 1: Add the PostgreSQL service definition**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: controlcheck
      POSTGRES_USER: controlcheck
      POSTGRES_PASSWORD: controlcheck
    ports:
      - "54329:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U controlcheck -d controlcheck"]
      interval: 2s
      timeout: 3s
      retries: 30
```

- [ ] **Step 2: Write the failing migration test**

```python
EXPECTED_TABLES = {
    "organizations", "projects", "source_files", "dataset_snapshots",
    "rule_catalogue_versions", "analysis_runs", "findings",
    "finding_evidence", "approved_exceptions", "audit_logs",
}

def test_alembic_upgrade_creates_phase4a_schema(postgres_url):
    command.upgrade(alembic_config(postgres_url), "head")
    assert EXPECTED_TABLES <= set(inspect(create_engine(postgres_url)).get_table_names())
```

- [ ] **Step 3: Start PostgreSQL and verify RED**

Run: `podman compose up -d postgres`

Run: `python -m pytest tests/persistence/test_migrations.py -q -p no:cacheprovider`

Expected: fails because Alembic configuration and migration do not exist.

- [ ] **Step 4: Implement database metadata and the migration**

Use PostgreSQL UUID and JSONB columns. The core run and finding identities must be declared exactly as follows:

```python
class AnalysisRunRecord(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"))
    catalogue_version_id: Mapped[UUID] = mapped_column(ForeignKey("rule_catalogue_versions.id", ondelete="RESTRICT"))
    engine_version: Mapped[str] = mapped_column(String(20))
    workbook_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="running")
    rule_count: Mapped[int] = mapped_column(Integer, default=0)
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FindingRecord(Base):
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("analysis_run_id", "engine_finding_id"),)
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    engine_finding_id: Mapped[str] = mapped_column(String(64))
    rule_id: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    metrics: Mapped[dict] = mapped_column(JSONB)
    calculation: Mapped[dict] = mapped_column(JSONB)
    business_impact: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
```

Add database check constraints for every state enum, confidence `0..1`, non-negative counts/durations, 64-character SHA-256 values, and effective exception dates. Mirror all constraints in the Alembic revision; downgrade drops tables in reverse dependency order.

- [ ] **Step 5: Verify migration upgrade and downgrade**

Run: `python -m pytest tests/persistence/test_migrations.py -q -p no:cacheprovider`

Expected: upgrade, schema inspection, downgrade, and second upgrade pass.

- [ ] **Step 6: Commit**

```powershell
git add compose.yaml alembic.ini alembic src/controlcheck/persistence tests/persistence
git commit -m "feat: add phase4a postgres schema"
```

### Task 3: Implement safe local workbook storage

**Files:**
- Create: `src/controlcheck/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Produces: `StoredObject(key: str, size_bytes: int, sha256: str)`.
- Produces: `LocalFileStorage.put(organization_id, project_id, filename, data) -> StoredObject`.
- Produces: `LocalFileStorage.delete(key) -> None`.

- [ ] **Step 1: Write failing storage tests**

```python
def test_storage_writes_under_configured_root(tmp_path):
    stored = LocalFileStorage(tmp_path).put(ORG_ID, PROJECT_ID, "project.xlsx", b"xlsx")
    assert (tmp_path / stored.key).read_bytes() == b"xlsx"
    assert stored.sha256 == hashlib.sha256(b"xlsx").hexdigest()


def test_storage_discards_path_traversal(tmp_path):
    stored = LocalFileStorage(tmp_path).put(ORG_ID, PROJECT_ID, "../../outside.xlsx", b"xlsx")
    assert Path(stored.key).name == "outside.xlsx"
    assert not (tmp_path.parent / "outside.xlsx").exists()
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_storage.py -q -p no:cacheprovider`

Expected: import fails because `controlcheck.storage` does not exist.

- [ ] **Step 3: Implement atomic local storage**

Use key format `<organization UUID>/<project UUID>/<object UUID>/<sanitized basename>`. Write to a sibling `.tmp` file, call `Path.replace`, verify the resolved target remains beneath the configured root, and make `delete` idempotent.

```python
class FileStorage(Protocol):
    def put(self, organization_id: UUID, project_id: UUID, filename: str, data: bytes) -> StoredObject: ...
    def delete(self, key: str) -> None: ...
```

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/test_storage.py -q -p no:cacheprovider`

```powershell
git add src/controlcheck/storage.py tests/test_storage.py
git commit -m "feat: add safe workbook storage adapter"
```

### Task 4: Add organization-scoped project repository

**Files:**
- Create: `src/controlcheck/persistence/repositories.py`
- Test: `tests/persistence/test_project_repository.py`

**Interfaces:**
- Produces: `ProjectRepository.create(organization_id, code, name, currency) -> ProjectRecord`.
- Produces: `ProjectRepository.list_for_organization(organization_id) -> list[ProjectRecord]`.
- Produces: `ProjectRepository.get_scoped(organization_id, project_id) -> ProjectRecord | None`.

- [ ] **Step 1: Write a failing cross-tenant repository test**

```python
def test_project_lookup_is_organization_scoped(db_session):
    first = seed_organization(db_session, "first")
    second = seed_organization(db_session, "second")
    project = ProjectRepository(db_session).create(first.id, "PRJ-1", "Project One", "IDR")
    assert ProjectRepository(db_session).get_scoped(second.id, project.id) is None
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/persistence/test_project_repository.py -q -p no:cacheprovider`

Expected: fails because `ProjectRepository` does not exist.

- [ ] **Step 3: Implement explicit organization predicates**

Every resource query must include `WHERE organization_id = :organization_id`; do not load by primary key and compare in Python.

```python
def get_scoped(self, organization_id: UUID, project_id: UUID) -> ProjectRecord | None:
    return self.session.scalar(
        select(ProjectRecord).where(
            ProjectRecord.id == project_id,
            ProjectRecord.organization_id == organization_id,
        )
    )
```

- [ ] **Step 4: Verify GREEN and commit**

Run: `python -m pytest tests/persistence/test_project_repository.py -q -p no:cacheprovider`

```powershell
git add src/controlcheck/persistence/repositories.py tests/persistence/test_project_repository.py
git commit -m "feat: add tenant scoped project repository"
```

### Task 5: Add tenant context, error envelope, and project API

**Files:**
- Create: `src/controlcheck/api_models.py`
- Create: `src/controlcheck/errors.py`
- Modify: `src/controlcheck/api.py`
- Test: `tests/test_persistent_project_api.py`

**Interfaces:**
- Produces: `TenantContext(organization_id: UUID)`.
- Extends: `create_app(..., session_factory=None, storage=None)` without breaking existing callers.
- Produces project create/list endpoints.

- [ ] **Step 1: Write failing API tests**

```python
def test_project_api_requires_tenant_header(persistent_client):
    response = persistent_client.get(f"/v1/organizations/{ORG_ID}/projects")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_tenant_context"


def test_project_path_must_match_tenant_header(persistent_client):
    response = persistent_client.get(
        f"/v1/organizations/{OTHER_ORG_ID}/projects",
        headers={"X-Organization-ID": str(ORG_ID)},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "tenant_scope_violation"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_persistent_project_api.py -q -p no:cacheprovider`

Expected: durable routes return 404.

- [ ] **Step 3: Implement the stable error handler and project routes**

```python
class ControlCheckApplicationError(Exception):
    def __init__(self, code: str, message: str, status_code: int, analysis_run_id: UUID | None = None):
        self.code, self.message, self.status_code = code, message, status_code
        self.analysis_run_id = analysis_run_id


def require_tenant(x_organization_id: str | None = Header(None)) -> TenantContext:
    if x_organization_id is None:
        raise ControlCheckApplicationError("missing_tenant_context", "X-Organization-ID is required", 400)
    try:
        return TenantContext(organization_id=UUID(x_organization_id))
    except ValueError as exc:
        raise ControlCheckApplicationError("invalid_tenant_context", "X-Organization-ID must be a UUID", 400) from exc
```

Add request-ID middleware and return `{"error": {"code", "message", "request_id", "analysis_run_id"}}`. Omit `analysis_run_id` when it is `None`.

- [ ] **Step 4: Verify the new and legacy APIs**

Run: `python -m pytest tests/test_persistent_project_api.py tests/test_api.py tests/test_cli_api_v02.py -q -p no:cacheprovider`

Expected: project tests and all stateless compatibility tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/controlcheck/api.py src/controlcheck/api_models.py src/controlcheck/errors.py tests/test_persistent_project_api.py
git commit -m "feat: add tenant scoped project api"
```

### Task 6: Persist analysis runs, findings, and evidence atomically

**Files:**
- Create: `src/controlcheck/application.py`
- Modify: `src/controlcheck/persistence/repositories.py`
- Modify: `src/controlcheck/api.py`
- Test: `tests/persistence/test_analysis_service.py`
- Test: `tests/test_persistent_analysis_api.py`

**Interfaces:**
- Produces: `AnalysisService.run(tenant, project_id, filename, content_type, data) -> AnalysisRunRecord`.
- Produces repository methods `start_run`, `complete_run`, `fail_run`, and `persist_findings`.
- Produces: `POST /v1/projects/{project_id}/analysis-runs`.

- [ ] **Step 1: Write the failing Golden persistence test**

```python
def test_golden_run_persists_59_findings_and_evidence(analysis_service, golden_bytes, seeded_project):
    run = analysis_service.run(ORG_ID, seeded_project.id, "golden.xlsx", XLSX_MIME, golden_bytes)
    assert run.status == "succeeded"
    assert run.finding_count == 59
    assert count_findings(run.id) == 59
    assert count_findings_without_evidence(run.id) == 0
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/persistence/test_analysis_service.py::test_golden_run_persists_59_findings_and_evidence -q -p no:cacheprovider`

Expected: fails because `AnalysisService` does not exist.

- [ ] **Step 3: Implement pre-run persistence and project alignment**

Load the workbook once to verify schema/version and read `dataset.project.project_id`. Compare it to `ProjectRecord.code`; on mismatch raise `workbook_project_mismatch` before an analysis run is created. Store source-file SHA-256, dataset version/data date, and the v0.2 catalogue JSON/hash.

```python
if dataset.project.project_id != project.code:
    storage.delete(stored.key)
    raise ControlCheckApplicationError(
        "workbook_project_mismatch",
        "Workbook project ID does not match the target project code",
        422,
    )
```

- [ ] **Step 4: Implement success transaction mapping**

Map each `Finding` to one `FindingRecord` and each `EvidenceItem` to ordered `FindingEvidenceRecord` rows. Convert Decimal/date values through Pydantic JSON mode before assigning JSONB fields.

```python
payload = finding.model_dump(mode="json")
record = FindingRecord(
    analysis_run_id=run.id,
    organization_id=run.organization_id,
    project_id=run.project_id,
    engine_finding_id=finding.finding_id,
    rule_id=finding.rule_id,
    entity_type=finding.entity_type,
    entity_id=finding.entity_id,
    category=finding.category,
    severity=finding.severity,
    metrics=payload["metrics"],
    calculation=payload["calculation"],
    business_impact=finding.business_impact,
    recommendation=finding.recommendation,
    confidence=Decimal(str(finding.confidence)),
)
```

- [ ] **Step 5: Write and verify failure atomicity RED**

```python
def test_failed_engine_run_has_no_partial_findings(service_with_failing_engine, seeded_project):
    with pytest.raises(ControlCheckApplicationError) as caught:
        service_with_failing_engine.run(ORG_ID, seeded_project.id, "project.xlsx", XLSX_MIME, valid_bytes)
    run_id = caught.value.analysis_run_id
    assert load_run(run_id).status == "failed"
    assert count_findings(run_id) == 0
```

Run: `python -m pytest tests/persistence/test_analysis_service.py::test_failed_engine_run_has_no_partial_findings -q -p no:cacheprovider`

Expected: fails until `fail_run` rolls back finding insertion and commits only safe run failure state.

- [ ] **Step 6: Implement failure persistence and API upload route**

Catch `WorkbookSchemaError`, `VersionCompatibilityError`, and unexpected engine failures separately. Persist stable safe codes, include the run UUID only when a run exists, and never store a traceback or local path.

- [ ] **Step 7: Verify Golden, Boundary, mismatch, and failure cases**

Run: `python -m pytest tests/persistence/test_analysis_service.py tests/test_persistent_analysis_api.py -q -p no:cacheprovider`

Expected: Golden has 59 findings, Boundary succeeds with zero, mismatch creates no run, and failed engine creates no partial finding.

- [ ] **Step 8: Commit**

```powershell
git add src/controlcheck/application.py src/controlcheck/persistence/repositories.py src/controlcheck/api.py tests/persistence/test_analysis_service.py tests/test_persistent_analysis_api.py
git commit -m "feat: persist deterministic analysis runs"
```

### Task 7: Add run history, finding retrieval, filters, evidence, and status changes

**Files:**
- Modify: `src/controlcheck/api_models.py`
- Modify: `src/controlcheck/persistence/repositories.py`
- Modify: `src/controlcheck/api.py`
- Test: `tests/test_persistent_query_api.py`

**Interfaces:**
- Produces all approved GET endpoints and `PATCH /v1/findings/{finding_id}/status`.
- Produces `FindingRepository.list_for_run(..., rule_id=None, severity=None, category=None, entity_id=None, status=None)`.

- [ ] **Step 1: Write failing tenant and filter tests**

```python
def test_finding_filters_are_combined(persistent_client, golden_run):
    response = persistent_client.get(
        f"/v1/analysis-runs/{golden_run.id}/findings",
        params={"rule_id": "CST-001", "severity": "critical"},
        headers=tenant_headers(ORG_ID),
    )
    assert response.status_code == 200
    assert all(item["rule_id"] == "CST-001" and item["severity"] == "critical" for item in response.json()["items"])


def test_cross_tenant_finding_is_not_returned(persistent_client, golden_finding):
    response = persistent_client.get(
        f"/v1/findings/{golden_finding.id}", headers=tenant_headers(OTHER_ORG_ID)
    )
    assert response.status_code in {403, 404}
    assert response.json()["error"]["code"] == "finding_not_found"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_persistent_query_api.py -q -p no:cacheprovider`

Expected: retrieval routes return 404.

- [ ] **Step 3: Implement repository predicates and response schemas**

Apply `organization_id` and parent ownership to every run/finding/evidence query. Sort run history newest-first, findings by severity then rule/entity, and evidence by `evidence_order`.

- [ ] **Step 4: Add strict lifecycle transition behavior**

Accept only `open`, `acknowledged`, `resolved`, and `dismissed`. Set `resolved_at` for resolved/dismissed and clear it when returning to open/acknowledged. Write an audit-log row in the same transaction.

- [ ] **Step 5: Verify GREEN and commit**

Run: `python -m pytest tests/test_persistent_query_api.py -q -p no:cacheprovider`

```powershell
git add src/controlcheck/api_models.py src/controlcheck/persistence/repositories.py src/controlcheck/api.py tests/test_persistent_query_api.py
git commit -m "feat: add persisted finding query api"
```

### Task 8: Prove PostgreSQL end-to-end behavior and compatibility

**Files:**
- Modify: `tests/persistence/conftest.py`
- Create: `tests/persistence/test_phase4a_end_to_end.py`
- Modify: `README.md`

**Interfaces:**
- Provides a reproducible PostgreSQL integration gate through `CONTROLCHECK_TEST_DATABASE_URL`.
- Documents container startup, migration, API startup, storage root, and tenant header.

- [ ] **Step 1: Write the failing end-to-end test**

```python
def test_phase4a_golden_and_boundary_workflow(persistent_client, project_root):
    project = create_project(persistent_client, code="PRJ-CCAI-001")
    golden = upload_run(persistent_client, project["id"], project_root / "data/ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx")
    assert golden["status"] == "succeeded" and golden["finding_count"] == 59
    findings = get_findings(persistent_client, golden["id"])
    assert len(findings) == 59
    assert all(get_evidence(persistent_client, item["id"]) for item in findings)

    boundary_project = create_project(persistent_client, code="PRJ-CCAI-BND-001")
    boundary = upload_run(persistent_client, boundary_project["id"], project_root / "data/ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx")
    assert boundary["status"] == "succeeded" and boundary["finding_count"] == 0
```

- [ ] **Step 2: Verify RED for any missing integration contract**

Run: `python -m pytest tests/persistence/test_phase4a_end_to_end.py -q -p no:cacheprovider`

Expected: fails on the first incomplete route, response field, or fixture contract.

- [ ] **Step 3: Make only the minimum integration fixes and update README**

Document these commands exactly:

```powershell
podman compose up -d postgres
$env:CONTROLCHECK_DATABASE_URL = "postgresql+psycopg://controlcheck:controlcheck@127.0.0.1:54329/controlcheck"
alembic upgrade head
$env:CONTROLCHECK_CATALOGUE = "data\controlcheck_rule_catalogue_v0.2.json"
$env:CONTROLCHECK_UPLOAD_ROOT = "var\uploads"
uvicorn controlcheck.api:app --app-dir src --host 127.0.0.1 --port 8000
```

- [ ] **Step 4: Run integration and full regression suites**

Run: `python -m pytest tests/persistence tests/test_persistent_project_api.py tests/test_persistent_analysis_api.py tests/test_persistent_query_api.py -q -p no:cacheprovider`

Run: `python -m pytest -q -p no:cacheprovider`

Run: `python -m compileall -q src`

Expected: all Phase 4A tests, all existing 77 tests, and compilation pass.

- [ ] **Step 5: Commit**

```powershell
git add README.md tests/persistence
git commit -m "test: verify phase4a postgres workflow"
```

### Task 9: Align ERD, SQL, rule catalogue, and PRD

**Files:**
- Create: `docs/002_controlcheck_persistence_schema_v0.2.sql`
- Create: `docs/ControlCheck_AI_ERD_Database_Spec_v0.2.docx`
- Create: `docs/ControlCheck_AI_Control_Rule_Catalogue_v0.2.docx`
- Create: `docs/ControlCheck_AI_PRD_v0.3.docx`
- Create: `tools/update_phase4a_documents.py`
- Create: `tests/test_phase4a_documents.py`
- Create: `validation/previews/phase4a-docs/`

**Interfaces:**
- Preserves all v0.1/v0.2 source documents byte-for-byte.
- Produces v0.2 ERD/catalogue and PRD v0.3 aligned with implemented Phase 4A behavior.

- [ ] **Step 1: Write failing structural document tests**

```python
def test_erd_v02_names_phase4a_tables(extracted_erd_text):
    for name in ("dataset_snapshots", "rule_catalogue_versions", "analysis_runs", "approved_exceptions"):
        assert name in extracted_erd_text
    assert "entity_id" in extracted_erd_text and "text" in extracted_erd_text


def test_rule_catalogue_v02_contains_all_runtime_rules(extracted_catalogue_text, project_root):
    runtime = json.loads((project_root / "data/controlcheck_rule_catalogue_v0.2.json").read_text())
    assert len(runtime["rules"]) == 20
    assert all(rule["code"] in extracted_catalogue_text for rule in runtime["rules"])


def test_prd_v03_records_phase4_sequencing(extracted_prd_text):
    assert "Phase 4A" in extracted_prd_text
    assert "Phase 4B" in extracted_prd_text
    assert "Authentication and complete RBAC are deferred" in extracted_prd_text
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_phase4a_documents.py -q -p no:cacheprovider`

Expected: fails because the new documents do not exist.

- [ ] **Step 3: Generate minimal versioned document updates**

Before authoring, follow the documents skill: mark one edit operation for three DOCX outputs, preserve each source document's visual system, apply local versioned changes, render every output, and inspect every page.

The SQL document must be a readable PostgreSQL representation of the Alembic head schema and must not become a second migration authority. Add a header stating that Alembic is executable authority.

- [ ] **Step 4: Run structural and visual verification**

Run: `python -m pytest tests/test_phase4a_documents.py -q -p no:cacheprovider`

Run the packaged DOCX renderer for all three documents. If LibreOffice is unavailable, use the existing fallback renderer, retain PDF/PNG previews, and disclose the fallback in the document QA record. Inspect every rendered page for clipping, overlap, table overflow, and missing glyphs.

- [ ] **Step 5: Run the complete release gate**

Run: `python -m pytest -q -p no:cacheprovider`

Run: `python -m compileall -q src`

Run: `alembic upgrade head`

Run both Golden and Boundary persisted integration scenarios once more.

Expected: zero failures, clean migration, Golden 59 findings with evidence, Boundary zero findings, and no unreviewed document defect.

- [ ] **Step 6: Commit**

```powershell
git add docs tools/update_phase4a_documents.py tests/test_phase4a_documents.py validation/previews/phase4a-docs
git commit -m "docs: align phase4a product specifications"
```

### Task 10: Final verification and branch handoff

**Files:**
- Modify only files required to fix a failing release gate; every fix starts with a reproducing test.

**Interfaces:**
- Produces a clean, reviewable Phase 4A branch.

- [ ] **Step 1: Run fresh verification**

Run: `python -m pytest -q -p no:cacheprovider`

Run: `python -m compileall -q src`

Run: `alembic current`

Run: `alembic check`

Run: `git diff --check`

- [ ] **Step 2: Confirm repository state and evidence**

Run: `git status --short`

Run: `git log --oneline --decorate -12`

Expected: only intentionally preserved user artefacts are tracked, no generated upload data is staged, and all required commits are present.

- [ ] **Step 3: Use verification-before-completion and finishing-development-branch**

Report exact test counts, migration revision, Golden/Boundary counts, document page counts, current branch, and whether a Git remote exists. Present merge/push/keep options to the user; do not merge without their choice.
