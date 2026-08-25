from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

import openpyxl
import pytest
from alembic import command
from sqlalchemy import func, select

from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import (
    AnalysisRunRecord,
    GovernedActualCostRecord,
    GovernedBudgetRecord,
    GovernedCommitmentRecord,
    GovernedDatasetSnapshotRecord,
    GovernedDatasetDomainStatusRecord,
    GovernedProgressRecord,
    GovernedRawRowRecord,
    GovernedScheduleActivityRecord,
    GovernedWBSNodeRecord,
    OrganizationRecord,
    ProjectRecord,
    SourceFileRecord,
)
from controlcheck.storage import LocalFileStorage


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GOVERNED_FACT_MODELS = (
    GovernedWBSNodeRecord,
    GovernedBudgetRecord,
    GovernedActualCostRecord,
    GovernedCommitmentRecord,
    GovernedScheduleActivityRecord,
    GovernedProgressRecord,
)


@pytest.fixture()
def governed_runtime(alembic_config, postgres_url, project_root: Path, tmp_path: Path):
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)
    with session_factory() as session:
        organization = OrganizationRecord(
            name="Governed runtime organization",
            slug=f"governed-runtime-{uuid4().hex}",
        )
        session.add(organization)
        session.flush()
        project = ProjectRecord(
            organization_id=organization.id,
            code="PRJ-CCAI-001",
            name="Mutable project master name",
            currency="IDR",
            status="active",
        )
        session.add(project)
        session.commit()
    storage = LocalFileStorage(tmp_path / "storage")
    golden = (
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    ).read_bytes()
    return (
        session_factory,
        storage,
        project_root / "data" / "controlcheck_mapping_profile_v0.1.json",
        organization.id,
        project.id,
        golden,
    )


def _service(session_factory, storage, profile_path):
    from controlcheck.ingestion.profile import load_mapping_profile
    from controlcheck.ingestion.service import SnapshotIngestionService

    return SnapshotIngestionService(
        session_factory,
        storage,
        load_mapping_profile(profile_path),
    )


def _stored_files(storage: LocalFileStorage) -> list[Path]:
    return sorted(path for path in storage.root.rglob("*") if path.is_file())


def test_ingestion_writes_complete_governed_snapshot_and_preserves_project_name(
    governed_runtime,
) -> None:
    session_factory, storage, profile_path, organization_id, project_id, golden = (
        governed_runtime
    )
    service = _service(session_factory, storage, profile_path)
    source_project_name = "  Source Project " + ("X" * 300) + "  "
    book = openpyxl.load_workbook(BytesIO(golden))
    book["Project_Info"]["B3"] = source_project_name
    payload = BytesIO()
    book.save(payload)
    book.close()

    snapshot = service.ingest(
        organization_id,
        project_id,
        "golden.xlsx",
        XLSX_MIME,
        payload.getvalue(),
    )

    with session_factory() as session:
        persisted = session.get(GovernedDatasetSnapshotRecord, snapshot.id)
        raw_count = session.scalar(
            select(func.count())
            .select_from(GovernedRawRowRecord)
            .where(GovernedRawRowRecord.dataset_snapshot_id == snapshot.id)
        )
        canonical_count = sum(
            session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.dataset_snapshot_id == snapshot.id)
            )
            for model in GOVERNED_FACT_MODELS
        )

    assert persisted is not None
    assert persisted.status == "validated"
    assert persisted.source_project_name == source_project_name
    assert persisted.row_count_raw == raw_count == 149
    assert persisted.row_count_canonical == canonical_count == 149


