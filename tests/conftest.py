from pathlib import Path
import os

import pytest

from controlcheck.config import load_catalogue
from controlcheck.engine import RuleContext
from controlcheck.loader import load_workbook


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
