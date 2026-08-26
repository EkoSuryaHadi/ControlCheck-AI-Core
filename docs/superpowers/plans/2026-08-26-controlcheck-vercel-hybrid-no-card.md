# ControlCheck AI Vercel Hybrid No-Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the ControlCheck AI public beta without a payment card by serving the React frontend and FastAPI backend from one Vercel project, with Supabase persistence and private Cloudflare R2 workbook storage.

**Architecture:** Vercel serves static React assets and routes `/api/*` to one Python FastAPI Function. The Function connects through the Supabase IPv4 session pooler, stores original workbooks in private R2, and runs deterministic analysis synchronously with a 4 MiB beta upload limit.

**Tech Stack:** Python 3.11, FastAPI, pandas, openpyxl, SQLAlchemy, psycopg, boto3, React, TypeScript, Vite, Vitest/Node test runner, pytest, Vercel Functions, Supabase PostgreSQL, Cloudflare R2.

**Spec:** `docs/superpowers/specs/2026-08-26-controlcheck-vercel-hybrid-no-card-design.md`

## Global Constraints

- Use one existing Vercel project for frontend and `/api`; do not create or depend on a Render service.
- Keep the Python Function bundle below the 500 MB uncompressed limit.
- Enforce a 4 MiB (`4_194_304` byte) workbook limit in both frontend and backend.
- Target at most 240 seconds for synchronous analysis.
- Use the Supabase IPv4 session pooler on port 5432; never run Alembic during Function startup.
- Keep the R2 bucket private and use only bucket-scoped credentials.
- Never commit, print, screenshot, or paste secrets into chat, source, tests, documentation, or logs.
- Use exact production origins and trusted hosts; wildcard production values remain forbidden.
- Production must fail closed when the database, JWT secret, or durable object storage is missing.
- Full authentication/RBAC hardening, payments, enterprise SSO, background queues, and files larger than 4 MiB remain out of scope.
- Update the PRD and runbook whenever the active deployment topology changes.
- Do not merge to the default branch until hosted register-to-findings verification passes and the user explicitly approves the merge.

---

### Task 1: Restore the Vercel FastAPI function and same-origin routing

**Files:**
- Modify: `vercel.json`
- Modify: `.vercelignore`
- Modify: `requirements.txt`
- Verify: `api/index.py`
- Modify: `frontend/src/lib/api-base-url.js`
- Modify: `frontend/src/lib/api-base-url.test.mjs`
- Delete: `tests/test_vercel_frontend_hosting.py`
- Create: `tests/test_vercel_hybrid_hosting.py`
- Create: `tests/test_vercel_python_packaging.py`

**Interfaces:**
- Consumes: canonical ASGI application `controlcheck.asgi:app` and wrapper `api.index:app`.
- Produces: same-origin public API prefix `/api`, Vercel route `/api/(.*) -> /api/index.py`, and an installable local package through `requirements.txt` entry `.`.

- [ ] **Step 1: Write failing hybrid-hosting tests**

Replace the frontend-only assertions with:

```python
def _git_check_ignore(tmp_path: Path, paths: list[str]) -> set[str]:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / ".gitignore").write_text(
        (ROOT / ".vercelignore").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "--quiet"], cwd=bundle, check=True)
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=bundle,
        input="\n".join(paths),
        capture_output=True,
        text=True,
        check=False,
    )
    return set(result.stdout.splitlines())


def test_vercel_routes_api_before_spa_fallback() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["routes"] == [
        {"src": "/api/(.*)", "dest": "/api/index.py"},
        {"handle": "filesystem"},
        {"src": "/(.*)", "dest": "/index.html"},
    ]
    assert "api/index.py" in config["functions"]


def test_vercel_keeps_python_entrypoint_and_project_metadata(tmp_path: Path) -> None:
    ignored = _git_check_ignore(
        tmp_path,
        ["api/index.py", "pyproject.toml", "data/controlcheck_rule_catalogue_v0.2.json"],
    )
    assert ignored == set()
```

Restore packaging coverage:

```python
def _requirements(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_vercel_requirements_install_controlcheck_project() -> None:
    requirements = _requirements(ROOT / "requirements.txt")
    assert "." in requirements


def test_vercel_excludes_non_runtime_assets() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    excluded = config["functions"]["api/index.py"]["excludeFiles"]
    for pattern in ("frontend/**", "tests/**", "docs/**", "validation/**", "build/**"):
        assert pattern in excluded
```

