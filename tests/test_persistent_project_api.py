import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from controlcheck.api import create_app
from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import OrganizationRecord


ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_ORG_ID = UUID("22222222-2222-2222-2222-222222222222")




@pytest.fixture()
def persistent_client(alembic_config, postgres_url, sample_catalogue):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)
    with session_factory() as session:
        session.add_all([
            OrganizationRecord(id=ORG_ID, name="Primary", slug=f"primary-{uuid4().hex[:8]}"),
            OrganizationRecord(id=OTHER_ORG_ID, name="Other", slug=f"other-{uuid4().hex[:8]}"),
        ])
        session.commit()
    with TestClient(create_app(sample_catalogue, session_factory=session_factory)) as client:
        yield client


def tenant_headers(organization_id=ORG_ID):
    return {"X-Organization-ID": str(organization_id)}


def test_project_api_requires_tenant_header(persistent_client):
    response = persistent_client.get(f"/v1/organizations/{ORG_ID}/projects")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_tenant_context"
    assert response.json()["error"]["request_id"]


def test_project_path_must_match_tenant_header(persistent_client):
    response = persistent_client.get(
        f"/v1/organizations/{OTHER_ORG_ID}/projects",
        headers=tenant_headers(),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "tenant_scope_violation"


def test_project_create_and_list_are_tenant_scoped(persistent_client):
    created = persistent_client.post(
        f"/v1/organizations/{ORG_ID}/projects",
        headers=tenant_headers(),
        json={"code": "PRJ-CCAI-001", "name": "Golden Project", "currency": "IDR"},
    )

    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["organization_id"] == str(ORG_ID)
    assert payload["code"] == "PRJ-CCAI-001"

    listed = persistent_client.get(
        f"/v1/organizations/{ORG_ID}/projects",
        headers=tenant_headers(),
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [payload["id"]]
