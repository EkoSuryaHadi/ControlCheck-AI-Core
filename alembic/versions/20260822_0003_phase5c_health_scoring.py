"""Phase 5C health scoring schema.

Revision ID: 20260822_0003
Revises: 20260821_0002
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260822_0003"
down_revision: str | None = "20260821_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "health_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_score", sa.Float, nullable=False),
        sa.Column("cost_score", sa.Float, nullable=False),
        sa.Column("schedule_score", sa.Float, nullable=False),
        sa.Column("progress_score", sa.Float, nullable=False),
        sa.Column("dq_score", sa.Float, nullable=False),
        sa.Column("score_band", sa.String(50), nullable=False),
        sa.Column("component_breakdown", postgresql.JSONB, nullable=False),
        sa.Column("key_drivers", postgresql.JSONB, nullable=False),
        sa.Column("score_version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("analysis_run_id", name="uq_health_snapshot_run"),
        sa.CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="ck_health_overall_score"),
        sa.CheckConstraint("cost_score >= 0 AND cost_score <= 100", name="ck_health_cost_score"),
        sa.CheckConstraint("schedule_score >= 0 AND schedule_score <= 100", name="ck_health_schedule_score"),
        sa.CheckConstraint("progress_score >= 0 AND progress_score <= 100", name="ck_health_progress_score"),
        sa.CheckConstraint("dq_score >= 0 AND dq_score <= 100", name="ck_health_dq_score"),
        sa.CheckConstraint("score_band IN ('Healthy', 'Needs Attention', 'At Risk', 'Critical')", name="ck_health_score_band"),
    )

    for col in ("organization_id", "project_id", "analysis_run_id"):
        op.create_index(f"ix_health_snapshots_{col}", "health_snapshots", [col])


def downgrade() -> None:
    op.drop_table("health_snapshots")
