# ControlCheck Core Engine v0.1

ControlCheck is a deterministic project-control audit engine for EPC cost, schedule, progress, and data-quality data. It reads the supplied synthetic Excel workbook, executes 20 catalogue rules, attaches traceable evidence to every finding, and evaluates the results against the 24-item ground truth.

No LLM, frontend, or database is used.

## What is included

- Typed Excel loader with required-sheet and required-column validation
- Five data-quality rules (`DQ-001`–`DQ-005`)
- Six cost and cost/progress rules (`CST-001`–`CST-006`)
- Five schedule rules (`SCH-001`–`SCH-005`)
- Three progress/cross-domain rules (`PRG-001`–`PRG-003`)
- One integrated cost/schedule rule (`XDOM-001`)
- Evidence-enforcing finding builder and stable finding IDs
- Deterministic registry and JSON output
- Ground-truth evaluator with TP, FP, FN, precision, recall, F1, per-rule results, and severity comparison
- Typer CLI and minimal FastAPI upload wrapper
- Automated test suite

## Requirements

- Python 3.11 or newer

Install in a virtual environment:

```powershell
python -m pip install -e ".[dev]"
```

## Input artifacts

The commands use:

- `ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx`
- `controlcheck_rule_catalogue_v0.1.json`
- `controlcheck_expected_findings_v0.1.json`

Put them in `data/`, or pass their existing absolute paths to the CLI. The source artifacts used for this evaluation were found in `C:\Users\USER\Downloads`.

## CLI

After editable installation:

```powershell
controlcheck run data\ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx `
  --catalogue data\controlcheck_rule_catalogue_v0.1.json `
  --output results\findings_v0.1.json
```

```powershell
controlcheck evaluate data\ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx `
  --catalogue data\controlcheck_rule_catalogue_v0.1.json `
  --ground-truth data\controlcheck_expected_findings_v0.1.json `
  --output results\evaluation_v0.1.json
```

Without installation, set `PYTHONPATH=src` and run `python -m controlcheck.cli` with the same subcommands.

Use `--strict` on `evaluate` when CI must fail unless both precision and recall equal `1.0`. Normal evaluation exits successfully even when labels disagree, so the diagnostic JSON is always produced.

## FastAPI

Set the catalogue path and start the app:

```powershell
$env:CONTROLCHECK_CATALOGUE = "data\controlcheck_rule_catalogue_v0.1.json"
uvicorn controlcheck.api:app --app-dir src --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health`
- `POST /v1/audits` with one `.xlsx` multipart upload

The upload is capped at 25 MiB by default and processed from a bounded in-memory buffer.

## Finding contract

Every finding includes:

- Stable finding, rule, project, and entity identifiers
- Category, severity, deterministic description, metrics, impact, and recommendation
- At least one evidence item with source sheet, row numbers, record IDs, and relevant values
- Calculation trace with formula, operands/thresholds, and result

The builder rejects a finding with no evidence.

## Evaluation identity

Detection matching uses `(rule_id, normalized_entity)`. Composite entities such as `ACT-9001/ACT-9002` are order-independent. Severity is deliberately evaluated separately because some supplied severity labels conflict with the catalogue defaults.

## Verified baseline result

Using the catalogue literally against the supplied workbook:

- Expected labels: 24
- Unique actual findings: 85
- True positives: 20
- False positives: 65
- False negatives: 4
- Precision: 0.2353
- Recall: 0.8333
- F1: 0.3670
- Deterministic repeated run: yes

The large FP count is primarily caused by the ground truth selecting only planted examples while catalogue thresholds also match many unlabelled records. For example, `CST-005` says a transaction at or above 5% of WBS budget is material; many ordinary synthetic transactions cross that threshold, but only `ACT-9006` is labelled. The engine does not suppress catalogue-valid findings merely to improve the test score.

The four false negatives are:

- `CST-001 / 3.1`: workbook actual is below its budget.
- `CST-001 / 3.2`: workbook actual is below its budget.
- `CST-002 / 3.3`: actual plus outstanding (committed minus invoiced) is below the catalogue condition under the workbook values.
- `PRG-003 / 3.1`: latest progress increases by 3 percentage points, above the catalogue maximum of 2 points.

See `results/evaluation_v0.1.json` for the complete FP/FN and per-rule lists.

## Tests

```powershell
python -m pytest -q -p no:cacheprovider
python -m compileall -q src
```

The suite covers loader validation, evidence invariants, deterministic ordering, all 20 rules, threshold boundaries, evaluator matching, CLI workflows, API uploads, and the supplied-artifact regression.

## Package layout

```text
src/controlcheck/
├── loader.py
├── models.py
├── config.py
├── builders.py
├── engine.py
├── evaluation.py
├── service.py
├── cli.py
├── api.py
└── rules/
```
