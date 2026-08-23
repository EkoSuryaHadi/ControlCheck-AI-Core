"""v0.6.16 persisted report packages.

Revision ID: 20260823_0008
Revises: 20260823_0007
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260823_0008"
down_revision: str | None = "20260823_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("report_name", sa.String(255), nullable=False),
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("period", sa.String(80), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("pdf_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("pdf_size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("report_type IN ('monthly','executive','cost','schedule','progress')", name="ck_report_packages_type"),
    )
    op.create_index("ix_report_packages_org_project_created", "report_packages", ["organization_id", "project_id", "created_at"])
    op.create_index("ix_report_packages_project_id", "report_packages", ["project_id"])
    op.create_index("ix_report_packages_analysis_run_id", "report_packages", ["analysis_run_id"])
    op.create_index("ix_report_packages_generated_by", "report_packages", ["generated_by"])


def downgrade() -> None:
    op.drop_table("report_packages")
