from pathlib import Path
from uuid import uuid4

from controlcheck.ingestion.normalizer import normalize_dataset_facts
from controlcheck.ingestion.raw_store import extract_raw_rows
from controlcheck.loader import load_workbook


def test_extract_raw_rows_golden_workbook(project_root: Path):
    golden_path = project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    raw_rows = extract_raw_rows(golden_path)

    assert len(raw_rows) > 0

    # Ensure sheets are captured
    sheet_names = {r.sheet_name for r in raw_rows}
    assert "WBS" in sheet_names
    assert "Budget" in sheet_names
    assert "Actual_Cost" in sheet_names
    assert "Commitments" in sheet_names
    assert "Schedule" in sheet_names
    assert "Progress" in sheet_names

    # Check that row numbers are > 1 (since row 1 is header)
    assert all(r.row_number >= 2 for r in raw_rows)

    # Check that raw_data is a dict with non-empty fields
    wbs_rows = [r for r in raw_rows if r.sheet_name == "WBS"]
    assert len(wbs_rows) > 0
    assert "wbs_code" in wbs_rows[0].raw_data


def test_normalize_dataset_facts_links_raw_rows(project_root: Path):
    golden_path = project_root / "data" / "ControlCheck_AI_Golden_Positive_Dataset_v0.2.xlsx"
    dataset = load_workbook(golden_path)
    raw_rows = extract_raw_rows(golden_path)

    org_id = uuid4()
    proj_id = uuid4()
    snapshot_id = uuid4()

    raw_row_map = {(r.sheet_name, r.row_number): r.id for r in raw_rows}

    bundle = normalize_dataset_facts(org_id, proj_id, snapshot_id, dataset, raw_row_map)

    assert bundle.total_count == (
        len(dataset.wbs_nodes)
        + len(dataset.budgets)
        + len(dataset.actual_costs)
        + len(dataset.commitments)
        + len(dataset.schedule)
        + len(dataset.progress)
    )

    # Check that every canonical fact has an assigned raw_row_id
    assert all(node.raw_row_id is not None for node in bundle.wbs_nodes)
    assert all(budget.raw_row_id is not None for budget in bundle.budgets)
    assert all(cost.raw_row_id is not None for cost in bundle.costs)
    assert all(comm.raw_row_id is not None for comm in bundle.commitments)
    assert all(sched.raw_row_id is not None for sched in bundle.schedules)
    assert all(prog.raw_row_id is not None for prog in bundle.progress)

    # Check attributes mapping
    first_wbs = bundle.wbs_nodes[0]
    assert first_wbs.organization_id == org_id
    assert first_wbs.project_id == proj_id
    assert first_wbs.dataset_snapshot_id == snapshot_id
    assert first_wbs.wbs_code == dataset.wbs_nodes[0].wbs_code
