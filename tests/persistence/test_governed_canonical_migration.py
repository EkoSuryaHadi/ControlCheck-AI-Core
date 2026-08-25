from __future__ import annotations

from uuid import UUID

from alembic import command
from sqlalchemy import BigInteger, Text, create_engine, inspect, text
from sqlalchemy.dialects import postgresql


HOMEPAGE_HEAD = "20260823_0008"
GOVERNED_HEAD = "20260825_0009"
GOVERNED_TABLES = {
    "governed_mapping_profile_versions",
    "governed_dataset_snapshots",
    "governed_import_batches",
    "governed_dataset_domain_statuses",
    "governed_raw_rows",
    "governed_wbs_nodes",
    "governed_budget_records",
    "governed_actual_cost_records",
    "governed_commitment_records",
    "governed_schedule_activities",
    "governed_progress_records",
}
SIMPLIFIED_TABLES = {
    "dataset_snapshots",
    "import_batches",
    "raw_rows",
    "wbs_nodes",
    "budget_records",
    "cost_records",
    "commitment_records",
    "schedule_activities",
    "progress_records",
}
CANONICAL_TABLES = {
    "governed_wbs_nodes",
    "governed_budget_records",
    "governed_actual_cost_records",
    "governed_commitment_records",
    "governed_schedule_activities",
    "governed_progress_records",
}


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _columns(inspector, table_name: str) -> dict[str, dict]:
    return {column["name"]: column for column in inspector.get_columns(table_name)}


def _unique_sets(inspector, table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(table_name)
    }


def _foreign_keys(inspector, table_name: str) -> set[tuple[tuple[str, ...], str, tuple[str, ...]]]:
    return {
        (
            tuple(constraint["constrained_columns"]),
            constraint["referred_table"],
            tuple(constraint["referred_columns"]),
        )
        for constraint in inspector.get_foreign_keys(table_name)
    }


def _seed_homepage_snapshot(database_url: str) -> UUID:
    snapshot_id = UUID("00000000-0000-0000-0000-000000000004")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO organizations (id, name, slug)
                    VALUES ('00000000-0000-0000-0000-000000000001', 'Legacy Org', 'legacy-org');
                    INSERT INTO projects (id, organization_id, code, name)
                    VALUES (
                        '00000000-0000-0000-0000-000000000002',
                        '00000000-0000-0000-0000-000000000001',
                        'LEGACY', 'Legacy Project'
                    );
                    INSERT INTO source_files (
                        id, organization_id, project_id, file_name, storage_key,
                        mime_type, file_size_bytes, sha256
                    ) VALUES (
                        '00000000-0000-0000-0000-000000000003',
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        'legacy.xlsx', 'legacy/legacy.xlsx',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        1, repeat('a', 64)
                    );
                    INSERT INTO dataset_snapshots (
                        id, organization_id, project_id, source_file_id,
                        dataset_version, data_date, source_project_id, status
                    ) VALUES (
                        '00000000-0000-0000-0000-000000000004',
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        '00000000-0000-0000-0000-000000000003',
                        '0.1', DATE '2026-08-24', 'LEGACY', 'validated'
                    );
                    """
                )
            )
    finally:
        engine.dispose()
    return snapshot_id


def test_governed_upgrade_from_homepage_head_is_additive(
    alembic_config, postgres_url
) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, HOMEPAGE_HEAD)
    legacy_snapshot_id = _seed_homepage_snapshot(postgres_url)

    engine = create_engine(postgres_url)
    try:
        before = inspect(engine)
        simplified_columns = {
            table_name: _column_names(before, table_name)
            for table_name in SIMPLIFIED_TABLES
        }
    finally:
        engine.dispose()

    command.upgrade(alembic_config, "head")

    engine = create_engine(postgres_url)
    try:
        after = inspect(engine)
        assert GOVERNED_TABLES <= set(after.get_table_names())
        for table_name, expected_columns in simplified_columns.items():
            assert _column_names(after, table_name) == expected_columns
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT status FROM dataset_snapshots WHERE id = :snapshot_id"),
                {"snapshot_id": legacy_snapshot_id},
            ) == "validated"
    finally:
        engine.dispose()


def test_governed_schema_pins_lossless_rows_and_snapshot_scoped_links(
    alembic_config, postgres_url
) -> None:
    command.upgrade(alembic_config, "head")
    engine = create_engine(postgres_url)
    try:
        inspector = inspect(engine)
        snapshot_columns = _columns(inspector, "governed_dataset_snapshots")
        raw_columns = _columns(inspector, "governed_raw_rows")
        assert isinstance(snapshot_columns["source_project_name"]["type"], Text)
        assert isinstance(raw_columns["id"]["type"], BigInteger)
        assert isinstance(raw_columns["raw_data"]["type"], postgresql.JSONB)
        assert isinstance(raw_columns["validation_errors"]["type"], postgresql.JSONB)
        assert (
            ("mapping_profile_version_id",),
            "governed_mapping_profile_versions",
            ("id",),
        ) in _foreign_keys(inspector, "governed_dataset_snapshots")
        assert (
            "dataset_snapshot_id",
            "domain",
            "source_sheet",
            "source_row_number",
        ) in _unique_sets(inspector, "governed_raw_rows")
        assert (
            ("dataset_snapshot_id", "import_batch_id"),
            "governed_import_batches",
            ("dataset_snapshot_id", "id"),
        ) in _foreign_keys(inspector, "governed_raw_rows")

        for table_name in CANONICAL_TABLES:
            columns = _columns(inspector, table_name)
            assert isinstance(columns["raw_row_id"]["type"], BigInteger)
            assert ("dataset_snapshot_id", "source_key") in _unique_sets(
                inspector, table_name
            )
            assert (
                ("dataset_snapshot_id", "raw_row_id"),
                "governed_raw_rows",
                ("dataset_snapshot_id", "id"),
            ) in _foreign_keys(inspector, table_name)
        for table_name in CANONICAL_TABLES - {"governed_wbs_nodes"}:
            assert (
                ("dataset_snapshot_id", "wbs_node_id"),
                "governed_wbs_nodes",
                ("dataset_snapshot_id", "id"),
            ) in _foreign_keys(inspector, table_name)
    finally:
        engine.dispose()


def test_governed_downgrade_boundary_preserves_homepage_data(
    alembic_config, postgres_url
) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, HOMEPAGE_HEAD)
    legacy_snapshot_id = _seed_homepage_snapshot(postgres_url)
    command.upgrade(alembic_config, GOVERNED_HEAD)

    command.downgrade(alembic_config, HOMEPAGE_HEAD)

    engine = create_engine(postgres_url)
    try:
        inspector = inspect(engine)
        assert not (GOVERNED_TABLES & set(inspector.get_table_names()))
        assert SIMPLIFIED_TABLES <= set(inspector.get_table_names())
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT status FROM dataset_snapshots WHERE id = :snapshot_id"),
                {"snapshot_id": legacy_snapshot_id},
            ) == "validated"
    finally:
        engine.dispose()
