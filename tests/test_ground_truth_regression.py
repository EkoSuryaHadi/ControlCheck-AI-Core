def test_supplied_dataset_evaluation_is_internally_consistent(
    sample_workbook, sample_catalogue, sample_ground_truth
):
    from controlcheck.service import run_evaluation

    audit, report = run_evaluation(sample_workbook, sample_catalogue, sample_ground_truth)

    assert report.expected_count == 24
    assert report.tp + report.fn == 24
    assert report.actual_count == report.tp + report.fp
    assert report.executed_rule_count == 20
    assert report.deterministic is True
    assert audit.rule_count == 20
    assert all(finding.evidence for finding in audit.findings)
