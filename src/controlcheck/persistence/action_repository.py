from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .action_models import FindingActionHistoryRecord, FindingActionRecord
from .models import FindingRecord


def evaluate_closure_readiness(action_statuses: list[str], evidence_count: int) -> dict:
    open_statuses = [status for status in action_statuses if status not in {"completed", "cancelled"}]
    completed_count = sum(1 for status in action_statuses if status == "completed")
    evidence_ready = evidence_count > 0
    actions_ready = len(open_statuses) == 0
    return {
        "can_close": evidence_ready and actions_ready,
        "evidence_ready": evidence_ready,
        "actions_ready": actions_ready,
        "action_count": len(action_statuses),
        "open_action_count": len(open_statuses),
        "completed_action_count": completed_count,
        "blockers": [
            *([] if evidence_ready else ["At least one evidence record is required before closure."]),
            *([] if actions_ready else ["All corrective actions must be completed or cancelled before closure."]),
        ],
    }


class FindingActionRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_project(self, organization_id: UUID, project_id: UUID):
        statement = (
            select(FindingActionRecord)
            .where(
                FindingActionRecord.organization_id == organization_id,
                FindingActionRecord.project_id == project_id,
            )
            .order_by(FindingActionRecord.due_date.asc(), FindingActionRecord.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def list_for_finding(self, organization_id: UUID, finding_id: UUID):
        statement = (
            select(FindingActionRecord)
            .where(
                FindingActionRecord.organization_id == organization_id,
                FindingActionRecord.finding_id == finding_id,
            )
            .order_by(FindingActionRecord.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def get(self, organization_id: UUID, action_id: UUID):
        statement = select(FindingActionRecord).where(
            FindingActionRecord.organization_id == organization_id,
            FindingActionRecord.id == action_id,
        )
        return self.session.scalar(statement)

    def create(self, organization_id: UUID, finding_id: UUID, *, title: str, owner: str, due_date: date,
               priority: str, notes: str | None, actor: str | None = None):
        finding = self.session.scalar(
            select(FindingRecord).where(
                FindingRecord.organization_id == organization_id,
                FindingRecord.id == finding_id,
            )
        )
        if finding is None:
            return None
        action = FindingActionRecord(
            organization_id=organization_id,
            project_id=finding.project_id,
            finding_id=finding_id,
            title=title,
            owner=owner,
            due_date=due_date,
            priority=priority,
            status="open",
            notes=notes,
            created_by=actor,
        )
        self.session.add(action)
        self.session.flush()
        self._history(organization_id, action.id, "created", actor, {
            "title": title, "owner": owner, "due_date": due_date.isoformat(), "priority": priority
        })
        return action

    def update(self, organization_id: UUID, action_id: UUID, patch: dict, actor: str | None = None):
        action = self.get(organization_id, action_id)
        if action is None:
            return None
        allowed = {"title", "owner", "due_date", "priority", "status", "notes"}
        changes: dict = {}
        for key, value in patch.items():
            if key not in allowed or value is None:
                continue
            previous = getattr(action, key)
            if previous != value:
                changes[key] = {"from": str(previous) if previous is not None else None, "to": str(value)}
                setattr(action, key, value)
        if "status" in patch:
            if patch["status"] == "completed" and action.completed_at is None:
                action.completed_at = datetime.now(timezone.utc)
            elif patch["status"] != "completed":
                action.completed_at = None
        if changes:
            self.session.flush()
            self._history(organization_id, action.id, "updated", actor, changes)
        return action

    def history(self, organization_id: UUID, action_id: UUID):
        statement = (
            select(FindingActionHistoryRecord)
            .where(
                FindingActionHistoryRecord.organization_id == organization_id,
                FindingActionHistoryRecord.action_id == action_id,
            )
            .order_by(FindingActionHistoryRecord.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def closure_readiness(self, organization_id: UUID, finding_id: UUID, evidence_count: int):
        actions = self.list_for_finding(organization_id, finding_id)
        return evaluate_closure_readiness([item.status for item in actions], evidence_count)

    def _history(self, organization_id: UUID, action_id: UUID, event_type: str, actor: str | None, changes: dict | None):
        self.session.add(FindingActionHistoryRecord(
            organization_id=organization_id,
            action_id=action_id,
            event_type=event_type,
            actor=actor,
            changes=changes,
        ))
