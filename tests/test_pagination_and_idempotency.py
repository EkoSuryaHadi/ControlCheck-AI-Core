from unittest.mock import MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from controlcheck.persistence.models import ProjectRecord, AnalysisRunRecord, FindingRecord
from controlcheck.persistence.repositories import ProjectRepository, AnalysisRepository, FindingRepository


def test_project_repository_pagination():
    mock_session = MagicMock()
    org_id = uuid4()

    # Mock count
    mock_session.scalar.return_value = 10
    # Mock items
    mock_projects = [
        ProjectRecord(
            id=uuid4(),
            organization_id=org_id,
            code=f"PRJ-{i}",
            name=f"Project {i}",
            currency="IDR",
        )
        for i in range(5)
    ]
    mock_session.scalars.return_value = mock_projects

    repo = ProjectRepository(mock_session)
    items, total = repo.list_for_organization(org_id, limit=5, offset=0)

    assert len(items) == 5
    assert total == 10


def test_analysis_repository_pagination():
    mock_session = MagicMock()
    org_id = uuid4()
    proj_id = uuid4()

    mock_session.scalar.return_value = 8
    mock_runs = [
        AnalysisRunRecord(
            id=uuid4(),
            organization_id=org_id,
            project_id=proj_id,
            dataset_snapshot_id=uuid4(),
            catalogue_version_id=uuid4(),
            engine_version="0.2.0",
            workbook_sha256="a" * 64,
            status="succeeded",
            started_at=datetime.now(timezone.utc),
        )
        for _ in range(3)
    ]
    mock_session.scalars.return_value = mock_runs

    repo = AnalysisRepository(mock_session)
    items, total = repo.list_runs(org_id, proj_id, limit=3, offset=0)

    assert len(items) == 3
    assert total == 8


def test_finding_repository_pagination():
    mock_session = MagicMock()
    org_id = uuid4()
    run_id = uuid4()

    mock_session.scalar.return_value = 59
    mock_findings = [
        FindingRecord(
            id=uuid4(),
            analysis_run_id=run_id,
            organization_id=org_id,
            project_id=uuid4(),
            engine_finding_id=f"FIND-{i}",
            rule_id="CST-001",
            rule_name="Actual Exceeds Budget",
            entity_type="WBS",
            entity_id=f"WBS-{i}",
            category="COST",
            severity="critical",
            status="open",
            title=f"Finding {i}",
            description="desc",
            metrics={},
            calculation={},
            business_impact="impact",
            recommendation="rec",
            confidence=1.0,
        )
        for i in range(10)
    ]
    mock_session.scalars.return_value = mock_findings

    repo = FindingRepository(mock_session)
    items, total = repo.list_for_run(org_id, run_id, limit=10, offset=0)

    assert len(items) == 10
    assert total == 59


def test_idempotency_key_lookup():
    mock_session = MagicMock()
    org_id = uuid4()
    proj_id = uuid4()
    run_id = uuid4()
    key = "idem-key-123"

    mock_log = MagicMock()
    mock_log.entity_id = str(run_id)
    mock_session.scalar.return_value = mock_log

    repo = AnalysisRepository(mock_session)
    # mock get_run
    mock_run = MagicMock()
    mock_run.id = run_id
    repo.get_run = MagicMock(return_value=mock_run)

    res = repo.get_run_by_idempotency_key(org_id, proj_id, key)
    assert res is not None
    assert res.id == run_id
