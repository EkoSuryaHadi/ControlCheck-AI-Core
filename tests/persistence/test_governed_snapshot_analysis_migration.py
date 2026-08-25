from __future__ import annotations

from datetime import date
from uuid import uuid4

from alembic import command
from sqlalchemy import text

from controlcheck.ingestion.profile import load_mapping_profile
from controlcheck.ingestion.service import SnapshotIngestionService
from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import (
    AnalysisRunRecord,
    DatasetSnapshotRecord,
    OrganizationRecord,
    ProjectRecord,
    RuleCatalogueVersionRecord,
    SourceFileRecord,
)
from controlcheck.storage import LocalFileStorage


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_downgrade_maps_governed_analysis_to_fresh_scoped_compatibility_snapshot(
    alembic_config,
    postgres_url,
    project_root,
    tmp_path,
):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)
    with session_factory() as session:
        governed_organization = OrganizationRecord(
            name="Governed analysis tenant",
            slug=f"governed-analysis-{uuid4().hex}",
        )
        collision_organization = OrganizationRecord(
            name="Unrelated simplified tenant",
            slug=f"simplified-collision-{uuid4().hex}",
        )
        session.add_all([governed_organization, collision_organization])
        session.flush()
        governed_project = ProjectRecord(
            organization_id=governed_organization.id,
            code="PRJ-CCAI-001",
            name="Governed project",
            currency="IDR",
        )
        collision_project = ProjectRecord(
            organization_id=collision_organization.id,
            code="UNRELATED",
            name="Unrelated project",
            currency="USD",
        )
        session.add_all([governed_project, collision_project])
        session.commit()

    storage = LocalFileStorage(tmp_path / "migration-storage")
    profile = load_mapping_profile(
        project_root / "data" / "controlcheck_mapping_profile_v0.1.json"
    )
    workbook = (
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    ).read_bytes()
    governed_snapshot = SnapshotIngestionService(
        session_factory,
        storage,
        profile,
    ).ingest(
        governed_organization.id,
        governed_project.id,
        "golden.xlsx",
        XLSX_MIME,
        workbook,
    ).snapshot

    with session_factory() as session:
        collision_source = SourceFileRecord(
            organization_id=collision_organization.id,
            project_id=collision_project.id,
            file_name="unrelated.xlsx",
            storage_key=f"unrelated/{uuid4()}.xlsx",
            mime_type=XLSX_MIME,
            file_size_bytes=1,
            sha256="b" * 64,
        )
        catalogue = RuleCatalogueVersionRecord(
            version="migration-test",
            sha256="c" * 64,
            definition={"version": "migration-test", "rules": []},
        )
        session.add_all([collision_source, catalogue])
        session.flush()
        collision = DatasetSnapshotRecord(
            id=governed_snapshot.id,
            organization_id=collision_organization.id,
            project_id=collision_project.id,
            source_file_id=collision_source.id,
            dataset_version="unrelated",
            data_date=date(2026, 1, 1),
            source_project_id="UNRELATED",
            status="validated",
        )
        run = AnalysisRunRecord(
            organization_id=governed_organization.id,
            project_id=governed_project.id,
            dataset_snapshot_id=None,
            governed_dataset_snapshot_id=governed_snapshot.id,
            catalogue_version_id=catalogue.id,
            engine_version="migration-test",
            workbook_sha256="a" * 64,
            status="succeeded",
            rule_count=0,
            finding_count=0,
        )
        session.add_all([collision, run])
        session.commit()
        run_id = run.id
        collision_snapshot_id = collision.id

    command.downgrade(alembic_config, "20260825_0009")

    with session_factory() as session:
        downgraded_run = session.execute(
            text(
                "SELECT dataset_snapshot_id, organization_id, project_id "
                "FROM analysis_runs WHERE id = :run_id"
            ),
            {"run_id": run_id},
        ).mappings().one()
        compatibility = session.execute(
            text(
                "SELECT organization_id, project_id, source_project_id "
                "FROM dataset_snapshots WHERE id = :snapshot_id"
            ),
            {"snapshot_id": downgraded_run["dataset_snapshot_id"]},
        ).mappings().one()
        collision_after = session.execute(
            text(
                "SELECT organization_id, project_id "
                "FROM dataset_snapshots WHERE id = :snapshot_id"
            ),
            {"snapshot_id": collision_snapshot_id},
        ).mappings().one()

    assert downgraded_run["dataset_snapshot_id"] != collision_snapshot_id
    assert downgraded_run["organization_id"] == governed_organization.id
    assert downgraded_run["project_id"] == governed_project.id
    assert compatibility["organization_id"] == governed_organization.id
    assert compatibility["project_id"] == governed_project.id
    assert compatibility["source_project_id"] == "PRJ-CCAI-001"
    assert collision_after["organization_id"] == collision_organization.id
    assert collision_after["project_id"] == collision_project.id
