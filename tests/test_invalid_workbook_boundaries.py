from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from controlcheck.api import create_app
from controlcheck.persistence.repositories import ProjectRepository
from controlcheck.storage import LocalFileStorage


def _valid_zip_without_xlsx_members() -> bytes:
    target = BytesIO()
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        archive.writestr("readme.txt", "not an xlsx workbook")
    return target.getvalue()


def _xlsx_with_malformed_workbook_xml(valid_workbook: bytes) -> bytes:
    source = BytesIO(valid_workbook)
    target = BytesIO()
    with ZipFile(source, "r") as original, ZipFile(target, "w", ZIP_DEFLATED) as broken:
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename == "xl/workbook.xml":
                data = b"<workbook><broken>"
            broken.writestr(item, data)
    return target.getvalue()


@pytest.fixture(params=["non_xlsx_zip", "malformed_xml"])
def invalid_xlsx_bytes(request, sample_workbook):
    if request.param == "non_xlsx_zip":
        return _valid_zip_without_xlsx_members()
    return _xlsx_with_malformed_workbook_xml(sample_workbook.read_bytes())


@pytest.fixture(params=["audit", "snapshot"])
def invalid_workbook_endpoint(
    request,
    monkeypatch,
    sample_catalogue,
    tmp_path,
):
    if request.param == "audit":
        return (
            TestClient(create_app(sample_catalogue), raise_server_exceptions=False),
            "/v1/audits",
            {},
        )

    monkeypatch.setattr(
        ProjectRepository,
        "get_scoped",
        lambda *_args, **_kwargs: SimpleNamespace(code="PROJECT"),
    )
    app = create_app(
        sample_catalogue,
        session_factory=sessionmaker(),
        storage=LocalFileStorage(tmp_path),
    )
    return (
        TestClient(app, raise_server_exceptions=False),
        "/v1/projects/11111111-1111-1111-1111-111111111111/dataset-snapshots",
        {"X-Organization-ID": "22222222-2222-2222-2222-222222222222"},
    )


def test_parser_originated_invalid_workbooks_are_safe_422(
    invalid_xlsx_bytes: bytes,
    invalid_workbook_endpoint,
) -> None:
    client, path, headers = invalid_workbook_endpoint

    response = client.post(
        path,
        headers=headers,
        files={
            "file": (
                "invalid.xlsx",
                invalid_xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 422
    payload = response.json()
    error = payload.get("error", payload.get("detail"))
    assert error["code"] == "invalid_workbook"
    assert error["message"] == "Workbook could not be parsed"
    body = response.text.lower()
    for internal in ("keyerror", "content_types", "workbook.xml", "syntax"):
        assert internal not in body
