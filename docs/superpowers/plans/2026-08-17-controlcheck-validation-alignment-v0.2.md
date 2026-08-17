# ControlCheck Validation Alignment v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a fully adjudicated, versioned validation baseline where the 20 deterministic rules, structured catalogue, two v0.2 workbooks, ground truth, evaluator, and PRD agree exactly.

**Architecture:** A version-aware schema layer validates catalogue/dataset/ground-truth compatibility before execution. Adjudication decisions define the structured v0.2 rules; independently authored positive and boundary fixtures validate those rules, while the unchanged v0.1 artifacts remain a historical regression baseline.

**Tech Stack:** Python 3.11+, Pydantic 2, openpyxl for engine ingestion, `@oai/artifact-tool` for workbook authoring, pytest, Typer, FastAPI, python-docx/OOXML helpers, LibreOffice render QA

## Global Constraints

- Production rules may not branch on synthetic entity IDs.
- Every finding must include evidence and a calculation trace.
- Every evaluated v0.2 condition must be labelled or represented as an approved exception.
- v0.1 workbook, catalogue, ground truth, and results remain unchanged.
- Rule runtime behavior comes from structured fields, never parsed prose.
- Controlled-fixture targets are 100% precision, recall, severity agreement, and expected boundary behavior.
- Controlled-fixture scores are not customer-accuracy claims.
- Any accepted product behavior change must appear in `ControlCheck_AI_PRD_v0.2.docx` and its change log.
- Final project state and deliverables live under `D:\Projects\ControlCheck-AI`.

## File Map

- `src/controlcheck/versioning.py`: version identifiers and compatibility checks.
- `src/controlcheck/config.py`: v0.1-compatible and structured v0.2 catalogue models.
- `src/controlcheck/models.py`: dataset-version metadata and approved-exception models.
- `src/controlcheck/loader.py`: reads dataset version from `Project_Info`.
- `src/controlcheck/ground_truth.py`: v0.2 ground-truth schema and validation.
- `src/controlcheck/adjudication.py`: inventory and decision-matrix validation.
- `src/controlcheck/engine.py`: compatibility preflight and exception-aware execution.
- `src/controlcheck/evaluation.py`: severity, metric, exception, and unreviewed-label metrics.
- `src/controlcheck/rules/*.py`: adjudicated grain, thresholds, severity, and materiality logic.
- `validation/adjudication_v0.2.csv`: complete decision inventory for v0.1 actual/expected mismatches.
- `data/controlcheck_rule_catalogue_v0.2.json`: structured 20-rule contract.
- `tools/build_validation_workbooks.mjs`: reproducible artifact-tool workbook builder/editor.
- `data/ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx`: exhaustive positive fixture.
- `data/ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx`: clean/boundary/exception fixture.
- `data/controlcheck_golden_expected_findings_v0.2.json`: exhaustive positive labels.
- `data/controlcheck_boundary_expected_findings_v0.2.json`: boundary/negative labels.
- `results/findings_v0.2.json`, `results/evaluation_v0.2.json`, `results/evaluation_summary_v0.2.md`: verified outputs.
- `docs/ControlCheck_AI_PRD_v0.1.docx`: preserved source PRD.
- `docs/ControlCheck_AI_PRD_v0.2.docx`: updated product baseline.
- `README.md`: v0.2 commands, compatibility, and metric interpretation.

---

### Task 0: Establish local Git baseline in the relocated project

**Files:**
- Create: `.gitignore`
- Track: current verified v0.1 project as the immutable baseline

**Interfaces:**
- Produces: local repository with baseline commit and feature branch `codex/validation-alignment-v0.2`
- Excludes: virtual environments, Python caches, pytest caches, render PNG/PDF intermediates, temporary Office files, and `work/`

- [ ] **Step 1: Verify the relocated v0.1 baseline before repository initialization**

Run: `python -m pytest -q -p no:cacheprovider`

Expected: 42 tests pass.

- [ ] **Step 2: Create `.gitignore` and initialize the local repository**

```text
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/
work/
~$*.docx
~$*.xlsx
*.tmp
```

Run: `git init; git add .; git commit -m "chore: baseline ControlCheck core v01"`

- [ ] **Step 3: Create the feature branch**

Run: `git switch -c codex/validation-alignment-v0.2`

Expected: `git branch --show-current` prints `codex/validation-alignment-v0.2`.

