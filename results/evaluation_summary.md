# ControlCheck v0.1 Evaluation Summary

## Result

| Metric | Value |
|---|---:|
| Expected findings | 24 |
| Unique actual findings | 85 |
| True positives | 20 |
| False positives | 65 |
| False negatives | 4 |
| Precision | 0.2353 |
| Recall | 0.8333 |
| F1 | 0.3670 |
| Severity matches | 14 |
| Severity mismatches | 6 |
| Executed rules | 20 |
| Deterministic repeated run | Yes |

## False negatives

- `CST-001 / 3.1`: workbook actual is Rp8,490,690,000 against Rp12,000,000,000 budget, so `actual > budget` is false.
- `CST-001 / 3.2`: workbook actual is Rp16,595,674,000 against Rp18,000,000,000 budget, so `actual > budget` is false.
- `CST-002 / 3.3`: the engine interprets open commitment as `committed - invoiced`; the supplied values do not reproduce the labelled condition under that interpretation.
- `PRG-003 / 3.1`: latest actual progress moves from 58% to 61%, a 3-point increase; the catalogue threshold requires no more than 2 points.

## Why false positives are high

The rule catalogue describes general control tests, while the ground truth labels only selected planted examples. Literal catalogue execution therefore reports unlabelled but threshold-valid findings. The largest difference is `CST-005`: the catalogue's 5% of WBS budget / 2% of project budget rule flags many synthetic transactions, whereas the ground truth labels only `ACT-9006`.

Other differences follow the same pattern: several activities are overdue, behind plan, critical, or have negative float, but the expected JSON selects one or two representative activities for each rule.

No entity-specific suppression was added to inflate evaluation metrics. Full lists and per-rule counts are available in `evaluation_v0.1.json`.
