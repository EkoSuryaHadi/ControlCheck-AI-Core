from uuid import UUID, uuid4

from alembic import command
from fastapi.testclient import TestClient

from controlcheck.api import create_app
from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import OrganizationRecord
from controlcheck.storage import LocalFileStorage


ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
HEADERS = {"X-Organization-ID": str(ORG_ID)}
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def create_project(client, code):
    response = client.post(
        f"/v1/organizations/{ORG_ID}/projects",
        headers=HEADERS,
        json={"code": code, "name": code, "currency": "IDR"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload_run(client, project_id, workbook):
    with workbook.open("rb") as source:
        response = client.post(
            f"/v1/projects/{project_id}/analysis-runs",
            headers=HEADERS,
            files={"file": (workbook.name, source, XLSX_MIME)},
        )
    assert response.status_code == 201, response.text
    return response.json()


def test_phase4a_golden_and_boundary_workflow(
    alembic_config, postgres_url, project_root, tmp_path
):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)
    with session_factory() as session:
        session.add(OrganizationRecord(id=ORG_ID, name="Primary", slug=f"primary-{uuid4().hex[:8]}"))
        session.commit()
    application = create_app(
        project_root / "data" / "controlcheck_rule_catalogue_v0.2.json",
        session_factory=session_factory,
        storage=LocalFileStorage(tmp_path),
    )

    with TestClient(application) as client:
        golden_project = create_project(client, "PRJ-CCAI-001")
        golden = upload_run(
            client,
            golden_project["id"],
            project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
        )
        assert golden["status"] == "succeeded"
        assert golden["finding_count"] == 59
        findings_response = client.get(
            f"/v1/analysis-runs/{golden['id']}/findings?limit=100", headers=HEADERS
        )
        findings = findings_response.json()["items"]
        assert len(findings) == 59
        for finding in findings:
            evidence = client.get(
                f"/v1/findings/{finding['id']}/evidence", headers=HEADERS
            )
            assert evidence.status_code == 200
            assert evidence.json()["items"]

        boundary_project = create_project(client, "PRJ-CCAI-BND-001")
        boundary = upload_run(
            client,
            boundary_project["id"],
            project_root / "data" / "ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx",
        )
        assert boundary["status"] == "succeeded"
        assert boundary["finding_count"] == 0
