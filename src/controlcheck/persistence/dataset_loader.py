from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, sessionmaker

from ..errors import ControlCheckApplicationError
from ..ingestion.mapper import DomainStatus
from ..models import (
    ActualCostRecord,
    BudgetRecord,
    CommitmentRecord,
    ProgressRecord,
    ProjectDataset,
    ProjectInfo,
    ScheduleActivity,
    SourceRef,
    WBSNode,
)
from .models import (
    CanonicalActualCostRecord,
    CanonicalBudgetRecord,
    CanonicalCommitmentRecord,
    DatasetDomainStatusRecord,
    DatasetSnapshotRecord,
    ProgressRecordRecord,
    ProjectRecord,
    RawRowRecord,
    ScheduleActivityRecord,
    WBSNodeRecord,
)


@dataclass(frozen=True)
class DatabaseDataset:
    snapshot: ProjectDataset
    domain_statuses: dict[str, DomainStatus]
    raw_row_index: dict[tuple[str, int], int]


def _source(sheet: str, row_number: int) -> SourceRef:
    return SourceRef(sheet=sheet, row_number=row_number)


def _legacy_decimal(value: Decimal) -> Decimal:
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return normalized.quantize(Decimal(1))
    return normalized


def _canonical_rows(
    session: Session,
    model: type[Any],
    organization_id: UUID,
    project_id: UUID,
    snapshot_id: UUID,
):
    return session.execute(
        select(model, RawRowRecord.source_sheet, RawRowRecord.source_row_number)
        .join(
            RawRowRecord,
            and_(
                RawRowRecord.id == model.raw_row_id,
                RawRowRecord.organization_id == model.organization_id,
                RawRowRecord.project_id == model.project_id,
                RawRowRecord.dataset_snapshot_id == model.dataset_snapshot_id,
            ),
        )
        .where(
            model.organization_id == organization_id,
            model.project_id == project_id,
            model.dataset_snapshot_id == snapshot_id,
            RawRowRecord.organization_id == organization_id,
            RawRowRecord.project_id == project_id,
            RawRowRecord.dataset_snapshot_id == snapshot_id,
        )
        .order_by(RawRowRecord.source_row_number, RawRowRecord.id)
    ).all()


