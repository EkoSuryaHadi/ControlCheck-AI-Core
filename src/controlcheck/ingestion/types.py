from __future__ import annotations

from dataclasses import dataclass
from typing import Any


GOVERNED_DOMAINS = (
    "actual_cost",
    "budget",
    "commitments",
    "progress",
    "schedule",
    "wbs",
)


@dataclass(frozen=True)
class TemplateIssue:
    code: str
    message: str
    domain: str
    sheet_name: str


@dataclass(frozen=True)
class ExtractedRow:
    domain: str
    sheet_name: str
    source_row_number: int
    values: dict[str, Any]
    source_key: str


@dataclass(frozen=True)
class ExtractedWorkbook:
    project_values: dict[str, Any]
    rows_by_domain: dict[str, list[ExtractedRow]]
    template_errors: list[TemplateIssue]
    workbook_sha256: str
