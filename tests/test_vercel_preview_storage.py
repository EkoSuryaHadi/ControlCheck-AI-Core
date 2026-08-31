from __future__ import annotations

from controlcheck.settings import ProductionSettings


def test_vercel_preview_uses_ephemeral_storage_instead_of_production_s3(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "preview")
    monkeypatch.setenv("CONTROLCHECK_ENV", "production")
    monkeypatch.setenv("CONTROLCHECK_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("CONTROLCHECK_S3_BUCKET", "production-workbooks")
    monkeypatch.setenv("CONTROLCHECK_CORS_ORIGINS", "*")
    monkeypatch.setenv("CONTROLCHECK_TRUSTED_HOSTS", "*")

    settings = ProductionSettings.from_env()

    assert settings.env == "development"
    assert settings.storage_backend == "local"
