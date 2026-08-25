from __future__ import annotations

import runpy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import controlcheck.api


ENTRYPOINT = Path(__file__).resolve().parents[1] / "api" / "index.py"


def _load_entrypoint() -> dict[str, object]:
    return runpy.run_path(str(ENTRYPOINT), run_name="controlcheck_serverless_test")


def test_serverless_entrypoint_does_not_publish_diagnostics(monkeypatch) -> None:
    monkeypatch.delenv("CONTROLCHECK_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    namespace = _load_entrypoint()
    client = TestClient(namespace["app"])

    response = client.get("/api/diagnostic")
    assert response.status_code == 404
    payload = response.text.lower()
    assert "sys_path" not in payload
    assert "env_keys" not in payload
    assert "import_status" not in payload
    assert "traceback" not in payload


def test_serverless_entrypoint_propagates_startup_failure(monkeypatch) -> None:
    def fail_startup():
        raise RuntimeError("configuration unavailable")

    monkeypatch.setattr(controlcheck.api, "create_configured_app", fail_startup)

    with pytest.raises(RuntimeError, match="configuration unavailable"):
        _load_entrypoint()


def test_serverless_entrypoint_preserves_configured_storage(monkeypatch, tmp_path) -> None:
    configured_root = str(tmp_path / "durable-uploads")
    monkeypatch.setenv("CONTROLCHECK_UPLOAD_ROOT", configured_root)

    _load_entrypoint()

    assert __import__("os").environ["CONTROLCHECK_UPLOAD_ROOT"] == configured_root
