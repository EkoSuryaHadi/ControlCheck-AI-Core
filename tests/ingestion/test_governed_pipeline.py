from __future__ import annotations

from io import BytesIO
from pathlib import Path

import openpyxl


def _pipeline(project_root: Path):
    from controlcheck.ingestion.extractor import extract_workbook
    from controlcheck.ingestion.mapper import DomainStatus, map_extracted_workbook
    from controlcheck.ingestion.profile import load_mapping_profile

    profile = load_mapping_profile(
        project_root / "data" / "controlcheck_mapping_profile_v0.1.json"
    )
    return extract_workbook, map_extracted_workbook, DomainStatus, profile


def test_extraction_preserves_coordinates_and_every_collision_prone_cell(
    project_root: Path,
) -> None:
    extract_workbook, _, _, profile = _pipeline(project_root)
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Progress"
    sheet.append(["title"])
    sheet.append(["metadata"])
    sheet.append(["x", "x", "x__duplicate_2", None, "__unnamed_column_4"])
    sheet.append(["first", "second", "third", "fourth", "fifth"])
    payload = BytesIO()
    book.save(payload)
    book.close()

    row = extract_workbook(payload.getvalue(), profile).rows_by_domain["progress"][0]

    assert row.sheet_name == "Progress"
    assert row.source_row_number == 4
    assert row.values == {
        "x": "first",
        "x__duplicate_3": "second",
        "x__duplicate_2": "third",
        "__unnamed_column_4__duplicate_2": "fourth",
        "__unnamed_column_4": "fifth",
    }


def test_golden_mapping_is_lossless_across_all_governed_domains(
    project_root: Path,
) -> None:
    extract_workbook, map_extracted_workbook, DomainStatus, profile = _pipeline(
        project_root
    )
    payload = (
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    ).read_bytes()

    mapped = map_extracted_workbook(extract_workbook(payload, profile), profile)

    assert {
        domain: sum(row.record is not None for row in rows)
        for domain, rows in mapped.rows_by_domain.items()
    } == {
        "wbs": 12,
        "budget": 9,
        "actual_cost": 73,
        "commitments": 6,
        "schedule": 13,
        "progress": 36,
    }
    assert set(mapped.domain_statuses.values()) == {DomainStatus.valid}
    assert mapped.project is not None
    assert mapped.project.project_id == "PRJ-CCAI-001"
    assert mapped.project.project_name == "EPC Gas Compression Facility Expansion"


def test_missing_fact_sheet_blocks_only_its_mapping_boundary(
    project_root: Path,
) -> None:
    extract_workbook, map_extracted_workbook, DomainStatus, profile = _pipeline(
        project_root
    )
    golden = (
        project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    ).read_bytes()
    book = openpyxl.load_workbook(BytesIO(golden))
    del book["Commitments"]
    payload = BytesIO()
    book.save(payload)
    book.close()

    mapped = map_extracted_workbook(
        extract_workbook(payload.getvalue(), profile), profile
    )

    assert mapped.domain_statuses["commitments"] is DomainStatus.blocked
    assert all(
        status is DomainStatus.valid
        for domain, status in mapped.domain_statuses.items()
        if domain != "commitments"
    )
    assert mapped.error_count == 1
