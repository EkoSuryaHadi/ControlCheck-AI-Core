from __future__ import annotations

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from controlcheck.api import create_app
from controlcheck.errors import InvalidWorkbookError
from controlcheck.ingestion.service import SnapshotIngestionService
from controlcheck.storage import LocalFileStorage
from controlcheck.storage_s3 import S3FileStorage


@pytest.mark.parametrize(
    ("failure", "expected_status", "expected_code"),
    [
        (InvalidWorkbookError("unsafe workbook parser detail"), 422, "invalid_workbook"),
        (
            OperationalError("SELECT secret", {}, RuntimeError("database password")),
            503,
            "snapshot_service_unavailable",
        ),
        (RuntimeError("unsafe implementation detail"), 500, "snapshot_ingestion_failed"),
    ],
)
def test_snapshot_upload_classifies_failures_without_exposing_internals(
    monkeypatch,
    sample_catalogue,
    tmp_path,
    failure: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    def fail_ingestion(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(SnapshotIngestionService, "ingest", fail_ingestion)
    app = create_app(
        sample_catalogue,
        session_factory=sessionmaker(),
        storage=LocalFileStorage(tmp_path),
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/v1/projects/11111111-1111-1111-1111-111111111111/dataset-snapshots",
        headers={"X-Organization-ID": "22222222-2222-2222-2222-222222222222"},
        files={
            "file": (
                "project.xlsx",
                b"not important at this boundary",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    body = response.text.lower()
    assert "unsafe" not in body
    assert "password" not in body
    assert "select secret" not in body


@pytest.mark.parametrize("operation", ["put", "head"])
def test_s3_provider_failure_returns_safe_503_envelope(
    monkeypatch,
    sample_catalogue,
    operation: str,
) -> None:
    class FailingClient:
        def fail(self, name: str):
            raise ClientError(
                {
                    "Error": {"Code": "AccessDenied", "Message": "provider secret"},
                    "ResponseMetadata": {"HTTPStatusCode": 403},
                },
                name,
            )

        def put_object(self, **_kwargs):
            self.fail("PutObject")

        def head_object(self, **_kwargs):
            self.fail("HeadObject")

    storage = S3FileStorage(bucket="workbooks")
    storage._client = FailingClient()

    def fail_through_storage(service, *_args, **_kwargs):
        if operation == "put":
            service.storage.put(
                _args[0], _args[1], "project.xlsx", b"xlsx"
            )
        else:
            service.storage.exists("org/project/project.xlsx")

    monkeypatch.setattr(SnapshotIngestionService, "ingest", fail_through_storage)
    client = TestClient(
        create_app(
            sample_catalogue,
            session_factory=sessionmaker(),
            storage=storage,
        ),
        raise_server_exceptions=False,
    )

    response = client.post(
        "/v1/projects/11111111-1111-1111-1111-111111111111/dataset-snapshots",
        headers={"X-Organization-ID": "22222222-2222-2222-2222-222222222222"},
        files={
            "file": (
                "project.xlsx",
                b"not important at this boundary",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"
    assert "provider secret" not in response.text.lower()
