from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OrganizationRecord(TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint("status IN ('active','suspended')", name="ck_organizations_status"),)
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")


class ProjectRecord(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_projects_org_code"),
        CheckConstraint("status IN ('planning','active','on_hold','completed','closed')", name="ck_projects_status"),
        CheckConstraint("planned_finish IS NULL OR planned_start IS NULL OR planned_finish >= planned_start", name="ck_projects_dates"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(250))
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_finish: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="planning")


class SourceFileRecord(Base):
    __tablename__ = "source_files"
    __table_args__ = (
        CheckConstraint("file_size_bytes >= 0", name="ck_source_files_size"),
        CheckConstraint("char_length(sha256) = 64", name="ck_source_files_sha256"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatasetSnapshotRecord(Base):
    __tablename__ = "dataset_snapshots"
    __table_args__ = (CheckConstraint("status IN ('validated','failed')", name="ck_dataset_snapshots_status"),)
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[UUID] = mapped_column(ForeignKey("source_files.id", ondelete="RESTRICT"))
    dataset_version: Mapped[str] = mapped_column(String(20))
    data_date: Mapped[date] = mapped_column(Date)
    source_project_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="validated")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RuleCatalogueVersionRecord(Base):
    __tablename__ = "rule_catalogue_versions"
    __table_args__ = (
        UniqueConstraint("version", "sha256", name="uq_catalogue_version_hash"),
        CheckConstraint("char_length(sha256) = 64", name="ck_catalogue_sha256"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(20))
    sha256: Mapped[str] = mapped_column(String(64))
    definition: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRunRecord(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','succeeded','failed')", name="ck_analysis_runs_status"),
        CheckConstraint("rule_count >= 0 AND finding_count >= 0", name="ck_analysis_runs_counts"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_analysis_runs_duration"),
        CheckConstraint("char_length(workbook_sha256) = 64", name="ck_analysis_runs_sha256"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"))
    catalogue_version_id: Mapped[UUID] = mapped_column(ForeignKey("rule_catalogue_versions.id", ondelete="RESTRICT"))
    engine_version: Mapped[str] = mapped_column(String(20))
    workbook_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    rule_count: Mapped[int] = mapped_column(Integer, default=0)
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FindingRecord(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "engine_finding_id", name="uq_findings_run_engine_id"),
        CheckConstraint("severity IN ('critical','warning','observation')", name="ck_findings_severity"),
        CheckConstraint("status IN ('open','acknowledged','resolved','dismissed')", name="ck_findings_status"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_findings_confidence"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    engine_finding_id: Mapped[str] = mapped_column(String(64))
    rule_id: Mapped[str] = mapped_column(String(40), index=True)
    rule_name: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    metrics: Mapped[dict] = mapped_column(JSONB)
    calculation: Mapped[dict] = mapped_column(JSONB)
    business_impact: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FindingEvidenceRecord(Base):
    __tablename__ = "finding_evidence"
    __table_args__ = (UniqueConstraint("finding_id", "evidence_order", name="uq_evidence_order"),)
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    evidence_order: Mapped[int] = mapped_column(Integer)
    source_sheet: Mapped[str] = mapped_column(String(100))
    source_rows: Mapped[list] = mapped_column(JSONB)
    record_ids: Mapped[list] = mapped_column(JSONB)
    fields: Mapped[dict] = mapped_column(JSONB)
    aggregation: Mapped[dict | None] = mapped_column(JSONB)


class ApprovedExceptionRecord(TimestampMixin, Base):
    __tablename__ = "approved_exceptions"
    __table_args__ = (
        CheckConstraint("status IN ('active','expired','revoked')", name="ck_exceptions_status"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_exceptions_dates"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(300))
    rationale: Mapped[str] = mapped_column(Text)
    approver_reference: Mapped[str] = mapped_column(String(200))
    evidence_reference: Mapped[str] = mapped_column(Text)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RawRowRecord(Base):
    __tablename__ = "raw_rows"
    __table_args__ = (UniqueConstraint("source_file_id", "sheet_name", "row_number", name="uq_raw_rows_source_location"),)
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[UUID] = mapped_column(ForeignKey("source_files.id", ondelete="CASCADE"), index=True)
    sheet_name: Mapped[str] = mapped_column(String(100))
    row_number: Mapped[int] = mapped_column(Integer)
    raw_data: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportBatchRecord(Base):
    __tablename__ = "import_batches"
    __table_args__ = (CheckConstraint("status IN ('pending','processing','completed','failed')", name="ck_import_batches_status"),)
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[UUID] = mapped_column(ForeignKey("source_files.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("dataset_snapshots.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="completed")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportColumnMappingRecord(Base):
    __tablename__ = "import_column_mappings"
    __table_args__ = (UniqueConstraint("project_id", "sheet_name", "source_column", name="uq_column_mapping"),)
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    sheet_name: Mapped[str] = mapped_column(String(100))
    source_column: Mapped[str] = mapped_column(String(100))
    canonical_field: Mapped[str] = mapped_column(String(100))
    is_custom: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WBSNodeRecord(Base):
    __tablename__ = "wbs_nodes"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), index=True)
    raw_row_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw_rows.id", ondelete="SET NULL"))
    wbs_code: Mapped[str] = mapped_column(String(80), index=True)
    wbs_name: Mapped[str] = mapped_column(String(255))
    parent_wbs: Mapped[str | None] = mapped_column(String(80))
    discipline: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BudgetRecordRecord(Base):
    __tablename__ = "budget_records"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), index=True)
    raw_row_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw_rows.id", ondelete="SET NULL"))
    budget_id: Mapped[str] = mapped_column(String(100))
    wbs_code: Mapped[str | None] = mapped_column(String(80), index=True)
    cost_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    status: Mapped[str] = mapped_column(String(50))
    effective_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CostRecordRecord(Base):
    __tablename__ = "cost_records"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), index=True)
    raw_row_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw_rows.id", ondelete="SET NULL"))
    transaction_id: Mapped[str] = mapped_column(String(100), index=True)
    transaction_date: Mapped[date] = mapped_column(Date)
    wbs_code: Mapped[str | None] = mapped_column(String(80), index=True)
    cost_code: Mapped[str | None] = mapped_column(String(80))
    vendor_id: Mapped[str | None] = mapped_column(String(100))
    vendor_name: Mapped[str | None] = mapped_column(String(255))
    po_number: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommitmentRecordRecord(Base):
    __tablename__ = "commitment_records"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), index=True)
    raw_row_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw_rows.id", ondelete="SET NULL"))
    commitment_id: Mapped[str] = mapped_column(String(100), index=True)
    wbs_code: Mapped[str | None] = mapped_column(String(80), index=True)
    po_number: Mapped[str | None] = mapped_column(String(100))
    vendor_id: Mapped[str | None] = mapped_column(String(100))
    vendor_name: Mapped[str | None] = mapped_column(String(255))
    committed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    invoiced_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    status: Mapped[str] = mapped_column(String(50))
    commitment_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduleActivityRecord(Base):
    __tablename__ = "schedule_activities"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), index=True)
    raw_row_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw_rows.id", ondelete="SET NULL"))
    activity_id: Mapped[str] = mapped_column(String(100), index=True)
    wbs_code: Mapped[str | None] = mapped_column(String(80), index=True)
    activity_name: Mapped[str] = mapped_column(String(255))
    discipline: Mapped[str | None] = mapped_column(String(100))
    baseline_start: Mapped[date] = mapped_column(Date)
    baseline_finish: Mapped[date] = mapped_column(Date)
    actual_start: Mapped[date | None] = mapped_column(Date)
    actual_finish: Mapped[date | None] = mapped_column(Date)
    planned_progress: Mapped[float] = mapped_column()
    actual_progress: Mapped[float] = mapped_column()
    total_float_days: Mapped[int] = mapped_column(Integer)
    critical: Mapped[bool] = mapped_column()
    status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProgressRecordRecord(Base):
    __tablename__ = "progress_records"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), index=True)
    raw_row_id: Mapped[UUID | None] = mapped_column(ForeignKey("raw_rows.id", ondelete="SET NULL"))
    progress_id: Mapped[str] = mapped_column(String(100), index=True)
    period: Mapped[date] = mapped_column(Date)
    wbs_code: Mapped[str | None] = mapped_column(String(80), index=True)
    planned_progress: Mapped[float] = mapped_column()
    actual_progress: Mapped[float] = mapped_column()
    variance: Mapped[float] = mapped_column()
    status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HealthSnapshotRecord(Base):
    __tablename__ = "health_snapshots"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", name="uq_health_snapshot_run"),
        CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="ck_health_overall_score"),
        CheckConstraint("cost_score >= 0 AND cost_score <= 100", name="ck_health_cost_score"),
        CheckConstraint("schedule_score >= 0 AND schedule_score <= 100", name="ck_health_schedule_score"),
        CheckConstraint("progress_score >= 0 AND progress_score <= 100", name="ck_health_progress_score"),
        CheckConstraint("dq_score >= 0 AND dq_score <= 100", name="ck_health_dq_score"),
        CheckConstraint("score_band IN ('Healthy', 'Needs Attention', 'At Risk', 'Critical')", name="ck_health_score_band"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    overall_score: Mapped[float] = mapped_column()
    cost_score: Mapped[float] = mapped_column()
    schedule_score: Mapped[float] = mapped_column()
    progress_score: Mapped[float] = mapped_column()
    dq_score: Mapped[float] = mapped_column()
    score_band: Mapped[str] = mapped_column(String(50))
    component_breakdown: Mapped[dict] = mapped_column(JSONB)
    key_drivers: Mapped[list] = mapped_column(JSONB)
    score_version: Mapped[str] = mapped_column(String(20), default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserRecord(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("status IN ('active','inactive','suspended')", name="ck_users_status"),)
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")


class OrganizationMemberRecord(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        CheckConstraint("role IN ('org_admin','org_member','org_viewer')", name="ck_org_member_role"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(50), default="org_member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectMemberRecord(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
        CheckConstraint("role IN ('project_manager','project_member','project_viewer')", name="ck_project_member_role"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(50), default="project_viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())



