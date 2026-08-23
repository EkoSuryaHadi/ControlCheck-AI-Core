from controlcheck.settings import PersistenceSettings, ProductionSettings


def test_production_settings_accepts_standard_database_url(monkeypatch):
    monkeypatch.delenv("CONTROLCHECK_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://preview-db/controlcheck")
    monkeypatch.setenv("CONTROLCHECK_ENV", "development")

    settings = ProductionSettings.from_env()

    assert settings.database_url == "postgresql://preview-db/controlcheck"


def test_controlcheck_database_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://standard/controlcheck")
    monkeypatch.setenv("CONTROLCHECK_DATABASE_URL", "postgresql://explicit/controlcheck")
    monkeypatch.setenv("CONTROLCHECK_ENV", "development")

    production = ProductionSettings.from_env()
    persistence = PersistenceSettings.from_env()

    assert production.database_url == "postgresql://explicit/controlcheck"
    assert persistence.database_url == "postgresql://explicit/controlcheck"
