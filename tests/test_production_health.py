from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from controlcheck.api import create_app
from controlcheck.settings import ApplicationSettings
from controlcheck.storage import LocalFileStorage


def build_settings(tmp_path, project_root):
    return ApplicationSettings(
        environment="production",
        database_url="postgresql+psycopg://db/app",
        upload_root=tmp_path.resolve(),
        catalogue_path=project_root / "data" / "controlcheck_rule_catalogue_v0.2.json",
        organization_id=UUID("11111111-1111-1111-1111-111111111111"),
        api_key="test-key-" + ("x" * 32),
        trusted_hosts=("testserver",),
        cors_origins=(),
        enable_docs=False,
        max_upload_bytes=25 * 1024 * 1024,
    )


def build_ready_client(tmp_path, project_root):
    settings = build_settings(tmp_path, project_root)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    sessions = sessionmaker(bind=engine)
    application = create_app(
        settings=settings,
        session_factory=sessions,
        storage=LocalFileStorage(tmp_path),
    )
    return TestClient(application)


def test_liveness_is_public_and_minimal(tmp_path, project_root):
    client = build_ready_client(tmp_path, project_root)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_readiness_returns_ready_when_dependencies_are_available(tmp_path, project_root):
    client = build_ready_client(tmp_path, project_root)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_returns_minimal_503_when_database_fails(
    monkeypatch, tmp_path, project_root
):
    client = build_ready_client(tmp_path, project_root)
    monkeypatch.setattr("controlcheck.health.database_ready", lambda _: False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "database" not in response.text.lower()


def test_local_storage_ready_requires_usable_root(tmp_path):
    storage_root = tmp_path / "new-storage-root"
    storage = LocalFileStorage(storage_root)

    assert storage.ready() is True
    assert storage_root.is_dir()


def test_local_storage_is_not_ready_when_root_is_a_file(tmp_path):
    storage_root = tmp_path / "not-a-directory"
    storage_root.write_text("occupied", encoding="utf-8")

    assert LocalFileStorage(storage_root).ready() is False
