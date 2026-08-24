# ControlCheck Internal Production MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy ControlCheck Core as a secure single-organization internal API with bearer authentication, managed PostgreSQL readiness, persistent upload storage, a non-root container, CI gates, and production documentation.

**Architecture:** A production-aware application factory derives one tenant from server settings and authenticates all `/v1/*` requests with a constant-time bearer API-key check. Public liveness/readiness endpoints expose minimal state, while a single Docker replica runs Alembic before Uvicorn and stores workbook binaries on a mounted persistent volume.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16, pytest, Uvicorn, Docker, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-08-24-controlcheck-production-mvp-design.md`

## Global Constraints

- Production mode is selected only by `CONTROLCHECK_ENV=production`; missing or invalid production settings fail startup.
- Every `/v1/*` route requires `Authorization: Bearer <key>` in production.
- Production tenant identity comes only from `CONTROLCHECK_ORGANIZATION_ID`; client headers cannot override it.
- `CONTROLCHECK_API_KEY` is at least 32 characters and compared with `secrets.compare_digest`.
- `/health/live` and `/health/ready` are public and return no internal exception details.
- Production docs/OpenAPI are disabled by default; CORS is absent unless exact HTTPS origins are configured.
- The first release runs one replica with managed PostgreSQL and an absolute persistent upload path.
- Existing deterministic behavior remains Golden 59 and Boundary zero with one Alembic head.
- Authentication secrets, database credentials, and real organization IDs never enter Git or logs.
- TDD applies to every Python behavior change: observe RED before production code, then GREEN, then refactor.

---

## File Structure

- `src/controlcheck/settings.py`: parse and validate development/test/production configuration.
- `src/controlcheck/security.py`: build bearer-access and fixed-tenant FastAPI dependencies.
- `src/controlcheck/health.py`: run bounded database, storage, and catalogue readiness checks.
- `src/controlcheck/api.py`: compose settings, middleware, auth dependencies, health routes, and safe errors.
- `src/controlcheck/storage.py`: expose a side-effect-free storage readiness contract.
- `tests/test_production_settings.py`: production configuration contract.
- `tests/test_production_security.py`: authentication, tenant, trusted host, CORS, docs, and error behavior.
- `tests/test_production_health.py`: liveness and readiness behavior.
- `tests/test_production_artifacts.py`: Docker, CI, example environment, runbook, and PRD artifact checks.
- `Dockerfile`: non-root production image.
- `docker/entrypoint.sh`: migrate then start Uvicorn without reload.
- `.dockerignore`: exclude local state, secrets, caches, and validation previews from images.
- `.env.example`: secret-free configuration contract.
- `.github/workflows/ci.yml`: PostgreSQL-backed release gates and Docker build.
- `docs/PRODUCTION_RUNBOOK.md`: staging, deployment, rotation, backup verification, rollback, and incident steps.
- `tools/update_production_documents.py`: generate immutable PRD v0.5 from the approved production scope.
- `docs/ControlCheck_AI_PRD_v0.5.docx`: versioned product requirements update.
- `README.md`: production quick start and security boundary.

---

### Task 1: Production Settings Contract

**Files:**
- Modify: `src/controlcheck/settings.py`
- Create: `tests/test_production_settings.py`
- Modify: `tests/test_phase4_settings.py`

**Interfaces:**
- Produces: `ApplicationSettings.from_env() -> ApplicationSettings`
- Produces fields: `environment: str`, `database_url: str | None`, `upload_root: Path`, `catalogue_path: Path | None`, `organization_id: UUID | None`, `api_key: str | None`, `trusted_hosts: tuple[str, ...]`, `cors_origins: tuple[str, ...]`, `enable_docs: bool`, `max_upload_bytes: int`
- Preserves: `PersistenceSettings.from_env()` for existing callers and tests.

- [ ] **Step 1: Write failing production-setting tests**

```python
def test_production_settings_require_security_boundary(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTROLCHECK_ENV", "production")
    monkeypatch.setenv("CONTROLCHECK_DATABASE_URL", "postgresql+psycopg://db/app")
    monkeypatch.setenv("CONTROLCHECK_UPLOAD_ROOT", str(tmp_path.resolve()))
    monkeypatch.delenv("CONTROLCHECK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="CONTROLCHECK_API_KEY"):
        ApplicationSettings.from_env()


def test_production_settings_parse_secure_values(monkeypatch, tmp_path):
    organization_id = UUID("11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("CONTROLCHECK_ENV", "production")
    monkeypatch.setenv("CONTROLCHECK_DATABASE_URL", "postgresql+psycopg://db/app")
    monkeypatch.setenv("CONTROLCHECK_UPLOAD_ROOT", str(tmp_path.resolve()))
    monkeypatch.setenv("CONTROLCHECK_ORGANIZATION_ID", str(organization_id))
    monkeypatch.setenv("CONTROLCHECK_API_KEY", "k" * 32)
    monkeypatch.setenv("CONTROLCHECK_TRUSTED_HOSTS", "api.example.com")
    settings = ApplicationSettings.from_env()
    assert settings.organization_id == organization_id
    assert settings.trusted_hosts == ("api.example.com",)
    assert settings.enable_docs is False
```

- [ ] **Step 2: Run settings tests and verify RED**

Run: `python -m pytest -q tests/test_production_settings.py -p no:cacheprovider`

Expected: collection fails because `ApplicationSettings` does not exist.

- [ ] **Step 3: Implement strict parsing**

Add an immutable `ApplicationSettings` dataclass. Parse comma-separated values by stripping entries and rejecting empty/wildcard trusted hosts. Require an absolute upload path, UUID organization, 32-character API key, trusted hosts, database URL, and readable catalogue path in production. Default docs to false only in production; default CORS to an empty tuple; require positive upload bytes.

```python
@dataclass(frozen=True)
class ApplicationSettings:
    environment: str
    database_url: str | None
    upload_root: Path
    catalogue_path: Path | None
    organization_id: UUID | None
    api_key: str | None
    trusted_hosts: tuple[str, ...]
    cors_origins: tuple[str, ...]
    enable_docs: bool
    max_upload_bytes: int

    @property
    def is_production(self) -> bool:
        return self.environment == "production"
```

- [ ] **Step 4: Run focused and compatibility tests**

Run: `python -m pytest -q tests/test_production_settings.py tests/test_phase4_settings.py tests/test_default_app_phase4.py -p no:cacheprovider`

Expected: all pass; existing development persistence behavior remains unchanged.

- [ ] **Step 5: Commit**

```powershell
git add src/controlcheck/settings.py tests/test_production_settings.py tests/test_phase4_settings.py
git commit -m "feat: validate production runtime settings"
```

---

### Task 2: Bearer Authentication and Fixed Tenant

**Files:**
- Create: `src/controlcheck/security.py`
- Modify: `src/controlcheck/api.py`
- Create: `tests/test_production_security.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_persistent_project_api.py`

**Interfaces:**
- Consumes: `ApplicationSettings`
- Produces: `build_access_dependency(settings) -> Callable[..., None]`
- Produces: `build_tenant_dependency(settings) -> Callable[..., TenantContext]`
- Preserves development `X-Organization-ID` behavior outside production.

- [ ] **Step 1: Write failing authentication tests**

```python
def test_production_rejects_missing_and_invalid_bearer_key(production_client):
    missing = production_client.post("/v1/audits")
    invalid = production_client.post(
        "/v1/audits", headers={"Authorization": "Bearer wrong"}
    )
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json()["error"]["code"] == "authentication_required"
    assert missing.headers["www-authenticate"] == "Bearer"


def test_production_tenant_cannot_be_overridden(production_app, configured_org_id):
    dependency = production_app.state.require_tenant
    tenant = dependency(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="k" * 32),
        x_organization_id="22222222-2222-2222-2222-222222222222",
    )
    assert tenant.organization_id == configured_org_id
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest -q tests/test_production_security.py -p no:cacheprovider`

Expected: FAIL because production auth dependencies and app state hooks do not exist.

- [ ] **Step 3: Implement dependencies with standard bearer transport**

Use `HTTPBearer(auto_error=False)`. Missing, malformed, and incorrect keys raise `ControlCheckApplicationError("authentication_required", "Authentication is required", 401)`. Compare credentials with `secrets.compare_digest`. Production tenant context always uses `settings.organization_id`; development continues parsing `X-Organization-ID`.

Attach the access dependency to `/v1/audits`. Replace the nested durable-route tenant dependency with `build_tenant_dependency(settings)`. Store dependencies on `application.state` only to permit direct contract tests.

- [ ] **Step 4: Enumerate routes in the test and assert every `/v1` route is protected**

```python
def test_every_v1_route_declares_access_or_tenant_dependency(production_app):
    unprotected = []
    for route in production_app.routes:
        if getattr(route, "path", "").startswith("/v1/") and not route.dependant.dependencies:
            unprotected.append(route.path)
    assert unprotected == []
```

- [ ] **Step 5: Run auth and API regression tests**

Run: `python -m pytest -q tests/test_production_security.py tests/test_api.py tests/test_persistent_project_api.py tests/test_snapshot_api.py -p no:cacheprovider`

Expected: all pass in production and development modes.

- [ ] **Step 6: Commit**

```powershell
git add src/controlcheck/security.py src/controlcheck/api.py tests/test_production_security.py tests/test_api.py tests/test_persistent_project_api.py
git commit -m "feat: protect production api with bearer key"
```

---

### Task 3: Production HTTP Guardrails and Safe Errors

**Files:**
- Modify: `src/controlcheck/api.py`
- Modify: `src/controlcheck/errors.py`
- Modify: `tests/test_production_security.py`

**Interfaces:**
- Consumes: `ApplicationSettings.trusted_hosts`, `cors_origins`, and `enable_docs`.
- Produces: validated `X-Request-ID` response header and generic `internal_server_error` envelope.

- [ ] **Step 1: Add failing middleware tests**

```python
def test_production_disables_docs_and_rejects_unknown_host(production_client):
    assert production_client.get("/docs").status_code == 404
    assert production_client.get("/openapi.json").status_code == 404
    response = production_client.get(
        "/health/live", headers={"Host": "attacker.example"}
    )
    assert response.status_code == 400


def test_unhandled_error_is_generic_and_has_safe_request_id(production_client, monkeypatch):
    response = production_client.get(
        "/test/unhandled",
        headers={"X-Request-ID": "bad id with spaces"},
    )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_server_error"
    assert "traceback" not in response.text.lower()
    UUID(response.headers["X-Request-ID"])
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest -q tests/test_production_security.py -p no:cacheprovider`

Expected: docs remain available, unknown hosts are accepted, or the unhandled error escapes the generic envelope.

- [ ] **Step 3: Add secure middleware and exception behavior**

Construct FastAPI with `docs_url`, `redoc_url`, and `openapi_url` derived from settings. Add `TrustedHostMiddleware` only in production. Add `CORSMiddleware` only when exact configured origins exist and use `allow_credentials=False`. Accept request IDs only when they match `^[A-Za-z0-9._-]{1,128}$`; otherwise generate UUID4.

Register an `Exception` handler in production that logs the exception with request ID and returns only:

```json
{"error":{"code":"internal_server_error","message":"The request could not be completed","request_id":"<id>"}}
```

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest -q tests/test_production_security.py tests/test_cli_api_v02.py tests/test_persistent_query_api.py -p no:cacheprovider`

Expected: all pass; no credentials or stack traces appear in captured output.

- [ ] **Step 5: Commit**

```powershell
git add src/controlcheck/api.py src/controlcheck/errors.py tests/test_production_security.py
git commit -m "feat: add production http guardrails"
```

---

### Task 4: Liveness and Readiness

**Files:**
- Create: `src/controlcheck/health.py`
- Modify: `src/controlcheck/storage.py`
- Modify: `src/controlcheck/api.py`
- Create: `tests/test_production_health.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Produces: `FileStorage.ready() -> bool`
- Produces: `check_readiness(session_factory, storage, catalogue_path) -> bool`
- Produces routes: `GET /health/live`, `GET /health/ready`
- Preserves legacy `GET /health` response during the pilot.

- [ ] **Step 1: Write failing readiness tests**

```python
def test_readiness_returns_minimal_503_when_database_fails(production_client, monkeypatch):
    monkeypatch.setattr("controlcheck.health.database_ready", lambda _: False)
    response = production_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "database" not in response.text.lower()


def test_local_storage_ready_requires_writable_root(tmp_path):
    storage = LocalFileStorage(tmp_path)
    assert storage.ready() is True
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest -q tests/test_production_health.py -p no:cacheprovider`

Expected: FAIL because readiness routes and `ready()` do not exist.

- [ ] **Step 3: Implement bounded dependency checks**

Use SQLAlchemy `select(1)` inside a short session for database readiness. `LocalFileStorage.ready()` creates the configured root when absent, verifies it is a directory, and uses `os.access(root, os.W_OK)`; it never writes or deletes a probe object. Catalogue readiness requires `is_file()` and read access.

Return only `{"status":"ready"}` or `{"status":"not_ready"}`. Catch dependency exceptions inside the readiness function and log at warning level without returning details.

- [ ] **Step 4: Run health, storage, and API tests**

Run: `python -m pytest -q tests/test_production_health.py tests/test_storage.py tests/test_api.py -p no:cacheprovider`

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/controlcheck/health.py src/controlcheck/storage.py src/controlcheck/api.py tests/test_production_health.py tests/test_api.py
git commit -m "feat: add production readiness checks"
```

---

### Task 5: Non-Root Production Container

**Files:**
- Create: `Dockerfile`
- Create: `docker/entrypoint.sh`
- Create: `.dockerignore`
- Create: `.env.example`
- Create: `tests/test_production_artifacts.py`

**Interfaces:**
- Container listens on `$PORT`, default `8000`.
- Entrypoint runs `alembic upgrade head` then `uvicorn controlcheck.api:app --app-dir src --host 0.0.0.0 --port "$PORT"`.

- [ ] **Step 1: Write failing artifact tests**

```python
def test_dockerfile_runs_as_non_root_and_has_no_reload(project_root):
    dockerfile = (project_root / "Dockerfile").read_text(encoding="utf-8")
    assert "USER controlcheck" in dockerfile
    assert "--reload" not in dockerfile
    assert "HEALTHCHECK" in dockerfile


def test_example_environment_contains_placeholders_not_secrets(project_root):
    example = (project_root / ".env.example").read_text(encoding="utf-8")
    assert "CONTROLCHECK_API_KEY=<generate-a-random-32-plus-character-secret>" in example
    assert "postgresql+psycopg://controlcheck:controlcheck" not in example
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest -q tests/test_production_artifacts.py -p no:cacheprovider`

Expected: FAIL because production artifacts do not exist.

- [ ] **Step 3: Create the image and startup contract**

Use `python:3.11.9-slim-bookworm`. Create UID/GID 10001, install the project, copy `src`, `alembic`, `data`, and entrypoint, then set `USER controlcheck`. The entrypoint contains `set -eu`, runs Alembic once, and uses `exec uvicorn` without reload. The Docker health check calls `/health/live` using Python stdlib so curl is not required.

Exclude `.git`, `.env`, `var`, caches, worktrees, result outputs, validation previews, and local PostgreSQL data in `.dockerignore`.

- [ ] **Step 4: Run artifact tests and build image**

Run: `python -m pytest -q tests/test_production_artifacts.py -p no:cacheprovider`

Run: `docker build -t controlcheck-core:production .`

Expected: tests pass and image builds successfully. If Docker is unavailable, record the build as an explicit release blocker; do not mark Task 5 complete.

- [ ] **Step 5: Inspect runtime user**

Run: `docker run --rm --entrypoint id controlcheck-core:production`

Expected: UID is `10001`, not `0`.

- [ ] **Step 6: Commit**

```powershell
git add Dockerfile docker/entrypoint.sh .dockerignore .env.example tests/test_production_artifacts.py
git commit -m "build: add non-root production container"
```

---

### Task 6: CI Release Gates

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `tests/test_production_artifacts.py`

**Interfaces:**
- GitHub Actions job `test` supplies PostgreSQL 16 and runs all Python gates.
- GitHub Actions job `container` builds the Docker image only after `test` succeeds.

- [ ] **Step 1: Extend artifact tests with failing CI assertions**

```python
def test_ci_runs_database_and_deterministic_release_gates(project_root):
    workflow = (project_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for required in (
        "postgres:16-alpine",
        "alembic upgrade head",
        "alembic check",
        "python -m pytest",
        "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
        "ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx",
        "docker build",
    ):
        assert required in workflow
```

- [ ] **Step 2: Run test and verify RED**

Run: `python -m pytest -q tests/test_production_artifacts.py::test_ci_runs_database_and_deterministic_release_gates -p no:cacheprovider`

Expected: FAIL because the workflow is absent.

- [ ] **Step 3: Create least-privilege workflow**

Set `permissions: contents: read`. Use Python 3.11, PostgreSQL 16 service, dependency cache keyed by `uv.lock`, and no production secrets. Run compile, migrations, `alembic check`, full pytest, strict Golden evaluation, strict Boundary evaluation, and Docker build. Do not use `pull_request_target`.

- [ ] **Step 4: Run artifact tests and parse workflow**

Run: `python -m pytest -q tests/test_production_artifacts.py -p no:cacheprovider`

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))"`

Expected: tests pass and YAML parses. Add `PyYAML` only to the dev dependency group if it is not already available.

- [ ] **Step 5: Commit**

```powershell
git add .github/workflows/ci.yml tests/test_production_artifacts.py pyproject.toml uv.lock
git commit -m "ci: enforce production release gates"
```

---

### Task 7: Runbook, README, and PRD v0.5

**Files:**
- Create: `docs/PRODUCTION_RUNBOOK.md`
- Modify: `README.md`
- Create: `tools/update_production_documents.py`
- Create: `docs/ControlCheck_AI_PRD_v0.5.docx`
- Modify: `docs/README.md`
- Modify: `tests/test_production_artifacts.py`

**Interfaces:**
- Documents the exact settings and one-replica production boundary from the approved spec.
- PRD v0.5 is generated without mutating historical PRDs.

- [ ] **Step 1: Add failing documentation contract tests**

```python
def test_runbook_covers_required_operations(project_root):
    runbook = (project_root / "docs" / "PRODUCTION_RUNBOOK.md").read_text(encoding="utf-8")
    for topic in (
        "Deployment",
        "Alembic migrations",
        "API key rotation",
        "Backup verification",
        "Rollback",
        "Incident diagnostics",
        "single replica",
    ):
        assert topic in runbook


def test_production_prd_is_versioned(project_root):
    path = project_root / "docs" / "ControlCheck_AI_PRD_v0.5.docx"
    assert path.exists() and path.stat().st_size > 0
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest -q tests/test_production_artifacts.py -p no:cacheprovider`

Expected: FAIL because runbook and PRD v0.5 are absent.

- [ ] **Step 3: Write operational documentation**

The runbook contains exact staging and production environment variable names, provider prerequisites, migration command, health checks, controlled Golden/Boundary smoke tests, key rotation procedure, backup restore-verification checklist, previous-image rollback, and request-ID incident lookup. It states that one replica and persistent disk are mandatory for the pilot.

README adds a production section that links the runbook and clearly labels `X-Organization-ID` as development-only.

- [ ] **Step 4: Generate PRD v0.5 using the documents skill**

Before document authoring, invoke the documents skill's artifact-operation marker. Generate v0.5 as a new file and record: internal single-organization pilot, bearer API key, fixed tenant, production health endpoints, container/CI gates, persistent storage, managed PostgreSQL, and explicit JWT/RBAC/S3/frontend deferrals.

- [ ] **Step 5: Render and inspect every PRD page**

Run the documents skill `render_docx.py` into `validation/previews/production-docs/prd-v0.5/`. Inspect every PNG page for clipping, overlap, broken lists, and unreadable tables. If LibreOffice is unavailable, record visual QA as a release blocker rather than silently skipping it.

- [ ] **Step 6: Run documentation tests**

Run: `python -m pytest -q tests/test_production_artifacts.py tests/test_phase4b_documents.py -p no:cacheprovider`

Expected: all pass and historical document checks remain green.

- [ ] **Step 7: Commit**

```powershell
git add README.md docs/README.md docs/PRODUCTION_RUNBOOK.md docs/ControlCheck_AI_PRD_v0.5.docx tools/update_production_documents.py tests/test_production_artifacts.py validation/previews/production-docs
git commit -m "docs: publish internal production runbook"
```

---

### Task 8: Final Release Verification and Handoff

**Files:**
- Modify only if a release gate exposes a defect; every defect begins with a failing regression test.

**Interfaces:**
- Produces a clean `codex/production-hardening` branch ready for review in `ControlCheck-AI-Core`.

- [ ] **Step 1: Run static and migration gates**

Run: `python -m compileall -q src`

Run: `alembic heads`

Expected: compilation succeeds and exactly `20260818_0002 (head)` is printed unless this plan intentionally adds one linear successor migration.

Run: `alembic check`

Expected: `No new upgrade operations detected.`

- [ ] **Step 2: Run the complete test suite**

Run: `python -m pytest -q -p no:cacheprovider`

Expected: all existing and new tests pass with no collection errors.

- [ ] **Step 3: Re-run deterministic release fixtures**

Run: `controlcheck evaluate data/ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx --catalogue data/controlcheck_rule_catalogue_v0.2.json --ground-truth data/controlcheck_golden_expected_findings_v0.2.json --output results/production_golden_evaluation.json --strict`

Expected: 59 true positives, zero false positives, zero false negatives, precision 100%, recall 100%.

Run: `controlcheck evaluate data/ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx --catalogue data/controlcheck_rule_catalogue_v0.2.json --ground-truth data/controlcheck_boundary_expected_findings_v0.2.json --output results/production_boundary_evaluation.json --strict`

Expected: zero findings and strict gate success.

- [ ] **Step 4: Build and smoke-test the container**

Run: `docker build -t controlcheck-core:production .`

Start PostgreSQL, provide generated local-only test secrets, mount a temporary upload directory, run the container, then assert `/health/live` is 200, `/health/ready` is 200, `/v1/audits` is 401 without a key, and production `/docs` is 404. Stop the container after verification.

- [ ] **Step 5: Review repository diff and secret scan**

Run: `git diff --check phase4b/main...HEAD`

Run: `rg -n "(CONTROLCHECK_API_KEY=.{32}|postgresql[^ ]*:[^ ]*@|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)" --glob '!*.docx' --glob '!uv.lock' .`

Expected: no committed secrets; example placeholders may be allowlisted only when they cannot authenticate.

- [ ] **Step 6: Push the review branch**

```powershell
git status --short
git push -u phase4b codex/production-hardening
```

Expected: clean working tree and a remote review branch. Do not merge to `main` until CI and human review pass.
