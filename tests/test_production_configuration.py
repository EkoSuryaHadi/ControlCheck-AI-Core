from pathlib import Path
from shutil import copyfile

import pytest

from controlcheck.api import create_configured_app
from controlcheck.settings import ProductionSettings


def _set_valid_production_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("CONTROLCHECK_ENV", "production")
    monkeypatch.setenv("CONTROLCHECK_JWT_SECRET", "a" * 64)
    monkeypatch.setenv(
        "CONTROLCHECK_DATABASE_URL",
        "postgresql+psycopg://controlcheck:controlcheck@database/controlcheck",
    )
    monkeypatch.setenv("CONTROLCHECK_CORS_ORIGINS", "https://controlcheck.example")
    monkeypatch.setenv("CONTROLCHECK_STORAGE_BACKEND", "local")
    monkeypatch.setenv(
        "CONTROLCHECK_CATALOGUE",
        str(root / "data" / "controlcheck_rule_catalogue_v0.2.json"),
    )
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)


def test_complete_production_configuration_is_accepted(monkeypatch) -> None:
    _set_valid_production_environment(monkeypatch)

    settings = ProductionSettings.from_env()

    assert settings.env == "production"
    assert settings.database_url.endswith("/controlcheck")
    assert settings.cors_origins == ["https://controlcheck.example"]


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("CONTROLCHECK_DATABASE_URL", None, "database"),
        ("CONTROLCHECK_CORS_ORIGINS", "*", "CORS"),
        ("CONTROLCHECK_STORAGE_BACKEND", "unknown", "storage"),
    ],
)
def test_incomplete_production_configuration_fails_closed(
    monkeypatch, variable: str, value: str | None, message: str
) -> None:
    _set_valid_production_environment(monkeypatch)
    if value is None:
        monkeypatch.delenv(variable)
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv(variable, value)

    with pytest.raises(ValueError, match=message):
        ProductionSettings.from_env()


def test_serverless_production_rejects_ephemeral_local_storage(monkeypatch) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")

    with pytest.raises(ValueError, match="durable storage"):
        ProductionSettings.from_env()


def test_production_startup_rejects_missing_catalogue(monkeypatch, tmp_path) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.setenv("CONTROLCHECK_CATALOGUE", str(tmp_path / "missing.json"))

    with pytest.raises(ValueError, match="catalogue"):
        create_configured_app()


def test_production_startup_rejects_invalid_catalogue(monkeypatch, tmp_path) -> None:
    _set_valid_production_environment(monkeypatch)
    root = Path(__file__).resolve().parents[1]
    catalogue = tmp_path / "controlcheck_rule_catalogue_v0.2.json"
    catalogue.write_text("{not-json", encoding="utf-8")
    copyfile(
        root / "data" / "controlcheck_mapping_profile_v0.1.json",
        tmp_path / "controlcheck_mapping_profile_v0.1.json",
    )
    monkeypatch.setenv("CONTROLCHECK_CATALOGUE", str(catalogue))

    with pytest.raises(ValueError, match="catalogue"):
        create_configured_app()
