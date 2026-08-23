from __future__ import annotations

import os
from datetime import datetime
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from .auth import decode_token
from .errors import ControlCheckApplicationError
from .governance import can_decide_approval
from .persistence.action_repository import FindingActionRepository
from .persistence.database import create_session_factory
from .persistence.governance_models import FindingClosureApprovalRecord, GovernanceEscalationRecord, ProjectGovernancePolicyRecord
from .persistence.governance_repository import GovernanceRepository
from .persistence.models import ProjectMemberRecord
from .persistence.repositories import FindingRepository, ProjectRepository


class GovernanceIdentity(BaseModel):
    organization_id: UUID
    user_id: UUID
    role: str | None = None


class GovernancePolicyUpdate(BaseModel):
    critical_sla_days: int | None = None
    warning_sla_days: int | None = None
    observation_sla_days: int | None = None
    require_critical_closure_approval: bool | None = None
    require_warning_closure_approval: bool | None = None


class GovernancePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_id: UUID
    critical_sla_days: int
    warning_sla_days: int
    observation_sla_days: int
    require_critical_closure_approval: bool
    require_warning_closure_approval: bool


class ApprovalRequestPayload(BaseModel):
    note: str | None = None


class ApprovalDecisionPayload(BaseModel):
    decision: str
    note: str | None = None


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    project_id: UUID
    finding_id: UUID
    requested_by: UUID | None = None
    decision: str
    decided_by: UUID | None = None
    decision_note: str | None = None
    requested_at: datetime
    decided_at: datetime | None = None


class ApprovalListResponse(BaseModel):
    items: list[ApprovalResponse]


class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    project_id: UUID
    finding_id: UUID
    action_id: UUID | None = None
    escalation_type: str
    severity: str
    status: str
    reason: str
    metadata_json: dict | None = None
    triggered_at: datetime
    acknowledged_by: UUID | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class EscalationListResponse(BaseModel):
    items: list[EscalationResponse]


