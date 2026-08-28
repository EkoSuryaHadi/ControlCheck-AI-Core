from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
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
        CheckConstraint(
            "(dataset_snapshot_id IS NULL) <> (governed_dataset_snapshot_id IS NULL)",
            name="ck_analysis_runs_one_snapshot_contract",
        ),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataset_snapshots.id", ondelete="RESTRICT")
    )
    governed_dataset_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("governed_dataset_snapshots.id", ondelete="RESTRICT"),
        index=True,
    )
    catalogue_version_id: Mapped[UUID] = mapped_column(ForeignKey("rule_catalogue_versions.id", ondelete="RESTRICT"))
    engine_version: Mapped[str] = mapped_column(String(20))
    workbook_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    rule_count: Mapped[int] = mapped_column(Integer, default=0)
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    executed_rule_ids: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    skipped_rules: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
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
    raw_row_ids: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
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


class ProductEventRecord(Base):
    __tablename__ = "product_events"
    __table_args__ = (
        Index("ix_product_events_org_created", "organization_id", "created_at"),
        Index("ix_product_events_name_created", "event_name", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    analysis_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="SET NULL"), index=True)
    finding_id: Mapped[UUID | None] = mapped_column(ForeignKey("findings.id", ondelete="SET NULL"), index=True)
    event_name: Mapped[str] = mapped_column(String(80))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FindingFeedbackRecord(Base):
    __tablename__ = "finding_feedback"
    __table_args__ = (
        CheckConstraint("rating IN ('useful','not_useful')", name="ck_finding_feedback_rating"),
        CheckConstraint("status IN ('new','reviewed','archived')", name="ck_finding_feedback_status"),
        Index("ix_finding_feedback_org_created", "organization_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[UUID | None] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    rating: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
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


class GovernedMappingProfileVersionRecord(Base):
    __tablename__ = "governed_mapping_profile_versions"
    __table_args__ = (
        UniqueConstraint(
            "version",
            "sha256",
            name="uq_governed_mapping_profile_version_hash",
        ),
        CheckConstraint(
            "char_length(sha256) = 64",
            name="ck_governed_mapping_profile_sha256",
        ),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(20))
    sha256: Mapped[str] = mapped_column(String(64))
    definition: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GovernedDatasetSnapshotRecord(Base):
    __tablename__ = "governed_dataset_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "import_batch_id",
            name="uq_governed_snapshots_import_batch",
        ),
        ForeignKeyConstraint(
            ["id", "import_batch_id"],
            [
                "governed_import_batches.dataset_snapshot_id",
                "governed_import_batches.id",
            ],
            name="fk_governed_snapshots_import_batch",
            use_alter=True,
        ),
        CheckConstraint(
            "status IN ('ingesting','validated','validated_with_errors','failed')",
            name="ck_governed_snapshots_status",
        ),
        CheckConstraint(
            "row_count_raw >= 0 AND row_count_canonical >= 0",
            name="ck_governed_snapshots_row_counts",
        ),
        Index(
            "ux_governed_snapshots_dedupe_key_not_null",
            "dedupe_key",
            unique=True,
            postgresql_where=text("dedupe_key IS NOT NULL"),
        ),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source_file_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_files.id", ondelete="RESTRICT"), index=True
    )
    mapping_profile_version_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "governed_mapping_profile_versions.id",
            ondelete="RESTRICT",
        )
    )
    import_batch_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    dataset_version: Mapped[str] = mapped_column(String(20))
    data_date: Mapped[date] = mapped_column(Date)
    source_project_id: Mapped[str] = mapped_column(String(100))
    source_project_name: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(String(64))
    row_count_raw: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    row_count_canonical: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(30), default="ingesting", server_default="ingesting", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GovernedImportBatchRecord(Base):
    __tablename__ = "governed_import_batches"
    __table_args__ = (
        UniqueConstraint(
            "dataset_snapshot_id",
            name="uq_governed_import_batches_snapshot",
        ),
        UniqueConstraint(
            "dataset_snapshot_id",
            "id",
            name="uq_governed_import_batches_snapshot_id",
        ),
        CheckConstraint(
            "status IN ('ingesting','completed','failed')",
            name="ck_governed_import_batches_status",
        ),
        CheckConstraint(
            "rows_read >= 0 AND rows_valid >= 0 AND rows_warning >= 0 AND rows_rejected >= 0",
            name="ck_governed_import_batches_counts",
        ),
        CheckConstraint(
            "rows_valid + rows_warning + rows_rejected <= rows_read",
            name="ck_governed_import_batches_count_totals",
        ),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("governed_dataset_snapshots.id", ondelete="CASCADE"), index=True
    )
    mapping_profile_version_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "governed_mapping_profile_versions.id",
            ondelete="RESTRICT",
        )
    )
    status: Mapped[str] = mapped_column(
        String(20), default="ingesting", server_default="ingesting", index=True
    )
    rows_read: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_valid: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_warning: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    safe_error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(Text)
    error_summary: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GovernedDatasetDomainStatusRecord(Base):
    __tablename__ = "governed_dataset_domain_statuses"
    __table_args__ = (
        UniqueConstraint(
            "dataset_snapshot_id",
            "domain",
            name="uq_governed_domain_statuses_snapshot_domain",
        ),
        CheckConstraint(
            "status IN ('valid','warning','blocked')",
            name="ck_governed_domain_statuses_status",
        ),
        CheckConstraint(
            "row_count_raw >= 0 AND row_count_canonical >= 0 AND error_count >= 0 AND warning_count >= 0",
            name="ck_governed_domain_statuses_counts",
        ),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("governed_dataset_snapshots.id", ondelete="CASCADE"), index=True
    )
    domain: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), index=True)
    row_count_raw: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    row_count_canonical: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    warning_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    validation_summary: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GovernedRawRowRecord(Base):
    __tablename__ = "governed_raw_rows"
    __table_args__ = (
        UniqueConstraint(
            "dataset_snapshot_id",
            "domain",
            "source_sheet",
            "source_row_number",
            name="uq_governed_raw_rows_source_location",
        ),
        UniqueConstraint(
            "dataset_snapshot_id",
            "id",
            name="uq_governed_raw_rows_snapshot_id",
        ),
        ForeignKeyConstraint(
            ["dataset_snapshot_id", "import_batch_id"],
            [
                "governed_import_batches.dataset_snapshot_id",
                "governed_import_batches.id",
            ],
            name="fk_governed_raw_rows_snapshot_import_batch",
        ),
        CheckConstraint(
            "source_row_number > 0",
            name="ck_governed_raw_rows_source_row_number",
        ),
        CheckConstraint(
            "char_length(row_hash) = 64",
            name="ck_governed_raw_rows_hash",
        ),
        CheckConstraint(
            "validation_status IN ('valid','warning','invalid')",
            name="ck_governed_raw_rows_validation_status",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("governed_dataset_snapshots.id", ondelete="CASCADE"), index=True
    )
    import_batch_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True)
    domain: Mapped[str] = mapped_column(String(30), index=True)
    source_sheet: Mapped[str] = mapped_column(String(100))
    source_row_number: Mapped[int] = mapped_column(Integer)
    row_hash: Mapped[str] = mapped_column(String(64))
    raw_data: Mapped[dict] = mapped_column(JSONB)
    validation_status: Mapped[str] = mapped_column(
        String(20), default="valid", server_default="valid", index=True
    )
    validation_errors: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GovernedWBSNodeRecord(Base):
    __tablename__ = "governed_wbs_nodes"
    __table_args__ = (
        UniqueConstraint(
            "dataset_snapshot_id",
            "source_key",
            name="uq_governed_wbs_nodes_snapshot_source_key",
        ),
        UniqueConstraint(
            "raw_row_id",
            name="uq_governed_wbs_nodes_raw_row_id",
        ),
        UniqueConstraint(
            "dataset_snapshot_id",
            "id",
            name="uq_governed_wbs_nodes_snapshot_id",
        ),
        ForeignKeyConstraint(
            ["dataset_snapshot_id", "raw_row_id"],
            ["governed_raw_rows.dataset_snapshot_id", "governed_raw_rows.id"],
            name="fk_governed_wbs_nodes_snapshot_raw_row",
        ),
        ForeignKeyConstraint(
            ["dataset_snapshot_id", "parent_id"],
            ["governed_wbs_nodes.dataset_snapshot_id", "governed_wbs_nodes.id"],
            name="fk_governed_wbs_nodes_snapshot_parent",
        ),
        CheckConstraint('"level" >= 1', name="ck_governed_wbs_nodes_level"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("governed_dataset_snapshots.id", ondelete="CASCADE"), index=True
    )
    raw_row_id: Mapped[int] = mapped_column(BigInteger, index=True)
    parent_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    source_key: Mapped[str] = mapped_column(String(300))
    wbs_code: Mapped[str] = mapped_column(String(100))
    wbs_name: Mapped[str] = mapped_column(String(250))
    parent_wbs: Mapped[str | None] = mapped_column(String(100))
    discipline: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GovernedCanonicalFactMixin:
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    dataset_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("governed_dataset_snapshots.id", ondelete="CASCADE"), index=True
    )
    raw_row_id: Mapped[int] = mapped_column(BigInteger, index=True)
    wbs_node_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), index=True)
    source_key: Mapped[str] = mapped_column(String(300))
    wbs_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _governed_canonical_constraints(table_name: str) -> tuple[object, ...]:
    return (
        UniqueConstraint(
            "dataset_snapshot_id",
            "source_key",
            name=f"uq_{table_name}_snapshot_source_key",
        ),
        UniqueConstraint("raw_row_id", name=f"uq_{table_name}_raw_row_id"),
        ForeignKeyConstraint(
            ["dataset_snapshot_id", "raw_row_id"],
            ["governed_raw_rows.dataset_snapshot_id", "governed_raw_rows.id"],
            name=f"fk_{table_name}_snapshot_raw_row",
        ),
        ForeignKeyConstraint(
            ["dataset_snapshot_id", "wbs_node_id"],
            ["governed_wbs_nodes.dataset_snapshot_id", "governed_wbs_nodes.id"],
            name=f"fk_{table_name}_snapshot_wbs_node",
        ),
    )


