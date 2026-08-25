from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _steps(job: dict[str, object]) -> dict[str, dict[str, str]]:
    return {
        step["name"]: step
        for step in job["steps"]  # type: ignore[index]
        if "name" in step
    }


def test_ci_runs_the_consolidated_production_baseline_gates() -> None:
    workflow = yaml.load(
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    jobs = workflow["jobs"]
    frontend = jobs["test-frontend"]
    backend = jobs["test-backend"]
    frontend_steps = _steps(frontend)
    backend_steps = _steps(backend)

    postgres = backend["services"]["postgres"]
    assert postgres["image"].startswith("postgres:16")
    assert backend["env"]["CONTROLCHECK_TEST_POSTGRES_URL"].endswith("/postgres")

    compile_command = backend_steps["Compile Python sources"]["run"]
    assert "python -m compileall" in compile_command
    for package in ("api", "src", "tests", "tools", "alembic"):
        assert package in compile_command.split()

    assert "tests/test_production_configuration.py" in backend_steps[
        "Validate production configuration"
    ]["run"]
    assert backend_steps["Run full backend suite"]["run"].startswith(
        "python -m pytest"
    )
    assert "test_alembic_metadata_has_no_drift" in backend_steps[
        "Check migration drift"
    ]["run"]

    setup_node = frontend_steps["Set up Node.js 20"]
    assert setup_node["with"]["cache-dependency-path"] == "frontend/package-lock.json"
    assert frontend_steps["Clean install frontend dependencies"]["run"] == "npm ci"
    assert frontend_steps["Build and typecheck React SPA"]["run"] == "npm run build"
    assert frontend_steps["Lint React SPA"]["run"] == "npm run lint"