- [ ] **Step 4: Verify repository state and baseline tests**

Run: `git status --short; python -m pytest -q -p no:cacheprovider`

Expected: clean status and 42 passing tests.

- [ ] **Step 5: Record baseline artifact hashes**

Create `validation/v01_artifact_hashes.json` containing SHA-256 hashes for the v0.1 workbook, catalogue, ground truth, findings, and evaluation files; commit it with message `chore: record v01 artifact hashes`.

### Task 1: Version-aware catalogue, dataset, and ground-truth schemas

**Files:**
- Create: `src/controlcheck/versioning.py`
- Create: `src/controlcheck/ground_truth.py`
- Modify: `src/controlcheck/config.py`
- Modify: `src/controlcheck/models.py`
- Modify: `src/controlcheck/loader.py`
- Test: `tests/test_versioning_v02.py`

**Interfaces:**
- Produces: `ArtifactVersion.parse(value: str) -> ArtifactVersion`
- Produces: `assert_compatible(dataset_version: str, catalogue_version: str, ground_truth_version: str | None) -> None`
- Produces: `RuleDefinitionV2`, `RuleCatalogueV2`, `GroundTruthV2`, and `ExpectedFindingV2`
- Extends: `ProjectDataset.dataset_version: str`

- [ ] **Step 1: Write failing version/schema tests**

```python
def test_v02_catalogue_requires_structured_runtime_fields(v02_catalogue_path):
    catalogue = load_catalogue(v02_catalogue_path)
    rule = catalogue.by_id("CST-005")
    assert rule.runtime.evaluation_grain == "transaction"
    assert rule.runtime.thresholds == {
        "wbs_share_min": 0.25,
        "project_share_min": 0.03,
    }


def test_incompatible_dataset_and_catalogue_fail_before_rules():
    with pytest.raises(VersionCompatibilityError, match="0.1.*0.2"):
        assert_compatible("0.1", "0.2", "0.2")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_versioning_v02.py -q -p no:cacheprovider`

Expected: import fails because `versioning` and v0.2 models do not exist.

- [ ] **Step 3: Implement discriminated v0.1/v0.2 parsing and compatibility**

```python
class RuleRuntimeV2(BaseModel):
    evaluation_grain: Literal["project", "wbs", "vendor_wbs", "transaction", "activity", "period_wbs"]
    operator: str
    thresholds: dict[str, Decimal | int]
    severity_bands: list[SeverityBand]
    lookback_periods: int | None = None
    materiality: dict[str, Decimal] = Field(default_factory=dict)
    exclusions: list[ExceptionSpec] = Field(default_factory=list)


def assert_compatible(dataset_version, catalogue_version, ground_truth_version=None):
    versions = {ArtifactVersion.parse(value).major_minor for value in [dataset_version, catalogue_version, ground_truth_version] if value}
    if len(versions) != 1:
        raise VersionCompatibilityError(f"Incompatible artifact versions: {sorted(versions)}")
```

- [ ] **Step 4: Run focused and full tests**

Run: `python -m pytest tests/test_versioning_v02.py -q -p no:cacheprovider; python -m pytest -q -p no:cacheprovider`

Expected: v0.2 compatibility tests and all v0.1 tests pass.

- [ ] **Step 5: Commit Task 1**

```text
git add src/controlcheck tests/test_versioning_v02.py
git commit -m "feat: add versioned validation schemas"
```

### Task 2: Complete adjudication inventory and decisions

**Files:**
- Create: `src/controlcheck/adjudication.py`
- Create: `validation/adjudication_v0.2.csv`
- Create: `tests/test_adjudication_v02.py`

**Interfaces:**
- Produces: `build_adjudication_inventory(audit: AuditResult, expected: GroundTruth) -> list[AdjudicationRow]`
- Produces: `load_adjudication(path: Path) -> list[AdjudicationRow]`
- Enforces: unique `(rule_id, normalized_entity)`, non-empty rationale, and no `unreviewed` decisions

- [ ] **Step 1: Write failing completeness tests**

