from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import openpyxl
import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select

from controlcheck.api import create_app
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
    HealthSnapshotRecord,
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
    with session_factory() as session:
        health = session.scalar(
            select(HealthSnapshotRecord).where(
                HealthSnapshotRecord.analysis_run_id == run.id
            )
        )
    assert health.computation_status == "partial"
    assert health.coverage_ratio == pytest.approx(12 / 20)
    assert health.unavailable_domains == ["progress"]
    assert health.overall_score is None
    assert health.score_band == "Partial"

    response = TestClient(create_app(session_factory=session_factory)).get(
        f"/v1/analysis-runs/{run.id}/health",
        headers={"X-Organization-ID": str(organization_id)},
    )
    assert response.status_code == 200
    assert response.json()["overall_score"] is None
    assert response.json()["computation_status"] == "partial"
    assert response.json()["score_band"] == "Partial"


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


def test_governed_run_cannot_bypass_blocked_domains_through_audit_runner(
    snapshot_harness,
    project_root,
):
    session_factory, storage, _, organization_id, project_id, _ = snapshot_harness
    data = (
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    ).read_bytes()
    book = openpyxl.load_workbook(BytesIO(data))
    book.remove(book["Progress"])
    changed = BytesIO()
    book.save(changed)
    book.close()

    def forbidden_raw_workbook_runner(*args, **kwargs):
        raise AssertionError("governed analysis invoked the raw workbook runner")

    service = AnalysisService(
        session_factory=session_factory,
        storage=storage,
        catalogue_path=project_root / "data" / "controlcheck_rule_catalogue_v0.3.json",
        audit_runner=forbidden_raw_workbook_runner,
    )

    run = service.run(
        organization_id,
        project_id,
        "missing-progress.xlsx",
        XLSX_MIME,
        changed.getvalue(),
    )

    expected_skips = {
        "CST-006",
        "DQ-001",
        "DQ-003",
        "DQ-004",
        "PRG-001",
        "PRG-002",
        "PRG-003",
        "XDOM-001",
    }
    assert run.status == "succeeded"
    assert run.rule_count == 12
    assert {item["rule_id"] for item in run.skipped_rules} == expected_skips
    assert all(
        item["reason_code"] == "blocked_required_domain"
        and item["blocked_domains"] == ["progress"]
        for item in run.skipped_rules
    )
    with session_factory() as session:
        persisted = session.get(AnalysisRunRecord, run.id)
    assert persisted.executed_rule_ids == run.executed_rule_ids
    assert persisted.skipped_rules == run.skipped_rules


def test_snapshot_analysis_treats_absent_domain_states_as_blocked(snapshot_harness):
    session_factory, _, service, organization_id, project_id, snapshot = snapshot_harness
    with session_factory() as session:
        for state in session.scalars(
            select(GovernedDatasetDomainStatusRecord).where(
                GovernedDatasetDomainStatusRecord.dataset_snapshot_id == snapshot.id
            )
        ):
            session.delete(state)
        session.commit()

    run = service.run_snapshot(organization_id, project_id, snapshot.id)

    assert run.status == "succeeded"
    assert run.rule_count == 0
    assert run.executed_rule_ids == []
    assert len(run.skipped_rules) == 20
    assert all(
        item["reason_code"] == "blocked_required_domain"
        and item["blocked_domains"]
        for item in run.skipped_rules
    )
    with session_factory() as session:
        health = session.scalar(
            select(HealthSnapshotRecord).where(
                HealthSnapshotRecord.analysis_run_id == run.id
            )
        )
    assert health.computation_status == "not_computed"
    assert health.coverage_ratio == 0
    assert health.unavailable_domains == [
        "actual_cost",
        "budget",
        "commitments",
        "progress",
        "schedule",
        "wbs",
    ]
    assert health.overall_score is None
    assert health.cost_score is None
    assert health.schedule_score is None
    assert health.progress_score is None
    assert health.dq_score is None
    assert health.score_band == "Not Computed"

    response = TestClient(create_app(session_factory=session_factory)).get(
        f"/v1/analysis-runs/{run.id}/health",
        headers={"X-Organization-ID": str(organization_id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_score"] is None
    assert body["cost_score"] is None
    assert body["computation_status"] == "not_computed"
    assert body["score_band"] == "Not Computed"


def test_snapshot_analysis_treats_missing_partial_domain_states_as_blocked(
    snapshot_harness,
):
    session_factory, _, service, organization_id, project_id, snapshot = snapshot_harness
    with session_factory() as session:
        for state in session.scalars(
            select(GovernedDatasetDomainStatusRecord).where(
                GovernedDatasetDomainStatusRecord.dataset_snapshot_id == snapshot.id,
                GovernedDatasetDomainStatusRecord.domain != "actual_cost",
            )
        ):
            session.delete(state)
        session.commit()

    run = service.run_snapshot(organization_id, project_id, snapshot.id)

    assert run.executed_rule_ids == ["CST-004", "DQ-002", "DQ-005"]
    assert run.rule_count == 3
    assert len(run.skipped_rules) == 17
    assert all(
        item["reason_code"] == "blocked_required_domain"
        and set(item["blocked_domains"]).issubset(
            {"budget", "commitments", "progress", "schedule", "wbs"}
        )
        for item in run.skipped_rules
    )


def test_post_server_commit_exception_reconciles_succeeded_analysis(
    snapshot_harness,
    monkeypatch,
):
    session_factory, _, service, organization_id, project_id, snapshot = snapshot_harness
    session_class = session_factory.class_
    original_commit = session_class.commit
    injected = False

    def commit_then_raise(session):
        nonlocal injected
        completed_run = any(
            isinstance(item, AnalysisRunRecord) and item.status == "succeeded"
            for item in session.identity_map.values()
        )
        original_commit(session)
        if completed_run and not injected:
            injected = True
            raise RuntimeError("injected post-server-commit transport failure")

    monkeypatch.setattr(session_class, "commit", commit_then_raise)

    run = service.run_snapshot(organization_id, project_id, snapshot.id)

    assert injected
    assert run.status == "succeeded"
    assert run.finding_count == 59
    with session_factory() as session:
        persisted = session.get(AnalysisRunRecord, run.id)
        findings = session.scalars(
            select(FindingRecord).where(FindingRecord.analysis_run_id == run.id)
        ).all()
    assert persisted.status == "succeeded"
    assert persisted.safe_error_code is None
    assert len(findings) == 59
