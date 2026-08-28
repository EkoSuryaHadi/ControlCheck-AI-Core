"""Add first-party beta usage telemetry and finding feedback.

Revision ID: 20260906_0001
Revises: 20260905_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260906_0001"
down_revision: str | None = "20260905_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL")),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id", ondelete="SET NULL")),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="SET NULL")),
        sa.Column("event_name", sa.String(80), nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_product_events_org", "product_events", ["organization_id"])
    op.create_index("ix_product_events_user", "product_events", ["user_id"])
    op.create_index("ix_product_events_project", "product_events", ["project_id"])
    op.create_index("ix_product_events_run", "product_events", ["analysis_run_id"])
    op.create_index("ix_product_events_finding", "product_events", ["finding_id"])
    op.create_index("ix_product_events_org_created", "product_events", ["organization_id", "created_at"])
    op.create_index("ix_product_events_name_created", "product_events", ["event_name", "created_at"])

    op.create_table(
        "finding_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE")),
        sa.Column("rating", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rating IN ('useful','not_useful')", name="ck_finding_feedback_rating"),
        sa.CheckConstraint("status IN ('new','reviewed','archived')", name="ck_finding_feedback_status"),
    )
    op.create_index("ix_finding_feedback_org", "finding_feedback", ["organization_id"])
    op.create_index("ix_finding_feedback_user", "finding_feedback", ["user_id"])
    op.create_index("ix_finding_feedback_project", "finding_feedback", ["project_id"])
    op.create_index("ix_finding_feedback_run", "finding_feedback", ["analysis_run_id"])
    op.create_index("ix_finding_feedback_finding", "finding_feedback", ["finding_id"])
    op.create_index("ix_finding_feedback_status", "finding_feedback", ["status"])
    op.create_index("ix_finding_feedback_org_created", "finding_feedback", ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_table("finding_feedback")
    op.drop_table("product_events")
