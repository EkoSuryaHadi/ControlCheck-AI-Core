from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class RecordModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRef(RecordModel):
    sheet: str
    row_number: int


class ProjectInfo(RecordModel):
    project_id: str
    project_name: str


class WBSNode(RecordModel):
    wbs_code: str
    wbs_name: str
    parent_wbs: str | None = None
    discipline: str | None = None
    level: int
    source: SourceRef


class BudgetRecord(RecordModel):
    budget_id: str
    wbs_code: str | None
    cost_code: str | None
    description: str
    budget_amount: Decimal
    status: str
    effective_date: date
    source: SourceRef


class ActualCostRecord(RecordModel):
    transaction_id: str
    transaction_date: date
    wbs_code: str | None
    cost_code: str | None
    vendor_id: str | None
    vendor_name: str | None
    po_number: str | None
    description: str
    actual_amount: Decimal
    status: str
    source: SourceRef


class CommitmentRecord(RecordModel):
    commitment_id: str
    wbs_code: str | None
    po_number: str | None
    vendor_id: str | None
    vendor_name: str | None
    committed_amount: Decimal
    invoiced_amount: Decimal
    status: str
    commitment_date: date
    source: SourceRef


class ScheduleActivity(RecordModel):
    activity_id: str
    wbs_code: str | None
    activity_name: str
    discipline: str | None
    baseline_start: date
    baseline_finish: date
    actual_start: date | None
    actual_finish: date | None
    planned_progress: float
    actual_progress: float
    total_float_days: int
    critical: bool
    status: str
    source: SourceRef


class ProgressRecord(RecordModel):
    progress_id: str
    period: date
    wbs_code: str | None
    planned_progress: float
    actual_progress: float
    variance: float
    status: str
    source: SourceRef


class ProjectDataset(RecordModel):
    project: ProjectInfo
    data_date: date
    wbs_nodes: list[WBSNode]
    budgets: list[BudgetRecord]
    actual_costs: list[ActualCostRecord]
    commitments: list[CommitmentRecord]
    schedule: list[ScheduleActivity]
    progress: list[ProgressRecord]
    dataset_version: str = "0.1"


class EvidenceItem(RecordModel):
    source_sheet: str
    source_rows: list[int] = []
    record_ids: list[str]
    fields: dict[str, Any]
    aggregation: dict[str, Any] | None = None


class Finding(RecordModel):
    finding_id: str
    rule_id: str
    rule_name: str
    category: str
    severity: str
    project_id: str
    entity_type: str
    entity_id: str
    title: str
    description: str
    metrics: dict[str, Any]
    business_impact: str
    recommendation: str
    confidence: float = 1.0
    evidence: list[EvidenceItem]
    calculation: dict[str, Any]


class AuditResult(RecordModel):
    engine_version: str = "0.1.0"
    project_id: str
    data_date: date
    rule_count: int
    finding_count: int
    findings: list[Finding]
