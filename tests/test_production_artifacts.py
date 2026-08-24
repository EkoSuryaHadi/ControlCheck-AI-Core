from pathlib import Path


def test_dockerfile_runs_as_non_root_and_has_no_reload(project_root: Path):
    dockerfile = (project_root / "Dockerfile").read_text(encoding="utf-8")

    assert "USER controlcheck" in dockerfile
    assert "--reload" not in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "python:3.11.9-slim-bookworm" in dockerfile


def test_entrypoint_migrates_before_starting_server(project_root: Path):
    entrypoint = (project_root / "docker" / "entrypoint.sh").read_text(
        encoding="utf-8"
    )

    migration = entrypoint.index("alembic upgrade head")
    server = entrypoint.index("exec uvicorn")
    assert migration < server
    assert "--reload" not in entrypoint


def test_example_environment_contains_placeholders_not_secrets(project_root: Path):
    example = (project_root / ".env.example").read_text(encoding="utf-8")

    assert (
        "CONTROLCHECK_API_KEY=<generate-a-random-32-plus-character-secret>"
        in example
    )
    assert "CONTROLCHECK_ENV=production" in example
    assert "CONTROLCHECK_UPLOAD_ROOT=/var/lib/controlcheck/uploads" in example
    assert "postgresql+psycopg://controlcheck:controlcheck" not in example


def test_container_context_excludes_local_secrets_and_state(project_root: Path):
    ignored = (project_root / ".dockerignore").read_text(encoding="utf-8")

    for required in (".git", ".env", "var", ".worktrees", "results"):
        assert required in ignored


def test_alembic_uses_runtime_database_url(project_root: Path):
    environment = (project_root / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "CONTROLCHECK_DATABASE_URL" in environment


def test_ci_runs_database_and_deterministic_release_gates(project_root: Path):
    workflow = (
        project_root / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")

    for required in (
        "permissions:",
        "contents: read",
        "postgres:16-alpine",
        "alembic upgrade head",
        "alembic check",
        "python -m pytest",
        "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
        "ControlCheck_AI_Boundary_Negative_Dataset_v0.2.xlsx",
        "--strict",
        "docker build",
    ):
        assert required in workflow
    assert "pull_request_target" not in workflow


def test_runbook_covers_required_operations(project_root: Path):
    runbook = (project_root / "docs" / "PRODUCTION_RUNBOOK.md").read_text(
        encoding="utf-8"
    )

    for topic in (
        "Deployment",
        "Alembic migrations",
        "API key rotation",
        "Backup verification",
        "Rollback",
        "Incident diagnostics",
        "single replica",
    ):
        assert topic in runbook


def test_production_prd_is_versioned_and_readme_links_runbook(project_root: Path):
    production_prd = project_root / "docs" / "ControlCheck_AI_PRD_v0.5.docx"
    readme = (project_root / "README.md").read_text(encoding="utf-8")

    assert production_prd.exists() and production_prd.stat().st_size > 0
    assert "docs/PRODUCTION_RUNBOOK.md" in readme
    assert "development-only" in readme
