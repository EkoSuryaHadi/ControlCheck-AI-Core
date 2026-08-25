from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from alembic import command

from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import (
    DatasetSnapshotRecord,
    GovernedDatasetDomainStatusRecord,
    GovernedRawRowRecord,
    OrganizationRecord,
    ProjectRecord,
    SourceFileRecord,
)
from controlcheck.storage import StoredObject


ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
PROJECT_ID = UUID("10000000-0000-0000-0000-000000000002")
LEGACY_SOURCE_ID = UUID("10000000-0000-0000-0000-000000000003")
LEGACY_SNAPSHOT_ID = UUID("10000000-0000-0000-0000-000000000004")


def test_repository_writes_governed_snapshots_and_reads_simplified_compatibly(
    alembic_config, postgres_url
) -> None:
    try:
        from controlcheck.persistence.ingestion_repositories import (
            SnapshotImmutableError,
            SnapshotRepository,
        )
    except ImportError:
        pytest.fail("governed SnapshotRepository is not implemented")

    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)
    long_project_name = "Governed Project " + ("X" * 600)

    with session_factory() as session:
        session.add(OrganizationRecord(id=ORG_ID, name="Org", slug="governed-org"))
        session.flush()
        session.add(
            ProjectRecord(
                id=PROJECT_ID,
                organization_id=ORG_ID,
                code="PRJ",
                name="Project",
                currency="IDR",
                status="active",
            )
        )
        session.flush()
        session.add(
            SourceFileRecord(
                id=LEGACY_SOURCE_ID,
                organization_id=ORG_ID,
                project_id=PROJECT_ID,
                file_name="legacy.xlsx",
                storage_key="legacy/legacy.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                file_size_bytes=1,
                sha256="a" * 64,
            )
        )
        session.flush()
        session.add(
            DatasetSnapshotRecord(
                id=LEGACY_SNAPSHOT_ID,
                organization_id=ORG_ID,
                project_id=PROJECT_ID,
                source_file_id=LEGACY_SOURCE_ID,
                dataset_version="0.1",
                data_date=date(2026, 8, 24),
                source_project_id="LEGACY",
                status="validated",
            )
        )
        session.commit()

        repository = SnapshotRepository(session)
        profile = repository.resolve_mapping_profile(
            version="0.1",
            sha256="b" * 64,
            definition={"domains": {"budget": {"sheet": "Budget"}}},
        )
        governed = repository.create_ingesting(
            organization_id=ORG_ID,
            project_id=PROJECT_ID,
            filename="governed.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            stored=StoredObject(key="governed/governed.xlsx", size_bytes=2, sha256="c" * 64),
            mapping_profile_version_id=profile.id,
            dataset_version="0.1",
            data_date=date(2026, 8, 25),
            source_project_id="GOVERNED",
            source_project_name=long_project_name,
            dedupe_key="d" * 64,
        )
        raw_values = {
            "x": "first",
            "x__duplicate_2": "second",
            "x__duplicate_3": "third",
            "__unnamed_column_4": "fourth",
            "__unnamed_column_4__duplicate_2": "fifth",
        }
        raw_row = GovernedRawRowRecord(
            organization_id=ORG_ID,
            project_id=PROJECT_ID,
            dataset_snapshot_id=governed.id,
            import_batch_id=governed.import_batch_id,
            domain="budget",
            source_sheet="Budget",
            source_row_number=7,
            row_hash="e" * 64,
            raw_data=raw_values,
            validation_status="valid",
            validation_errors=[],
        )
        session.add(raw_row)
        for domain in (
            "actual_cost",
            "budget",
            "commitments",
            "progress",
            "schedule",
            "wbs",
        ):
            session.add(
                GovernedDatasetDomainStatusRecord(
                    organization_id=ORG_ID,
                    project_id=PROJECT_ID,
                    dataset_snapshot_id=governed.id,
                    domain=domain,
                    status="valid",
                    row_count_raw=1 if domain == "budget" else 0,
                    row_count_canonical=1 if domain == "budget" else 0,
                    error_count=0,
                    warning_count=0,
                    validation_summary={},
                )
            )
        session.flush()
        repository.complete(
            ORG_ID,
            PROJECT_ID,
            governed.id,
            status="validated",
            row_count_raw=1,
            row_count_canonical=1,
        )
        session.commit()

        items = repository.list_scoped(ORG_ID, PROJECT_ID)
        by_id = {item.id: item for item in items}
        session.refresh(raw_row)
        assert raw_row.raw_data == raw_values
        assert isinstance(raw_row.id, int)
        assert by_id[governed.id].storage_contract == "governed"
        assert by_id[governed.id].source_project_name == long_project_name
        assert by_id[LEGACY_SNAPSHOT_ID].storage_contract == "simplified"
        assert by_id[LEGACY_SNAPSHOT_ID].source_project_name is None
        assert repository.get_scoped(ORG_ID, PROJECT_ID, LEGACY_SNAPSHOT_ID) == by_id[
            LEGACY_SNAPSHOT_ID
        ]

        with pytest.raises(SnapshotImmutableError, match="immutable"):
            repository.complete(
                ORG_ID,
                PROJECT_ID,
                governed.id,
                status="validated_with_errors",
                row_count_raw=2,
                row_count_canonical=1,
            )