def install_governance_routes(application) -> None:
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("CONTROLCHECK_DATABASE_URL")
    if not database_url:
        return
    session_factory = create_session_factory(database_url)

    def require_identity(authorization: str | None = Header(None)) -> GovernanceIdentity:
        if not authorization or not authorization.startswith("Bearer "):
            raise ControlCheckApplicationError("authentication_required", "Authentication is required for governance operations", 401)
        try:
            payload = decode_token(authorization[7:].strip())
            return GovernanceIdentity(
                organization_id=UUID(payload["org_id"]),
                user_id=UUID(payload["sub"]),
                role=payload.get("role"),
            )
        except Exception as exc:
            raise ControlCheckApplicationError("invalid_token", "Authentication token is invalid or expired", 401) from exc

    def project_role(session, identity: GovernanceIdentity, project_id: UUID) -> str | None:
        if identity.role == "org_admin":
            return "org_admin"
        member = session.scalar(
            select(ProjectMemberRecord).where(
                ProjectMemberRecord.project_id == project_id,
                ProjectMemberRecord.user_id == identity.user_id,
            )
        )
        return member.role if member is not None else identity.role

    def require_manager(session, identity: GovernanceIdentity, project_id: UUID) -> str:
        role = project_role(session, identity, project_id)
        if role not in {"org_admin", "project_manager"}:
            raise ControlCheckApplicationError(
                "governance_authority_required",
                "Only an organization admin or project manager may perform this governance operation",
                403,
            )
        return role

    def policy_response(project_id: UUID, record: ProjectGovernancePolicyRecord | None):
        if record is None:
            return GovernancePolicyResponse(
                project_id=project_id,
                critical_sla_days=3,
                warning_sla_days=7,
                observation_sla_days=14,
                require_critical_closure_approval=True,
                require_warning_closure_approval=False,
            )
        return GovernancePolicyResponse.model_validate(record)

    @application.get("/v1/projects/{project_id}/governance-policy", response_model=GovernancePolicyResponse)
    def get_policy(project_id: UUID, identity: GovernanceIdentity = Depends(require_identity)):
        with session_factory() as session:
            if ProjectRepository(session).get_scoped(identity.organization_id, project_id) is None:
                raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
            record = GovernanceRepository(session).get_policy_record(identity.organization_id, project_id)
            return policy_response(project_id, record)

    @application.patch("/v1/projects/{project_id}/governance-policy", response_model=GovernancePolicyResponse)
    def update_policy(project_id: UUID, payload: GovernancePolicyUpdate, identity: GovernanceIdentity = Depends(require_identity)):
        with session_factory() as session:
            if ProjectRepository(session).get_scoped(identity.organization_id, project_id) is None:
                raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
            require_manager(session, identity, project_id)
            patch = payload.model_dump(exclude_none=True)
            if any(key.endswith("_sla_days") and (value < 1 or value > 365) for key, value in patch.items() if isinstance(value, int)):
                raise ControlCheckApplicationError("invalid_governance_sla", "Governance SLA must be between 1 and 365 days", 422)
            record = GovernanceRepository(session).upsert_policy(identity.organization_id, project_id, patch)
            session.commit()
            session.refresh(record)
            return GovernancePolicyResponse.model_validate(record)

    @application.get("/v1/projects/{project_id}/closure-approvals", response_model=ApprovalListResponse)
    def list_closure_approvals(project_id: UUID, decision: str | None = None, identity: GovernanceIdentity = Depends(require_identity)):
        if decision not in {None, "pending", "approved", "rejected", "withdrawn"}:
            raise ControlCheckApplicationError("invalid_approval_decision", "Approval decision filter is invalid", 422)
        with session_factory() as session:
            if ProjectRepository(session).get_scoped(identity.organization_id, project_id) is None:
                raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
            items = GovernanceRepository(session).list_approvals(identity.organization_id, project_id, decision=decision)
            return ApprovalListResponse(items=[ApprovalResponse.model_validate(item) for item in items])

    @application.get("/v1/findings/{finding_id}/closure-approval", response_model=ApprovalResponse | None)
    def get_closure_approval(finding_id: UUID, identity: GovernanceIdentity = Depends(require_identity)):
        with session_factory() as session:
            finding = FindingRepository(session).get(identity.organization_id, finding_id)
            if finding is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            approval = GovernanceRepository(session).latest_approval(identity.organization_id, finding_id)
            return ApprovalResponse.model_validate(approval) if approval is not None else None

    @application.post("/v1/findings/{finding_id}/closure-approval", response_model=ApprovalResponse, status_code=201)
    def request_closure_approval(finding_id: UUID, payload: ApprovalRequestPayload, identity: GovernanceIdentity = Depends(require_identity)):
        with session_factory() as session:
            finding_repo = FindingRepository(session)
            finding = finding_repo.get(identity.organization_id, finding_id)
            if finding is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            governance_repo = GovernanceRepository(session)
            gate = governance_repo.approval_status(identity.organization_id, finding)
            if not gate["approval_required"]:
                raise ControlCheckApplicationError("approval_not_required", "Closure approval is not required for this finding", 409)

            evidence_count = len(finding_repo.evidence(identity.organization_id, finding_id))
            action_readiness = FindingActionRepository(session).closure_readiness(identity.organization_id, finding_id, evidence_count)
            if not action_readiness["can_close"]:
                raise ControlCheckApplicationError(
                    "approval_request_not_ready",
                    "Closure approval can only be requested after evidence is present and all corrective actions are completed or cancelled",
                    409,
                )

            approval = governance_repo.request_approval(identity.organization_id, finding_id, identity.user_id)
            if approval is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            if payload.note:
                approval.decision_note = f"Request note: {payload.note}"
            session.commit()
            session.refresh(approval)
            return ApprovalResponse.model_validate(approval)

    @application.post("/v1/closure-approvals/{approval_id}/decision", response_model=ApprovalResponse)
    def decide_closure_approval(approval_id: UUID, payload: ApprovalDecisionPayload, identity: GovernanceIdentity = Depends(require_identity)):
        if payload.decision not in {"approved", "rejected"}:
            raise ControlCheckApplicationError("invalid_approval_decision", "Approval decision must be approved or rejected", 422)
        with session_factory() as session:
            approval = session.scalar(
                select(FindingClosureApprovalRecord).where(
                    FindingClosureApprovalRecord.organization_id == identity.organization_id,
                    FindingClosureApprovalRecord.id == approval_id,
                )
            )
            if approval is None:
                raise ControlCheckApplicationError("approval_not_found", "Closure approval request was not found", 404)
            if approval.decision != "pending":
                raise ControlCheckApplicationError("approval_already_decided", "Closure approval request has already been decided", 409)
            role = project_role(session, identity, approval.project_id)
            allowed, reason = can_decide_approval(
                requester_user_id=str(approval.requested_by) if approval.requested_by else None,
                approver_user_id=str(identity.user_id),
                approver_role=role,
            )
            if not allowed:
                raise ControlCheckApplicationError("maker_checker_blocked", reason or "Approval decision is not permitted", 403)
            approval = GovernanceRepository(session).decide_approval(
                identity.organization_id,
                approval_id,
                decision=payload.decision,
                decided_by=identity.user_id,
                note=payload.note,
            )
            session.commit()
            session.refresh(approval)
            return ApprovalResponse.model_validate(approval)

    @application.post("/v1/projects/{project_id}/governance-escalations/scan", response_model=EscalationListResponse)
    def scan_escalations(project_id: UUID, identity: GovernanceIdentity = Depends(require_identity)):
        with session_factory() as session:
            if ProjectRepository(session).get_scoped(identity.organization_id, project_id) is None:
                raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
            require_manager(session, identity, project_id)
            created = GovernanceRepository(session).scan_escalations(identity.organization_id, project_id)
            session.commit()
            return EscalationListResponse(items=[EscalationResponse.model_validate(item) for item in created])

    @application.get("/v1/projects/{project_id}/governance-escalations", response_model=EscalationListResponse)
    def list_escalations(project_id: UUID, status: str | None = None, identity: GovernanceIdentity = Depends(require_identity)):
        if status not in {None, "open", "acknowledged", "resolved"}:
            raise ControlCheckApplicationError("invalid_escalation_status", "Escalation status is invalid", 422)
        with session_factory() as session:
            if ProjectRepository(session).get_scoped(identity.organization_id, project_id) is None:
                raise ControlCheckApplicationError("project_not_found", "Project was not found for this organization", 404)
            items = GovernanceRepository(session).list_escalations(identity.organization_id, project_id, status=status)
            return EscalationListResponse(items=[EscalationResponse.model_validate(item) for item in items])

    @application.post("/v1/governance-escalations/{escalation_id}/acknowledge", response_model=EscalationResponse)
    def acknowledge_escalation(escalation_id: UUID, identity: GovernanceIdentity = Depends(require_identity)):
        with session_factory() as session:
            escalation = session.scalar(
                select(GovernanceEscalationRecord).where(
                    GovernanceEscalationRecord.organization_id == identity.organization_id,
                    GovernanceEscalationRecord.id == escalation_id,
                )
            )
            if escalation is None:
                raise ControlCheckApplicationError("escalation_not_found", "Governance escalation was not found", 404)
            require_manager(session, identity, escalation.project_id)
            escalation = GovernanceRepository(session).acknowledge_escalation(identity.organization_id, escalation_id, identity.user_id)
            session.commit()
            session.refresh(escalation)
            return EscalationResponse.model_validate(escalation)
