from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantContext(BaseModel):
    organization_id: UUID
    user_id: UUID | None = None
    email: str | None = None
    role: str | None = None


class TelemetryEventCreate(BaseModel):
    event_name: str = Field(min_length=1, max_length=80)
    project_id: UUID | None = None
    analysis_run_id: UUID | None = None
    finding_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)


class FeedbackCreate(BaseModel):
    rating: Literal["useful", "not_useful"]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    project_id: UUID
    analysis_run_id: UUID
    finding_id: UUID | None
    rating: str
    comment: str | None
    status: str
    created_at: datetime


class OwnerMetricsResponse(BaseModel):
    registrations: int
    active_users: int
    projects: int
    uploads_accepted: int
    analyses_completed: int
    result_use_events: int
    result_use_rate: float
    feedback_count: int
    useful_feedback_rate: float
    error_rate: float
    generated_at: datetime


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
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


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
    source_project_name: str | None
    dataset_version: str
    data_date: date
    mapping_profile_version: str | None
    mapping_profile_sha256: str | None
    workbook_sha256: str
    status: str
    row_count_raw: int | None
    row_count_canonical: int | None
    error_count: int
    warning_count: int
    domain_statuses: dict[str, DomainStatusResponse]
    created_at: datetime
    storage_contract: str


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
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


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
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


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
    # `resolved` is intentionally excluded. Resolution must use the governed
    # /v1/findings/{finding_id}/close endpoint so evidence/action gates cannot
    # be bypassed through this legacy status mutation endpoint.
    status: Literal["open", "in_review", "dismissed"]


class HealthSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    project_id: UUID
    analysis_run_id: UUID
    overall_score: float | None
    cost_score: float | None
    schedule_score: float | None
    progress_score: float | None
    dq_score: float | None
    score_band: str
    component_breakdown: dict
    key_drivers: list
    score_version: str
    computation_status: Literal["computed", "partial", "not_computed"]
    coverage_ratio: float
    unavailable_domains: list[str]
    created_at: datetime


class HealthTrendListResponse(BaseModel):
    items: list[HealthSnapshotResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = None
    organization_name: str | None = None


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: UUID | None = None
    email: str | None = None
    full_name: str | None = None
    org_id: UUID | None = None
    role: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str | None
    status: str
    created_at: datetime


class AIAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: UUID | None = None


class AIAskResponse(BaseModel):
    conversation_id: UUID
    answer: str
    key_evidence: list[dict] = []
    impact: str
    recommended_action: str
    confidence: str = "high"
    data_caveat: str | None = None
    evidence_references: list[str] = []


class AIConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    project_id: UUID
    title: str
    created_at: datetime


class AIConversationListResponse(BaseModel):
    items: list[AIConversationResponse]
    total: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False


class AIMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    tool_calls: dict | list | None = None
    created_at: datetime
