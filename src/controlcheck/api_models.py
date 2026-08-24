from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantContext(BaseModel):
    organization_id: UUID


class ProjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=250)
    currency: str = Field(default="IDR", min_length=3, max_length=3)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    code: str
    name: str
    currency: str
    status: str


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]


class DomainStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    domain: str
    status: str
    row_count_raw: int
    row_count_canonical: int
    error_count: int
    warning_count: int


class DatasetSnapshotResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID
    source_project_id: str
    dataset_version: str
    data_date: date
    mapping_profile_version: str
    mapping_profile_sha256: str
    workbook_sha256: str
    status: str
    row_count_raw: int
    row_count_canonical: int
    error_count: int
    warning_count: int
    domain_statuses: dict[str, DomainStatusResponse]
    created_at: datetime


class DatasetSnapshotListResponse(BaseModel):
    items: list[DatasetSnapshotResponse]


class AnalysisRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    project_id: UUID
    engine_version: str
    workbook_sha256: str
    status: str
    rule_count: int
    finding_count: int
    executed_rule_ids: list[str]
    skipped_rules: list[dict]
    duration_ms: int | None
    safe_error_code: str | None
    safe_error_message: str | None
    started_at: datetime
    completed_at: datetime | None


class AnalysisRunListResponse(BaseModel):
    items: list[AnalysisRunResponse]


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    analysis_run_id: UUID
    engine_finding_id: str
    rule_id: str
    rule_name: str
    entity_type: str
    entity_id: str
    category: str
    severity: str
    status: str
    title: str
    description: str
    metrics: dict
    calculation: dict
    business_impact: str
    recommendation: str
    confidence: float
    detected_at: datetime
    resolved_at: datetime | None


class FindingListResponse(BaseModel):
    items: list[FindingResponse]


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    evidence_order: int
    source_sheet: str
    source_rows: list[int]
    record_ids: list[str]
    raw_row_ids: list[int]
    fields: dict
    aggregation: dict | None


class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]


class FindingStatusUpdate(BaseModel):
    status: str
