from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import BigInteger, Text

from controlcheck.persistence.database import Base
from controlcheck.persistence.models import WBSNodeRecord


GOVERNED_TABLES = {
    "governed_mapping_profile_versions",
    "governed_dataset_snapshots",
    "governed_import_batches",
    "governed_dataset_domain_statuses",
    "governed_raw_rows",
    "governed_wbs_nodes",
    "governed_budget_records",
    "governed_actual_cost_records",
    "governed_commitment_records",
    "governed_schedule_activities",
    "governed_progress_records",
}


def test_governed_models_are_additive_and_keep_bigint_raw_lineage() -> None:
    assert GOVERNED_TABLES <= set(Base.metadata.tables)

    raw_rows = Base.metadata.tables["governed_raw_rows"]
    assert isinstance(raw_rows.c.id.type, BigInteger)

    for table_name in GOVERNED_TABLES - {
        "governed_mapping_profile_versions",
        "governed_dataset_snapshots",
        "governed_import_batches",
        "governed_dataset_domain_statuses",
        "governed_raw_rows",
    }:
        assert isinstance(Base.metadata.tables[table_name].c.raw_row_id.type, BigInteger)

    assert isinstance(
        Base.metadata.tables["governed_dataset_snapshots"].c.source_project_name.type,
        Text,
    )

    # Homepage-v3 simplified tables remain separately mapped during reconciliation.
    assert "dataset_snapshots" in Base.metadata.tables
    assert "raw_rows" in Base.metadata.tables
    assert "wbs_nodes" in Base.metadata.tables
    assert Base.metadata.tables["dataset_snapshots"] is not Base.metadata.tables[
        "governed_dataset_snapshots"
    ]


def test_simplified_wbs_model_accepts_the_existing_normalizer_contract() -> None:
    record = WBSNodeRecord(
        organization_id=uuid4(),
        project_id=uuid4(),
        dataset_snapshot_id=uuid4(),
        raw_row_id=uuid4(),
        wbs_code="WBS-1",
        wbs_name="Project",
        parent_wbs=None,
        discipline="Project Controls",
        level=1,
        created_at=date(2026, 8, 25),
    )

    assert record.parent_wbs is None
    assert record.discipline == "Project Controls"
