from sqlalchemy import create_engine, inspect
from alembic import command


EXPECTED_TABLES = {
    "organizations",
    "projects",
    "source_files",
    "dataset_snapshots",
    "rule_catalogue_versions",
    "analysis_runs",
    "findings",
    "finding_evidence",
    "approved_exceptions",
    "audit_logs",
}


def test_alembic_upgrade_creates_phase4a_schema(alembic_config, postgres_url):
    command.upgrade(alembic_config, "head")

    engine = create_engine(postgres_url)
    try:
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_alembic_downgrade_and_second_upgrade(alembic_config, postgres_url):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    engine = create_engine(postgres_url)
    try:
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_alembic_metadata_has_no_drift(alembic_config, postgres_url):
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)

