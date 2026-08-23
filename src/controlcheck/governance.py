from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class GovernancePolicy:
    critical_sla_days: int = 3
    warning_sla_days: int = 7
    observation_sla_days: int = 14
    require_critical_closure_approval: bool = True
    require_warning_closure_approval: bool = False

    def sla_days(self, severity: str) -> int:
        return {
            "critical": self.critical_sla_days,
            "warning": self.warning_sla_days,
            "observation": self.observation_sla_days,
        }.get(severity, self.observation_sla_days)

    def approval_required(self, severity: str) -> bool:
        if severity == "critical":
            return self.require_critical_closure_approval
        if severity == "warning":
            return self.require_warning_closure_approval
        return False


def finding_due_at(detected_at: datetime, severity: str, policy: GovernancePolicy) -> datetime:
    detected = detected_at if detected_at.tzinfo else detected_at.replace(tzinfo=timezone.utc)
    return detected + timedelta(days=policy.sla_days(severity))


def finding_is_overdue(detected_at: datetime, severity: str, policy: GovernancePolicy, now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    return current > finding_due_at(detected_at, severity, policy)


def approval_gate(*, severity: str, policy: GovernancePolicy, latest_decision: str | None) -> dict:
    required = policy.approval_required(severity)
    approved = (not required) or latest_decision == "approved"
    return {
        "approval_required": required,
        "approval_ready": approved,
        "approval_decision": latest_decision,
        "blocker": None if approved else "Closure approval is required before this finding can be closed.",
    }


def can_decide_approval(*, requester_user_id: str | None, approver_user_id: str | None, approver_role: str | None) -> tuple[bool, str | None]:
    if not approver_user_id:
        return False, "Authenticated approver identity is required."
    if requester_user_id and requester_user_id == approver_user_id:
        return False, "Maker-checker policy prevents the requester from approving their own closure request."
    if approver_role not in {"org_admin", "project_manager"}:
        return False, "Only an organization admin or project manager may decide closure approval."
    return True, None
