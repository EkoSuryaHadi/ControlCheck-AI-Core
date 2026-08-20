import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from controlcheck.api import create_app
from controlcheck.application import AnalysisService
from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import AuditLogRecord, FindingRecord, OrganizationRecord
from controlcheck.persistence.repositories import ProjectRepository
from controlcheck.storage import LocalFileStorage


ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_ORG_ID = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture()
def query_context(alembic_config, postgres_url, project_root, tmp_path_factory):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)

    with session_factory() as session:
        session.add_all([
            OrganizationRecord(id=ORG_ID, name="Primary", slug=f"primary-{uuid4().hex[:8]}"),
            OrganizationRecord(id=OTHER_ORG_ID, name="Other", slug=f"other-{uuid4().hex[:8]}"),
        ])
        session.flush()
        project = ProjectRepository(session).create(ORG_ID, "PRJ-CCAI-001", "Golden", "IDR")
        session.commit()
    catalogue = project_root / "data" / "controlcheck_rule_catalogue_v0.2.json"
    storage = LocalFileStorage(tmp_path_factory.mktemp("query-uploads"))
    service = AnalysisService(session_factory, storage, catalogue)
    workbook = (project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx").read_bytes()
    run = service.run(ORG_ID, project.id, "golden.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", workbook)
    with session_factory() as session:
        finding = session.scalar(select(FindingRecord).where(FindingRecord.analysis_run_id == run.id).order_by(FindingRecord.id))
        finding_id = finding.id
    with TestClient(create_app(catalogue, session_factory=session_factory, storage=storage)) as client:
        yield client, session_factory, project.id, run.id, finding_id


def headers(organization_id=ORG_ID):
    return {"X-Organization-ID": str(organization_id)}


def test_run_history_detail_and_combined_filters(query_context):
    client, _, project_id, run_id, _ = query_context
    history = client.get(f"/v1/projects/{project_id}/analysis-runs", headers=headers())
    assert history.status_code == 200
    assert history.json()["items"][0]["id"] == str(run_id)

    detail = client.get(f"/v1/analysis-runs/{run_id}", headers=headers())
    assert detail.status_code == 200
    assert detail.json()["finding_count"] == 59

    findings = client.get(
        f"/v1/analysis-runs/{run_id}/findings",
        params={"rule_id": "CST-001", "severity": "warning"},
        headers=headers(),
    )
    assert findings.status_code == 200
    assert findings.json()["items"]
    assert all(item["rule_id"] == "CST-001" and item["severity"] == "warning" for item in findings.json()["items"])


def test_cross_tenant_finding_is_not_returned(query_context):
    client, _, _, _, finding_id = query_context
    response = client.get(f"/v1/findings/{finding_id}", headers=headers(OTHER_ORG_ID))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "finding_not_found"


def test_evidence_and_status_update_are_persisted_and_audited(query_context):
    client, session_factory, _, _, finding_id = query_context
    evidence = client.get(f"/v1/findings/{finding_id}/evidence", headers=headers())
    assert evidence.status_code == 200
    assert evidence.json()["items"]

    updated = client.patch(
        f"/v1/findings/{finding_id}/status",
        headers=headers(),
        json={"status": "resolved"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "resolved"
    with session_factory() as session:
        assert session.get(FindingRecord, finding_id).resolved_at is not None
        assert session.scalar(select(AuditLogRecord).where(AuditLogRecord.entity_id == str(finding_id))) is not None
