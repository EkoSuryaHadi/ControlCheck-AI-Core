from __future__ import annotations

from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import select

from controlcheck.application import AnalysisService
from controlcheck.engine import ControlEngine
from controlcheck.errors import ControlCheckApplicationError
from controlcheck.ingestion.profile import load_mapping_profile
from controlcheck.ingestion.service import SnapshotIngestionService
from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import (
    AnalysisRunRecord,
    GovernedDatasetDomainStatusRecord,
    FindingEvidenceRecord,
    FindingRecord,
    OrganizationRecord,
    ProjectRecord,
    SourceFileRecord,
)
from controlcheck.rules import ALL_RULES
from controlcheck.storage import LocalFileStorage


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture()
def snapshot_harness(alembic_config, postgres_url, project_root, tmp_path):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)
    with session_factory() as session:
        organization = OrganizationRecord(
            name="Snapshot analysis organization",
            slug=f"snapshot-analysis-{uuid4().hex}",
        )
        session.add(organization)
        session.flush()
        project = ProjectRecord(
            organization_id=organization.id,
            code="PRJ-CCAI-001",
            name="Mutable project master name",
            currency="IDR",
        )
        session.add(project)
        session.commit()

    storage = LocalFileStorage(tmp_path / "storage")
    profile = load_mapping_profile(
        project_root / "data" / "controlcheck_mapping_profile_v0.1.json"
    )
    ingestion = SnapshotIngestionService(session_factory, storage, profile)
    data = (
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    ).read_bytes()
    snapshot = ingestion.ingest(
        organization.id,
        project.id,
        "golden.xlsx",
        XLSX_MIME,
        data,
    )
    service = AnalysisService(
        session_factory=session_factory,
        storage=storage,
        catalogue_path=project_root / "data" / "controlcheck_rule_catalogue_v0.3.json",
    )
    return session_factory, storage, service, organization.id, project.id, snapshot


def test_snapshot_analysis_uses_database_and_persists_lineage(snapshot_harness):
    session_factory, storage, service, organization_id, project_id, snapshot = snapshot_harness
    with session_factory() as session:
        source = session.get(SourceFileRecord, snapshot.source_file_id)
        storage.delete(source.storage_key)

    run = service.run_snapshot(organization_id, project_id, snapshot.id)

    assert run.status == "succeeded"
    assert run.finding_count == 59
    assert run.rule_count == 20
    assert run.executed_rule_ids == sorted(run.executed_rule_ids)
    assert len(run.executed_rule_ids) == 20
    assert run.skipped_rules == []
    with session_factory() as session:
        evidence = session.scalars(
            select(FindingEvidenceRecord)
            .join(FindingRecord, FindingRecord.id == FindingEvidenceRecord.finding_id)
            .where(FindingRecord.analysis_run_id == run.id)
        ).all()
    assert evidence
    assert all(item.raw_row_ids for item in evidence)
    assert all(all(isinstance(raw_id, int) for raw_id in item.raw_row_ids) for item in evidence)


def test_snapshot_analysis_persists_progress_domain_skips(snapshot_harness):
    session_factory, _, service, organization_id, project_id, snapshot = snapshot_harness
    with session_factory() as session:
        progress = session.scalar(
            select(GovernedDatasetDomainStatusRecord).where(
                GovernedDatasetDomainStatusRecord.dataset_snapshot_id == snapshot.id,
                GovernedDatasetDomainStatusRecord.domain == "progress",
            )
        )
        progress.status = "blocked"
        session.commit()

    run = service.run_snapshot(organization_id, project_id, snapshot.id)

    assert run.executed_rule_ids == sorted(run.executed_rule_ids)
    assert {item["rule_id"] for item in run.skipped_rules} == {
        "DQ-001",
        "DQ-003",
        "DQ-004",
        "CST-006",
        "PRG-001",
        "PRG-002",
        "PRG-003",
        "XDOM-001",
    }
    assert all(item["reason_code"] == "blocked_required_domain" for item in run.skipped_rules)
    assert "CST-001" in run.executed_rule_ids
    assert run.rule_count == 12


def test_snapshot_analysis_failure_has_no_partial_findings(snapshot_harness, project_root):
    session_factory, storage, _, organization_id, project_id, snapshot = snapshot_harness

    class FailingEngine(ControlEngine):
        def run_gated(self, *args, **kwargs):
            raise RuntimeError("unsafe internal detail")

    service = AnalysisService(
        session_factory=session_factory,
        storage=storage,
        catalogue_path=project_root / "data" / "controlcheck_rule_catalogue_v0.3.json",
        engine=FailingEngine(ALL_RULES),
    )

    with pytest.raises(ControlCheckApplicationError) as caught:
        service.run_snapshot(organization_id, project_id, snapshot.id)

    assert caught.value.code == "analysis_failed"
    with session_factory() as session:
        run = session.get(AnalysisRunRecord, caught.value.analysis_run_id)
        findings = session.scalars(
            select(FindingRecord).where(FindingRecord.analysis_run_id == run.id)
        ).all()
    assert run.status == "failed"
    assert findings == []
