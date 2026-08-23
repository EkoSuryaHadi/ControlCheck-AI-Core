from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..governance import GovernancePolicy, approval_gate, finding_due_at, finding_is_overdue
from .action_models import FindingActionRecord
from .governance_models import FindingClosureApprovalRecord, GovernanceEscalationRecord, ProjectGovernancePolicyRecord
from .models import FindingRecord


class GovernanceRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_policy_record(self, organization_id: UUID, project_id: UUID):
        return self.session.scalar(
            select(ProjectGovernancePolicyRecord).where(
                ProjectGovernancePolicyRecord.organization_id == organization_id,
                ProjectGovernancePolicyRecord.project_id == project_id,
            )
        )

    def get_policy(self, organization_id: UUID, project_id: UUID) -> GovernancePolicy:
        record = self.get_policy_record(organization_id, project_id)
        if record is None:
            return GovernancePolicy()
        return GovernancePolicy(
            critical_sla_days=record.critical_sla_days,
            warning_sla_days=record.warning_sla_days,
            observation_sla_days=record.observation_sla_days,
            require_critical_closure_approval=record.require_critical_closure_approval,
            require_warning_closure_approval=record.require_warning_closure_approval,
        )

    def upsert_policy(self, organization_id: UUID, project_id: UUID, patch: dict):
        record = self.get_policy_record(organization_id, project_id)
        if record is None:
            record = ProjectGovernancePolicyRecord(
                organization_id=organization_id,
                project_id=project_id,
            )
            self.session.add(record)
        for key, value in patch.items():
            if value is not None and hasattr(record, key):
                setattr(record, key, value)
        self.session.flush()
        return record

    def latest_approval(self, organization_id: UUID, finding_id: UUID):
        statement = (
            select(FindingClosureApprovalRecord)
            .where(
                FindingClosureApprovalRecord.organization_id == organization_id,
                FindingClosureApprovalRecord.finding_id == finding_id,
            )
            .order_by(FindingClosureApprovalRecord.requested_at.desc())
        )
        return self.session.scalar(statement)

    def request_approval(self, organization_id: UUID, finding_id: UUID, requested_by: UUID | None):
        finding = self.session.scalar(
            select(FindingRecord).where(
                FindingRecord.organization_id == organization_id,
                FindingRecord.id == finding_id,
            )
        )
        if finding is None:
            return None
        current = self.latest_approval(organization_id, finding_id)
        if current is not None and current.decision == "pending":
            return current
        record = FindingClosureApprovalRecord(
            organization_id=organization_id,
            project_id=finding.project_id,
            finding_id=finding_id,
            requested_by=requested_by,
            decision="pending",
        )
        self.session.add(record)
        self.session.flush()
        return record

    def decide_approval(self, organization_id: UUID, approval_id: UUID, *, decision: str, decided_by: UUID, note: str | None):
        approval = self.session.scalar(
            select(FindingClosureApprovalRecord).where(
                FindingClosureApprovalRecord.organization_id == organization_id,
                FindingClosureApprovalRecord.id == approval_id,
            )
        )
        if approval is None:
            return None
        approval.decision = decision
        approval.decided_by = decided_by
        approval.decision_note = note
        approval.decided_at = datetime.now(timezone.utc)
        self.session.flush()
        return approval

    def approval_status(self, organization_id: UUID, finding: FindingRecord) -> dict:
        policy = self.get_policy(organization_id, finding.project_id)
        latest = self.latest_approval(organization_id, finding.id)
        gate = approval_gate(
            severity=finding.severity,
            policy=policy,
            latest_decision=latest.decision if latest is not None else None,
        )
        gate["approval_id"] = str(latest.id) if latest is not None else None
        return gate

    def scan_escalations(self, organization_id: UUID, project_id: UUID, now: datetime | None = None):
        current = now or datetime.now(timezone.utc)
        policy = self.get_policy(organization_id, project_id)
        findings = list(self.session.scalars(
            select(FindingRecord).where(
                FindingRecord.organization_id == organization_id,
                FindingRecord.project_id == project_id,
                FindingRecord.status.in_(["open", "acknowledged"]),
            )
        ))
        created: list[GovernanceEscalationRecord] = []
        for finding in findings:
            if finding_is_overdue(finding.detected_at, finding.severity, policy, current):
                created_record = self._ensure_escalation(
                    organization_id, project_id, finding.id, None,
                    escalation_type="finding_sla",
                    severity=finding.severity,
                    reason=f"{finding.severity.title()} finding exceeded {policy.sla_days(finding.severity)}-day review SLA.",
                    metadata={"due_at": finding_due_at(finding.detected_at, finding.severity, policy).isoformat()},
                )
                if created_record is not None:
                    created.append(created_record)

        actions = list(self.session.scalars(
            select(FindingActionRecord).where(
                FindingActionRecord.organization_id == organization_id,
                FindingActionRecord.project_id == project_id,
                FindingActionRecord.status.in_(["open", "in_review"]),
                FindingActionRecord.due_date < current.date(),
            )
        ))
        for action in actions:
            finding = self.session.scalar(select(FindingRecord).where(FindingRecord.id == action.finding_id))
            if finding is None:
                continue
            created_record = self._ensure_escalation(
                organization_id, project_id, finding.id, action.id,
                escalation_type="action_overdue",
                severity=finding.severity,
                reason=f"Corrective action '{action.title}' is overdue since {action.due_date.isoformat()}.",
                metadata={"owner": action.owner, "due_date": action.due_date.isoformat()},
            )
            if created_record is not None:
                created.append(created_record)
        return created

    def list_escalations(self, organization_id: UUID, project_id: UUID, status: str | None = None):
        statement = select(GovernanceEscalationRecord).where(
            GovernanceEscalationRecord.organization_id == organization_id,
            GovernanceEscalationRecord.project_id == project_id,
        )
        if status:
            statement = statement.where(GovernanceEscalationRecord.status == status)
        return list(self.session.scalars(statement.order_by(GovernanceEscalationRecord.triggered_at.desc())))

    def acknowledge_escalation(self, organization_id: UUID, escalation_id: UUID, user_id: UUID):
        record = self.session.scalar(select(GovernanceEscalationRecord).where(
            GovernanceEscalationRecord.organization_id == organization_id,
            GovernanceEscalationRecord.id == escalation_id,
        ))
        if record is None:
            return None
        if record.status == "open":
            record.status = "acknowledged"
            record.acknowledged_by = user_id
            record.acknowledged_at = datetime.now(timezone.utc)
            self.session.flush()
        return record

    def _ensure_escalation(self, organization_id: UUID, project_id: UUID, finding_id: UUID, action_id: UUID | None,
                           *, escalation_type: str, severity: str, reason: str, metadata: dict):
        statement = select(GovernanceEscalationRecord).where(
            GovernanceEscalationRecord.organization_id == organization_id,
            GovernanceEscalationRecord.project_id == project_id,
            GovernanceEscalationRecord.finding_id == finding_id,
            GovernanceEscalationRecord.escalation_type == escalation_type,
            GovernanceEscalationRecord.status.in_(["open", "acknowledged"]),
        )
        if action_id is None:
            statement = statement.where(GovernanceEscalationRecord.action_id.is_(None))
        else:
            statement = statement.where(GovernanceEscalationRecord.action_id == action_id)
        if self.session.scalar(statement) is not None:
            return None
        record = GovernanceEscalationRecord(
            organization_id=organization_id,
            project_id=project_id,
            finding_id=finding_id,
            action_id=action_id,
            escalation_type=escalation_type,
            severity=severity,
            reason=reason,
            metadata_json=metadata,
        )
        self.session.add(record)
        self.session.flush()
        return record
