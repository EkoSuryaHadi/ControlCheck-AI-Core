from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import func, select

from controlcheck.application import AnalysisService
from controlcheck.errors import ControlCheckApplicationError
from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import AnalysisRunRecord, FindingEvidenceRecord, FindingRecord, OrganizationRecord
from controlcheck.persistence.repositories import ProjectRepository
from controlcheck.storage import LocalFileStorage


ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture()
def phase4_database(alembic_config, postgres_url):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)
    with session_factory() as session:
        organization = OrganizationRecord(id=ORG_ID, name="Primary", slug=f"primary-{uuid4().hex[:8]}")
        session.add(organization)
        session.flush()
        golden = ProjectRepository(session).create(ORG_ID, "PRJ-CCAI-001", "Golden", "IDR")
        boundary = ProjectRepository(session).create(ORG_ID, "PRJ-CCAI-BND-001", "Boundary", "IDR")
        mismatch = ProjectRepository(session).create(ORG_ID, "WRONG-PROJECT", "Mismatch", "IDR")
        session.commit()
    return session_factory, golden.id, boundary.id, mismatch.id


def build_service(project_root, tmp_path, session_factory, audit_runner=None):
    return AnalysisService(
        session_factory=session_factory,
        storage=LocalFileStorage(tmp_path),
        catalogue_path=project_root / "data" / "controlcheck_rule_catalogue_v0.2.json",
        audit_runner=audit_runner,
    )


def scalar_count(session_factory, model, where=None):
    with session_factory() as session:
        statement = select(func.count()).select_from(model)
        if where is not None:
            statement = statement.where(where)
        return session.scalar(statement)


def test_golden_run_persists_59_findings_and_evidence(project_root, tmp_path, phase4_database):
    session_factory, golden_id, _, _ = phase4_database
    service = build_service(project_root, tmp_path, session_factory)
    data = (project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx").read_bytes()

    run = service.run(ORG_ID, golden_id, "golden.xlsx", XLSX_MIME, data)

    assert run.status == "succeeded"
    assert run.finding_count == 59
    assert scalar_count(session_factory, FindingRecord, FindingRecord.analysis_run_id == run.id) == 59
    assert scalar_count(session_factory, FindingEvidenceRecord) >= 59


def test_boundary_run_succeeds_with_zero_findings(project_root, tmp_path, phase4_database):
    session_factory, _, boundary_id, _ = phase4_database
    service = build_service(project_root, tmp_path, session_factory)
    data = (project_root / "data" / "ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx").read_bytes()

    run = service.run(ORG_ID, boundary_id, "boundary.xlsx", XLSX_MIME, data)

    assert run.status == "succeeded"
    assert run.finding_count == 0
    assert scalar_count(session_factory, FindingRecord, FindingRecord.analysis_run_id == run.id) == 0


def test_workbook_project_mismatch_creates_no_run(project_root, tmp_path, phase4_database):
    session_factory, _, _, mismatch_id = phase4_database
    service = build_service(project_root, tmp_path, session_factory)
    data = (project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx").read_bytes()

    with pytest.raises(ControlCheckApplicationError) as caught:
        service.run(ORG_ID, mismatch_id, "golden.xlsx", XLSX_MIME, data)

    assert caught.value.code == "workbook_project_mismatch"
    assert scalar_count(session_factory, AnalysisRunRecord) == 0
    assert list(tmp_path.rglob("*.xlsx")) == []


def test_failed_engine_run_has_no_partial_findings(project_root, tmp_path, phase4_database):
    session_factory, golden_id, _, _ = phase4_database

    def failing_runner(*args, **kwargs):
        raise RuntimeError("unsafe internal detail")

    service = build_service(project_root, tmp_path, session_factory, audit_runner=failing_runner)
    data = (project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx").read_bytes()

    with pytest.raises(ControlCheckApplicationError) as caught:
        service.run(ORG_ID, golden_id, "golden.xlsx", XLSX_MIME, data)

    assert caught.value.code == "analysis_failed"
    assert caught.value.analysis_run_id is not None
    with session_factory() as session:
        run = session.get(AnalysisRunRecord, caught.value.analysis_run_id)
        assert run.status == "failed"
        assert run.safe_error_message == "Analysis could not be completed"
    assert scalar_count(session_factory, FindingRecord) == 0