```python
def test_adjudication_covers_actual_union_expected(v01_audit, v01_ground_truth, adjudication_path):
    inventory = build_adjudication_inventory(v01_audit, v01_ground_truth)
    decisions = load_adjudication(adjudication_path)
    assert {row.key for row in decisions} == {row.key for row in inventory}
    assert all(row.decision != "unreviewed" and row.rationale.strip() for row in decisions)


def test_adjudication_has_explicit_disposition_for_every_artifact():
    rows = load_adjudication(ADJUDICATION_PATH)
    assert all(row.catalogue_action and row.dataset_action and row.ground_truth_action and row.test_action and row.prd_action for row in rows)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_adjudication_v02.py -q -p no:cacheprovider`

Expected: adjudication module and CSV are missing.

- [ ] **Step 3: Implement inventory and author the complete decision CSV**

Decision policy encoded in the CSV:

```text
CST-001 3.1/3.2                       dataset_defect; adjust v0.2 budgets so planted actual exceeds budget
CST-002 3.3                           dataset_defect; adjust remaining open commitment to exceed budget
PRG-003 3.1                           dataset_defect; change latest progress from 61% to 60%
CST-003 additional WBS findings       valid_finding; add exhaustive labels
CST-004 vendor findings               catalogue_ambiguity; use vendor_wbs grain and WBS+vendor entity key
CST-005 broad transaction matches     threshold_noise; use both 25% WBS share and 3% project share
Schedule/progress additional matches  valid_finding; add exhaustive labels
PRG-003 low-materiality 4.0            threshold_noise; apply 1% project-budget current-period materiality
XDOM-001 additional WBS findings      valid_finding; add exhaustive labels
Severity mismatches                   ground_truth_defect; follow structured catalogue bands
```

- [ ] **Step 4: Run adjudication and full tests**

Run: `python -m pytest tests/test_adjudication_v02.py -q -p no:cacheprovider; python -m pytest -q -p no:cacheprovider`

Expected: union coverage is exact and unresolved count is zero.

- [ ] **Step 5: Commit Task 2**

```text
git add src/controlcheck/adjudication.py validation/adjudication_v0.2.csv tests/test_adjudication_v02.py
git commit -m "test: adjudicate v01 validation mismatches"
```

### Task 3: Structured Rule Catalogue v0.2 and rule behavior

**Files:**
- Create: `data/controlcheck_rule_catalogue_v0.2.json`
- Modify: `src/controlcheck/rules/cost.py`
- Modify: `src/controlcheck/rules/progress.py`
- Modify: `src/controlcheck/rules/schedule.py`
- Modify: `src/controlcheck/rules/cross_domain.py`
- Modify: `src/controlcheck/builders.py`
- Test: `tests/rules/test_catalogue_v02.py`

**Interfaces:**
- Consumes: `RuleDefinitionV2.runtime`
- Produces: entity keys at the declared grain, including `WBS|VENDOR` for `vendor_wbs`
- Preserves: v0.1 rules when the v0.1 catalogue is loaded

- [ ] **Step 1: Write failing catalogue-driven behavior tests**

```python
def test_cst005_requires_both_materiality_thresholds(v02_dataset, v02_context):
    findings = run_rule("CST-005", v02_dataset, v02_context)
    assert {finding.entity_id for finding in findings} == {"ACT-9006", "ACT-9007"}


def test_prg003_excludes_current_cost_below_project_materiality(v02_dataset, v02_context):
    assert "4.0" not in {finding.entity_id for finding in run_rule("PRG-003", v02_dataset, v02_context)}


def test_vendor_concentration_uses_wbs_vendor_identity(v02_dataset, v02_context):
    findings = run_rule("CST-004", v02_dataset, v02_context)
    assert all("|" in finding.entity_id for finding in findings)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/rules/test_catalogue_v02.py -q -p no:cacheprovider`

Expected: v0.2 catalogue or declared-grain behavior is absent.

- [ ] **Step 3: Author all 20 structured definitions and consume their runtime values**

```python
runtime = context.definition(self.rule_id).runtime
wbs_share_min = Decimal(str(runtime.thresholds["wbs_share_min"]))
project_share_min = Decimal(str(runtime.thresholds["project_share_min"]))
if wbs_share < wbs_share_min or project_share < project_share_min:
    continue
```

- [ ] **Step 4: Run rule and historical regression tests**

Run: `python -m pytest tests/rules/test_catalogue_v02.py tests/rules tests/test_ground_truth_regression.py -q -p no:cacheprovider`

Expected: v0.2 behavior passes and v0.1 evaluation remains reproducible.

- [ ] **Step 5: Commit Task 3**

