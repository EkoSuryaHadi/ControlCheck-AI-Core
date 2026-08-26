from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _docx_text(path: Path) -> str:
    document = Document(path)
    blocks = [paragraph.text for paragraph in document.paragraphs]
    blocks.extend(cell.text for table in document.tables for row in table.rows for cell in row.cells)
    return "\n".join(blocks)


def test_prd_v12_records_vercel_hybrid_public_beta_contract() -> None:
    text = _docx_text(DOCS / "ControlCheck_AI_PRD_v1.2.docx")

    for expected in (
        "Product Requirements Document v1.2",
        "Version 1.2 | Vercel Hybrid Public Beta Deployment | 26 August 2026",
        "Phase 10 Vercel Hybrid Public Beta Deployment Alignment",
        "Vercel React + FastAPI",
        "browser → Vercel React frontend → Vercel FastAPI Function → Supabase PostgreSQL + private Cloudflare R2",
        "register/login → create project → upload workbook",
        "4 MiB",
        "240-second",
        "500 MB",
        "explicit release step",
        "fail closed",
        "direct-to-R2",
        "hosted register-to-findings flow passes",
        "no secrets appear in source/logs/docs",
        "registrations, active users, projects, workbook uploads, and completed analysis runs are measurable from persisted records",
        "Supabase Free may pause after low activity and has limited capacity/no managed downloadable backups",
        "R2 Standard free allowance is used and the bucket remains private",
        "Supabase database approaches 400 MB",
        "R2 approaches 8 GB",
        "full authentication/RBAC hardening, payment/subscription, enterprise SSO, and production-scale HA/DR remain deferred",
        "Change Log v1.2",
        "26 Aug 2026",
        "Vercel hybrid public-beta architecture",
    ):
        assert expected in text

    for forbidden in (
        "Vercel frontend → Render",
        "Deploy the Render",
        "persist across Render restart",
    ):
        assert forbidden not in text


def test_public_beta_operations_docs_record_exact_architecture_and_recovery_contract() -> None:
    runbook = (DOCS / "PRODUCTION_RUNBOOK.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_readme = (DOCS / "README.md").read_text(encoding="utf-8")
    architecture = "browser → Vercel React frontend → Vercel FastAPI Function → Supabase PostgreSQL + private Cloudflare R2"

    required = (
        architecture,
        "Vercel React + FastAPI",
        "Supabase",
        "Cloudflare R2",
        "4 MiB",
        "explicit release step",
        "register/login → create project → upload workbook",
        "Apply Supabase migrations explicitly",
        "Create private R2 bucket and scoped credentials",
        "Configure Vercel production/preview secrets",
        "Deploy the hybrid Vercel project",
        "Verify readiness and register-to-findings persistence",
        "CONTROLCHECK_DATABASE_URL",
        "controlcheck-beta-workbooks",
        "no secrets appear in source/logs/docs",
        "Registrations, active users, projects, workbook uploads, and completed analysis runs",
        "region `auto`",
        "Supabase database approaches 400 MB",
        "R2 approaches 8 GB",
        "Full authentication/RBAC hardening, payment/subscription, enterprise SSO, and production-scale HA/DR remain deferred",
    )
    for document in (runbook, readme, docs_readme):
        for expected in required[:6]:
            assert expected in document

    for expected in required[6:]:
        assert expected in runbook
    for expected in required[1:6] + required[12:]:
        assert expected in readme

    for forbidden in (
        "Vercel frontend → Render",
        "Deploy the Render",
        "persist across Render restart",
    ):
        assert forbidden not in runbook
        assert forbidden not in readme

    assert not (ROOT / "render.yaml").exists()


def test_public_beta_document_generator_and_plan_are_versioned() -> None:
    assert (ROOT / "tools" / "update_public_beta_documents.py").is_file()
    assert (DOCS / "superpowers" / "plans" / "2026-08-26-public-beta-cloud-deployment.md").is_file()


def test_public_beta_prd_generator_is_archive_byte_deterministic() -> None:
    generator = ROOT / "tools" / "update_public_beta_documents.py"
    target = DOCS / "ControlCheck_AI_PRD_v1.2.docx"

    subprocess.run([sys.executable, str(generator)], cwd=ROOT, check=True)
    first = target.read_bytes()
    time.sleep(2.1)
    subprocess.run([sys.executable, str(generator)], cwd=ROOT, check=True)

    assert target.read_bytes() == first
    assert target.name == "ControlCheck_AI_PRD_v1.2.docx"
