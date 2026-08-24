from __future__ import annotations

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
from controlcheck.persistence.repositories import ProjectRepository
from controlcheck.storage import LocalFileStorage


ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_ORG_ID = UUID("22222222-2222-2222-2222-222222222222")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture()
def snapshot_client(project_root: Path, tmp_path):
    postgres_url = os.environ.get(
        "CONTROLCHECK_TEST_DATABASE_URL",
        "postgresql+psycopg://controlcheck:controlcheck@127.0.0.1:54329/controlcheck",
    )
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    session_factory = create_session_factory(postgres_url)
    with session_factory() as session:
        session.add_all(
            [
                OrganizationRecord(id=ORG_ID, name="Primary", slug=f"primary-{uuid4().hex}"),
                OrganizationRecord(id=OTHER_ORG_ID, name="Other", slug=f"other-{uuid4().hex}"),
            ]
        )
        session.flush()
        project = ProjectRepository(session).create(
            ORG_ID, "PRJ-CCAI-001", "Golden", "IDR"
        )
        session.commit()
    app = create_app(
        project_root / "data" / "controlcheck_rule_catalogue_v0.3.json",
        session_factory=session_factory,
        storage=LocalFileStorage(tmp_path),
    )
    with TestClient(app) as client:
        yield client, project.id, project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"


def _headers(org_id=ORG_ID):
    return {"X-Organization-ID": str(org_id)}


def _upload(client, project_id, workbook, org_id=ORG_ID, filename="golden.xlsx"):
    with workbook.open("rb") as source:
        return client.post(
            f"/v1/projects/{project_id}/dataset-snapshots",
            headers=_headers(org_id),
            files={"file": (filename, source, XLSX_MIME)},
        )


def test_snapshot_upload_list_detail_and_analysis(snapshot_client):
    client, project_id, workbook = snapshot_client
    uploaded = _upload(client, project_id, workbook)

    assert uploaded.status_code == 201, uploaded.text
    snapshot = uploaded.json()
    assert snapshot["status"] == "validated"
    assert snapshot["row_count_raw"] == 149
    assert snapshot["row_count_canonical"] == 149
    assert snapshot["workbook_sha256"]
    assert snapshot["mapping_profile_version"] == "0.1"
    assert snapshot["domain_statuses"]["progress"]["status"] == "valid"
    assert "storage_key" not in snapshot

    listed = client.get(
        f"/v1/projects/{project_id}/dataset-snapshots", headers=_headers()
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == snapshot["id"]

    detail = client.get(
        f"/v1/projects/{project_id}/dataset-snapshots/{snapshot['id']}",
        headers=_headers(),
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == snapshot["id"]

    run = client.post(
        f"/v1/projects/{project_id}/dataset-snapshots/{snapshot['id']}/analysis-runs",
        headers=_headers(),
    )
    assert run.status_code == 201, run.text
    assert run.json()["finding_count"] == 59
    assert run.json()["skipped_rules"] == []


def test_duplicate_snapshot_upload_returns_existing_snapshot(snapshot_client):
    client, project_id, workbook = snapshot_client
    first = _upload(client, project_id, workbook)
    second = _upload(client, project_id, workbook, filename="renamed.xlsx")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_forced_snapshot_upload_creates_distinct_snapshot(snapshot_client):
    client, project_id, workbook = snapshot_client
    first = _upload(client, project_id, workbook)
    forced = client.post(
        f"/v1/projects/{project_id}/dataset-snapshots?force_new=true",
        headers=_headers(),
        files={"file": ("golden.xlsx", workbook.open("rb"), XLSX_MIME)},
    )

    assert first.status_code == 201
    assert forced.status_code == 201
    assert forced.json()["id"] != first.json()["id"]


def test_snapshot_routes_enforce_tenant_scope(snapshot_client):
    client, project_id, workbook = snapshot_client
    uploaded = _upload(client, project_id, workbook)
    snapshot_id = uploaded.json()["id"]

    response = client.get(
        f"/v1/projects/{project_id}/dataset-snapshots/{snapshot_id}",
        headers=_headers(OTHER_ORG_ID),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "snapshot_not_found"
