from pathlib import Path

import pytest

from controlcheck.settings import PersistenceSettings


def test_persistence_settings_require_database_url(monkeypatch):
    monkeypatch.delenv("CONTROLCHECK_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="CONTROLCHECK_DATABASE_URL"):
        PersistenceSettings.from_env()


def test_persistence_settings_read_environment(monkeypatch):
    monkeypatch.setenv("CONTROLCHECK_DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("CONTROLCHECK_UPLOAD_ROOT", "var/test-uploads")

    settings = PersistenceSettings.from_env()

    assert settings.database_url == "postgresql+psycopg://user:pass@localhost/db"
    assert settings.upload_root == Path("var/test-uploads")
