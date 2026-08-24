from dataclasses import replace
from uuid import UUID

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from controlcheck.api import create_app
from controlcheck.settings import ApplicationSettings


CONFIGURED_ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")
OVERRIDE_ORGANIZATION_ID = "22222222-2222-2222-2222-222222222222"
SECURE_API_KEY = "test-key-" + ("x" * 32)


@pytest.fixture
def production_settings(monkeypatch, tmp_path, project_root):
    monkeypatch.setenv("CONTROLCHECK_ENV", "production")
    monkeypatch.setenv("CONTROLCHECK_DATABASE_URL", "postgresql+psycopg://db/app")
    monkeypatch.setenv("CONTROLCHECK_UPLOAD_ROOT", str(tmp_path.resolve()))
    monkeypatch.setenv(
        "CONTROLCHECK_CATALOGUE",
        str(project_root / "data" / "controlcheck_rule_catalogue_v0.2.json"),
    )
    monkeypatch.setenv("CONTROLCHECK_ORGANIZATION_ID", str(CONFIGURED_ORGANIZATION_ID))
    monkeypatch.setenv("CONTROLCHECK_API_KEY", SECURE_API_KEY)
    monkeypatch.setenv("CONTROLCHECK_TRUSTED_HOSTS", "testserver")
    return ApplicationSettings.from_env()


@pytest.fixture
def production_app(production_settings):
    return create_app(settings=production_settings)


@pytest.fixture
def production_client(production_app):
    with TestClient(production_app) as client:
        yield client


def test_production_rejects_missing_and_invalid_bearer_key(production_client):
    missing = production_client.post("/v1/audits")
    invalid = production_client.post(
        "/v1/audits", headers={"Authorization": "Bearer wrong"}
    )

    for response in (missing, invalid):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "authentication_required"
        assert response.json()["error"]["message"] == "Authentication is required"
        assert response.headers["www-authenticate"] == "Bearer"


def test_valid_bearer_key_reaches_request_validation(production_client):
    response = production_client.post(
        "/v1/audits", headers={"Authorization": f"Bearer {SECURE_API_KEY}"}
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_production_tenant_cannot_be_overridden(production_app):
    dependency = production_app.state.require_tenant

    tenant = dependency(
        credentials=HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=SECURE_API_KEY
        ),
        x_organization_id=OVERRIDE_ORGANIZATION_ID,
    )

    assert tenant.organization_id == CONFIGURED_ORGANIZATION_ID


def test_every_v1_route_declares_access_or_tenant_dependency(production_settings):
    application = create_app(
        settings=production_settings,
        session_factory=lambda: None,
    )

    unprotected = [
        route.path
        for route in application.routes
        if getattr(route, "path", "").startswith("/v1/")
        and not route.dependant.dependencies
    ]

    assert unprotected == []


def test_development_tenant_still_comes_from_header(monkeypatch):
    monkeypatch.setenv("CONTROLCHECK_ENV", "development")
    settings = ApplicationSettings.from_env()
    application = create_app(settings=settings)

    tenant = application.state.require_tenant(
        credentials=None,
        x_organization_id=OVERRIDE_ORGANIZATION_ID,
    )

    assert tenant.organization_id == UUID(OVERRIDE_ORGANIZATION_ID)


def test_production_disables_docs_and_rejects_unknown_host(production_client):
    assert production_client.get("/docs").status_code == 404
    assert production_client.get("/openapi.json").status_code == 404

    response = production_client.get(
        "/health", headers={"Host": "attacker.example"}
    )

    assert response.status_code == 400


def test_unhandled_error_is_generic_and_has_safe_request_id(production_app):
    @production_app.get("/test/unhandled")
    def unhandled_error():
        raise RuntimeError("private database detail")

    with TestClient(production_app, raise_server_exceptions=False) as client:
        response = client.get(
            "/test/unhandled",
            headers={"X-Request-ID": "bad id with spaces"},
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_server_error"
    assert response.json()["error"]["message"] == "The request could not be completed"
    assert "private database detail" not in response.text
    UUID(response.headers["X-Request-ID"])


def test_safe_request_id_is_preserved(production_client):
    response = production_client.get(
        "/health", headers={"X-Request-ID": "pilot-request_001"}
    )

    assert response.headers["X-Request-ID"] == "pilot-request_001"


def test_cors_is_absent_by_default_and_allows_only_configured_origin(
    production_settings,
):
    default_client = TestClient(create_app(settings=production_settings))
    configured_client = TestClient(create_app(settings=replace(
        production_settings,
        cors_origins=("https://app.example.com",),
    )))

    default_response = default_client.get(
        "/health", headers={"Origin": "https://app.example.com"}
    )
    allowed_response = configured_client.get(
        "/health", headers={"Origin": "https://app.example.com"}
    )
    rejected_response = configured_client.get(
        "/health", headers={"Origin": "https://attacker.example"}
    )

    assert "access-control-allow-origin" not in default_response.headers
    assert allowed_response.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-credentials" not in allowed_response.headers
    assert "access-control-allow-origin" not in rejected_response.headers
