from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient

from controlcheck.api import create_app
from controlcheck.persistence.ingestion_repositories import SnapshotRepository
from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import OrganizationRecord, ProjectRecord
from controlcheck.storage import LocalFileStorage


PRIMARY_ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_ORG_ID = UUID("22222222-2222-2222-2222-222222222222")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture()
def snapshot_client(alembic_config, postgres_url, project_root: Path, tmp_path: Path):
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    session_factory = create_session_factory(postgres_url)
    with session_factory() as session:
        primary = OrganizationRecord(
            id=PRIMARY_ORG_ID,
            name="Snapshot API primary",
            slug=f"snapshot-api-primary-{uuid4().hex}",
        )
        other = OrganizationRecord(
            id=OTHER_ORG_ID,
            name="Snapshot API other",
            slug=f"snapshot-api-other-{uuid4().hex}",
        )
        session.add_all([primary, other])
        session.flush()
        project = ProjectRecord(
            organization_id=primary.id,
            code="PRJ-CCAI-001",
            name="Golden",
            currency="IDR",
            status="active",
        )
        session.add(project)
        session.commit()
    app = create_app(
        project_root / "data" / "controlcheck_rule_catalogue_v0.2.json",
        session_factory=session_factory,
        storage=LocalFileStorage(tmp_path / "api-storage"),
    )
    with TestClient(app) as client:
        yield (
            client,
            project.id,
            project_root
            / "data"
            / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
        )


def _headers(organization_id: UUID = PRIMARY_ORG_ID) -> dict[str, str]:
    return {"X-Organization-ID": str(organization_id)}


def _upload_snapshot(client, project_id, workbook, *, force_new=False, name="golden.xlsx"):
    suffix = "?force_new=true" if force_new else ""
    with workbook.open("rb") as source:
        return client.post(
            f"/v1/projects/{project_id}/dataset-snapshots{suffix}",
            headers=_headers(),
            files={"file": (name, source, XLSX_MIME)},
        )


def test_snapshot_api_upload_list_detail_and_tenant_scope(snapshot_client) -> None:
    client, project_id, workbook = snapshot_client
    with workbook.open("rb") as source:
        uploaded = client.post(
            f"/v1/projects/{project_id}/dataset-snapshots",
            headers=_headers(),
            files={"file": ("golden.xlsx", source, XLSX_MIME)},
        )

    assert uploaded.status_code == 201, uploaded.text
    snapshot = uploaded.json()
    assert snapshot["status"] == "validated"
    assert snapshot["storage_contract"] == "governed"
    assert snapshot["source_project_name"] == (
        "EPC Gas Compression Facility Expansion"
    )
    assert snapshot["row_count_raw"] == 149
    assert snapshot["row_count_canonical"] == 149
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

    denied = client.get(
        f"/v1/projects/{project_id}/dataset-snapshots/{snapshot['id']}",
        headers=_headers(OTHER_ORG_ID),
    )
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "snapshot_not_found"

    analyzed = client.post(
        f"/v1/projects/{project_id}/dataset-snapshots/{snapshot['id']}/analysis-runs",
        headers=_headers(),
    )
    assert analyzed.status_code == 201, analyzed.text
    run = analyzed.json()
    assert run["finding_count"] == 59
    assert run["rule_count"] == 20
    assert run["executed_rule_ids"] == sorted(run["executed_rule_ids"])
    assert len(run["executed_rule_ids"]) == 20
    assert run["skipped_rules"] == []


def test_snapshot_api_status_comes_from_created_or_deduplicated_outcome(
    snapshot_client,
    monkeypatch,
) -> None:
    client, project_id, workbook = snapshot_client

    created = _upload_snapshot(client, project_id, workbook)
    duplicate = _upload_snapshot(client, project_id, workbook, name="renamed.xlsx")
    forced = _upload_snapshot(client, project_id, workbook, force_new=True)

    assert created.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == created.json()["id"]
    assert forced.status_code == 201
    assert forced.json()["id"] != created.json()["id"]

    original_find_duplicate = SnapshotRepository.find_duplicate
    calls = 0

    def hide_winner_during_both_preflight_reads(
        repository,
        organization_id,
        scoped_project_id,
        dedupe_key,
    ):
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return original_find_duplicate(
            repository,
            organization_id,
            scoped_project_id,
            dedupe_key,
        )

    monkeypatch.setattr(
        SnapshotRepository,
        "find_duplicate",
        hide_winner_during_both_preflight_reads,
    )

    raced = _upload_snapshot(client, project_id, workbook, name="raced.xlsx")

    assert calls == 2
    assert raced.status_code == 200
    assert raced.json()["id"] == created.json()["id"]
