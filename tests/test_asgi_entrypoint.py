from __future__ import annotations

import importlib.util

from fastapi import FastAPI

import controlcheck.actions_api
import controlcheck.api
import controlcheck.governance_api
import controlcheck.reports_api


def test_local_asgi_entrypoint_creates_and_configures_one_application(monkeypatch) -> None:
    application = FastAPI()
    calls: list[str] = []

    monkeypatch.setattr(
        controlcheck.api,
        "create_configured_app",
        lambda: calls.append("create") or application,
    )
    monkeypatch.setattr(
        controlcheck.actions_api,
        "install_action_routes",
        lambda received: calls.append("actions") if received is application else None,
    )
    monkeypatch.setattr(
        controlcheck.governance_api,
        "install_governance_routes",
        lambda received: calls.append("governance") if received is application else None,
    )
    monkeypatch.setattr(
        controlcheck.reports_api,
        "install_report_routes",
        lambda received: calls.append("reports") if received is application else None,
    )
    spec = importlib.util.find_spec("controlcheck.asgi")

    assert spec is not None

    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.app is application
    assert calls == ["create", "actions", "governance", "reports"]