```text
git add data/controlcheck_rule_catalogue_v0.2.json src/controlcheck/rules src/controlcheck/builders.py tests/rules/test_catalogue_v02.py
git commit -m "feat: add structured rule catalogue v02"
```

### Task 4: Golden Positive and Boundary/Negative workbooks

**Files:**
- Create: `tools/build_validation_workbooks.mjs`
- Create: `data/ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx`
- Create: `data/ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx`
- Create: `tests/test_validation_workbooks_v02.py`

**Interfaces:**
- Produces two workbooks with the existing loader-compatible sheet/header layout
- Golden changes: WBS 3.1 budget `8_000_000_000`, WBS 3.2 budget `16_000_000_000`, COM-005 invoiced amount `5_000_000_000`, PRG-31-4 actual progress `0.60`
- Boundary workbook contains literal just-below/equal/just-above cases for every numeric rule and explicit exception records

- [ ] **Step 1: Write failing workbook-value and boundary tests**

```python
def test_golden_planted_values_satisfy_their_formulas(golden_dataset):
    assert budget(golden_dataset, "3.1") == Decimal("8000000000")
    assert actual(golden_dataset, "3.1") > budget(golden_dataset, "3.1")
    assert budget(golden_dataset, "3.2") == Decimal("16000000000")
    assert latest_progress(golden_dataset, "3.1").actual_progress == 0.60


def test_boundary_dataset_has_below_equal_above_cases(boundary_manifest):
    assert boundary_manifest.cases("SCH-004") == {"below", "equal", "above"}
    assert boundary_manifest.cases("CST-005") == {"below", "equal", "above", "approved_exception"}
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_validation_workbooks_v02.py -q -p no:cacheprovider`

Expected: v0.2 workbook files do not exist.

- [ ] **Step 3: Use the Spreadsheets skill and artifact-tool builder to author both workbooks**

The builder imports v0.1 for the golden workbook, changes only adjudicated values, updates `Project_Info.dataset_version` to `0.2`, and adds a machine-readable `Validation_Cases` sheet. It creates the boundary workbook from explicit literal rows, preserves typed dates/numbers/percentages, and never computes expected values with production rule functions.

- [ ] **Step 4: Render/inspect every workbook sheet and run loader tests**

Run: `node tools/build_validation_workbooks.mjs`

Run: `python -m pytest tests/test_validation_workbooks_v02.py tests/test_loader.py -q -p no:cacheprovider`

Expected: all sheets render legibly and both workbooks load with dataset version `0.2`.

- [ ] **Step 5: Commit Task 4**

```text
git add tools/build_validation_workbooks.mjs data/ControlCheck_AI_*_v0.2.xlsx tests/test_validation_workbooks_v02.py
git commit -m "test: add v02 validation workbooks"
```

### Task 5: Independently curated v0.2 ground truth

**Files:**
- Create: `data/controlcheck_golden_expected_findings_v0.2.json`
- Create: `data/controlcheck_boundary_expected_findings_v0.2.json`
- Create: `tests/test_ground_truth_v02.py`

**Interfaces:**
- Consumes: adjudication decisions, literal workbook values, and catalogue v0.2
- Produces: unique expected keys, metric expectations, severities, evidence anchors, and adjudication references

- [ ] **Step 1: Write failing ground-truth integrity tests**

```python
def test_v02_ground_truth_is_unique_complete_and_versioned(golden_ground_truth):
    keys = [finding.match_key for finding in golden_ground_truth.expected_findings]
    assert len(keys) == len(set(keys)) == golden_ground_truth.expected_finding_count
    assert golden_ground_truth.dataset_version == "0.2"
    assert golden_ground_truth.catalogue_version == "0.2"
    assert all(finding.adjudication_ref and finding.metric_expectations for finding in golden_ground_truth.expected_findings)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_ground_truth_v02.py -q -p no:cacheprovider`

Expected: v0.2 ground-truth files are absent.

- [ ] **Step 3: Author labels from adjudication and hand-checked literal calculations**

Ground truth includes every catalogue-valid golden finding, uses `WBS|VENDOR` keys for `CST-004`, labels both adjudicated `CST-005` outliers, excludes materiality-suppressed `PRG-003 / 4.0`, and records all boundary expected/no-finding cases.

- [ ] **Step 4: Run integrity and cross-artifact checks**

Run: `python -m pytest tests/test_ground_truth_v02.py tests/test_versioning_v02.py -q -p no:cacheprovider`

