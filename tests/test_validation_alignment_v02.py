import json
from pathlib import Path

from controlcheck.service import run_evaluation


def test_validation_alignment_v02_acceptance(project_root: Path):
    data = project_root / "data"
    catalogue = data / "controlcheck_rule_catalogue_v0.2.json"
    golden = run_evaluation(
        data / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
        catalogue,
        data / "controlcheck_golden_expected_findings_v0.2.json",
    )[1]
    boundary = run_evaluation(
        data / "ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx",
        catalogue,
        data / "controlcheck_boundary_expected_findings_v0.2.json",
    )[1]

    assert (
        golden.precision,
        golden.recall,
        golden.severity_accuracy,
        golden.metric_accuracy,
    ) == (1.0, 1.0, 1.0, 1.0)
    assert boundary.fp == boundary.fn == boundary.unreviewed_label_count == 0
    assert golden.executed_rule_count == boundary.executed_rule_count == 20

    result_paths = [
        project_root / "results" / "findings_v0.2.json",
        project_root / "results" / "evaluation_v0.2.json",
        project_root / "results" / "boundary_findings_v0.2.json",
        project_root / "results" / "boundary_evaluation_v0.2.json",
    ]
    assert all(path.exists() for path in result_paths)
    published = json.loads(result_paths[1].read_text(encoding="utf-8"))
    assert published["tp"] == published["actual_count"] == published["expected_count"] == 59
    assert published["fp"] == published["fn"] == 0

