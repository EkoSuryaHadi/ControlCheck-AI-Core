from pathlib import Path

from fastapi.testclient import TestClient

from controlcheck.api import create_app


def test_health(sample_catalogue):
    client = TestClient(create_app(sample_catalogue))
    assert client.get("/health").json() == {"status": "ok", "engine_version": "0.2.0"}


def test_audit_rejects_non_xlsx(sample_catalogue):
    client = TestClient(create_app(sample_catalogue))
    response = client.post("/v1/audits", files={"file": ("bad.txt", b"text", "text/plain")})
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_file_type"


def test_audit_accepts_valid_workbook(sample_catalogue, sample_workbook):
    client = TestClient(create_app(sample_catalogue))
    with Path(sample_workbook).open("rb") as source:
        response = client.post(
            "/v1/audits",
            files={"file": ("project.xlsx", source, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["rule_count"] == 20
    assert payload["finding_count"] == len(payload["findings"])


def test_audit_rejects_oversize_upload(sample_catalogue):
    client = TestClient(create_app(sample_catalogue, max_upload_bytes=8))
    response = client.post(
        "/v1/audits",
        files={"file": ("large.xlsx", b"0123456789", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"


def test_audit_rejects_malformed_xlsx_without_parser_details(sample_catalogue):
    client = TestClient(create_app(sample_catalogue), raise_server_exceptions=False)

    response = client.post(
        "/v1/audits",
        files={
            "file": (
                "invalid.xlsx",
                b"not a zip archive",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "invalid_workbook",
        "message": "Workbook could not be parsed",
    }
    assert "zip" not in response.text.lower()
