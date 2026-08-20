"""Create versioned Phase 4B specification documents without mutating history."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.text import WD_BREAK
from docx.shared import Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FIXED_MODIFIED = datetime(2026, 8, 20, tzinfo=timezone.utc)


def _replace(document: DocumentObject, old: str, new: str) -> None:
    for paragraph in document.paragraphs:
        if paragraph.text.strip() == old:
            paragraph.text = new
            return
    raise ValueError(f"Source heading not found: {old}")


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
    style = "List Bullet" if bullet else None
    paragraph = document.add_paragraph(text, style=style)
    paragraph.paragraph_format.space_after = Pt(5)


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


def _shading(fill: str):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    return shading


def _prepare(source_name: str, target_name: str, title: str, old_title: str) -> DocumentObject:
    document = Document(DOCS / source_name)
    _replace(document, old_title, title)
    document.core_properties.title = title
    document.core_properties.modified = FIXED_MODIFIED
    document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    return document


def build_erd() -> Path:
    target = DOCS / "ControlCheck_AI_ERD_Database_Spec_v0.3.docx"
    document = _prepare(
        "ControlCheck_AI_ERD_Database_Spec_v0.2.docx",
        target.name,
        "ERD & Database Specification v0.3",
        "ERD & Database Specification v0.2",
    )
    _heading(document, "Phase 4B Canonical Facts Alignment", 1)
    _paragraph(document, "Version 0.3 incorporates the executable schema for verbatim raw row persistence, import batches, column mappings, and canonical fact tables (WBS, budget, cost, commitment, schedule, and progress) delivered in Phase 4B. Alembic migration 20260821_0002 is the executable schema authority.")
    _heading(document, "Implemented Phase 4B tables", 2)
    rows = [
        ("raw_rows", "Verbatim JSON rows with file, sheet, and row reference", "Immutable row-level source lineage"),
        ("import_batches", "Batch ingestion status and row counts", "queued/processing/completed/failed"),
        ("import_column_mappings", "Detected and confirmed column mappings", "Maps source headers to canonical fields"),
        ("wbs_nodes", "Canonical WBS hierarchy linked to raw rows", "Hierarchical WBS master"),
        ("budget_records", "Canonical budget facts linked to raw rows", "Budget amounts and cost codes"),
        ("cost_records", "Canonical actual cost facts linked to raw rows", "Actual transaction records with vendors/POs"),
        ("commitment_records", "Canonical commitment facts linked to raw rows", "Committed and invoiced amounts"),
        ("schedule_activities", "Canonical schedule activities linked to raw rows", "Activities, dates, float, and critical path"),
        ("progress_records", "Canonical progress facts linked to raw rows", "Physical progress and variances per period"),
    ]
    _table(document, ("Table", "Purpose", "Key contract"), rows)
    _heading(document, "Lineage and Integrity Guarantees", 2)
    for item in (
        "Every canonical fact record maintains a raw_row_id backlink to its originating raw_rows entry for auditability.",
        "Raw rows are indexed by (organization_id, project_id, source_file_id) with unique constraints on (source_file_id, sheet_name, row_number).",
        "All canonical fact tables are scoped by organization_id and dataset_snapshot_id for multi-tenant isolation.",
        "Ingestion and normalization occur atomically within the dataset snapshot creation transaction.",
    ):
        _paragraph(document, item, bullet=True)
    document.save(target)
    return target


def build_prd() -> Path:
    target = DOCS / "ControlCheck_AI_PRD_v0.4.docx"
    document = _prepare(
        "ControlCheck_AI_PRD_v0.3.docx",
        target.name,
        "Product Requirements Document v0.4",
        "Product Requirements Document v0.3",
    )
    _replace(document, "Version 0.3 | Backend Persistence Alignment | 17 August 2026", "Version 0.4 | Raw Lineage & Canonical Facts Alignment | 20 August 2026")
    _replace_table_row(document, "Version", {1: "0.4"})
    _heading(document, "Phase 4B Product Alignment", 1)
    _paragraph(document, "Phase 4B delivers verbatim raw row lineage and canonical fact normalization. Every imported Excel row is stored verbatim, and normalized into canonical WBS, budget, cost, commitment, schedule, and progress fact tables, with each fact retaining a direct foreign-key link to its raw row.")
    _heading(document, "Scope delivered in Phase 4B", 2)
    for item in (
        "Verbatim raw row ingestion with sheet name and row number preservation.",
        "Canonical fact normalization for all six domains with raw_row_id foreign-key lineage.",
        "Import batches and column mapping metadata tables.",
        "Automated raw row extraction and normalization pipeline in the application service.",
        "Reversible Alembic migration 20260821_0002.",
    ):
        _paragraph(document, item, bullet=True)
    _heading(document, "Change Log v0.4", 2)
    _table(
        document,
        ("Version", "Date", "Change"),
        [
            ("0.1", "17 Aug 2026", "Initial MVP blueprint."),
            ("0.2", "17 Aug 2026", "Rule and synthetic validation alignment."),
            ("0.3", "17 Aug 2026", "Phase 4A PostgreSQL persistence, durable API, storage, lifecycle, and Phase 4B sequencing."),
            ("0.4", "20 Aug 2026", "Phase 4B raw-row lineage, canonical fact normalization, and import batch tracking."),
        ],
    )
    document.save(target)
    return target


def main() -> None:
    outputs = (build_erd(), build_prd())
    for output in outputs:
        print("Generated:", output)


if __name__ == "__main__":
    main()
