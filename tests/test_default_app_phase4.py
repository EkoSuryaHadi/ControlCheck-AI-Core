from controlcheck.api import create_configured_app


def test_configured_app_enables_durable_routes_from_environment(monkeypatch, project_root, tmp_path):
    monkeypatch.setenv(
        "CONTROLCHECK_DATABASE_URL",
        "postgresql+psycopg://controlcheck:controlcheck@127.0.0.1:54329/controlcheck",
    )
    monkeypatch.setenv("CONTROLCHECK_UPLOAD_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "CONTROLCHECK_CATALOGUE",
        str(project_root / "data" / "controlcheck_rule_catalogue_v0.2.json"),
    )

    application = create_configured_app()
    paths = {route.path for route in application.routes}

    assert "/v1/projects/{project_id}/analysis-runs" in paths
    assert "/v1/findings/{finding_id}/evidence" in paths
