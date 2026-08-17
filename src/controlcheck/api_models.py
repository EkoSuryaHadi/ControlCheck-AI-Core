from __future__ import annotations

from datetime import datetime
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
    duration_ms: int | None
    safe_error_code: str | None
    safe_error_message: str | None
    started_at: datetime
    completed_at: datetime | None
