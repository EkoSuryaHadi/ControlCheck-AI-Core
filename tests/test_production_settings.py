from pathlib import Path
from uuid import UUID

import pytest

from controlcheck.settings import ApplicationSettings


ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"
SECURE_API_KEY = "test-key-" + ("x" * 32)


def configure_production(monkeypatch, tmp_path: Path, project_root: Path) -> None:
    monkeypatch.setenv("CONTROLCHECK_ENV", "production")
    monkeypatch.setenv("CONTROLCHECK_DATABASE_URL", "postgresql+psycopg://db/app")
    monkeypatch.setenv("CONTROLCHECK_UPLOAD_ROOT", str(tmp_path.resolve()))
    monkeypatch.setenv("CONTROLCHECK_CATALOGUE", str(
        project_root / "data" / "controlcheck_rule_catalogue_v0.2.json"
    ))
    monkeypatch.setenv("CONTROLCHECK_ORGANIZATION_ID", ORGANIZATION_ID)
    monkeypatch.setenv("CONTROLCHECK_API_KEY", SECURE_API_KEY)
    monkeypatch.setenv("CONTROLCHECK_TRUSTED_HOSTS", "api.example.com")


def test_production_settings_require_api_key(monkeypatch, tmp_path, project_root):
    configure_production(monkeypatch, tmp_path, project_root)
    monkeypatch.delenv("CONTROLCHECK_API_KEY")

    with pytest.raises(RuntimeError, match="CONTROLCHECK_API_KEY"):
        ApplicationSettings.from_env()


def test_production_settings_parse_secure_values(monkeypatch, tmp_path, project_root):
    configure_production(monkeypatch, tmp_path, project_root)
    monkeypatch.setenv("CONTROLCHECK_TRUSTED_HOSTS", "api.example.com, internal.example.com")
    monkeypatch.setenv("CONTROLCHECK_CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("CONTROLCHECK_MAX_UPLOAD_BYTES", "1048576")

    settings = ApplicationSettings.from_env()

    assert settings.environment == "production"
    assert settings.database_url == "postgresql+psycopg://db/app"
    assert settings.upload_root == tmp_path.resolve()
    assert settings.organization_id == UUID(ORGANIZATION_ID)
    assert settings.api_key == SECURE_API_KEY
    assert settings.trusted_hosts == ("api.example.com", "internal.example.com")
    assert settings.cors_origins == ("https://app.example.com",)
    assert settings.enable_docs is False
    assert settings.max_upload_bytes == 1048576
    assert settings.is_production is True


@pytest.mark.parametrize("environment", ["prod", "staging", "", "PRODUCTION"])
def test_environment_must_be_an_explicit_supported_value(monkeypatch, environment):
    monkeypatch.setenv("CONTROLCHECK_ENV", environment)

    with pytest.raises(RuntimeError, match="CONTROLCHECK_ENV"):
        ApplicationSettings.from_env()


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("CONTROLCHECK_DATABASE_URL", ""),
        ("CONTROLCHECK_UPLOAD_ROOT", "relative/uploads"),
        ("CONTROLCHECK_ORGANIZATION_ID", "not-a-uuid"),
        ("CONTROLCHECK_API_KEY", "too-short"),
        ("CONTROLCHECK_TRUSTED_HOSTS", ""),
        ("CONTROLCHECK_TRUSTED_HOSTS", "*"),
        ("CONTROLCHECK_CORS_ORIGINS", "http://app.example.com"),
        ("CONTROLCHECK_MAX_UPLOAD_BYTES", "0"),
    ],
)
def test_production_rejects_insecure_values(
    monkeypatch, tmp_path, project_root, variable, value
):
    configure_production(monkeypatch, tmp_path, project_root)
    monkeypatch.setenv(variable, value)

    with pytest.raises(RuntimeError, match=variable):
        ApplicationSettings.from_env()


def test_production_requires_readable_catalogue(monkeypatch, tmp_path, project_root):
    configure_production(monkeypatch, tmp_path, project_root)
    monkeypatch.setenv("CONTROLCHECK_CATALOGUE", str(tmp_path / "missing.json"))

    with pytest.raises(RuntimeError, match="CONTROLCHECK_CATALOGUE"):
        ApplicationSettings.from_env()


def test_docs_default_by_environment(monkeypatch, tmp_path, project_root):
    monkeypatch.setenv("CONTROLCHECK_ENV", "development")
    monkeypatch.delenv("CONTROLCHECK_ENABLE_DOCS", raising=False)
    development = ApplicationSettings.from_env()

    configure_production(monkeypatch, tmp_path, project_root)
    monkeypatch.delenv("CONTROLCHECK_ENABLE_DOCS", raising=False)
    production = ApplicationSettings.from_env()

    assert development.enable_docs is True
    assert production.enable_docs is False


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("false", False)])
def test_docs_can_be_explicitly_configured(monkeypatch, raw, expected):
    monkeypatch.setenv("CONTROLCHECK_ENV", "test")
    monkeypatch.setenv("CONTROLCHECK_ENABLE_DOCS", raw)

    assert ApplicationSettings.from_env().enable_docs is expected


def test_invalid_boolean_is_rejected(monkeypatch):
    monkeypatch.setenv("CONTROLCHECK_ENV", "test")
    monkeypatch.setenv("CONTROLCHECK_ENABLE_DOCS", "sometimes")

    with pytest.raises(RuntimeError, match="CONTROLCHECK_ENABLE_DOCS"):
        ApplicationSettings.from_env()
