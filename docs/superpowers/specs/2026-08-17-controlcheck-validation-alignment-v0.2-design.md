# ControlCheck Validation Alignment v0.2 Design

## Purpose

Align the deterministic engine, rule catalogue, synthetic workbook, severity definitions, and ground truth so the evaluation measures rule correctness instead of inconsistencies between artifacts.

This milestone improves the validation foundation. It does not add a frontend, LLM reasoning, database persistence, authentication, or multi-project SaaS functionality.

## Current Baseline

ControlCheck Core Engine v0.1 executes 20 deterministic rules and emits 85 unique evidence-backed findings on the supplied EPC workbook. Evaluation against the 24-item ground truth produces:

- True positives: 20
- False positives: 65
- False negatives: 4
- Precision: 0.2353
- Recall: 0.8333
- F1: 0.3670

The engine is deterministic and the 42-test suite passes. The metric gap is dominated by catalogue/ground-truth incompleteness rather than random execution.

## Governing Principles

1. **No entity-specific logic.** Production rules may not branch on synthetic transaction, activity, vendor, or WBS identifiers.
2. **No evidence, no finding.** Every accepted finding retains source records and calculation trace.
3. **Every evaluated condition is labelled.** Ground truth must not contain only representative examples while leaving other catalogue-valid findings unlabelled.
4. **Rules are versioned contracts.** Formula, scope, threshold, severity, exclusions, and aggregation grain are machine-readable.
5. **Exceptions are explicit.** A valid condition suppressed for a business reason must be represented as an approved exception, not silently omitted.
6. **Historical artifacts are immutable.** v0.1 inputs and results remain available for regression and audit history.
7. **PRD follows product behavior.** Any accepted behavioral or acceptance-criteria change is incorporated into PRD v0.2 and recorded in its change log.

## Sources of Truth

For v0.2, source authority is applied in this order:

1. An approved adjudication decision defines the intended business control.
2. The v0.2 machine-readable rule catalogue encodes that decision.
3. Engine behavior implements the catalogue without dataset-specific branches.
4. Synthetic datasets exercise the behavior.
5. Ground truth labels every expected finding produced by the approved behavior.
6. The PRD records the product-level capability, governance, and acceptance criteria.

Existing v0.1 prose does not automatically override a reviewed adjudication decision. Any change from v0.1 must include a rationale and compatibility classification.

## Adjudication Workflow

All 85 v0.1 findings and four false negatives enter an adjudication matrix. Each row records:

- rule ID and rule version
- entity and source records
- formula inputs and computed values
- v0.1 expected/actual status
- catalogue wording
- decision classification
- decision rationale
- required catalogue, engine, dataset, ground-truth, test, and PRD changes
- reviewer status

Decision classifications are:

- `valid_finding`: the condition is a true finding and must be labelled.
- `expected_exception`: the condition is true but suppressed by an explicit, testable exception.
- `threshold_noise`: the formula is correct but the threshold is not materially useful and must be revised for all comparable records.
- `rule_logic_defect`: the engine does not implement the approved rule correctly.
- `dataset_defect`: planted values do not satisfy the stated expected condition.
- `ground_truth_defect`: the expected label is missing, extra, misidentified, or has the wrong severity.
- `catalogue_ambiguity`: aggregation grain, period, comparison population, severity, or exclusion is underspecified.

No row may remain unreviewed in the final v0.2 evaluation set.

## Rule Catalogue v0.2

Each of the 20 rule definitions contains structured fields for:

- `rule_id`, `version`, `name`, `category`, and `enabled`
- input domains and required fields
- evaluation grain: project, WBS, vendor, transaction, activity, or period
- lookback period and comparison population
- formula/operator
- typed thresholds and units
- warning/critical severity bands
- materiality floor
- explicit exclusions and approved-exception keys
- evidence contract
- deterministic entity-key construction
- positive, boundary, and negative acceptance examples
- compatibility note from v0.1

Free-text explanation remains for humans, but runtime behavior must not depend on parsing prose.

## Dataset Strategy

Validation uses two complementary datasets:

### Golden Positive Dataset v0.2

An updated EPC project workbook contains controlled, realistic positive cases across all 20 rules. Every catalogue-valid finding is labelled. Values are reconciled so planted conditions genuinely satisfy their formulas.