- [ ] **Step 2: Run the focused tests and verify the frontend-only configuration fails**

Run:

```powershell
.\.venv\Scripts\pytest.exe tests\test_vercel_hybrid_hosting.py tests\test_vercel_python_packaging.py -q
```

Expected: Python tests fail because `vercel.json` has no Function route, `.vercelignore` excludes `api/` and `pyproject.toml`, and `requirements.txt` lacks `.`. Run the frontend test separately with Node:

```powershell
node --test frontend\src\lib\api-base-url.test.mjs
```

- [ ] **Step 3: Restore the minimal hybrid Vercel configuration**

Use this route order and exclusion contract:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "api/index.py": {
      "maxDuration": 240,
      "excludeFiles": "{frontend/**,tests/**,docs/**,results/**,validation/**,tools/**,docker/**,build/**,.venv/**,alembic/**,data/*.xlsx,data/*.inspect.ndjson,data/*expected_findings*.json}"
    }
  },
  "routes": [
    { "src": "/api/(.*)", "dest": "/api/index.py" },
    { "handle": "filesystem" },
    { "src": "/(.*)", "dest": "/index.html" }
  ]
}
```

Remove `api/`, `pyproject.toml`, and the runtime JSON catalogue/profile from `.vercelignore`. Add the local package to `requirements.txt`:

```text
boto3>=1.35
.
```

Keep the frontend default same-origin:

```javascript
export function resolveApiBaseUrl(viteApiBaseUrl) {
  const configured = viteApiBaseUrl?.trim()
  return configured || "/api"
}
```

- [ ] **Step 4: Verify the ASGI prefix wrapper and focused tests**

Run:

```powershell
.\.venv\Scripts\pytest.exe tests\test_serverless_entrypoint.py tests\test_asgi_entrypoint.py tests\test_vercel_hybrid_hosting.py tests\test_vercel_python_packaging.py -q
node --test frontend\src\lib\api-base-url.test.mjs
```

Expected: all tests pass; `/api/health` dispatches to `/health`, startup failures propagate, and packaging keeps Python metadata.

- [ ] **Step 5: Commit Task 1**

```powershell
git add vercel.json .vercelignore requirements.txt api/index.py frontend/src/lib/api-base-url.js frontend/src/lib/api-base-url.test.mjs tests/test_vercel_hybrid_hosting.py tests/test_vercel_python_packaging.py
git add -u tests/test_vercel_frontend_hosting.py
git commit -m "feat: restore Vercel hybrid FastAPI hosting"
```

---

### Task 2: Enforce the 4 MiB beta workbook boundary

**Files:**
- Create: `src/controlcheck/limits.py`
- Modify: `src/controlcheck/api.py`
- Modify: `src/controlcheck/settings.py`
- Modify: `.env.production.example`
- Create: `frontend/src/lib/upload-limits.js`
- Create: `frontend/src/lib/upload-limits.d.ts`
- Create: `frontend/src/lib/upload-limits.test.mjs`
- Modify: `frontend/src/pages/data/DataImportWizard.tsx`
- Modify: `tests/test_api.py`
- Modify: `tests/test_production_configuration.py`

**Interfaces:**
- Consumes: upload routes created by `create_app(..., max_upload_bytes=...)` and frontend `File` objects.
- Produces: Python constant `PUBLIC_BETA_MAX_UPLOAD_BYTES: int = 4_194_304`, JavaScript export `PUBLIC_BETA_MAX_UPLOAD_BYTES`, and `validatePublicBetaUpload(file)` returning `null | string`.

- [ ] **Step 1: Write failing backend limit tests**

Add:

```python
from controlcheck.limits import PUBLIC_BETA_MAX_UPLOAD_BYTES


def test_public_beta_upload_limit_is_four_mib() -> None:
    assert PUBLIC_BETA_MAX_UPLOAD_BYTES == 4 * 1024 * 1024


def test_production_settings_default_to_public_beta_upload_limit(monkeypatch) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.delenv("CONTROLCHECK_MAX_UPLOAD_BYTES", raising=False)
    assert ProductionSettings.from_env().max_upload_bytes == PUBLIC_BETA_MAX_UPLOAD_BYTES
