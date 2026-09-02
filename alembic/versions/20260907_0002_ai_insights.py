"""Add persisted evidence-grounded AI insights.

Revision ID: 20260907_0002
Revises: 20260831_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260907_0002"
down_revision: str | None = "20260831_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("model", sa.String(100)),
        sa.Column("content", postgresql.JSONB),
        sa.Column("referenced_finding_ids", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("error_code", sa.String(80)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("analysis_run_id", name="uq_ai_insights_run"),
        sa.CheckConstraint("status IN ('pending','generating','ready','failed')", name="ck_ai_insights_status"),
    )
    op.create_index("ix_ai_insights_organization_id", "ai_insights", ["organization_id"])
    op.create_index("ix_ai_insights_project_id", "ai_insights", ["project_id"])
    op.create_index("ix_ai_insights_analysis_run_id", "ai_insights", ["analysis_run_id"])
    op.create_index("ix_ai_insights_status", "ai_insights", ["status"])
    op.create_index("ix_ai_insights_org_run", "ai_insights", ["organization_id", "analysis_run_id"])


def downgrade() -> None:
    op.drop_table("ai_insights")