# ControlCheck Core Engine v0.2 / Canonical Ingestion Phase 4B

ControlCheck is a deterministic project-control audit engine for EPC cost, schedule, progress, and data-quality data. It reads versioned Excel datasets, executes 20 catalogue rules, attaches traceable evidence to every finding, and evaluates results against governed ground truth.

No LLM, frontend, or database is used in the core engine.

## Internal production pilot

The production MVP is a single-organization, API-only deployment using one bearer API key, a server-fixed tenant UUID, managed PostgreSQL, a persistent upload volume, and exactly one application replica. Every `/v1/*` route is authenticated in production; `/health/live` and `/health/ready` remain public and minimal. API docs are disabled and CORS is absent by default.

Use [the production runbook](docs/PRODUCTION_RUNBOOK.md) for environment variables, deployment, migrations, API key rotation, backup verification, rollback, and incident handling. Copy `.env.example` only as a placeholder contract; never commit real secrets.

`X-Organization-ID` is a development-only tenant header. Production ignores it and derives the tenant exclusively from `CONTROLCHECK_ORGANIZATION_ID`. JWT, complete RBAC, object storage, multi-replica scaling, frontend, and LLM orchestration remain deferred.

## Phase 4B canonical snapshot workflow

The durable workflow is: governed template upload → immutable dataset snapshot → raw-row lineage and canonical facts → domain validation → gated deterministic analysis → persisted findings/evidence. Snapshot analysis is database-native; the compatibility `/v1/projects/{project_id}/analysis-runs` upload route remains available during migration.

- Ingestion is template-only and preserves source anomalies unchanged.
- Duplicate business IDs remain addressable through `source_key`; raw lineage uses BIGINT IDs.
- `source_project_name` is preserved losslessly on the snapshot.
- Progress above 100% and contradictory actual dates are detected by PRG-002 and DQ-003, not rewritten.
- Partial-domain snapshots execute only rules whose required domains are valid; skipped rules are durable and explicit.
- Authentication and complete RBAC are deferred; `X-Organization-ID` is a controlled development tenant contract.

Golden parity acceptance is 59 findings with exact deterministic payload equality between Excel and database snapshot execution. Boundary acceptance is zero findings.

## v0.2 validation alignment

Validation Alignment v0.2 adds:

- Structured runtime definitions for all 20 rules
- Dataset, catalogue, and ground-truth compatibility preflight
- Exhaustive adjudication of 89 v0.1 actual/expected rule–entity combinations
- Golden Positive and Boundary / Negative workbooks
- Exhaustive v0.2 ground truth with evidence anchors and metric expectations
- Raw and exception-aware evaluation metrics
- Separate severity and metric agreement reporting
- CLI and FastAPI version-mismatch error contracts
- Preserved v0.1 artifacts and SHA-256 manifest

The core changes backed by adjudication are:

- `CST-004` now evaluates at `WBS|VENDOR` grain.
- `CST-005` requires both 25% of WBS budget and 3% of project budget.
- `PRG-003` requires current-period cost of at least 1% of project budget.
- Golden fixture values correct four planted-positive inconsistencies from v0.1.

## Verified controlled-fixture result

| Fixture | Expected | Actual | TP | FP | FN | Precision | Recall | Severity | Metrics |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Golden Positive | 59 | 59 | 59 | 0 | 0 | 100% | 100% | 100% | 100% |
| Boundary / Negative | 0 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 100% |

The boundary workbook contains 50 literal cases across 16 numeric rules. Empty-set precision and recall are 100% when both expected and actual full-engine finding sets are empty.

These results prove agreement on controlled synthetic fixtures. They are **not a customer-accuracy claim** and do not predict performance on unseen projects.

See `results/evaluation_summary_v0.2.md` for the interpretation and historical comparison.

## Requirements and installation

- Python 3.11 or newer

```powershell
python -m pip install -e ".[dev]"
```

## v0.2 artifacts

```text
data/
├── ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx
├── ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx
├── controlcheck_rule_catalogue_v0.2.json
├── controlcheck_golden_expected_findings_v0.2.json
└── controlcheck_boundary_expected_findings_v0.2.json

validation/
├── adjudication_v0.2.csv
├── v01_artifact_hashes.json
└── previews/v0.2/
```

