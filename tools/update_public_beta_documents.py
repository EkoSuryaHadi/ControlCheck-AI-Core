"""Create the versioned public-beta PRD without mutating prior PRDs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.text import WD_BREAK
from docx.shared import Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FIXED_MODIFIED = datetime(2026, 8, 26, tzinfo=timezone.utc)


def _replace(document: DocumentObject, old: str, new: str) -> None:
    for paragraph in document.paragraphs:
        if paragraph.text.strip() == old:
            paragraph.text = new
            return
    raise ValueError(f"Source text not found: {old}")


def _replace_table_row(document: DocumentObject, key: str, replacements: dict[int, str]) -> None:
    for table in document.tables:
        for row in table.rows:
            if row.cells and row.cells[0].text.strip() == key:
                for index, value in replacements.items():
                    row.cells[index].text = value
                return
    raise ValueError(f"Source table row not found: {key}")


def _heading(document: DocumentObject, text: str, level: int = 1) -> None:
    paragraph = document.add_heading(text, level=level)
    paragraph.paragraph_format.keep_with_next = True


def _paragraph(document: DocumentObject, text: str, *, bullet: bool = False) -> None:
    paragraph = document.add_paragraph(text, style="List Bullet" if bullet else None)
    paragraph.paragraph_format.space_after = Pt(2)


def _shading(fill: str):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    return shading


def _table(document: DocumentObject, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True
    for cell, value in zip(table.rows[0].cells, headers, strict=True):
        cell.text = value
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
        cell._tc.get_or_add_tcPr().append(_shading("123047"))
    for row_values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row_values, strict=True):
            cell.text = value
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(8)
    document.add_paragraph()


def build_prd() -> Path:
    target = DOCS / "ControlCheck_AI_PRD_v1.1.docx"
    document = Document(DOCS / "ControlCheck_AI_PRD_v1.0.docx")
    _replace(document, "Product Requirements Document v1.0", "Product Requirements Document v1.1")
    _replace(
        document,
        "Version 1.0 | Universal Flexible Ingestion & Auto-Mapper | 20 August 2026",
        "Version 1.1 | Public Beta Cloud Deployment & Usage Validation | 26 August 2026",
    )
    _replace_table_row(document, "Version", {1: "1.1"})
    document.core_properties.title = "Product Requirements Document v1.1"
    document.core_properties.modified = FIXED_MODIFIED
    document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    _heading(document, "Phase 10 Public Beta Cloud Deployment & Usage Validation Alignment")
    _paragraph(
        document,
        "The public-beta cloud architecture is browser → Vercel frontend → Render Free FastAPI → Supabase Free PostgreSQL plus private Cloudflare R2 Standard object storage.",
    )
    _heading(document, "Hosted data flow", 2)
    _paragraph(
        document,
        "register/login → create project → upload workbook → persist workbook in R2 → canonical ingestion and deterministic analysis on Render → persist run/findings/evidence in Supabase → display results in Vercel.",
    )
    _heading(document, "Public-beta success criteria", 2)
    for item in (
        "hosted register-to-findings flow passes.",
        "uploaded files and results persist across Render restart/cold start.",
        "no secrets appear in source/logs/docs.",
        "registrations, active users, projects, workbook uploads, and completed analysis runs are measurable from persisted records.",
    ):
        _paragraph(document, item, bullet=True)
    _heading(document, "Free-tier constraints and upgrade triggers", 2)
    for item in (
        "Render cold start after idle.",
        "Supabase Free may pause after low activity and has limited capacity/no managed downloadable backups.",
        "R2 Standard free allowance is used and the bucket remains private.",
        "Upgrade when user experience is materially affected by cold starts, Supabase database approaches 400 MB, R2 approaches 8 GB, or usage becomes routine enough to justify an always-on backend.",
    ):
        _paragraph(document, item, bullet=True)
    _heading(document, "Deferred non-goals", 2)
    _paragraph(
        document,
        "full authentication/RBAC hardening, payment/subscription, enterprise SSO, and production-scale HA/DR remain deferred.",
    )
    document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _heading(document, "Change Log v1.1", 2)
    _table(
        document,
        ("Version", "Date", "Change"),
        [("1.1", "26 Aug 2026", "public-beta cloud architecture and usage validation.")],
    )
    document.save(target)
    return target


def main() -> None:
    print("Generated:", build_prd())


if __name__ == "__main__":
    main()