```

Keep an API boundary test that sends `limit + 1` bytes and asserts:

```python
assert response.status_code == 413
assert response.json()["detail"]["code"] == "file_too_large"
assert response.json()["detail"]["max_bytes"] == PUBLIC_BETA_MAX_UPLOAD_BYTES
```

- [ ] **Step 2: Write failing frontend limit tests**

Create:

```javascript
import test from "node:test"
import assert from "node:assert/strict"
import { PUBLIC_BETA_MAX_UPLOAD_BYTES, validatePublicBetaUpload } from "./upload-limits.js"

test("public beta upload limit is 4 MiB", () => {
  assert.equal(PUBLIC_BETA_MAX_UPLOAD_BYTES, 4 * 1024 * 1024)
})

test("oversized workbook has actionable copy", () => {
  const error = validatePublicBetaUpload({ name: "large.xlsx", size: PUBLIC_BETA_MAX_UPLOAD_BYTES + 1 })
  assert.match(error, /4 MB public beta limit/i)
})

test("workbook at the boundary is accepted", () => {
  assert.equal(validatePublicBetaUpload({ name: "valid.xlsx", size: PUBLIC_BETA_MAX_UPLOAD_BYTES }), null)
})
```

- [ ] **Step 3: Run tests to verify missing constants and modules fail**

```powershell
.\.venv\Scripts\pytest.exe tests\test_api.py tests\test_production_configuration.py -q
node --test frontend\src\lib\upload-limits.test.mjs
```

Expected: import/module failures or assertions showing the existing 25 MiB limit.

- [ ] **Step 4: Implement one backend source of truth**

Create:

```python
PUBLIC_BETA_MAX_UPLOAD_BYTES = 4 * 1024 * 1024
```

Import the constant in `api.py` and `settings.py`; replace both 25 MiB defaults. Set the production example explicitly:

```dotenv
CONTROLCHECK_MAX_UPLOAD_BYTES=4194304
```

Do not change streaming/read-loop enforcement: every upload path must continue rejecting once accumulated bytes exceed `max_upload_bytes`.

- [ ] **Step 5: Implement frontend validation and copy**

Create:

```javascript
export const PUBLIC_BETA_MAX_UPLOAD_BYTES = 4 * 1024 * 1024

export function validatePublicBetaUpload(file) {
  if (file.size > PUBLIC_BETA_MAX_UPLOAD_BYTES) {
    return "File exceeds the 4 MB public beta limit. Use a smaller workbook for this beta."
  }
  return null
}
```

Import it into `DataImportWizard.tsx`, remove the local 25 MiB constant, compose its result with existing extension validation, and change visible copy to:

```tsx
<p className="mt-1 text-xs text-slate-500">
  Accepted: .xlsx, .xls, .csv · Public beta maximum 4 MB
</p>
```

- [ ] **Step 6: Run focused backend and frontend tests**

```powershell
.\.venv\Scripts\pytest.exe tests\test_api.py tests\test_production_configuration.py tests\test_invalid_workbook_boundaries.py -q
node --test frontend\src\lib\upload-limits.test.mjs frontend\src\lib\api-base-url.test.mjs
npm.cmd --prefix frontend run build
```

Expected: all tests and the TypeScript build pass.

- [ ] **Step 7: Commit Task 2**

```powershell
git add src/controlcheck/limits.py src/controlcheck/api.py src/controlcheck/settings.py .env.production.example frontend/src/lib/upload-limits.js frontend/src/lib/upload-limits.d.ts frontend/src/lib/upload-limits.test.mjs frontend/src/pages/data/DataImportWizard.tsx tests/test_api.py tests/test_production_configuration.py
git commit -m "feat: enforce Vercel beta workbook limit"
```

---

### Task 3: Replace Render documentation and publish PRD v1.2

**Files:**
- Delete: `render.yaml`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/PRODUCTION_RUNBOOK.md`
- Modify: `tools/update_public_beta_documents.py`
- Create: `docs/ControlCheck_AI_PRD_v1.2.docx`
- Modify: `tests/test_public_beta_documents.py`
- Modify: `tests/test_production_configuration.py`

**Interfaces:**
- Consumes: approved design spec and deployed environment contract from Tasks 1–2.
- Produces: deterministic `build_prd() -> Path` targeting PRD v1.2 and documentation that identifies Vercel–Supabase–R2 as the only active beta topology.

- [ ] **Step 1: Use the documents skill before editing the DOCX generator or artifact**

