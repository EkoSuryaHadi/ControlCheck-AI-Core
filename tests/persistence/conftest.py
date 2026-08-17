from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config


@pytest.fixture(scope="session")
def postgres_url() -> str:
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