def test_ingestion_failure_rolls_back_partial_snapshot_and_deletes_object(
    governed_runtime, monkeypatch
) -> None:
    from controlcheck.persistence.ingestion_repositories import SnapshotRepository

    session_factory, storage, profile_path, organization_id, project_id, golden = (
        governed_runtime
    )
    service = _service(session_factory, storage, profile_path)

    def fail_canonical_write(*args, **kwargs):
        raise RuntimeError("injected canonical database failure")

    monkeypatch.setattr(
        SnapshotRepository, "persist_canonical_rows", fail_canonical_write
    )

    with pytest.raises(RuntimeError, match="injected canonical database failure"):
        service.ingest(
            organization_id,
            project_id,
            "golden.xlsx",
            XLSX_MIME,
            golden,
        )

    with session_factory() as session:
        snapshot_count = session.scalar(
            select(func.count())
            .select_from(GovernedDatasetSnapshotRecord)
            .where(
                GovernedDatasetSnapshotRecord.organization_id == organization_id,
                GovernedDatasetSnapshotRecord.project_id == project_id,
            )
        )
        source_count = session.scalar(
            select(func.count())
            .select_from(SourceFileRecord)
            .where(
                SourceFileRecord.organization_id == organization_id,
                SourceFileRecord.project_id == project_id,
            )
        )

    assert snapshot_count == 0
    assert source_count == 0
    assert _stored_files(storage) == []


def test_database_loader_reconstructs_engine_dataset_without_source_object(
    governed_runtime,
) -> None:
    from controlcheck.persistence.dataset_loader import DatabaseDatasetLoader

    session_factory, storage, profile_path, organization_id, project_id, golden = (
        governed_runtime
    )
    service = _service(session_factory, storage, profile_path)
    snapshot = service.ingest(
        organization_id, project_id, "golden.xlsx", XLSX_MIME, golden
    )
    with session_factory() as session:
        source = session.get(SourceFileRecord, snapshot.source_file_id)
        assert source is not None
        storage.delete(source.storage_key)

    loaded = DatabaseDatasetLoader(session_factory).load(
        organization_id, project_id, snapshot.id
    )

    assert loaded.snapshot.project.project_name == (
        "EPC Gas Compression Facility Expansion"
    )
    assert len(loaded.snapshot.actual_costs) == 73
    assert len(loaded.raw_row_index) == 149
    assert all(isinstance(raw_row_id, int) for raw_row_id in loaded.raw_row_index.values())


def test_snapshot_analysis_persists_deterministic_domain_skip_metadata(
    governed_runtime, project_root: Path
) -> None:
    from controlcheck.application import AnalysisService

    session_factory, storage, profile_path, organization_id, project_id, golden = (
        governed_runtime
    )
    snapshot = _service(session_factory, storage, profile_path).ingest(
        organization_id, project_id, "golden.xlsx", XLSX_MIME, golden
    )
    with session_factory() as session:
        progress = session.scalar(
            select(GovernedDatasetDomainStatusRecord).where(
                GovernedDatasetDomainStatusRecord.dataset_snapshot_id
                == snapshot.id,
                GovernedDatasetDomainStatusRecord.domain == "progress",
            )
        )
        assert progress is not None
        progress.status = "blocked"
        session.commit()

    run = AnalysisService(
        session_factory,
        storage,
        project_root / "data" / "controlcheck_rule_catalogue_v0.3.json",
    ).run_snapshot(organization_id, project_id, snapshot.id)

    expected_skips = {
        "DQ-001",
        "DQ-003",
        "DQ-004",
        "CST-006",
        "PRG-001",
        "PRG-002",
        "PRG-003",
        "XDOM-001",
    }
    assert run.rule_count == 12
    assert run.executed_rule_ids == sorted(run.executed_rule_ids)
    assert {item["rule_id"] for item in run.skipped_rules} == expected_skips
    assert all(
        item["reason_code"] == "blocked_required_domain"
        and item["blocked_domains"] == ["progress"]
        for item in run.skipped_rules
    )
    with session_factory() as session:
        persisted = session.get(AnalysisRunRecord, run.id)
        assert persisted is not None
        assert persisted.skipped_rules == run.skipped_rules