Expected: declared counts, keys, versions, metrics, and evidence anchors reconcile.

- [ ] **Step 5: Commit Task 5**

```text
git add data/controlcheck_*expected_findings_v0.2.json tests/test_ground_truth_v02.py
git commit -m "test: curate exhaustive v02 ground truth"
```

### Task 6: Exception-aware evaluator and compatibility preflight

**Files:**
- Modify: `src/controlcheck/engine.py`
- Modify: `src/controlcheck/evaluation.py`
- Modify: `src/controlcheck/service.py`
- Modify: `src/controlcheck/cli.py`
- Modify: `src/controlcheck/api.py`
- Test: `tests/test_evaluation_v02.py`
- Test: `tests/test_cli_api_v02.py`

**Interfaces:**
- Produces: `EvaluationReportV2` with raw/exception-aware metrics, severity accuracy, metric agreement, approved exceptions, unreviewed count, compatibility, and determinism
- Preflight: catalogue/dataset/ground-truth versions must match before rule execution

- [ ] **Step 1: Write failing evaluator/preflight tests**

```python
def test_v02_evaluation_reports_complete_quality_dimensions(v02_report):
    assert v02_report.precision == v02_report.recall == 1.0
    assert v02_report.severity_accuracy == 1.0
    assert v02_report.metric_accuracy == 1.0
    assert v02_report.unreviewed_label_count == 0
    assert v02_report.deterministic is True


def test_cli_rejects_incompatible_versions(runner, v01_workbook, v02_catalogue):
    result = runner.invoke(app, ["run", str(v01_workbook), "--catalogue", str(v02_catalogue)])
    assert result.exit_code == 1
    assert "incompatible_artifact_versions" in result.output
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_evaluation_v02.py tests/test_cli_api_v02.py -q -p no:cacheprovider`

Expected: v0.2 metrics and compatibility error contract do not exist.

- [ ] **Step 3: Implement preflight and extended evaluation without changing v0.1 report fields**

```python
assert_compatible(dataset.dataset_version, catalogue.version, ground_truth.dataset_version)
metric_matches = compare_metric_expectations(findings, ground_truth, money_tolerance=Decimal("1"), ratio_tolerance=Decimal("0.000001"))
```

- [ ] **Step 4: Run focused and full tests**

Run: `python -m pytest tests/test_evaluation_v02.py tests/test_cli_api_v02.py -q -p no:cacheprovider; python -m pytest -q -p no:cacheprovider`

Expected: v0.2 reports complete dimensions and v0.1 APIs remain compatible.

- [ ] **Step 5: Commit Task 6**

```text
git add src/controlcheck tests/test_evaluation_v02.py tests/test_cli_api_v02.py
git commit -m "feat: add v02 validation preflight and metrics"
```

### Task 7: v0.2 regression outputs and developer documentation

**Files:**
- Create: `tests/test_validation_alignment_v02.py`
- Create: `results/findings_v0.2.json`
- Create: `results/evaluation_v0.2.json`
- Create: `results/evaluation_summary_v0.2.md`
- Modify: `README.md`

**Interfaces:**
- Proves: exact controlled-fixture targets and unchanged v0.1 reproducibility

- [ ] **Step 1: Write the failing end-to-end acceptance test**

```python
def test_validation_alignment_v02_acceptance(v02_paths):
    golden = run_evaluation(v02_paths.golden_workbook, v02_paths.catalogue, v02_paths.golden_truth)[1]
    boundary = run_evaluation(v02_paths.boundary_workbook, v02_paths.catalogue, v02_paths.boundary_truth)[1]
    assert (golden.precision, golden.recall, golden.severity_accuracy, golden.metric_accuracy) == (1.0, 1.0, 1.0, 1.0)
    assert boundary.fp == boundary.fn == boundary.unreviewed_label_count == 0
    assert golden.executed_rule_count == boundary.executed_rule_count == 20
```

- [ ] **Step 2: Run acceptance test and verify RED**

Run: `python -m pytest tests/test_validation_alignment_v02.py -q -p no:cacheprovider`

Expected: acceptance fails until all v0.2 artifacts align.

- [ ] **Step 3: Resolve only adjudication-backed gaps, generate reports, and update README**

Run both CLI evaluations, write full FP/FN/exception/per-rule reports, document v0.1 versus v0.2 semantics, and include reproducible commands using only project-relative paths.

