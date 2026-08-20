import socket
from pathlib import Path

import pytest
from alembic.config import Config


def _is_postgres_available(host: str = "127.0.0.1", port: int = 54329) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def postgres_url() -> str:
    if not _is_postgres_available():
        pytest.skip("PostgreSQL test database not available on 127.0.0.1:54329 (start via podman compose)")
    return os.environ.get(
        "CONTROLCHECK_TEST_DATABASE_URL",
        "postgresql+psycopg://controlcheck:controlcheck@127.0.0.1:54329/controlcheck",
    )


@pytest.fixture()
def alembic_config(project_root: Path, postgres_url: str) -> Config:
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    return config

