import pytest

from controlcheck.evaluation import ExpectedFinding, GroundTruth, evaluate
from controlcheck.models import EvidenceItem, Finding


def finding(rule_id, entity, severity):
    return Finding(
        finding_id=f"F-{rule_id}-{entity}", rule_id=rule_id, rule_name=rule_id,
        category="test", severity=severity, project_id="P1", entity_type="test",
        entity_id=entity, title="Test", description="Test", metrics={},
        business_impact="impact", recommendation="recommend",
        evidence=[EvidenceItem(source_sheet="Test", record_ids=[entity], fields={})],
        calculation={"result": True},
    )


def expected(expected_id, rule_id, entity, severity):
    return ExpectedFinding(
        expected_id=expected_id, rule_id=rule_id, category="Test", severity=severity,
        source="Test", entity=entity, finding_title="Test", why_expected="Test",
    )


def test_evaluator_reports_tp_fp_fn_and_severity_separately():
    report = evaluate(
        [finding("R1", "A", "warning"), finding("R2", "EXTRA", "critical")],
        GroundTruth(dataset_version="x", project_id="P1", data_date="2026-08-15",
                    expected_finding_count=2,
                    expected_findings=[expected("E1", "R1", "A", "Critical"),
                                       expected("E2", "R3", "MISSING", "Warning")]),
    )
    assert (report.tp, report.fp, report.fn) == (1, 1, 1)
    assert report.precision == pytest.approx(0.5)
    assert report.recall == pytest.approx(0.5)
    assert report.f1 == pytest.approx(0.5)
    assert len(report.severity_mismatches) == 1


def test_composite_entity_matching_is_order_independent():
    report = evaluate(
        [finding("DQ-002", "ACT-9002/ACT-9001", "warning")],
        GroundTruth(dataset_version="x", project_id="P1", data_date="2026-08-15",
                    expected_finding_count=1,
                    expected_findings=[expected("E1", "DQ-002", "ACT-9001/ACT-9002", "Warning")]),
    )
    assert (report.tp, report.fp, report.fn) == (1, 0, 0)

