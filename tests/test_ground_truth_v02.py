from pathlib import Path

import openpyxl

from controlcheck.ground_truth import GroundTruthV2, load_ground_truth


def _paths(project_root: Path):
    return (
        project_root / "data" / "controlcheck_golden_expected_findings_v0.2.json",
        project_root / "data" / "controlcheck_boundary_expected_findings_v0.2.json",
    )


def test_v02_golden_ground_truth_is_unique_complete_and_versioned(project_root: Path):
    golden_path, _ = _paths(project_root)
    ground_truth = load_ground_truth(golden_path)

    assert isinstance(ground_truth, GroundTruthV2)
    keys = [finding.match_key for finding in ground_truth.expected_findings]
    assert len(keys) == len(set(keys)) == ground_truth.expected_finding_count == 59
    assert ground_truth.schema_version == "0.2"
    assert ground_truth.dataset_version == "0.2"
    assert ground_truth.catalogue_version == "0.2"
    assert all(finding.adjudication_ref for finding in ground_truth.expected_findings)
    assert all(finding.metric_expectations for finding in ground_truth.expected_findings)
    assert all(finding.evidence_anchors for finding in ground_truth.expected_findings)


def test_v02_golden_ground_truth_encodes_approved_alignment(project_root: Path):
    golden_path, _ = _paths(project_root)
    ground_truth = load_ground_truth(golden_path)
    keys = {finding.match_key for finding in ground_truth.expected_findings}

    assert ("CST-004", "3.2|V005") in keys
    assert ("CST-005", "ACT-9006") in keys
    assert ("CST-005", "ACT-9007") in keys
    assert ("PRG-003", "4.0") not in keys
    assert ("PRG-003", "3.1") in keys


def test_boundary_ground_truth_records_all_literal_expected_and_negative_cases(project_root: Path):
    _, boundary_path = _paths(project_root)
    ground_truth = load_ground_truth(boundary_path)

    assert isinstance(ground_truth, GroundTruthV2)
    assert ground_truth.expected_finding_count == 0
    assert len(ground_truth.boundary_cases) == 50
    assert len({case.case_id for case in ground_truth.boundary_cases}) == 50
    assert any(case.expected_trigger for case in ground_truth.boundary_cases)
    assert any(not case.expected_trigger for case in ground_truth.boundary_cases)
    assert {case.exception_id for case in ground_truth.boundary_cases if case.exception_id} == {
        "EXC-ADVANCE-PAYMENT",
        "EXC-ADVANCE-PROCUREMENT",
    }


def test_boundary_ground_truth_matches_workbook_manifest(project_root: Path):
    _, boundary_path = _paths(project_root)
    ground_truth = load_ground_truth(boundary_path)
    workbook_path = project_root / "data" / "ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx"
    book = openpyxl.load_workbook(workbook_path, data_only=True, read_only=True)
    rows = list(book["Validation_Cases"].iter_rows(values_only=True))
    header_index = next(index for index, row in enumerate(rows) if row and row[0] == "case_id")
    headers = rows[header_index]
    manifest = {
        row[0]: dict(zip(headers, row))
        for row in rows[header_index + 1:]
        if row and row[0]
    }
    book.close()

    assert set(manifest) == {case.case_id for case in ground_truth.boundary_cases}
    assert all(
        manifest[case.case_id]["expected_trigger"] is case.expected_trigger
        and manifest[case.case_id]["rule_id"] == case.rule_id
        and manifest[case.case_id]["entity_id"] == case.entity_id
        for case in ground_truth.boundary_cases
    )

