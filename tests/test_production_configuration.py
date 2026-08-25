from pathlib import Path
from shutil import copyfile
import tomllib

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
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.delenv("ENV", raising=False)


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


def test_production_environment_is_trimmed_and_case_normalized(monkeypatch) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.setenv("CONTROLCHECK_ENV", "  ProDucTion  ")

    assert ProductionSettings.from_env().env == "production"


@pytest.mark.parametrize("value", ["prodution", " "])
def test_invalid_explicit_environment_fails_closed(monkeypatch, value: str) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.setenv("CONTROLCHECK_ENV", value)

    with pytest.raises(ValueError, match="environment"):
        ProductionSettings.from_env()


def test_controlcheck_environment_takes_precedence_over_legacy_env(monkeypatch) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.setenv("CONTROLCHECK_ENV", "test")
    monkeypatch.setenv("ENV", "production")

    assert ProductionSettings.from_env().env == "test"


def test_vercel_production_signal_cannot_be_overridden_by_development(monkeypatch) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.setenv("CONTROLCHECK_ENV", "development")
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("CONTROLCHECK_JWT_SECRET", "unsafe")

    with pytest.raises(ValueError, match="INSECURE CONFIGURATION"):
        ProductionSettings.from_env()


@pytest.mark.parametrize("indicator", ["VERCEL", "AWS_LAMBDA_FUNCTION_NAME"])
def test_serverless_without_mode_fails_closed_as_production(
    monkeypatch, indicator: str
) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.delenv("CONTROLCHECK_ENV")
    monkeypatch.setenv(indicator, "present")
    monkeypatch.setenv("CONTROLCHECK_JWT_SECRET", "unsafe")

    with pytest.raises(ValueError, match="INSECURE CONFIGURATION"):
        ProductionSettings.from_env()


def test_vercel_preview_without_explicit_mode_remains_development(monkeypatch) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.delenv("CONTROLCHECK_ENV")
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "preview")

    assert ProductionSettings.from_env().env == "development"


@pytest.mark.parametrize("value", ["stagin", " "])
def test_invalid_vercel_environment_fails_closed(monkeypatch, value: str) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.delenv("CONTROLCHECK_ENV")
    monkeypatch.setenv("VERCEL_ENV", value)

    with pytest.raises(ValueError, match="environment"):
        ProductionSettings.from_env()


def test_production_extra_declares_s3_runtime_dependency() -> None:
    project = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )

    assert any(
        dependency.lower().startswith("boto3")
        for dependency in project["project"]["optional-dependencies"]["production"]
    )


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
