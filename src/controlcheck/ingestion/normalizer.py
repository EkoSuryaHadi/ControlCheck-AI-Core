from __future__ import annotations

from uuid import UUID
from typing import Mapping

from ..models import ProjectDataset
from ..persistence.models import (
    BudgetRecordRecord,
    CommitmentRecordRecord,
    CostRecordRecord,
    ProgressRecordRecord,
    ScheduleActivityRecord,
    WBSNodeRecord,
)
from ..logging import get_logger

logger = get_logger("ingestion.normalizer")


class CanonicalFactBundle:
    def __init__(
        self,
        wbs_nodes: list[WBSNodeRecord],
        budgets: list[BudgetRecordRecord],
        costs: list[CostRecordRecord],
        commitments: list[CommitmentRecordRecord],
        schedules: list[ScheduleActivityRecord],
        progress: list[ProgressRecordRecord],
    ):
        self.wbs_nodes = wbs_nodes
        self.budgets = budgets
        self.costs = costs
        self.commitments = commitments
        self.schedules = schedules
        self.progress = progress

    @property
    def total_count(self) -> int:
        return (
            len(self.wbs_nodes)
            + len(self.budgets)
            + len(self.costs)
            + len(self.commitments)
            + len(self.schedules)
            + len(self.progress)
        )


def normalize_dataset_facts(
    organization_id: UUID,
    project_id: UUID,
    dataset_snapshot_id: UUID,
    dataset: ProjectDataset,
    raw_row_map: Mapping[tuple[str, int], UUID],
) -> CanonicalFactBundle:
    """Normalizes a loaded ProjectDataset into canonical fact records with raw_row lineage."""
    logger.info("Normalizing dataset canonical facts for snapshot %s", dataset_snapshot_id)

    wbs_records = [
        WBSNodeRecord(
            organization_id=organization_id,
            project_id=project_id,
            dataset_snapshot_id=dataset_snapshot_id,
            raw_row_id=raw_row_map.get((item.source.sheet, item.source.row_number)),
            wbs_code=item.wbs_code,
            wbs_name=item.wbs_name,
            parent_wbs=item.parent_wbs,
            discipline=item.discipline,
            level=item.level,
        )
        for item in dataset.wbs_nodes
    ]

    budget_records = [
        BudgetRecordRecord(
            organization_id=organization_id,
            project_id=project_id,
            dataset_snapshot_id=dataset_snapshot_id,
            raw_row_id=raw_row_map.get((item.source.sheet, item.source.row_number)),
            budget_id=item.budget_id,
            wbs_code=item.wbs_code,
            cost_code=item.cost_code,
            description=item.description,
            budget_amount=item.budget_amount,
            status=item.status,
            effective_date=item.effective_date,
        )
        for item in dataset.budgets
    ]

    cost_records = [
        CostRecordRecord(
            organization_id=organization_id,
            project_id=project_id,
            dataset_snapshot_id=dataset_snapshot_id,
            raw_row_id=raw_row_map.get((item.source.sheet, item.source.row_number)),
            transaction_id=item.transaction_id,
            transaction_date=item.transaction_date,
            wbs_code=item.wbs_code,
            cost_code=item.cost_code,
            vendor_id=item.vendor_id,
            vendor_name=item.vendor_name,
            po_number=item.po_number,
            description=item.description,
            actual_amount=item.actual_amount,
            status=item.status,
        )
        for item in dataset.actual_costs
    ]

    commitment_records = [
        CommitmentRecordRecord(
            organization_id=organization_id,
            project_id=project_id,
            dataset_snapshot_id=dataset_snapshot_id,
            raw_row_id=raw_row_map.get((item.source.sheet, item.source.row_number)),
            commitment_id=item.commitment_id,
            wbs_code=item.wbs_code,
            po_number=item.po_number,
            vendor_id=item.vendor_id,
            vendor_name=item.vendor_name,
            committed_amount=item.committed_amount,
            invoiced_amount=item.invoiced_amount,
            status=item.status,
            commitment_date=item.commitment_date,
        )
        for item in dataset.commitments
    ]

    schedule_records = [
        ScheduleActivityRecord(
            organization_id=organization_id,
            project_id=project_id,
            dataset_snapshot_id=dataset_snapshot_id,
            raw_row_id=raw_row_map.get((item.source.sheet, item.source.row_number)),
            activity_id=item.activity_id,
            wbs_code=item.wbs_code,
            activity_name=item.activity_name,
            discipline=item.discipline,
            baseline_start=item.baseline_start,
            baseline_finish=item.baseline_finish,
            actual_start=item.actual_start,
            actual_finish=item.actual_finish,
            planned_progress=item.planned_progress,
            actual_progress=item.actual_progress,
            total_float_days=item.total_float_days,
            critical=item.critical,
            status=item.status,
        )
        for item in dataset.schedule
    ]

    progress_records = [
        ProgressRecordRecord(
            organization_id=organization_id,
            project_id=project_id,
            dataset_snapshot_id=dataset_snapshot_id,
            raw_row_id=raw_row_map.get((item.source.sheet, item.source.row_number)),
            progress_id=item.progress_id,
            period=item.period,
            wbs_code=item.wbs_code,
            planned_progress=item.planned_progress,
            actual_progress=item.actual_progress,
            variance=item.variance,
            status=item.status,
        )
        for item in dataset.progress
    ]

    bundle = CanonicalFactBundle(
        wbs_nodes=wbs_records,
        budgets=budget_records,
        costs=cost_records,
        commitments=commitment_records,
        schedules=schedule_records,
        progress=progress_records,
    )

    logger.info("Normalized %d canonical fact records across all 6 domains", bundle.total_count)
    return bundle
