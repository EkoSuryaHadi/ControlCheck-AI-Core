from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

import openpyxl
import pytest

from controlcheck.ingestion.extractor import extract_workbook
from controlcheck.ingestion.profile import load_mapping_profile


@pytest.fixture()
def mapping_profile(project_root: Path):
    return load_mapping_profile(project_root / "data/controlcheck_mapping_profile_v0.1.json")


@pytest.fixture()
def golden_bytes(project_root: Path) -> bytes:
    return (project_root / "data/ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx").read_bytes()


@pytest.fixture()
def invalid_progress_workbook(golden_bytes: bytes) -> bytes:
    book = openpyxl.load_workbook(BytesIO(golden_bytes))
    sheet = book["Progress"]
    sheet.append(["PRG-INVALID", "2026-08-31", "WBS-001", "25%", "not-a-percent", "0%", "Open"])
    result = BytesIO()
    book.save(result)
    book.close()
    return result.getvalue()


def test_golden_extractor_retains_all_domain_rows(golden_bytes, mapping_profile):
    extracted = extract_workbook(golden_bytes, mapping_profile)

    assert {name: len(rows) for name, rows in extracted.rows_by_domain.items()} == {
        "wbs": 12,
        "budget": 9,
        "actual_cost": 73,
        "commitments": 6,
        "schedule": 13,
        "progress": 36,
    }
    assert extracted.template_errors == []
    assert extracted.project_values["project_id"] == "PRJ-CCAI-001"
    assert extracted.workbook_sha256 == sha256(golden_bytes).hexdigest()


def test_non_empty_invalid_row_is_retained(invalid_progress_workbook, mapping_profile):
    extracted = extract_workbook(invalid_progress_workbook, mapping_profile)

    row = extracted.rows_by_domain["progress"][-1]
    assert row.values["actual_progress"] == "not-a-percent"
    assert row.source_row_number > 1


def test_missing_governed_sheet_becomes_a_stable_template_issue(golden_bytes, mapping_profile):
    book = openpyxl.load_workbook(BytesIO(golden_bytes))
    del book["Progress"]
    payload = BytesIO()
    book.save(payload)
    book.close()

    extracted = extract_workbook(payload.getvalue(), mapping_profile)

    assert extracted.rows_by_domain["progress"] == []
    assert [(issue.code, issue.domain, issue.sheet_name) for issue in extracted.template_errors] == [
        ("missing_sheet", "progress", "Progress"),
    ]


def test_malformed_headers_are_reported_in_a_stable_order_without_dropping_rows(
    golden_bytes, mapping_profile
):
    book = openpyxl.load_workbook(BytesIO(golden_bytes))
    sheet = book["Progress"]
    sheet.cell(row=3, column=2, value="progress_id")
    sheet.cell(row=3, column=8, value="unexpected")
    payload = BytesIO()
    book.save(payload)
    book.close()

    first = extract_workbook(payload.getvalue(), mapping_profile)
    second = extract_workbook(payload.getvalue(), mapping_profile)

    assert len(first.rows_by_domain["progress"]) == 36
    assert [(issue.code, issue.domain, issue.sheet_name) for issue in first.template_errors] == [
        ("duplicate_header", "progress", "Progress"),
        ("missing_required_column", "progress", "Progress"),
        ("unexpected_header", "progress", "Progress"),
    ]
    assert first.template_errors == second.template_errors


def test_extracted_values_are_json_safe_and_source_keys_are_deterministic(
    golden_bytes, mapping_profile
):
    first = extract_workbook(golden_bytes, mapping_profile)
    second = extract_workbook(golden_bytes, mapping_profile)

    first_rows = first.rows_by_domain["schedule"]
    second_rows = second.rows_by_domain["schedule"]
    assert json.loads(json.dumps(first_rows[0].values)) == first_rows[0].values
    assert [row.source_key for row in first_rows] == [row.source_key for row in second_rows]
    assert len({row.source_key for row in first_rows}) == len(first_rows)
