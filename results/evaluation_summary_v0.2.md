# ControlCheck Validation Alignment v0.2

## Outcome

The deterministic engine and the adjudicated v0.2 validation artifacts are fully aligned.

| Controlled fixture | Expected | Actual | TP | FP | FN | Precision | Recall | Severity | Metrics |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Golden Positive | 59 | 59 | 59 | 0 | 0 | 100% | 100% | 100% | 100% |
| Boundary / Negative | 0 | 0 | 0 | 0 | 0 | 100% | 100% | 100% | 100% |

The Boundary / Negative workbook also contains 50 literal below/equal/above and approved-exception cases across 16 numeric rules. Its empty-set precision and recall are defined as 100% because neither expected nor actual full-engine findings exist in the benign carrier dataset.

## Governance controls verified

- All 20 rules execute deterministically.
- Catalogue, dataset, and ground-truth versions must share the same major/minor version before rule execution.
- Every golden label has an adjudication reference, evidence anchor, severity, and at least one metric expectation.
- `CST-004` uses the `WBS|VENDOR` evaluation grain.
- `CST-005` requires both 25% WBS-share and 3% project-share materiality.
- `PRG-003` applies a 1% project-budget current-period materiality floor.
- Approved exceptions remain visible in raw reporting and are excluded only from exception-aware error counts.

## Interpretation limit

The 100% figures apply only to controlled synthetic validation fixtures. They demonstrate implementation-to-specification agreement and regression stability; they are **not a customer-accuracy claim** and do not establish performance on unseen project data.

## Historical v0.1 comparison

The preserved v0.1 baseline produced 20 TP, 65 FP, and 4 FN against a representative 24-label ground truth. Validation Alignment v0.2 resolves the documented dataset defects, catalogue ambiguities, threshold noise, incomplete labels, and severity conflicts while retaining the v0.1 artifacts and their checksum manifest for auditability.
