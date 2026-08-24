from pathlib import Path


def test_phase4b_specifications_exist_and_state_governance(project_root: Path):
    required = [
        project_root / "docs" / "ControlCheck_AI_PRD_v0.4.docx",
        project_root / "docs" / "ControlCheck_AI_ERD_Database_Spec_v0.3.docx",
        project_root / "docs" / "ControlCheck_AI_Control_Rule_Catalogue_v0.3.docx",
        project_root / "docs" / "003_controlcheck_canonical_ingestion_schema_v0.3.sql",
    ]
    assert all(path.exists() and path.stat().st_size > 0 for path in required)
    sql = required[-1].read_text(encoding="utf-8")
    assert "Alembic" in sql
    assert "BIGINT" in sql
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    for phrase in ("immutable dataset snapshot", "source_project_name", "Partial-domain", "Authentication and complete RBAC"):
        assert phrase in readme