class GovernedBudgetRecord(GovernedCanonicalFactMixin, Base):
    __tablename__ = "governed_budget_records"
    __table_args__ = _governed_canonical_constraints(__tablename__)
    budget_id: Mapped[str] = mapped_column(String(300))
    cost_code: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    status: Mapped[str] = mapped_column(String(50))
    effective_date: Mapped[date] = mapped_column(Date)


class GovernedActualCostRecord(GovernedCanonicalFactMixin, Base):
    __tablename__ = "governed_actual_cost_records"
    __table_args__ = _governed_canonical_constraints(__tablename__)
    transaction_id: Mapped[str] = mapped_column(String(300))
    transaction_date: Mapped[date] = mapped_column(Date)
    cost_code: Mapped[str | None] = mapped_column(String(100))
    vendor_id: Mapped[str | None] = mapped_column(String(100))
    vendor_name: Mapped[str | None] = mapped_column(String(250))
    po_number: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    status: Mapped[str] = mapped_column(String(50))


class GovernedCommitmentRecord(GovernedCanonicalFactMixin, Base):
    __tablename__ = "governed_commitment_records"
    __table_args__ = _governed_canonical_constraints(__tablename__)
    commitment_id: Mapped[str] = mapped_column(String(300))
    po_number: Mapped[str | None] = mapped_column(String(100))
    vendor_id: Mapped[str | None] = mapped_column(String(100))
    vendor_name: Mapped[str | None] = mapped_column(String(250))
    committed_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    invoiced_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    status: Mapped[str] = mapped_column(String(50))
    commitment_date: Mapped[date] = mapped_column(Date)


