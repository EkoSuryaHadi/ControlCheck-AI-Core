"""Phase 4B raw-row lineage and canonical facts schema.

Revision ID: 20260821_0002
Revises: 20260817_0001
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0002"
down_revision: str | None = "20260817_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Raw rows
    op.create_table(
        "raw_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sheet_name", sa.String(100), nullable=False),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.Column("raw_data", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_file_id", "sheet_name", "row_number", name="uq_raw_rows_source_location"),
    )

    # 2. Import batches
    op.create_table(
        "import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_snapshots.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('pending','processing','completed','failed')", name="ck_import_batches_status"),
    )

    # 3. Import column mappings
    op.create_table(
        "import_column_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sheet_name", sa.String(100), nullable=False),
        sa.Column("source_column", sa.String(100), nullable=False),
        sa.Column("canonical_field", sa.String(100), nullable=False),
        sa.Column("is_custom", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "sheet_name", "source_column", name="uq_column_mapping"),
    )

    # 4. Canonical WBS Nodes
    op.create_table(
        "wbs_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_row_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_rows.id", ondelete="SET NULL")),
        sa.Column("wbs_code", sa.String(80), nullable=False),
        sa.Column("wbs_name", sa.String(255), nullable=False),
        sa.Column("parent_wbs", sa.String(80)),
        sa.Column("discipline", sa.String(100)),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 5. Canonical Budget Records
    op.create_table(
        "budget_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_row_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_rows.id", ondelete="SET NULL")),
        sa.Column("budget_id", sa.String(100), nullable=False),
        sa.Column("wbs_code", sa.String(80)),
        sa.Column("cost_code", sa.String(80)),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("budget_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 6. Canonical Cost Records
    op.create_table(
        "cost_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_row_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_rows.id", ondelete="SET NULL")),
        sa.Column("transaction_id", sa.String(100), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("wbs_code", sa.String(80)),
        sa.Column("cost_code", sa.String(80)),
        sa.Column("vendor_id", sa.String(100)),
        sa.Column("vendor_name", sa.String(255)),
        sa.Column("po_number", sa.String(100)),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("actual_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 7. Canonical Commitment Records
    op.create_table(
        "commitment_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_row_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_rows.id", ondelete="SET NULL")),
        sa.Column("commitment_id", sa.String(100), nullable=False),
        sa.Column("wbs_code", sa.String(80)),
        sa.Column("po_number", sa.String(100)),
        sa.Column("vendor_id", sa.String(100)),
        sa.Column("vendor_name", sa.String(255)),
        sa.Column("committed_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("invoiced_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("commitment_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 8. Canonical Schedule Activities
    op.create_table(
        "schedule_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_row_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_rows.id", ondelete="SET NULL")),
        sa.Column("activity_id", sa.String(100), nullable=False),
        sa.Column("wbs_code", sa.String(80)),
        sa.Column("activity_name", sa.String(255), nullable=False),
        sa.Column("discipline", sa.String(100)),
        sa.Column("baseline_start", sa.Date, nullable=False),
        sa.Column("baseline_finish", sa.Date, nullable=False),
        sa.Column("actual_start", sa.Date),
        sa.Column("actual_finish", sa.Date),
        sa.Column("planned_progress", sa.Float, nullable=False),
        sa.Column("actual_progress", sa.Float, nullable=False),
        sa.Column("total_float_days", sa.Integer, nullable=False),
        sa.Column("critical", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 9. Canonical Progress Records
    op.create_table(
        "progress_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_row_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("raw_rows.id", ondelete="SET NULL")),
        sa.Column("progress_id", sa.String(100), nullable=False),
        sa.Column("period", sa.Date, nullable=False),
        sa.Column("wbs_code", sa.String(80)),
        sa.Column("planned_progress", sa.Float, nullable=False),
        sa.Column("actual_progress", sa.Float, nullable=False),
        sa.Column("variance", sa.Float, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Indices
    for table, columns in {
        "raw_rows": ("organization_id", "project_id", "source_file_id"),
        "import_batches": ("organization_id", "project_id", "source_file_id"),
        "import_column_mappings": ("organization_id", "project_id"),
        "wbs_nodes": ("organization_id", "project_id", "dataset_snapshot_id", "wbs_code"),
        "budget_records": ("organization_id", "project_id", "dataset_snapshot_id", "wbs_code"),
        "cost_records": ("organization_id", "project_id", "dataset_snapshot_id", "wbs_code", "transaction_id"),
        "commitment_records": ("organization_id", "project_id", "dataset_snapshot_id", "wbs_code", "commitment_id"),
        "schedule_activities": ("organization_id", "project_id", "dataset_snapshot_id", "wbs_code", "activity_id"),
        "progress_records": ("organization_id", "project_id", "dataset_snapshot_id", "wbs_code", "progress_id"),
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table in (
        "progress_records",
        "schedule_activities",
        "commitment_records",
        "cost_records",
        "budget_records",
        "wbs_nodes",
        "import_column_mappings",
        "import_batches",
        "raw_rows",
    ):
        op.drop_table(table)
