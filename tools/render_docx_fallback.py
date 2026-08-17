"""Fallback DOCX content renderer used when LibreOffice/Word is unavailable.

The DOCX itself remains the source artifact. This renderer preserves document
block order, headings, lists, paragraphs, and tables for paginated visual QA.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def iter_blocks(document: DocumentObject):
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield DocxParagraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield DocxTable(child, document)


def page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#536A77"))
    canvas.drawRightString(doc.pagesize[0] - 0.55 * inch, 0.38 * inch, f"Page {doc.page}")
    canvas.restoreState()


def render(source: Path, output: Path) -> None:
    document = Document(source)
    section = document.sections[0]
    page_width = section.page_width / 12700
    page_height = section.page_height / 12700
    left = section.left_margin / 12700
    right = section.right_margin / 12700
    top = section.top_margin / 12700
    bottom = section.bottom_margin / 12700
    available_width = page_width - left - right

    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = SimpleDocTemplate(
        str(output),
        pagesize=(page_width, page_height),
        leftMargin=left,
        rightMargin=right,
        topMargin=top,
        bottomMargin=bottom,
        title="ControlCheck AI PRD v0.2 QA Preview",
    )
    defaults = getSampleStyleSheet()
    styles = {
        "Normal": ParagraphStyle("Body", parent=defaults["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.2, textColor=colors.HexColor("#1F3542"), spaceAfter=4),
        "Heading 1": ParagraphStyle("H1", parent=defaults["Heading1"], fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=colors.HexColor("#123047"), spaceBefore=10, spaceAfter=6, keepWithNext=True),
        "Heading 2": ParagraphStyle("H2", parent=defaults["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=colors.HexColor("#0F6B6D"), spaceBefore=7, spaceAfter=4, keepWithNext=True),
        "List Bullet": ParagraphStyle("Bullet", parent=defaults["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.2, leftIndent=14, firstLineIndent=-8, bulletIndent=4, spaceAfter=2),
        "List Number": ParagraphStyle("Number", parent=defaults["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.2, leftIndent=14, firstLineIndent=-8, spaceAfter=2),
        "Cover": ParagraphStyle("Cover", parent=defaults["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, alignment=TA_CENTER, textColor=colors.HexColor("#123047"), spaceAfter=12),
    }

    story = []
    list_number = 0
    for index, block in enumerate(iter_blocks(document)):
        if isinstance(block, DocxParagraph):
            text = block.text.strip()
            if not text:
                story.append(Spacer(1, 3))
                continue
            style_name = block.style.name if block.style else "Normal"
            if index < 4:
                style = styles["Cover"] if index == 0 else styles["Normal"]
            else:
                style = styles.get(style_name, styles["Normal"])
            safe = escape(text).replace("\n", "<br/>")
            if style_name == "List Bullet":
                safe = f"• {safe}"
            elif style_name == "List Number":
                list_number += 1
                safe = f"{list_number}. {safe}"
            else:
                list_number = 0
            if "w:type=\"page\"" in block._p.xml:
                story.append(PageBreak())
            story.append(Paragraph(safe, style))
        else:
            data = []
            for row in block.rows:
                data.append([
                    Paragraph(escape(cell.text).replace("\n", "<br/>"), styles["Normal"])
                    for cell in row.cells
                ])
            if not data:
                continue
            col_count = max(len(row) for row in data)
            table = Table(data, colWidths=[available_width / col_count] * col_count, repeatRows=1, hAlign=TA_LEFT)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123047")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B9CAD3")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F6")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.extend([table, Spacer(1, 6)])

    pdf.build(story, onFirstPage=page_number, onLaterPages=page_number)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.source, args.output)


if __name__ == "__main__":
    main()
