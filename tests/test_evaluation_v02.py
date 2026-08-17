from pathlib import Path

import pytest

from controlcheck.ground_truth import load_ground_truth
from controlcheck.service import run_audit, run_evaluation


def _paths(project_root: Path):
    return (
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
        project_root / "data" / "controlcheck_rule_catalogue_v0.2.json",
        project_root / "data" / "controlcheck_golden_expected_findings_v0.2.json",
    )


def test_v02_evaluation_reports_complete_quality_dimensions(project_root: Path):
    audit, report = run_evaluation(*_paths(project_root))

    assert audit.finding_count == 59
    assert report.schema_version == "0.2"
    assert report.compatible is True
    assert report.precision == report.recall == report.f1 == 1.0
    assert report.raw_precision == report.raw_recall == 1.0
    assert report.severity_accuracy == 1.0
    assert report.metric_accuracy == 1.0
    assert report.unreviewed_label_count == 0
    assert report.deterministic is True
    assert report.approved_exceptions == []


def test_v02_metric_mismatch_is_reported_separately(project_root: Path):
    workbook, catalogue, ground_truth_path = _paths(project_root)
    audit = run_audit(workbook, catalogue)
    ground_truth = load_ground_truth(ground_truth_path)
    changed = ground_truth.model_copy(deep=True)
    changed.expected_findings[0].metric_expectations = {"budget": "1"}

    from controlcheck.evaluation import evaluate

    report = evaluate(audit.findings, changed)
    assert report.precision == report.recall == 1.0
    assert report.severity_accuracy == 1.0
    assert report.metric_accuracy < 1.0
    assert report.metric_mismatches[0]["metric"] == "budget"


def test_v02_boundary_zero_findings_is_perfect_empty_set(project_root: Path):
    workbook = project_root / "data" / "ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx"
    catalogue = project_root / "data" / "controlcheck_rule_catalogue_v0.2.json"
    ground_truth = project_root / "data" / "controlcheck_boundary_expected_findings_v0.2.json"

    audit, report = run_evaluation(workbook, catalogue, ground_truth)
    assert audit.finding_count == 0
    assert report.expected_count == report.actual_count == 0
    assert report.precision == report.recall == report.f1 == 1.0
    assert report.boundary_case_count == 50


def test_v02_approved_exception_is_visible_but_excluded_from_effective_counts(project_root: Path):
    workbook, catalogue, ground_truth_path = _paths(project_root)
    audit = run_audit(workbook, catalogue)
    ground_truth = load_ground_truth(ground_truth_path).model_copy(deep=True)
    ground_truth.expected_findings[0].exception_id = "EXC-APPROVED-TEST"

    from controlcheck.evaluation import evaluate

    report = evaluate(audit.findings, ground_truth)
    assert report.raw_tp == 59
    assert report.tp == report.expected_count == report.actual_count == 58
    assert report.precision == report.recall == 1.0
    assert report.approved_exceptions == [{
        "rule_id": ground_truth.expected_findings[0].rule_id,
        "entity": ground_truth.expected_findings[0].entity_id,
        "exception_id": "EXC-APPROVED-TEST",
    }]