class GovernedScheduleActivityRecord(GovernedCanonicalFactMixin, Base):
    __tablename__ = "governed_schedule_activities"
    __table_args__ = _governed_canonical_constraints(__tablename__) + (
        CheckConstraint(
            "planned_progress >= 0 AND actual_progress >= 0",
            name="ck_governed_schedule_activities_progress",
        ),
        CheckConstraint(
            "baseline_finish >= baseline_start",
            name="ck_governed_schedule_activities_baseline_dates",
        ),
    )
    activity_id: Mapped[str] = mapped_column(String(300))
    activity_name: Mapped[str] = mapped_column(String(500))
    discipline: Mapped[str | None] = mapped_column(String(100))
    baseline_start: Mapped[date] = mapped_column(Date)
    baseline_finish: Mapped[date] = mapped_column(Date)
    actual_start: Mapped[date | None] = mapped_column(Date)
    actual_finish: Mapped[date | None] = mapped_column(Date)
    planned_progress: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    actual_progress: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    total_float_days: Mapped[int] = mapped_column(Integer)
    critical: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(50))


class GovernedProgressRecord(GovernedCanonicalFactMixin, Base):
    __tablename__ = "governed_progress_records"
    __table_args__ = _governed_canonical_constraints(__tablename__) + (
        CheckConstraint(
            "planned_progress >= 0 AND actual_progress >= 0",
            name="ck_governed_progress_records_progress",
        ),
        CheckConstraint(
            "variance >= -1 AND variance <= 1",
            name="ck_governed_progress_records_variance",
        ),
    )
    progress_id: Mapped[str] = mapped_column(String(300))
    period: Mapped[date] = mapped_column(Date)
    planned_progress: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    actual_progress: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    variance: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    status: Mapped[str] = mapped_column(String(50))