Read the complete documents skill and its required create/edit and render-verification references. Use the bundled workspace Python runtime discovered by the dependency loader. Do not edit the DOCX as an opaque binary.

- [ ] **Step 2: Write failing documentation tests**

Require all active documentation to contain:

```python
required = (
    "Vercel React + FastAPI",
    "Supabase",
    "Cloudflare R2",
    "4 MiB",
    "explicit release step",
    "register/login → create project → upload workbook",
)
```

Require it not to describe Render as active:

```python
for forbidden in (
    "Vercel frontend → Render",
    "Deploy the Render",
    "persist across Render restart",
):
    assert forbidden not in runbook
    assert forbidden not in prd_text

assert not (ROOT / "render.yaml").exists()
```

Add deterministic regeneration coverage:

```python
first = build_prd().read_bytes()
second = build_prd().read_bytes()
assert first == second
assert build_prd().name == "ControlCheck_AI_PRD_v1.2.docx"
```

- [ ] **Step 3: Run documentation tests and verify they fail on the Render topology**

```powershell
.\.venv\Scripts\pytest.exe tests\test_public_beta_documents.py tests\test_production_configuration.py -q
```

Expected: failures mention Render wording, `render.yaml`, PRD v1.1 target, and missing 4 MiB contract.

- [ ] **Step 4: Update the deterministic PRD generator**

Base v1.2 on the immutable v1.1 artifact:

```python
target = DOCS / "ControlCheck_AI_PRD_v1.2.docx"
document = Document(DOCS / "ControlCheck_AI_PRD_v1.1.docx")
_replace(document, "Product Requirements Document v1.1", "Product Requirements Document v1.2")
_replace_table_row(document, "Version", {1: "1.2"})
document.core_properties.title = "Product Requirements Document v1.2"
```

Append a Phase 10 amendment that records:

```text
browser → Vercel React frontend → Vercel FastAPI Function → Supabase PostgreSQL + private Cloudflare R2
```

Include the 4 MiB boundary, 240-second target, 500 MB bundle limit, explicit migration release step, fail-closed storage/database behavior, no-card reason, and future direct-to-R2 upload path. Preserve fixed ZIP timestamps and member ordering.

- [ ] **Step 5: Update Markdown operations documentation and remove Render manifest**

Document this deployment order exactly:

```text
1. Apply Supabase migrations explicitly.
2. Create private R2 bucket and scoped credentials.
3. Configure Vercel production/preview secrets.
4. Deploy the hybrid Vercel project.
5. Verify readiness and register-to-findings persistence.
```

Remove active Render instructions and delete `render.yaml`. Keep historical plan/spec files immutable; they are decision history, not current operations.

- [ ] **Step 6: Generate, render, and inspect PRD v1.2**

Run with the bundled workspace Python:

```powershell
& 'C:\Users\USER\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\update_public_beta_documents.py
```

Render the DOCX with the canonical renderer. If LibreOffice is unavailable, use the documented fallback renderer, record that exception, and inspect every rendered page for clipping, overlaps, broken tables, blank pages, and incorrect version text.

- [ ] **Step 7: Run documentation and determinism tests**

```powershell
.\.venv\Scripts\pytest.exe tests\test_public_beta_documents.py tests\test_production_configuration.py tests\test_phase9_documents.py -q
git diff --check
```

Expected: all pass; two regenerations of PRD v1.2 are byte-identical.

- [ ] **Step 8: Commit Task 3**

```powershell
git add README.md docs/README.md docs/PRODUCTION_RUNBOOK.md tools/update_public_beta_documents.py docs/ControlCheck_AI_PRD_v1.2.docx tests/test_public_beta_documents.py tests/test_production_configuration.py
git add -u render.yaml
git commit -m "docs: adopt Vercel hybrid public beta"
```

---

### Task 4: Complete local release verification

**Files:**
- Modify only if failures expose defects in Tasks 1–3.
- Record: `.superpowers/sdd/2026-08-26-controlcheck-vercel-hybrid-no-card/progress.md` (ignored coordination ledger).

**Interfaces:**
- Consumes: hybrid routing, 4 MiB limit, production configuration, and current Supabase/R2 adapters.
- Produces: a release candidate commit with passing Python, frontend, packaging, security, and documentation checks.

- [ ] **Step 1: Run the complete Python suite**

```powershell
.\.venv\Scripts\pytest.exe -q
```

