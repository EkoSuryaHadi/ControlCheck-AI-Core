"""Persistent corrective actions and closure governance.

Revision ID: 20260823_0006
Revises: 20260905_0005
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260823_0006"
down_revision: str | None = "20260905_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finding_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("owner", sa.String(200), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", sa.String(200)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("priority IN ('high','medium','low')", name="ck_finding_actions_priority"),
        sa.CheckConstraint("status IN ('open','in_review','completed','cancelled')", name="ck_finding_actions_status"),
    )
    op.create_index("ix_finding_actions_org", "finding_actions", ["organization_id"])
    op.create_index("ix_finding_actions_project", "finding_actions", ["project_id"])
    op.create_index("ix_finding_actions_finding", "finding_actions", ["finding_id"])
    op.create_index("ix_finding_actions_due_date", "finding_actions", ["due_date"])
    op.create_index("ix_finding_actions_priority", "finding_actions", ["priority"])
    op.create_index("ix_finding_actions_status", "finding_actions", ["status"])

    op.create_table(
        "finding_action_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finding_actions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(200)),
        sa.Column("changes", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_finding_action_history_org", "finding_action_history", ["organization_id"])
    op.create_index("ix_finding_action_history_action", "finding_action_history", ["action_id"])


def downgrade() -> None:
    op.drop_table("finding_action_history")
    op.drop_table("finding_actions")
