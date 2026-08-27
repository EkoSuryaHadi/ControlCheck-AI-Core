from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import controlcheck
import controlcheck.api
from controlcheck.settings import ProductionSettings


ENTRYPOINT = Path(__file__).resolve().parents[1] / "api" / "index.py"


def _load_entrypoint() -> dict[str, object]:
    sys.modules.pop("controlcheck.asgi", None)
    controlcheck.__dict__.pop("asgi", None)
    return runpy.run_path(str(ENTRYPOINT), run_name="controlcheck_serverless_test")


def test_serverless_entrypoint_bootstraps_source_package_once(monkeypatch) -> None:
    source_root = str(ENTRYPOINT.parents[1] / "src")
    isolated_path = [entry for entry in sys.path if entry != source_root]
    monkeypatch.setattr(sys, "path", isolated_path.copy())

    _load_entrypoint()
    _load_entrypoint()

    assert sys.path[0] == source_root
    assert sys.path.count(source_root) == 1


def test_serverless_entrypoint_creates_one_configured_application(monkeypatch) -> None:
    calls = 0
    original_from_env = ProductionSettings.from_env
    previous_api = sys.modules.pop("controlcheck.api")

    def counted_from_env():
        nonlocal calls
        calls += 1
        return original_from_env()

    monkeypatch.setattr(
        ProductionSettings,
        "from_env",
        staticmethod(counted_from_env),
    )
    try:
        _load_entrypoint()
        assert calls == 1
    finally:
        sys.modules["controlcheck.api"] = previous_api
        controlcheck.api = previous_api
        sys.modules.pop("controlcheck.asgi", None)


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