### Boundary and Negative Dataset v0.2

A compact workbook covers exact thresholds, just-below thresholds, approved exceptions, clean records, missing optional values, and aggregation boundaries. Its expected result contains no unreviewed findings.

The existing v0.1 workbook is preserved unchanged. v0.2 files use new filenames and embedded dataset-version metadata.

## Ground-Truth Contract

Ground truth v0.2 stores:

- dataset and catalogue versions
- deterministic match key `(rule_id, normalized_entity)`
- expected severity
- source domain and evidence anchors
- expected metric values or ranges
- rationale
- label status: active or approved exception
- adjudication reference

Composite entities remain order-independent. Duplicate expected keys are invalid. Ground-truth validation fails when the declared count, unique-key count, or catalogue version does not match.

## Engine Changes

Engine changes are permitted only for adjudicated `rule_logic_defect` or to consume structured v0.2 configuration. Likely changes include:

- structured threshold loading and validation
- explicit aggregation grain and period selection
- approved-exception evaluation
- consistent severity-band calculation
- metric tolerance for money, ratios, and percentage points
- catalogue/dataset version compatibility checks

The v0.1 behavior remains testable through historical regression fixtures.

## Evaluation and Metrics

The evaluator reports both raw detection quality and exception-aware quality:

- TP, FP, FN, precision, recall, and F1
- severity accuracy
- metric-value agreement
- per-rule results
- approved-exception counts
- unreviewed-label count
- catalogue/dataset compatibility
- deterministic repeated-run result

Acceptance targets for the controlled v0.2 fixtures are:

- 20 of 20 rules executed
- 100% precision and recall on the Golden Positive Dataset
- 100% expected behavior on boundary/negative cases
- 100% severity agreement
- zero unreviewed labels
- zero findings without evidence or calculation trace
- byte-equivalent repeated normalized output
- all v0.1 and v0.2 automated tests passing

These targets validate controlled fixtures; they are not presented as real-customer accuracy claims.

## PRD v0.2 Update

The existing PRD is preserved. A new `ControlCheck_AI_PRD_v0.2.docx` is created with minimal, traceable updates to:

- deterministic rule-engine requirements
- structured rule and threshold governance
- approved-exception behavior
- evidence and calculation-trace requirements
- synthetic dataset and ground-truth governance
- validation metrics and their interpretation
- QA acceptance criteria
- version compatibility and auditability
- roadmap ordering: validation before production API/UI/AI expansion
- change log describing deviations from v0.1

The updated DOCX preserves the original visual system, is rendered page-by-page, and is not delivered until visual QA passes.

## Deliverables

- adjudication matrix v0.2
- rule catalogue JSON v0.2
- Golden Positive Dataset workbook v0.2
- Boundary and Negative Dataset workbook v0.2
- ground-truth JSON for both datasets
- engine/configuration changes supported by adjudication
- automated v0.1 historical and v0.2 validation tests
- findings and evaluation reports v0.2
- evaluation summary explaining all changes
- `ControlCheck_AI_PRD_v0.2.docx`
- updated developer README

All deliverables are stored under `D:\Projects\ControlCheck-AI`; temporary rendering and build files are excluded.

## Error Handling

Runs fail before rule execution when catalogue, dataset, or ground-truth versions are incompatible; structured thresholds are malformed; required fields are unavailable; expected keys are duplicated; or declared expected counts do not reconcile.

Adjudication export fails when any row lacks a decision, rationale, or required-change disposition. A rule execution error fails the complete run rather than returning partial success.

## Testing Strategy

Implementation follows red-green-refactor cycles:

- schema tests for v0.2 catalogue and ground truth
- unit tests for each adjudicated formula, threshold, severity, and exception
- exact-boundary tests using independently derived values
- integration tests for both v0.2 workbooks
- historical regression against v0.1
- determinism and evidence-contract tests
- CLI and FastAPI compatibility tests
- PRD structural and visual render verification

## Definition of Done

Validation Alignment v0.2 is complete only when all deliverables are versioned; adjudication has zero unresolved rows; controlled-fixture targets pass; v0.1 remains reproducible; the PRD change log matches accepted behavior; the DOCX render is visually clean; and the complete test suite passes from `D:\Projects\ControlCheck-AI`.
