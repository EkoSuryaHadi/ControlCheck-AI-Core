from pathlib import Path

import openpyxl

from controlcheck.ingestion.profile import (
    load_mapping_profile,
    mapping_profile_sha256,
)


PROFILE_SHA256 = "1332b574985e8989c7b094a7ce99c11476defa9874d8aba4d0d874e46775497f"

GOVERNED_DOMAINS = {
    "wbs": (
        "WBS",
        [
            ("wbs_code", "string", True, False, "trim"),
            ("wbs_name", "string", True, False, "trim"),
            ("parent_wbs", "string", False, True, "trim"),
            ("discipline", "string", False, True, "trim"),
            ("level", "integer", True, False, "integer"),
        ],
    ),
    "budget": (
        "Budget",
        [
            ("budget_id", "string", True, False, "trim"),
            ("wbs_code", "string", False, True, "trim"),
            ("cost_code", "string", False, True, "trim"),
            ("description", "string", True, False, "trim"),
            ("budget_amount", "decimal", True, False, "decimal"),
            ("status", "string", True, False, "trim"),
            ("effective_date", "date", True, False, "excel_or_iso_date"),
        ],
    ),
    "actual_cost": (
        "Actual_Cost",
        [
            ("transaction_id", "string", True, False, "trim"),
            ("transaction_date", "date", True, False, "excel_or_iso_date"),
            ("wbs_code", "string", False, True, "trim"),
            ("cost_code", "string", False, True, "trim"),
            ("vendor_id", "string", False, True, "trim"),
            ("vendor_name", "string", False, True, "trim"),
            ("po_number", "string", False, True, "trim"),
            ("description", "string", True, False, "trim"),
            ("actual_amount", "decimal", True, False, "decimal"),
            ("status", "string", True, False, "trim"),
        ],
    ),
    "commitments": (
        "Commitments",
        [
            ("commitment_id", "string", True, False, "trim"),
            ("wbs_code", "string", False, True, "trim"),
            ("po_number", "string", False, True, "trim"),
            ("vendor_id", "string", False, True, "trim"),
            ("vendor_name", "string", False, True, "trim"),
            ("committed_amount", "decimal", True, False, "decimal"),
            ("invoiced_amount", "decimal", True, False, "decimal"),
            ("status", "string", True, False, "trim"),
            ("commitment_date", "date", True, False, "excel_or_iso_date"),
        ],
    ),
    "schedule": (
        "Schedule",
        [
            ("activity_id", "string", True, False, "trim"),
            ("wbs_code", "string", False, True, "trim"),
            ("activity_name", "string", True, False, "trim"),
            ("discipline", "string", False, True, "trim"),
            ("baseline_start", "date", True, False, "excel_or_iso_date"),
            ("baseline_finish", "date", True, False, "excel_or_iso_date"),
            ("actual_start", "date", False, True, "excel_or_iso_date"),
            ("actual_finish", "date", False, True, "excel_or_iso_date"),
            ("planned_progress", "decimal", True, False, "percentage_to_decimal"),
            ("actual_progress", "decimal", True, False, "percentage_to_decimal"),
            ("total_float_days", "integer", True, False, "integer"),
            ("critical", "boolean", True, False, "boolean"),
            ("status", "string", True, False, "trim"),
        ],
    ),
    "progress": (
        "Progress",
        [
            ("progress_id", "string", True, False, "trim"),
            ("period", "date", True, False, "excel_or_iso_date"),
            ("wbs_code", "string", False, True, "trim"),
            ("planned_progress", "decimal", True, False, "percentage_to_decimal"),
            ("actual_progress", "decimal", True, False, "percentage_to_decimal"),
            ("variance", "decimal", True, False, "percentage_to_decimal"),
            ("status", "string", True, False, "trim"),
        ],
    ),
}


def test_governed_profile_matches_every_governed_workbook_header(project_root: Path):
    profile = load_mapping_profile(
        project_root / "data/controlcheck_mapping_profile_v0.1.json"
    )
    workbook = openpyxl.load_workbook(
        project_root / "data/ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx",
        read_only=True,
        data_only=True,
    )

    assert profile.version == "0.1"
    assert profile.row_indexing == "one_based"
    assert set(profile.domains) == set(GOVERNED_DOMAINS)

    for domain, (sheet_name, expected_columns) in GOVERNED_DOMAINS.items():
        domain_profile = profile.domains[domain]
        expected_headers = [header for header, *_ in expected_columns]

        assert domain_profile.sheet_name == sheet_name
        assert domain_profile.header_row == 3
        assert list(domain_profile.columns) == expected_headers
        assert [column.source_header for column in domain_profile.columns.values()] == expected_headers
        assert [column.target_field for column in domain_profile.columns.values()] == expected_headers
        assert [
            (
                column.scalar_type,
                column.required,
                column.nullable,
                column.normalization,
            )
            for column in domain_profile.columns.values()
        ] == [tuple(column[1:]) for column in expected_columns]
        assert list(
            next(
                workbook[sheet_name].iter_rows(
                    min_row=domain_profile.header_row,
                    max_row=domain_profile.header_row,
                    values_only=True,
                )
            )
        )[: len(expected_headers)] == expected_headers

    workbook.close()


def test_mapping_profile_hash_is_the_committed_canonical_digest(project_root: Path):
    profile = load_mapping_profile(
        project_root / "data/controlcheck_mapping_profile_v0.1.json"
    )

    assert mapping_profile_sha256(profile) == PROFILE_SHA256
