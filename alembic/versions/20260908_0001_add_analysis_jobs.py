"""Add analysis_jobs queue for the VPS Celery worker.

Large workbooks are uploaded directly to object storage (R2); this table is
the durable queue consumed by the VPS worker for heavy analysis.

Revision ID: 20260908_0001
Revises: 20260907_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260908_0001"
down_revision: str | None = "20260907_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id", ondelete="SET NULL")),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("workbook_sha256", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('queued','processing','completed','failed')", name="ck_analysis_jobs_status"),
        sa.CheckConstraint("file_size_bytes >= 0", name="ck_analysis_jobs_size"),
    )
    op.create_index("ix_analysis_jobs_organization_id", "analysis_jobs", ["organization_id"])
    op.create_index("ix_analysis_jobs_project_id", "analysis_jobs", ["project_id"])
    op.create_index("ix_analysis_jobs_analysis_run_id", "analysis_jobs", ["analysis_run_id"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])
    op.create_index("ix_analysis_jobs_org_status_created", "analysis_jobs", ["organization_id", "status", "created_at"])


def downgrade() -> None:
    op.drop_table("analysis_jobs")
