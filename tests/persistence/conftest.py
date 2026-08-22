import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest
from alembic.config import Config


def _get_target_database_url() -> str:
    if "CONTROLCHECK_TEST_DATABASE_URL" in os.environ:
        return os.environ["CONTROLCHECK_TEST_DATABASE_URL"]
    for port in (54329, 54330):
        try:
            conn = psycopg.connect(f"postgresql://controlcheck:controlcheck@localhost:{port}/controlcheck", connect_timeout=1.0)
            conn.close()
            return f"postgresql+psycopg://controlcheck:controlcheck@localhost:{port}/controlcheck"
        except Exception:
            pass
    return "postgresql+psycopg://controlcheck:controlcheck@localhost:54329/controlcheck"


def _is_postgres_available() -> bool:
    db_url = _get_target_database_url()
    connect_url = db_url.replace("+psycopg", "")
    try:
        conn = psycopg.connect(connect_url, connect_timeout=2.0)
        conn.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_url() -> str:
    if not _is_postgres_available():
        pytest.skip("PostgreSQL test database not available (start via podman/docker compose)")
    return _get_target_database_url()


@pytest.fixture()
def alembic_config(project_root: Path, postgres_url: str) -> Config:
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    return config