Expected: zero failures. Treat skipped PostgreSQL integration tests as acceptable only when they explicitly require a live test database; do not suppress new failures.

- [ ] **Step 2: Run frontend tests, lint, and production build**

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Expected: tests and build pass; existing documented lint warnings may remain, but no lint errors are accepted.

- [ ] **Step 3: Inspect runtime dependency size**

Build an isolated install target using the locked project metadata, then measure it:

```powershell
$bundleProbe = Join-Path $env:TEMP 'controlcheck-vercel-bundle-probe'
New-Item -ItemType Directory -Force -Path $bundleProbe | Out-Null
.\.venv\Scripts\python.exe -m pip install --no-cache-dir --target $bundleProbe .
$bundleBytes = (Get-ChildItem -LiteralPath $bundleProbe -Recurse -File | Measure-Object Length -Sum).Sum
[math]::Round($bundleBytes / 1MB, 2)
```

Expected: measured runtime dependencies and application files remain below 500 MB. Preserve the measurement in the ignored progress ledger, not a committed generated bundle.

- [ ] **Step 4: Run security and production readiness tests**

```powershell
.\.venv\Scripts\pytest.exe tests\test_production_configuration.py tests\test_production_readiness.py tests\test_serverless_entrypoint.py tests\test_storage.py tests\test_structured_logging.py -q
```

Expected: production fails closed with missing secrets, local serverless storage is rejected, and S3 readiness failures are safe.

- [ ] **Step 5: Confirm the release-candidate diff is scoped**

```powershell
git status --short
git diff --check HEAD~3..HEAD
git log --oneline -6
```

Expected: only intended source, configuration, tests, and documentation are tracked. The existing untracked `build/` directory remains untouched and uncommitted.

---

### Task 5: Provision private R2 and configure Vercel secrets

**Files:**
- No repository files.
- Record only non-secret resource names and verification outcomes in the ignored progress ledger.

**Interfaces:**
- Consumes: bucket name `controlcheck-beta-workbooks`, Supabase session-pooler endpoint, and Vercel environment contract.
- Produces: private R2 bucket, bucket-scoped credentials, and Vercel Production/Preview environment variables.

- [ ] **Step 1: Reconfirm the migrated Supabase boundary**

Run this read-only query in the existing Supabase project:

```sql
select
  (select version_num from alembic_version) as schema_version,
  count(*) filter (where c.relname <> 'alembic_version') as application_tables,
  count(*) filter (
    where c.relname <> 'alembic_version' and c.relrowsecurity
  ) as rls_enabled_tables
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r';
```

Expected: schema `20260825_0011`, 42 application tables, and 42 RLS-enabled application tables. This is verification only; do not rerun already-applied migrations.

- [ ] **Step 2: Confirm before creating the R2 bucket**

At the final Cloudflare create action, ask the user to confirm creation of:

```text
Bucket: controlcheck-beta-workbooks
Location: automatic
Public access: disabled
```

Create only after confirmation, then verify the bucket is private.

- [ ] **Step 3: Confirm before creating persistent R2 credentials**

At the final token creation action, ask the user to confirm a bucket-scoped read/write token. Scope it only to `controlcheck-beta-workbooks`. The user handles any sensitive credential display directly; do not read, capture, log, or repeat the secret.

- [ ] **Step 4: Reuse or set the Supabase pooler secret**

Construct the SQLAlchemy URI in the provider form from these exact non-secret fields and the database password entered directly by the user:

```text
scheme: postgresql+psycopg
user: postgres.ntpeaayhbtlccoeiipmx
host: aws-0-ap-northeast-2.pooler.supabase.com
port: 5432
database: postgres
```

If an existing Vercel database secret already targets this pooler, reuse it without revealing its value. If the password is unavailable, ask for confirmation before resetting it; the user enters the new password directly into provider forms.

- [ ] **Step 5: Configure Vercel Production and Preview variables**

Set these exact non-secret values:

```text
CONTROLCHECK_ENV=production
CONTROLCHECK_STORAGE_BACKEND=s3
CONTROLCHECK_S3_BUCKET=controlcheck-beta-workbooks
CONTROLCHECK_S3_REGION=auto
CONTROLCHECK_MAX_UPLOAD_BYTES=4194304
CONTROLCHECK_CORS_ORIGINS=https://control-check-ai-git-codex-public-8a91d7-ekosuryahadis-projects.vercel.app
CONTROLCHECK_TRUSTED_HOSTS=control-check-ai-git-codex-public-8a91d7-ekosuryahadis-projects.vercel.app
```

