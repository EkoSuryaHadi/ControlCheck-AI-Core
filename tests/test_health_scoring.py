from unittest.mock import MagicMock
from uuid import uuid4

from controlcheck.health.scoring import compute_health_score, determine_score_band
from controlcheck.models import Finding
from controlcheck.persistence.models import HealthSnapshotRecord
from controlcheck.persistence.repositories import HealthRepository


def test_health_score_with_zero_findings():
    result = compute_health_score([])
    assert result.overall_score == 100.0
    assert result.score_band == "Healthy"
    assert result.category_scores["COST"].score == 100.0
    assert result.category_scores["SCHEDULE"].score == 100.0
    assert result.category_scores["PROGRESS"].score == 100.0
    assert result.category_scores["DATA_QUALITY"].score == 100.0
    assert len(result.top_drivers) == 0


def test_health_score_formula_and_bands():
    # 2 critical cost findings (-30 points -> 70.0 * 0.30 = 21.0)
    # 1 critical schedule finding (-15 points -> 85.0 * 0.30 = 25.5)
    # 0 progress findings (100.0 * 0.25 = 25.0)
    # 1 warning DQ finding (-5 points -> 95.0 * 0.15 = 14.25)
    # Expected overall: 21.0 + 25.5 + 25.0 + 14.25 = 85.75 -> "Healthy"

    findings = [
        Finding(
            finding_id="F1",
            project_id="PRJ-1",
            rule_id="CST-001",
            rule_name="Actual Exceeds Budget",
            entity_type="WBS",
            entity_id="1.0",
            category="COST",
            severity="critical",
            title="Cost overrun",
            description="WBS 1.0 cost exceeded budget",
            metrics={},
            calculation={},
            business_impact="Impact",
            recommendation="Action",
            evidence=[],
        ),
        Finding(
            finding_id="F2",
            project_id="PRJ-1",
            rule_id="CST-002",
            rule_name="Exposure Exceeds Budget",
            entity_type="WBS",
            entity_id="2.0",
            category="COST",
            severity="critical",
            title="Exposure overrun",
            description="WBS 2.0 exposure exceeded budget",
            metrics={},
            calculation={},
            business_impact="Impact",
            recommendation="Action",
            evidence=[],
        ),
        Finding(
            finding_id="F3",
            project_id="PRJ-1",
            rule_id="SCH-001",
            rule_name="Overdue Activity",
            entity_type="Activity",
            entity_id="ACT-10",
            category="SCHEDULE",
            severity="critical",
            title="Overdue activity",
            description="Activity is delayed",
            metrics={},
            calculation={},
            business_impact="Impact",
            recommendation="Action",
            evidence=[],
        ),
        Finding(
            finding_id="F4",
            project_id="PRJ-1",
            rule_id="DQ-001",
            rule_name="Missing WBS",
            entity_type="Transaction",
            entity_id="TX-100",
            category="DATA_QUALITY",
            severity="warning",
            title="Missing WBS reference",
            description="Transaction without WBS",
            metrics={},
            calculation={},
            business_impact="Impact",
            recommendation="Action",
            evidence=[],
        ),
    ]


    result = compute_health_score(findings)

    assert result.category_scores["COST"].score == 70.0
    assert result.category_scores["SCHEDULE"].score == 85.0
    assert result.category_scores["PROGRESS"].score == 100.0
    assert result.category_scores["DATA_QUALITY"].score == 95.0
    assert result.overall_score == 85.75
    assert result.score_band == "Healthy"
    assert len(result.top_drivers) == 4


def test_determine_score_band():
    assert determine_score_band(95.0) == "Healthy"
    assert determine_score_band(80.0) == "Healthy"
    assert determine_score_band(79.9) == "Needs Attention"
    assert determine_score_band(60.0) == "Needs Attention"
    assert determine_score_band(59.9) == "At Risk"
    assert determine_score_band(40.0) == "At Risk"
    assert determine_score_band(39.9) == "Critical"
    assert determine_score_band(0.0) == "Critical"


def test_health_repository_crud():
    mock_session = MagicMock()
    org_id = uuid4()
    proj_id = uuid4()
    run_id = uuid4()

    repo = HealthRepository(mock_session)

    record = repo.create_snapshot(
        organization_id=org_id,
        project_id=proj_id,
        analysis_run_id=run_id,
        overall_score=85.0,
        cost_score=80.0,
        schedule_score=90.0,
        progress_score=90.0,
        dq_score=80.0,
        score_band="Healthy",
        component_breakdown={"COST": {"score": 80.0}},
        key_drivers=[],
    )

    assert record.overall_score == 85.0
    assert record.score_band == "Healthy"
    mock_session.add.assert_called_once_with(record)
    mock_session.flush.assert_called_once()
