from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class FindingActionRecord(Base):
    __tablename__ = "finding_actions"
    __table_args__ = (
        CheckConstraint("priority IN ('high','medium','low')", name="ck_finding_actions_priority"),
        CheckConstraint("status IN ('open','in_review','completed','cancelled')", name="ck_finding_actions_status"),
        Index("ix_finding_actions_org", "organization_id"),
        Index("ix_finding_actions_project", "project_id"),
        Index("ix_finding_actions_finding", "finding_id"),
        Index("ix_finding_actions_due_date", "due_date"),
        Index("ix_finding_actions_priority", "priority"),
        Index("ix_finding_actions_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(300))
    owner: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="open")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(200))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FindingActionHistoryRecord(Base):
    __tablename__ = "finding_action_history"
    __table_args__ = (
        Index("ix_finding_action_history_org", "organization_id"),
        Index("ix_finding_action_history_action", "action_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    action_id: Mapped[UUID] = mapped_column(ForeignKey("finding_actions.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str | None] = mapped_column(String(200))
    changes: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
