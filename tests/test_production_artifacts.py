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
