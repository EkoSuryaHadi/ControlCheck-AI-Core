from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ProjectGovernancePolicyRecord(Base):
    __tablename__ = "project_governance_policies"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_governance_policy_project"),
        CheckConstraint("critical_sla_days > 0 AND warning_sla_days > 0 AND observation_sla_days > 0", name="ck_governance_policy_sla_positive"),
        Index("ix_governance_policy_org_project", "organization_id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    critical_sla_days: Mapped[int] = mapped_column(Integer, default=3)
    warning_sla_days: Mapped[int] = mapped_column(Integer, default=7)
    observation_sla_days: Mapped[int] = mapped_column(Integer, default=14)
    require_critical_closure_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    require_warning_closure_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FindingClosureApprovalRecord(Base):
    __tablename__ = "finding_closure_approvals"
    __table_args__ = (
        CheckConstraint("decision IN ('pending','approved','rejected','withdrawn')", name="ck_closure_approval_decision"),
        Index("ix_closure_approvals_org_finding", "organization_id", "finding_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"))
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision: Mapped[str] = mapped_column(String(20), default="pending")
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision_note: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GovernanceEscalationRecord(Base):
    __tablename__ = "governance_escalations"
    __table_args__ = (
        CheckConstraint("escalation_type IN ('finding_sla','action_overdue')", name="ck_governance_escalation_type"),
        CheckConstraint("severity IN ('critical','warning','observation')", name="ck_governance_escalation_severity"),
        CheckConstraint("status IN ('open','acknowledged','resolved')", name="ck_governance_escalation_status"),
        Index("ix_governance_escalations_org_project_status", "organization_id", "project_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"))
    action_id: Mapped[UUID | None] = mapped_column(ForeignKey("finding_actions.id", ondelete="SET NULL"))
    escalation_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="open")
    reason: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acknowledged_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
