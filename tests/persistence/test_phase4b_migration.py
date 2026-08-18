from __future__ import annotations

from uuid import UUID

from alembic import command
from sqlalchemy import create_engine, inspect, text


PHASE4B_TABLES = {
    "mapping_profile_versions",
    "import_batches",
    "raw_rows",
    "dataset_domain_statuses",
    "wbs_nodes",
    "budget_records",
    "actual_cost_records",
    "commitment_records",
    "schedule_activities",
    "progress_records",
}

CANONICAL_TABLES = {
    "wbs_nodes",
    "budget_records",
    "actual_cost_records",
    "commitment_records",
    "schedule_activities",
    "progress_records",
}

FACT_TABLES = CANONICAL_TABLES - {"wbs_nodes"}


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _unique_column_sets(inspector, table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(table_name)
    }


def _foreign_key_column_pairs(inspector, table_name: str) -> set[tuple[tuple[str, ...], str, tuple[str, ...]]]:
    return {
        (
            tuple(constraint["constrained_columns"]),
            constraint["referred_table"],
            tuple(constraint["referred_columns"]),
        )
        for constraint in inspector.get_foreign_keys(table_name)
    }


def _seed_phase4a_snapshot_and_run(database_url: str) -> tuple[UUID, UUID]:
    snapshot_id = UUID("00000000-0000-0000-0000-000000000004")
    run_id = UUID("00000000-0000-0000-0000-000000000006")
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
                        'LEGACY',
                        'Legacy Project'
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
                        '0.1', DATE '2026-08-17', 'LEGACY', 'validated'
                    );
                    INSERT INTO rule_catalogue_versions (id, version, sha256, definition)
                    VALUES (
                        '00000000-0000-0000-0000-000000000005',
                        '0.2', repeat('b', 64), '{}'::jsonb
                    );
                    INSERT INTO analysis_runs (
                        id, organization_id, project_id, dataset_snapshot_id,
                        catalogue_version_id, engine_version, workbook_sha256, status
                    ) VALUES (
                        '00000000-0000-0000-0000-000000000006',
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        '00000000-0000-0000-0000-000000000004',
                        '00000000-0000-0000-0000-000000000005',
                        '0.2.0', repeat('c', 64), 'succeeded'
                    );
                    """
                )
            )
    finally:
        engine.dispose()
    return snapshot_id, run_id


def test_phase4b_upgrade_preserves_phase4a_data_and_adds_schema(alembic_config, postgres_url):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "20260817_0001")
    snapshot_id, run_id = _seed_phase4a_snapshot_and_run(postgres_url)

    command.upgrade(alembic_config, "head")

    engine = create_engine(postgres_url)
    try:
        inspector = inspect(engine)
        assert PHASE4B_TABLES <= set(inspector.get_table_names())
        assert {
            "mapping_profile_version_id",
            "import_batch_id",
            "dedupe_key",
            "row_count_raw",
            "row_count_canonical",
        } <= _column_names(inspector, "dataset_snapshots")
        assert {"executed_rule_ids", "skipped_rules"} <= _column_names(inspector, "analysis_runs")
        assert "raw_row_ids" in _column_names(inspector, "finding_evidence")

        with engine.connect() as connection:
            snapshot = connection.execute(
                text(
                    """
                    SELECT status, row_count_raw, row_count_canonical
                    FROM dataset_snapshots
                    WHERE id = :snapshot_id
                    """
                ),
                {"snapshot_id": snapshot_id},
            ).mappings().one()
            run = connection.execute(
                text(
                    """
                    SELECT executed_rule_ids, skipped_rules
                    FROM analysis_runs
                    WHERE id = :run_id
                    """
                ),
                {"run_id": run_id},
            ).mappings().one()

        assert snapshot == {
            "status": "validated",
            "row_count_raw": 0,
            "row_count_canonical": 0,
        }
        assert run == {"executed_rule_ids": [], "skipped_rules": []}
    finally:
        engine.dispose()


def test_phase4b_constraints_keep_raw_and_canonical_links_snapshot_scoped(alembic_config, postgres_url):
    command.upgrade(alembic_config, "head")
    inspector = inspect(create_engine(postgres_url))

    assert (
        ("id", "import_batch_id"),
        "import_batches",
        ("dataset_snapshot_id", "id"),
    ) in _foreign_key_column_pairs(inspector, "dataset_snapshots")
    assert ("dataset_snapshot_id", "domain", "source_row_number") in _unique_column_sets(
        inspector, "raw_rows"
    )
    assert (
        ("dataset_snapshot_id", "import_batch_id"),
        "import_batches",
        ("dataset_snapshot_id", "id"),
    ) in _foreign_key_column_pairs(inspector, "raw_rows")

    for table_name in CANONICAL_TABLES:
        unique_columns = _unique_column_sets(inspector, table_name)
        assert ("dataset_snapshot_id", "source_key") in unique_columns
        assert ("raw_row_id",) in unique_columns
        assert (
            ("dataset_snapshot_id", "raw_row_id"),
            "raw_rows",
            ("dataset_snapshot_id", "id"),
        ) in _foreign_key_column_pairs(inspector, table_name)

    assert (
        ("dataset_snapshot_id", "parent_id"),
        "wbs_nodes",
        ("dataset_snapshot_id", "id"),
    ) in _foreign_key_column_pairs(inspector, "wbs_nodes")
    for table_name in FACT_TABLES:
        assert (
            ("dataset_snapshot_id", "wbs_node_id"),
            "wbs_nodes",
            ("dataset_snapshot_id", "id"),
        ) in _foreign_key_column_pairs(inspector, table_name)


def test_phase4b_downgrade_restores_phase4a_shape(alembic_config, postgres_url):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "20260817_0001")

    engine = create_engine(postgres_url)
    try:
        inspector = inspect(engine)
        assert not (PHASE4B_TABLES & set(inspector.get_table_names()))
        assert not {
            "mapping_profile_version_id",
            "import_batch_id",
            "dedupe_key",
            "row_count_raw",
            "row_count_canonical",
        } & _column_names(inspector, "dataset_snapshots")
        assert not {"executed_rule_ids", "skipped_rules"} & _column_names(inspector, "analysis_runs")
        assert "raw_row_ids" not in _column_names(inspector, "finding_evidence")
    finally:
        engine.dispose()