Set these as secrets without exposing values:

```text
CONTROLCHECK_DATABASE_URL
CONTROLCHECK_JWT_SECRET
CONTROLCHECK_S3_ENDPOINT_URL
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

Do not define `VITE_API_BASE_URL`; the frontend must use same-origin `/api`.

- [ ] **Step 6: Verify environment names and scopes without reading values**

Confirm every required key exists in Production and the approved Preview scope. Confirm there are no Render hostnames, wildcard CORS values, public R2 URLs, or browser-exposed secret prefixes.

---

### Task 6: Deploy and verify the hosted register-to-findings flow

**Files:**
- Modify only if hosted verification exposes a reproducible defect.
- Update: `.superpowers/sdd/2026-08-26-controlcheck-vercel-hybrid-no-card/progress.md` with non-secret evidence.

**Interfaces:**
- Consumes: verified release candidate and configured cloud resources.
- Produces: a hosted public beta whose static UI and `/api` share one Vercel origin.

- [ ] **Step 1: Push the release branch to the canonical repository**

```powershell
git push phase4b codex/public-beta-v1
```

Expected: `EkoSuryaHadi/ControlCheck-AI-Core` contains every Task 1–3 commit. Do not merge.

- [ ] **Step 2: Reconnect the existing Vercel project to the canonical repository**

Connect the existing ControlCheck Vercel project to `EkoSuryaHadi/ControlCheck-AI-Core`, select branch `codex/public-beta-v1`, and preserve the established project/domain. Ask for confirmation immediately before the final reconnect/deploy action because it changes the live deployment source.

- [ ] **Step 3: Deploy the hybrid preview and inspect build output**

Expected build evidence:

```text
React/Vite static output created
api/index.py detected as one Python Function
Python Function bundle below 500 MB
Deployment status Ready
```

If deployment fails, capture only non-secret build errors, reproduce locally where possible, fix with TDD, rerun Task 4, commit, push, and redeploy.

- [ ] **Step 4: Verify liveness and readiness**

```text
GET /api/health
Expected: 200 and live status

GET /api/health/ready
Expected: 200, database connected, storage ready
```

No response may include database hosts with passwords, R2 credentials, JWT secrets, stack traces, or environment dumps.

- [ ] **Step 5: Run the hosted positive workflow**

Using a new beta test identity:

```text
register/login
→ create organization/workspace
→ create project
→ upload docs/ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx
→ receive a real analysis-run ID
→ open findings and health summary
→ reload and retrieve the same persisted run
```

Expected: upload remains below 4 MiB, workbook object exists privately in R2, and Supabase contains the source, snapshot, run, findings, and evidence.

- [ ] **Step 6: Run hosted negative boundaries**

Verify:

```text
4 MiB + 1 byte workbook → HTTP 413 and actionable 4 MB message
invalid workbook → validation error and no successful run
untrusted Host → rejected
missing/invalid session → unauthorized response
```

Do not intentionally disable the live database or delete credentials. Storage/database failure behavior is covered by isolated tests unless a safe preview-only fault injection already exists.

- [ ] **Step 7: Verify durability across a cold start or redeploy**

After the Function becomes cold or a no-code redeploy completes, retrieve the same project, run, findings, and R2-backed source metadata. Expected: all persisted records remain available and no local filesystem dependency appears.

- [ ] **Step 8: Record release evidence**

Record only:

```text
deployment URL
deployment commit
health/readiness result
test identity identifier without password
analysis-run ID
finding count
R2 object existence result without signed URL
Supabase schema version 20260825_0011
```

- [ ] **Step 9: Verify the rollback path**

Record the prior frontend-only Vercel deployment identifier before promotion. If the hybrid deployment fails its health or data-flow gate, promote that prior deployment without reversing Supabase migrations or deleting R2 objects. Confirm the prior UI loads and report that API functionality remains intentionally unavailable until the hybrid defect is fixed.

- [ ] **Step 10: Request merge approval**

Report hosted evidence, remaining free-tier limitations, the 4 MiB beta boundary, and whether rollback was needed. Ask the user explicitly before merging `codex/public-beta-v1` into the canonical default branch.
