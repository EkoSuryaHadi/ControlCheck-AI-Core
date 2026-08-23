"""v0.6 approval and escalation governance.

Revision ID: 20260823_0007
Revises: 20260823_0006
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260823_0007"
down_revision: str | None = "20260823_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_governance_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("critical_sla_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("warning_sla_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("observation_sla_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("require_critical_closure_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_warning_closure_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", name="uq_governance_policy_project"),
        sa.CheckConstraint("critical_sla_days > 0 AND warning_sla_days > 0 AND observation_sla_days > 0", name="ck_governance_policy_sla_positive"),
    )
    op.create_index("ix_governance_policy_org_project", "project_governance_policies", ["organization_id", "project_id"])

    op.create_table(
        "finding_closure_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decision", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("decision_note", sa.Text()),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("decision IN ('pending','approved','rejected','withdrawn')", name="ck_closure_approval_decision"),
    )
    op.create_index("ix_closure_approvals_org_finding", "finding_closure_approvals", ["organization_id", "finding_id"])

    op.create_table(
        "governance_escalations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("finding_actions.id", ondelete="SET NULL")),
        sa.Column("escalation_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("escalation_type IN ('finding_sla','action_overdue')", name="ck_governance_escalation_type"),
        sa.CheckConstraint("severity IN ('critical','warning','observation')", name="ck_governance_escalation_severity"),
        sa.CheckConstraint("status IN ('open','acknowledged','resolved')", name="ck_governance_escalation_status"),
    )
    op.create_index("ix_governance_escalations_org_project_status", "governance_escalations", ["organization_id", "project_id", "status"])


def downgrade() -> None:
    op.drop_table("governance_escalations")
    op.drop_table("finding_closure_approvals")
    op.drop_table("project_governance_policies")
