import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import psycopg
from alembic.config import Config
from psycopg import sql

from controlcheck.config import load_catalogue
from controlcheck.engine import RuleContext
from controlcheck.loader import load_workbook


_TEST_DATABASE_PREFIX = "controlcheck_test_"


def _get_target_database_url() -> str:
    if "CONTROLCHECK_TEST_POSTGRES_URL" in os.environ:
        return os.environ["CONTROLCHECK_TEST_POSTGRES_URL"]
    if "CONTROLCHECK_TEST_DATABASE_URL" in os.environ:
        return os.environ["CONTROLCHECK_TEST_DATABASE_URL"]
    for port in (54329, 54330):
        try:
            admin_url = f"postgresql://controlcheck:controlcheck@localhost:{port}/postgres"
            conn = psycopg.connect(admin_url, connect_timeout=1.0)
            conn.close()
            return f"postgresql+psycopg://controlcheck:controlcheck@localhost:{port}/postgres"
        except Exception:
            pass
    return "postgresql+psycopg://controlcheck:controlcheck@localhost:54329/postgres"


def _is_postgres_available() -> bool:
    db_url = _get_target_database_url()
    connect_url = db_url.replace("+psycopg", "")
    try:
        conn = psycopg.connect(connect_url, connect_timeout=2.0)
        conn.close()
        return True
    except Exception:
        return False


def _database_url(admin_url: str, database_name: str) -> str:
    parsed = urlsplit(admin_url)
    return urlunsplit(parsed._replace(path=f"/{database_name}"))


def _run_database_admin_statement(admin_url: str, action: str, database_name: str) -> None:
    if not database_name.startswith(_TEST_DATABASE_PREFIX):
        raise RuntimeError(f"refusing to {action.lower()} unsafe test database")

    connect_url = admin_url.replace("+psycopg", "")
    statement = sql.SQL(f"{action} DATABASE {{}}").format(sql.Identifier(database_name))
    if action == "DROP":
        statement += sql.SQL(" WITH (FORCE)")
    with psycopg.connect(connect_url, autocommit=True) as connection:
        connection.execute(statement)


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    if not _is_postgres_available():
        pytest.skip("PostgreSQL test database not available (start via podman/docker compose)")

    admin_url = _get_target_database_url()
    database_name = f"{_TEST_DATABASE_PREFIX}{uuid.uuid4().hex}"
    _run_database_admin_statement(admin_url, "CREATE", database_name)
    try:
        yield _database_url(admin_url, database_name)
    finally:
        _run_database_admin_statement(admin_url, "DROP", database_name)


@pytest.fixture()
def alembic_config(project_root: Path, postgres_url: str) -> Config:
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    return config


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]



@pytest.fixture(scope="session")
def sample_workbook(project_root: Path) -> Path:
    bundled = project_root / "data" / "ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx"
    if bundled.exists():
        return bundled
    return Path(os.environ.get(
        "CONTROLCHECK_SAMPLE_WORKBOOK",
        r"C:\Users\USER\Downloads\ControlCheck_AI_Synthetic_Project_Dataset_v0.1.xlsx",
    ))


@pytest.fixture(scope="session")
def sample_dataset(sample_workbook: Path):
    return load_workbook(sample_workbook)


@pytest.fixture(scope="session")
def context(project_root: Path):
    bundled = project_root / "data" / "controlcheck_rule_catalogue_v0.1.json"
    path = bundled if bundled.exists() else Path(r"C:\Users\USER\Downloads\controlcheck_rule_catalogue_v0.1.json")
    return RuleContext(catalogue=load_catalogue(path))


@pytest.fixture(scope="session")
def sample_catalogue(project_root: Path) -> Path:
    bundled = project_root / "data" / "controlcheck_rule_catalogue_v0.1.json"
    return bundled if bundled.exists() else Path(r"C:\Users\USER\Downloads\controlcheck_rule_catalogue_v0.1.json")


@pytest.fixture(scope="session")
def sample_ground_truth(project_root: Path) -> Path:
    bundled = project_root / "data" / "controlcheck_expected_findings_v0.1.json"
    return bundled if bundled.exists() else Path(r"C:\Users\USER\Downloads\controlcheck_expected_findings_v0.1.json")
