import os
import subprocess
import sys
import tomllib
from pathlib import Path
from shutil import copyfile

import pytest
import yaml
from fastapi.testclient import TestClient

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
    monkeypatch.setenv("CONTROLCHECK_TRUSTED_HOSTS", "controlcheck.example")
    monkeypatch.setenv("CONTROLCHECK_STORAGE_BACKEND", "local")
    monkeypatch.setenv(
        "CONTROLCHECK_CATALOGUE",
        str(root / "data" / "controlcheck_rule_catalogue_v0.2.json"),
    )
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("ENV", raising=False)


def test_render_manifest_uses_canonical_fail_closed_production_configuration(
    monkeypatch,
) -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = yaml.safe_load((root / "render.yaml").read_text(encoding="utf-8"))
    variables = manifest["services"][0]["envVars"]
    by_name = {item["key"]: item for item in variables}

    assert {
        "CONTROLCHECK_ENV",
        "CONTROLCHECK_JWT_SECRET",
        "CONTROLCHECK_DATABASE_URL",
        "CONTROLCHECK_CORS_ORIGINS",
        "CONTROLCHECK_TRUSTED_HOSTS",
        "CONTROLCHECK_STORAGE_BACKEND",
        "CONTROLCHECK_S3_BUCKET",
    }.issubset(by_name)
    assert {"ENVIRONMENT", "SECRET_KEY", "CORS_ORIGINS"}.isdisjoint(by_name)
    assert by_name["CONTROLCHECK_CORS_ORIGINS"]["value"] == "https://app.controlcheck.ai"
    assert by_name["CONTROLCHECK_TRUSTED_HOSTS"]["value"] == "controlcheck-api.onrender.com"
    assert by_name["CONTROLCHECK_STORAGE_BACKEND"]["value"] == "s3"

    monkeypatch.setenv("RENDER", "true")
    for name, declaration in by_name.items():
        if name == "PYTHON_VERSION":
            continue
        if "value" in declaration:
            monkeypatch.setenv(name, str(declaration["value"]))
    monkeypatch.setenv("CONTROLCHECK_JWT_SECRET", "r" * 64)
    monkeypatch.setenv(
        "CONTROLCHECK_DATABASE_URL",
        "postgresql+psycopg://controlcheck:controlcheck@database/controlcheck",
    )
    monkeypatch.setenv("CONTROLCHECK_S3_BUCKET", "controlcheck-render-uploads")

    settings = ProductionSettings.from_env()

    assert settings.env == "production"
    assert settings.storage_backend == "s3"
    assert settings.trusted_hosts == ["controlcheck-api.onrender.com"]


def test_render_runtime_without_explicit_mode_fails_closed(monkeypatch) -> None:
    _set_valid_production_environment(monkeypatch)
    monkeypatch.delenv("CONTROLCHECK_ENV")
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("CONTROLCHECK_JWT_SECRET", "unsafe")

    with pytest.raises(ValueError, match="INSECURE CONFIGURATION"):
        ProductionSettings.from_env()


def test_auth_runtime_has_no_known_fallback_jwt_secret(monkeypatch) -> None:
    monkeypatch.delenv("CONTROLCHECK_JWT_SECRET", raising=False)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from controlcheck.auth.tokens import DEFAULT_SECRET_KEY; print(DEFAULT_SECRET_KEY)",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={
            key: value
            for key, value in os.environ.items()
            if key != "CONTROLCHECK_JWT_SECRET"
        },
    )

    assert result.returncode == 0, result.stderr
    secret = result.stdout.strip()
    assert len(secret) >= 32
    assert "change-in-production" not in secret


@pytest.mark.parametrize("value", [None, "*"])
def test_production_requires_explicit_trusted_hosts(monkeypatch, value) -> None:
    _set_valid_production_environment(monkeypatch)
    if value is None:
        monkeypatch.delenv("CONTROLCHECK_TRUSTED_HOSTS")
    else:
        monkeypatch.setenv("CONTROLCHECK_TRUSTED_HOSTS", value)

    with pytest.raises(ValueError, match="trusted host"):
        ProductionSettings.from_env()


def test_application_rejects_untrusted_host_header() -> None:
    app = create_configured_app.__globals__["create_app"](
        trusted_hosts=["controlcheck.example"]
    )
    client = TestClient(app, base_url="https://controlcheck.example")

    assert client.get("/health").status_code == 200
    response = client.get("/health", headers={"Host": "attacker.example"})

    assert response.status_code == 400
    assert "controlcheck" not in response.text.lower()


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


def test_isolated_runtime_can_import_s3_sdk() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", "import boto3; print(boto3.__name__)"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "boto3"


def test_base_runtime_manifests_include_s3_sdk() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = {
        line.split(">=", 1)[0].lower()
        for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    locked_packages = {package["name"] for package in lock["package"]}
    locked_project = next(
        package for package in lock["package"] if package["name"] == "controlcheck-core"
    )
    locked_project_dependencies = {
        dependency["name"] for dependency in locked_project["dependencies"]
    }

    assert any(
        dependency.lower().startswith("boto3")
        for dependency in project["project"]["dependencies"]
    )
    assert "boto3" in requirements
    assert "boto3" in locked_packages
    assert "boto3" in locked_project_dependencies


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
