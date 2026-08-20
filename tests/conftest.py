import os
import socket
from pathlib import Path

import pytest
from alembic.config import Config

from controlcheck.config import load_catalogue
from controlcheck.engine import RuleContext
from controlcheck.loader import load_workbook


def _is_postgres_available(host: str = "127.0.0.1", port: int = 54329) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
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
