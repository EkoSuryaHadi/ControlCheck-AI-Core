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




@pytest.fixture()
def analysis_client(alembic_config, postgres_url, project_root, tmp_path):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)
    with session_factory() as session:
        session.add(OrganizationRecord(id=ORG_ID, name="Primary", slug=f"primary-{uuid4().hex[:8]}"))
        session.flush()
        golden = ProjectRepository(session).create(ORG_ID, "PRJ-CCAI-001", "Golden", "IDR")
        mismatch = ProjectRepository(session).create(ORG_ID, "WRONG-PROJECT", "Mismatch", "IDR")
        session.commit()
    app = create_app(
        project_root / "data" / "controlcheck_rule_catalogue_v0.2.json",
        session_factory=session_factory,
        storage=LocalFileStorage(tmp_path),
    )
    with TestClient(app) as client:
        yield client, golden.id, mismatch.id


def test_analysis_upload_persists_golden_run(analysis_client, project_root):
    client, golden_id, _ = analysis_client
    workbook = project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    with workbook.open("rb") as source:
        response = client.post(
            f"/v1/projects/{golden_id}/analysis-runs",
            headers={"X-Organization-ID": str(ORG_ID)},
            files={"file": ("golden.xlsx", source, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "succeeded"
    assert response.json()["finding_count"] == 59


def test_analysis_upload_accepts_source_project_mismatch(analysis_client, project_root):
    client, _, mismatch_id = analysis_client
    workbook = project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    with workbook.open("rb") as source:
        response = client.post(
            f"/v1/projects/{mismatch_id}/analysis-runs",
            headers={"X-Organization-ID": str(ORG_ID)},
            files={"file": ("golden.xlsx", source, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "succeeded"
    assert response.json()["finding_count"] == 59


def test_analysis_upload_rejects_invalid_workbook_safely(analysis_client):
    client, golden_id, _ = analysis_client

    response = client.post(
        f"/v1/projects/{golden_id}/analysis-runs",
        headers={"X-Organization-ID": str(ORG_ID)},
        files={
            "file": (
                "invalid.xlsx",
                b"this is not an xlsx zip archive",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_workbook"
    assert response.json()["error"]["message"] == "Workbook could not be parsed"
    assert "zip" not in response.text.lower()