class HealthSnapshotRecord(Base):
    __tablename__ = "health_snapshots"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", name="uq_health_snapshot_run"),
        CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="ck_health_overall_score"),
        CheckConstraint("cost_score >= 0 AND cost_score <= 100", name="ck_health_cost_score"),
        CheckConstraint("schedule_score >= 0 AND schedule_score <= 100", name="ck_health_schedule_score"),
        CheckConstraint("progress_score >= 0 AND progress_score <= 100", name="ck_health_progress_score"),
        CheckConstraint("dq_score >= 0 AND dq_score <= 100", name="ck_health_dq_score"),
        CheckConstraint("score_band IN ('Healthy', 'Needs Attention', 'At Risk', 'Critical', 'Partial', 'Not Computed')", name="ck_health_score_band"),
        CheckConstraint("computation_status IN ('computed', 'partial', 'not_computed')", name="ck_health_computation_status"),
        CheckConstraint("coverage_ratio >= 0 AND coverage_ratio <= 1", name="ck_health_coverage_ratio"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    overall_score: Mapped[float | None] = mapped_column(nullable=True)
    cost_score: Mapped[float | None] = mapped_column(nullable=True)
    schedule_score: Mapped[float | None] = mapped_column(nullable=True)
    progress_score: Mapped[float | None] = mapped_column(nullable=True)
    dq_score: Mapped[float | None] = mapped_column(nullable=True)
    score_band: Mapped[str] = mapped_column(String(50))
    component_breakdown: Mapped[dict] = mapped_column(JSONB)
    key_drivers: Mapped[list] = mapped_column(JSONB)
    score_version: Mapped[str] = mapped_column(String(20), default="1.0")
    computation_status: Mapped[str] = mapped_column(String(20), default="computed")
    coverage_ratio: Mapped[float] = mapped_column(default=1.0)
    unavailable_domains: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserRecord(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('active','inactive','suspended')", name="ck_users_status"),
        Index("ix_users_email", "email"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="active")


class OrganizationMemberRecord(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        CheckConstraint("role IN ('org_admin','org_member','org_viewer')", name="ck_org_member_role"),
        Index("ix_org_members_org_user", "organization_id", "user_id"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50), default="org_member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectMemberRecord(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
        CheckConstraint("role IN ('project_manager','project_member','project_viewer')", name="ck_project_member_role"),
        Index("ix_project_members_project_user", "project_id", "user_id"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(50), default="project_viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIConversationRecord(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        Index("ix_ai_conversations_org_project", "organization_id", "project_id"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), default="Project Audit Conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIMessageRecord(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','system','tool')", name="ck_ai_messages_role"),
        Index("ix_ai_messages_conversation", "conversation_id"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("ai_conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[dict | list | None] = mapped_column(JSONB)
    model_version: Mapped[str] = mapped_column(String(50), default="deterministic-grounded-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportPackageRecord(Base):
    __tablename__ = "report_packages"
    __table_args__ = (
        CheckConstraint("report_type IN ('monthly','executive','cost','schedule','progress')", name="ck_report_packages_type"),
        Index("ix_report_packages_org_project_created", "organization_id", "project_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="RESTRICT"), index=True)
    generated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    report_name: Mapped[str] = mapped_column(String(255))
    report_type: Mapped[str] = mapped_column(String(30))
    period: Mapped[str] = mapped_column(String(80))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    pdf_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    pdf_size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
