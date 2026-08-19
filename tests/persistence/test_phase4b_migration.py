from __future__ import annotations

import re
from uuid import UUID

import pytest
from alembic import command
from sqlalchemy import Numeric, create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError


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


def _columns_by_name(inspector, table_name: str) -> dict[str, dict]:
    return {column["name"]: column for column in inspector.get_columns(table_name)}


def _checks_by_name(inspector, table_name: str) -> dict[str, str]:
    return {
        constraint["name"]: constraint["sqltext"]
        for constraint in inspector.get_check_constraints(table_name)
    }


def _allowed_check_values(sqltext: str) -> set[str]:
    return set(re.findall(r"'([^']+)'", sqltext))


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


def _seed_phase4b_downgrade_rows(database_url: str) -> tuple[UUID, UUID, UUID]:
    ingesting_snapshot_id = UUID("00000000-0000-0000-0000-000000000010")
    partial_snapshot_id = UUID("00000000-0000-0000-0000-000000000011")
    evidence_id = UUID("00000000-0000-0000-0000-000000000013")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO dataset_snapshots (
                        id, organization_id, project_id, source_file_id,
                        dataset_version, data_date, source_project_id, status
                    ) VALUES
                    (
                        '00000000-0000-0000-0000-000000000010',
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        '00000000-0000-0000-0000-000000000003',
                        '0.1', DATE '2026-08-18', 'LEGACY', 'ingesting'
                    ),
                    (
                        '00000000-0000-0000-0000-000000000011',
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        '00000000-0000-0000-0000-000000000003',
                        '0.1', DATE '2026-08-18', 'LEGACY', 'validated_with_errors'
                    );
                    INSERT INTO findings (
                        id, analysis_run_id, organization_id, project_id,
                        engine_finding_id, rule_id, rule_name, entity_type,
                        entity_id, category, severity, status, title,
                        description, metrics, calculation, business_impact,
                        recommendation, confidence
                    ) VALUES (
                        '00000000-0000-0000-0000-000000000012',
                        '00000000-0000-0000-0000-000000000006',
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        'legacy-finding', 'DQ-001', 'Legacy finding', 'budget',
                        'BUD-001', 'data_quality', 'warning', 'open',
                        'Legacy title', 'Legacy description', '{"count": 1}'::jsonb,
                        '{"method": "legacy"}'::jsonb, 'Legacy impact',
                        'Legacy recommendation', 1.0
                    );
                    INSERT INTO finding_evidence (
                        id, finding_id, evidence_order, source_sheet, source_rows,
                        record_ids, raw_row_ids, fields, aggregation
                    ) VALUES (
                        '00000000-0000-0000-0000-000000000013',
                        '00000000-0000-0000-0000-000000000012',
                        1, 'Budget', '[7]'::jsonb, '["BUD-001"]'::jsonb,
                        '[101]'::jsonb, '{"budget_amount": "100.00"}'::jsonb,
                        '{"count": 1}'::jsonb
                    );
                    """
                )
            )
    finally:
        engine.dispose()
    return ingesting_snapshot_id, partial_snapshot_id, evidence_id


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
            "source_project_name",
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
    engine = create_engine(postgres_url)
    try:
        inspector = inspect(engine)
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
    finally:
        engine.dispose()


def test_phase4b_dedupe_key_is_unique_only_when_non_null(alembic_config, postgres_url):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    _seed_phase4a_snapshot_and_run(postgres_url)

    engine = create_engine(postgres_url)
    try:
        inspector = inspect(engine)
        dedupe_index = next(
            index
            for index in inspector.get_indexes("dataset_snapshots")
            if index["name"] == "ux_dataset_snapshots_dedupe_key_not_null"
        )
        assert dedupe_index["unique"] is True
        assert "dedupe_key IS NOT NULL" in str(
            dedupe_index["dialect_options"]["postgresql_where"]
        )

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO dataset_snapshots (
                        id, organization_id, project_id, source_file_id,
                        dataset_version, data_date, source_project_id, dedupe_key
                    ) VALUES
                    (
                        '00000000-0000-0000-0000-000000000020',
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        '00000000-0000-0000-0000-000000000003',
                        '0.1', DATE '2026-08-18', 'LEGACY', NULL
                    ),
                    (
                        '00000000-0000-0000-0000-000000000021',
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        '00000000-0000-0000-0000-000000000003',
                        '0.1', DATE '2026-08-18', 'LEGACY', NULL
                    ),
                    (
                        '00000000-0000-0000-0000-000000000022',
                        '00000000-0000-0000-0000-000000000001',
                        '00000000-0000-0000-0000-000000000002',
                        '00000000-0000-0000-0000-000000000003',
                        '0.1', DATE '2026-08-18', 'LEGACY', repeat('d', 64)
                    );
                    """
                )
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO dataset_snapshots (
                            id, organization_id, project_id, source_file_id,
                            dataset_version, data_date, source_project_id, dedupe_key
                        ) VALUES (
                            '00000000-0000-0000-0000-000000000023',
                            '00000000-0000-0000-0000-000000000001',
                            '00000000-0000-0000-0000-000000000002',
                            '00000000-0000-0000-0000-000000000003',
                            '0.1', DATE '2026-08-18', 'LEGACY', repeat('d', 64)
                        )
                        """
                    )
                )

        with engine.connect() as connection:
            counts = connection.execute(
                text(
                    """
                    SELECT count(*) FILTER (WHERE dedupe_key IS NULL) AS null_keys,
                           count(*) FILTER (WHERE dedupe_key = repeat('d', 64)) AS duplicate_key
                    FROM dataset_snapshots
                    WHERE id IN (
                        '00000000-0000-0000-0000-000000000020',
                        '00000000-0000-0000-0000-000000000021',
                        '00000000-0000-0000-0000-000000000022',
                        '00000000-0000-0000-0000-000000000023'
                    )
                    """
                )
            ).mappings().one()
        assert counts == {"null_keys": 2, "duplicate_key": 1}
    finally:
        engine.dispose()


def test_phase4b_database_contract_pins_checks_types_nullability_and_defaults(
    alembic_config, postgres_url
):
    command.upgrade(alembic_config, "head")
    engine = create_engine(postgres_url)
    try:
        inspector = inspect(engine)

        expected_status_values = {
            "dataset_snapshots": {
                "ck_dataset_snapshots_status": {
                    "ingesting", "validated", "validated_with_errors", "failed"
                }
            },
            "import_batches": {
                "ck_import_batches_status": {"ingesting", "completed", "failed"}
            },
            "dataset_domain_statuses": {
                "ck_dataset_domain_statuses_status": {"valid", "warning", "blocked"}
            },
            "raw_rows": {
                "ck_raw_rows_validation_status": {"valid", "warning", "invalid"}
            },
        }
        for table_name, constraints in expected_status_values.items():
            checks = _checks_by_name(inspector, table_name)
            for constraint_name, allowed_values in constraints.items():
                assert _allowed_check_values(checks[constraint_name]) == allowed_values

        expected_non_negative_checks = {
            "dataset_snapshots": {
                "ck_dataset_snapshots_row_counts": {"row_count_raw", "row_count_canonical"}
            },
            "import_batches": {
                "ck_import_batches_counts": {
                    "rows_read", "rows_valid", "rows_warning", "rows_rejected"
                }
            },
            "dataset_domain_statuses": {
                "ck_dataset_domain_statuses_counts": {
                    "row_count_raw", "row_count_canonical", "error_count", "warning_count"
                }
            },
        }
        for table_name, constraints in expected_non_negative_checks.items():
            checks = _checks_by_name(inspector, table_name)
            for constraint_name, columns in constraints.items():
                sqltext = checks[constraint_name]
                for column_name in columns:
                    assert re.search(rf"\b{column_name}\s*>=\s*0\b", sqltext)

        progress_checks = {
            "schedule_activities": "ck_schedule_activities_progress",
            "progress_records": "ck_progress_records_progress",
        }
        for table_name, constraint_name in progress_checks.items():
            sqltext = _checks_by_name(inspector, table_name)[constraint_name]
            assert re.search(r"\bplanned_progress\s*>=\s*0\b", sqltext)
            assert re.search(r"\bactual_progress\s*>=\s*0\b", sqltext)
            assert not re.search(r"\bplanned_progress\s*<=", sqltext)
            assert not re.search(r"\bactual_progress\s*<=", sqltext)
            columns = _columns_by_name(inspector, table_name)
            for column_name in ("planned_progress", "actual_progress"):
                assert isinstance(columns[column_name]["type"], Numeric)
                assert columns[column_name]["nullable"] is False

        schedule_checks = _checks_by_name(inspector, "schedule_activities")
        assert "ck_schedule_activities_baseline_dates" in schedule_checks
        assert "ck_schedule_activities_actual_dates" not in schedule_checks

        uuid_columns = {
            "dataset_snapshots": {"mapping_profile_version_id", "import_batch_id"},
            "mapping_profile_versions": {"id"},
            "import_batches": {
                "id", "organization_id", "project_id", "dataset_snapshot_id",
                "mapping_profile_version_id"
            },
            "dataset_domain_statuses": {
                "id", "organization_id", "project_id", "dataset_snapshot_id"
            },
            "raw_rows": {
                "organization_id", "project_id", "dataset_snapshot_id", "import_batch_id"
            },
            "wbs_nodes": {
                "id", "organization_id", "project_id", "dataset_snapshot_id", "parent_id"
            },
        }
        for table_name in FACT_TABLES:
            uuid_columns[table_name] = {
                "id", "organization_id", "project_id", "dataset_snapshot_id", "wbs_node_id"
            }
        for table_name, column_names in uuid_columns.items():
            columns = _columns_by_name(inspector, table_name)
            for column_name in column_names:
                assert isinstance(columns[column_name]["type"], postgresql.UUID)

        jsonb_columns = {
            "mapping_profile_versions": {"definition"},
            "import_batches": {"error_summary"},
            "dataset_domain_statuses": {"validation_summary"},
            "raw_rows": {"raw_data", "validation_errors"},
            "analysis_runs": {"executed_rule_ids", "skipped_rules"},
            "finding_evidence": {"raw_row_ids"},
        }
        for table_name, column_names in jsonb_columns.items():
            columns = _columns_by_name(inspector, table_name)
            for column_name in column_names:
                assert isinstance(columns[column_name]["type"], postgresql.JSONB)

        expected_column_contracts = {
            "dataset_snapshots": {
                "mapping_profile_version_id": (True, None),
                "import_batch_id": (True, None),
                "dedupe_key": (True, None),
                "row_count_raw": (False, "0"),
                "row_count_canonical": (False, "0"),
                "status": (False, "'ingesting'::character varying"),
            },
            "import_batches": {
                "dataset_snapshot_id": (True, None),
                "mapping_profile_version_id": (False, None),
                "status": (False, "'ingesting'::character varying"),
                "rows_read": (False, "0"),
                "rows_valid": (False, "0"),
                "rows_warning": (False, "0"),
                "rows_rejected": (False, "0"),
            },
            "dataset_domain_statuses": {
                "status": (False, None),
                "row_count_raw": (False, "0"),
                "row_count_canonical": (False, "0"),
                "error_count": (False, "0"),
                "warning_count": (False, "0"),
                "validation_summary": (False, "'{}'::jsonb"),
            },
            "raw_rows": {
                "raw_data": (False, None),
                "validation_status": (False, "'valid'::character varying"),
                "validation_errors": (False, "'[]'::jsonb"),
            },
            "analysis_runs": {
                "executed_rule_ids": (False, "'[]'::jsonb"),
                "skipped_rules": (False, "'[]'::jsonb"),
            },
            "finding_evidence": {"raw_row_ids": (False, "'[]'::jsonb")},
        }
        for table_name, contracts in expected_column_contracts.items():
            columns = _columns_by_name(inspector, table_name)
            for column_name, (nullable, server_default) in contracts.items():
                assert columns[column_name]["nullable"] is nullable
                assert columns[column_name]["default"] == server_default
    finally:
        engine.dispose()


def test_phase4b_downgrade_restores_phase4a_shape(alembic_config, postgres_url):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "20260817_0001")
    legacy_snapshot_id, _ = _seed_phase4a_snapshot_and_run(postgres_url)
    command.upgrade(alembic_config, "head")
    ingesting_snapshot_id, partial_snapshot_id, evidence_id = _seed_phase4b_downgrade_rows(
        postgres_url
    )

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

        status_column = _columns_by_name(inspector, "dataset_snapshots")["status"]
        assert status_column["nullable"] is False
        assert status_column["type"].length == 20
        assert status_column["default"] == "'validated'::character varying"
        assert _allowed_check_values(
            _checks_by_name(inspector, "dataset_snapshots")["ck_dataset_snapshots_status"]
        ) == {"validated", "failed"}

        with engine.connect() as connection:
            snapshot_statuses = dict(
                connection.execute(
                    text(
                        """
                        SELECT id, status
                        FROM dataset_snapshots
                        WHERE id IN (:legacy_id, :ingesting_id, :partial_id)
                        """
                    ),
                    {
                        "legacy_id": legacy_snapshot_id,
                        "ingesting_id": ingesting_snapshot_id,
                        "partial_id": partial_snapshot_id,
                    },
                ).all()
            )
            evidence = connection.execute(
                text(
                    """
                    SELECT source_sheet, source_rows, record_ids, fields, aggregation
                    FROM finding_evidence
                    WHERE id = :evidence_id
                    """
                ),
                {"evidence_id": evidence_id},
            ).mappings().one()

        assert snapshot_statuses == {
            legacy_snapshot_id: "validated",
            ingesting_snapshot_id: "failed",
            partial_snapshot_id: "validated",
        }
        assert evidence == {
            "source_sheet": "Budget",
            "source_rows": [7],
            "record_ids": ["BUD-001"],
            "fields": {"budget_amount": "100.00"},
            "aggregation": {"count": 1},
        }
    finally:
        engine.dispose()
