from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Any

import openpyxl

from .preflight_validator import MS_PROJECT_ALIASES, STANDARD_ALIASES, _as_date, _as_number, _find_column, _read_rows


SCHEDULE_HEADERS = [
    "activity_id", "wbs_code", "activity_name", "discipline",
    "baseline_start", "baseline_finish", "actual_start", "actual_finish",
    "planned_progress", "actual_progress", "total_float_days", "critical", "status",
]


def _cell(row: list[Any], mapping: dict[str, int | None], name: str) -> Any:
    index = mapping.get(name)
    return row[index] if index is not None and index < len(row) else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _date_value(value: Any) -> date | None:
    return _as_date(value)


def _number(value: Any, default: float = 0) -> float:
    parsed = _as_number(value)
    return default if parsed is None else parsed


def build_schedule_workbook(
    data: bytes,
    filename: str,
    *,
    project_code: str,
    project_name: str,
    data_date: date,
    preset: str = "msproject",
) -> bytes:
    """Convert a preflight-validated schedule export to the governed Schedule sheet."""
    sheet_name, headers, source_rows = _read_rows(data, filename)
    aliases = MS_PROJECT_ALIASES if preset == "msproject" else STANDARD_ALIASES
    mapping = {field: _find_column(headers, candidates) for field, candidates in aliases.items()}

    book = openpyxl.Workbook()
    project_sheet = book.active
    project_sheet.title = "Project_Info"
    project_sheet.append(["field", "value"])
    project_sheet.append(["project_id", project_code])
    project_sheet.append(["project_name", project_name])
    project_sheet.append(["data_date", data_date.isoformat()])
    project_sheet.append(["dataset_version", "validated-schedule-v1"])
    project_sheet.append(["source_sheet", sheet_name])

    schedule = book.create_sheet("Schedule")
    schedule.append([])
    schedule.append([])
    schedule.append(SCHEDULE_HEADERS)

    for row in source_rows:
        if not any(value is not None and str(value).strip() for value in row):
            continue
        activity_id = _text(_cell(row, mapping, "activity_id"))
        activity_name = _text(_cell(row, mapping, "activity_name"))
        baseline_start = _date_value(_cell(row, mapping, "baseline_start"))
        baseline_finish = _date_value(_cell(row, mapping, "baseline_finish"))
        if not activity_id or not activity_name or not baseline_start or not baseline_finish:
            continue
        actual_start = _date_value(_cell(row, mapping, "start"))
        actual_finish = _date_value(_cell(row, mapping, "finish"))
        progress = _number(_cell(row, mapping, "progress"))
        total_float = int(round(_number(_cell(row, mapping, "total_float"))))
        status = "completed" if progress >= 100 else "in_progress"
        schedule.append([
            activity_id,
            _text(_cell(row, mapping, "wbs")),
            activity_name,
            None,
            baseline_start,
            baseline_finish,
            actual_start,
            actual_finish,
            progress,
            progress,
            total_float,
            total_float <= 0,
            status,
        ])

    output = BytesIO()
    book.save(output)
    return output.getvalue()