- [ ] **Step 4: Run v0.1 historical and v0.2 acceptance suites**

Run: `python -m pytest tests/test_ground_truth_regression.py tests/test_validation_alignment_v02.py -q -p no:cacheprovider`

Expected: both historical reproducibility and v0.2 controlled targets pass.

- [ ] **Step 5: Commit Task 7**

```text
git add tests/test_validation_alignment_v02.py results README.md
git commit -m "docs: publish v02 validation baseline"
```

### Task 8: Update and visually verify PRD v0.2

**Files:**
- Copy: `C:\Users\USER\Downloads\ControlCheck_AI_PRD_v0.1.docx` to `docs/ControlCheck_AI_PRD_v0.1.docx`
- Create: `docs/ControlCheck_AI_PRD_v0.2.docx`
- Create: `tools/update_prd_v02.py`
- Test: `tests/test_prd_v02.py`

**Interfaces:**
- Preserves: original PRD structure and visual system
- Adds: rule governance, exceptions, validation governance/metrics, version compatibility, revised QA criteria, roadmap ordering, and change log

- [ ] **Step 1: Write failing structural PRD tests**

```python
def test_prd_v02_contains_accepted_product_changes(prd_v02_text):
    required = [
        "Rule and Threshold Governance", "Approved Exceptions",
        "Ground-Truth Governance", "Validation Metrics",
        "Artifact Version Compatibility", "Change Log v0.2",
    ]
    assert all(section in prd_v02_text for section in required)
    assert "100% on controlled validation fixtures" in prd_v02_text
    assert "not a customer-accuracy claim" in prd_v02_text
```

- [ ] **Step 2: Run test and verify RED**

Run: `python -m pytest tests/test_prd_v02.py -q -p no:cacheprovider`

Expected: PRD v0.2 does not exist.

- [ ] **Step 3: Use the Documents skill to apply minimal tracked product updates**

Run the required edit-operation marker once, preserve v0.1, patch v0.2 with python-docx/OOXML helpers, update document metadata/version, and add a concise change log tied to adjudication decisions.

- [ ] **Step 4: Render every PRD page, inspect PNGs, fix defects, and rerun structural tests**

Run: `render_docx.py docs/ControlCheck_AI_PRD_v0.2.docx --output_dir work/prd_v02_render --emit_pdf`

Run: `python -m pytest tests/test_prd_v02.py -q -p no:cacheprovider`

Expected: every page is legible with no clipping, overlap, broken tables, or unexplained style drift.

- [ ] **Step 5: Commit Task 8**

```text
git add docs/ControlCheck_AI_PRD_v0.1.docx docs/ControlCheck_AI_PRD_v0.2.docx tools/update_prd_v02.py tests/test_prd_v02.py
git commit -m "docs: update ControlCheck PRD for validation v02"
```

### Task 9: Complete verification and project handoff

**Files:**
- Verify all files above
- Modify: `results/evaluation_summary_v0.2.md` only if fresh verified values differ from its generated values

**Interfaces:**
- Produces: one verified project state under `D:\Projects\ControlCheck-AI`

- [ ] **Step 1: Run the full test and compile gates**

```text
python -m pytest -q -p no:cacheprovider
python -m compileall -q src
```

- [ ] **Step 2: Run both v0.2 CLI evaluations from project-relative paths**

```text
controlcheck evaluate data/ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx --catalogue data/controlcheck_rule_catalogue_v0.2.json --ground-truth data/controlcheck_golden_expected_findings_v0.2.json --output results/evaluation_v0.2.json
controlcheck evaluate data/ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx --catalogue data/controlcheck_rule_catalogue_v0.2.json --ground-truth data/controlcheck_boundary_expected_findings_v0.2.json --output results/boundary_evaluation_v0.2.json
```

- [ ] **Step 3: Verify deliverable integrity**

Check that all v0.2 findings have evidence/calculation traces, both reports are deterministic, adjudication unresolved count is zero, PRD render page count is nonzero, and v0.1 source hashes remain unchanged.

- [ ] **Step 4: Run a fresh final test suite after all generated artifacts and PRD edits**

Run: `python -m pytest -q -p no:cacheprovider`

Expected: zero failures.

- [ ] **Step 5: Commit the verified release state**

```text
git add .
git commit -m "release: complete ControlCheck validation alignment v02"
```