class DatabaseDatasetLoader:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def load(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
    ) -> DatabaseDataset:
        with self.session_factory() as session:
            snapshot_row = session.execute(
                select(DatasetSnapshotRecord, ProjectRecord)
                .join(
                    ProjectRecord,
                    and_(
                        ProjectRecord.id == DatasetSnapshotRecord.project_id,
                        ProjectRecord.organization_id == DatasetSnapshotRecord.organization_id,
                    ),
                )
                .where(
                    DatasetSnapshotRecord.organization_id == organization_id,
                    DatasetSnapshotRecord.project_id == project_id,
                    DatasetSnapshotRecord.id == snapshot_id,
                    ProjectRecord.organization_id == organization_id,
                    ProjectRecord.id == project_id,
                )
            ).one_or_none()
            if snapshot_row is None:
                raise ControlCheckApplicationError(
                    "snapshot_not_found",
                    "Dataset snapshot was not found for this project",
                    404,
                )
            snapshot, project = snapshot_row
            if snapshot.status == "ingesting":
                raise ControlCheckApplicationError(
                    "snapshot_not_ready",
                    "Dataset snapshot is still ingesting",
                    409,
                )
            if snapshot.status == "failed":
                raise ControlCheckApplicationError(
                    "snapshot_failed",
                    "Dataset snapshot ingestion failed",
                    409,
                )

            wbs_nodes = [
                WBSNode(
                    wbs_code=row.wbs_code,
                    wbs_name=row.wbs_name,
                    parent_wbs=row.parent_wbs,
                    discipline=row.discipline,
                    level=row.level,
                    source=_source(sheet, row_number),
                )
                for row, sheet, row_number in _canonical_rows(
                    session, WBSNodeRecord, organization_id, project_id, snapshot_id
                )
            ]
            budgets = [
                BudgetRecord(
                    budget_id=row.budget_id,
                    wbs_code=row.wbs_code,
                    cost_code=row.cost_code,
                    description=row.description,
                    budget_amount=_legacy_decimal(row.budget_amount),
                    status=row.status,
                    effective_date=row.effective_date,
                    source=_source(sheet, row_number),
                )
                for row, sheet, row_number in _canonical_rows(
                    session,
                    CanonicalBudgetRecord,
                    organization_id,
                    project_id,
                    snapshot_id,
                )
            ]
            actual_costs = [
                ActualCostRecord(
                    transaction_id=row.transaction_id,
                    transaction_date=row.transaction_date,
                    wbs_code=row.wbs_code,
                    cost_code=row.cost_code,
                    vendor_id=row.vendor_id,
                    vendor_name=row.vendor_name,
                    po_number=row.po_number,
                    description=row.description,
                    actual_amount=_legacy_decimal(row.actual_amount),
                    status=row.status,
                    source=_source(sheet, row_number),
                )
                for row, sheet, row_number in _canonical_rows(
                    session,
                    CanonicalActualCostRecord,
                    organization_id,
                    project_id,
                    snapshot_id,
                )
            ]
            commitments = [
                CommitmentRecord(
                    commitment_id=row.commitment_id,
                    wbs_code=row.wbs_code,
                    po_number=row.po_number,
                    vendor_id=row.vendor_id,
                    vendor_name=row.vendor_name,
                    committed_amount=_legacy_decimal(row.committed_amount),
                    invoiced_amount=_legacy_decimal(row.invoiced_amount),
                    status=row.status,
                    commitment_date=row.commitment_date,
                    source=_source(sheet, row_number),
                )
                for row, sheet, row_number in _canonical_rows(
                    session,
                    CanonicalCommitmentRecord,
                    organization_id,
                    project_id,
                    snapshot_id,
                )
            ]
            schedule = [
                ScheduleActivity(
                    activity_id=row.activity_id,
                    wbs_code=row.wbs_code,
                    activity_name=row.activity_name,
                    discipline=row.discipline,
                    baseline_start=row.baseline_start,
                    baseline_finish=row.baseline_finish,
                    actual_start=row.actual_start,
                    actual_finish=row.actual_finish,
                    planned_progress=row.planned_progress,
                    actual_progress=row.actual_progress,
                    total_float_days=row.total_float_days,
                    critical=row.critical,
                    status=row.status,
                    source=_source(sheet, row_number),
                )
                for row, sheet, row_number in _canonical_rows(
                    session,
                    ScheduleActivityRecord,
                    organization_id,
                    project_id,
                    snapshot_id,
                )
            ]
            progress = [
                ProgressRecord(
                    progress_id=row.progress_id,
                    period=row.period,
                    wbs_code=row.wbs_code,
                    planned_progress=row.planned_progress,
                    actual_progress=row.actual_progress,
                    # The legacy model uses binary-float subtraction for this derived field.
                    # Rebuilding it from the stored base values preserves exact model parity.
                    variance=float(row.actual_progress) - float(row.planned_progress),
                    status=row.status,
                    source=_source(sheet, row_number),
                )
                for row, sheet, row_number in _canonical_rows(
                    session,
                    ProgressRecordRecord,
                    organization_id,
                    project_id,
                    snapshot_id,
                )
            ]

            domain_statuses = {
                row.domain: DomainStatus(row.status)
                for row in session.scalars(
                    select(DatasetDomainStatusRecord)
                    .where(
                        DatasetDomainStatusRecord.organization_id == organization_id,
                        DatasetDomainStatusRecord.project_id == project_id,
                        DatasetDomainStatusRecord.dataset_snapshot_id == snapshot_id,
                    )
                    .order_by(DatasetDomainStatusRecord.domain)
                )
            }
            raw_row_index = {
                (row.source_sheet, row.source_row_number): row.id
                for row in session.scalars(
                    select(RawRowRecord)
                    .where(
                        RawRowRecord.organization_id == organization_id,
                        RawRowRecord.project_id == project_id,
                        RawRowRecord.dataset_snapshot_id == snapshot_id,
                    )
                    .order_by(
                        RawRowRecord.source_sheet,
                        RawRowRecord.source_row_number,
                        RawRowRecord.id,
                    )
                )
            }
            dataset = ProjectDataset(
                project=ProjectInfo(
                    project_id=snapshot.source_project_id,
                    project_name=project.name,
                ),
                data_date=snapshot.data_date,
                wbs_nodes=wbs_nodes,
                budgets=budgets,
                actual_costs=actual_costs,
                commitments=commitments,
                schedule=schedule,
                progress=progress,
                dataset_version=snapshot.dataset_version,
            )
            return DatabaseDataset(
                snapshot=dataset,
                domain_statuses=domain_statuses,
                raw_row_index=raw_row_index,
            )


__all__ = ["DatabaseDataset", "DatabaseDatasetLoader"]