The v0.1 workbook, catalogue, ground truth, findings, evaluation, and checksum records remain unchanged for historical reproducibility.

## CLI

After editable installation, run the Golden Positive fixture:

```powershell
controlcheck run data\ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx `
  --catalogue data\controlcheck_rule_catalogue_v0.2.json `
  --output results\findings_v0.2.json
```

```powershell
controlcheck evaluate data\ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx `
  --catalogue data\controlcheck_rule_catalogue_v0.2.json `
  --ground-truth data\controlcheck_golden_expected_findings_v0.2.json `
  --output results\evaluation_v0.2.json `
  --strict
```

Run the Boundary / Negative fixture:

```powershell
controlcheck evaluate data\ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx `
  --catalogue data\controlcheck_rule_catalogue_v0.2.json `
  --ground-truth data\controlcheck_boundary_expected_findings_v0.2.json `
  --output results\boundary_evaluation_v0.2.json `
  --strict
```

Without installation, add `src` to Python's import path and invoke `controlcheck.cli` with the same arguments.

`--strict` requires precision, recall, severity accuracy, and metric accuracy of 100%, with zero unreviewed labels. Normal evaluation still writes diagnostics when quality gates fail.

## Version compatibility

The engine compares the dataset, catalogue, and ground-truth major/minor versions before executing rules. A mismatch returns `incompatible_artifact_versions` through both CLI and API; rule execution and output writing do not proceed.

## FastAPI

```powershell
$env:CONTROLCHECK_CATALOGUE = "data\controlcheck_rule_catalogue_v0.2.json"
uvicorn controlcheck.api:app --app-dir src --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health`
- `POST /v1/audits` with one `.xlsx` multipart upload

The upload is capped at 25 MiB by default and processed from a bounded in-memory buffer. Incompatible workbook/catalogue versions return HTTP 422 with a structured error code.

## Finding and evaluation contracts

Every finding includes a stable ID, rule and entity identity, severity, deterministic metrics, business impact, recommendation, calculation trace, and at least one evidence item.

Detection matching uses `(rule_id, normalized_entity)`. The v0.2 evaluator reports:

- TP, FP, FN, precision, recall, and F1
- Raw and exception-aware counts
- Approved exceptions without hiding them from raw reporting
- Severity accuracy and mismatches
- Metric accuracy and mismatches
- Unreviewed label count
- Per-rule reconciliation
- Repeated-run determinism

## Development and verification

```powershell
python -m pytest -q -p no:cacheprovider
python -m compileall -q src
```

## PostgreSQL persistence API (Phase 4A)

Start the local PostgreSQL 16 service and apply the executable schema:

```powershell
podman compose up -d postgres
$env:CONTROLCHECK_DATABASE_URL = "postgresql+psycopg://controlcheck:controlcheck@127.0.0.1:54329/controlcheck"
alembic upgrade head
```

Run FastAPI with the validated v0.2 catalogue and local upload storage:

```powershell
$env:CONTROLCHECK_CATALOGUE = "data\controlcheck_rule_catalogue_v0.2.json"
$env:CONTROLCHECK_UPLOAD_ROOT = "var\uploads"
uvicorn controlcheck.api:app --app-dir src --host 127.0.0.1 --port 8000
```

Outside production, durable endpoints require `X-Organization-ID: <uuid>`. This is an explicit development-only tenant context, not authentication. Production uses bearer authentication and the server-fixed organization described in the runbook. Login and complete RBAC are deferred. The primary workflow is project creation followed by `POST /v1/projects/{project_id}/analysis-runs`; run history, findings, evidence, filters, and finding status are then available through the `/v1` resources documented by FastAPI OpenAPI in development.

Rebuild the validation workbooks with the bundled artifact-tool runtime:

```powershell
node tools\build_validation_workbooks.mjs
```

The builder exports both workbooks, inspection logs, and rendered previews for every sheet.

## Package layout

```text
src/controlcheck/
├── loader.py
├── models.py
├── config.py
├── versioning.py
├── ground_truth.py
├── adjudication.py
├── builders.py
├── engine.py
├── evaluation.py
├── service.py
├── cli.py
├── api.py
└── rules/
```
