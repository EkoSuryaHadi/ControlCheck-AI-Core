from __future__ import annotations

import os
from datetime import date, datetime
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from .auth import decode_token
from .errors import ControlCheckApplicationError
from .persistence.action_repository import FindingActionRepository
from .persistence.database import create_session_factory
from .persistence.governance_repository import GovernanceRepository
from .persistence.models import ProjectMemberRecord
from .persistence.repositories import FindingRepository


class ActionCreate(BaseModel):
    title: str
    owner: str
    due_date: date
    priority: str = "medium"
    notes: str | None = None


class ActionUpdate(BaseModel):
    title: str | None = None
    owner: str | None = None
    due_date: date | None = None
    priority: str | None = None
    status: str | None = None
    notes: str | None = None


class ActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    project_id: UUID
    finding_id: UUID
    title: str
    owner: str
    due_date: date
    priority: str
    status: str
    notes: str | None = None
    created_by: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ActionListResponse(BaseModel):
    items: list[ActionResponse]


class ClosureReadinessResponse(BaseModel):
    can_close: bool
    evidence_ready: bool
    actions_ready: bool
    approval_required: bool = False
    approval_ready: bool = True
    approval_decision: str | None = None
    approval_id: str | None = None
    action_count: int
    open_action_count: int
    completed_action_count: int
    blockers: list[str]


def governance_enabled() -> bool:
    """Return whether approval/escalation governance participates in closure.

    Governance is intentionally opt-in while the module is parked from the active
    product experience. Re-enable with CONTROLCHECK_GOVERNANCE_ENABLED=true.
    """
    return os.environ.get("CONTROLCHECK_GOVERNANCE_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def install_action_routes(application) -> None:
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("CONTROLCHECK_DATABASE_URL")
    if not database_url:
        return
    session_factory = create_session_factory(database_url)

    def require_identity(authorization: str | None = Header(None)) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise ControlCheckApplicationError("authentication_required", "Authentication is required for corrective-action operations", 401)
        try:
            payload = decode_token(authorization[7:].strip())
            if not payload.get("org_id") or not payload.get("sub"):
                raise ValueError("missing identity claims")
            return {
                "organization_id": UUID(payload["org_id"]),
                "user_id": UUID(payload["sub"]),
                "role": payload.get("role"),
            }
        except ControlCheckApplicationError:
            raise
        except Exception as exc:
            raise ControlCheckApplicationError("invalid_token", "Authentication token is invalid or expired", 401) from exc

    def ensure_closure_authority(session, identity: dict, project_id: UUID) -> None:
        # While Governance is parked, any authenticated user in the tenant can
        # close a finding once evidence/action readiness is satisfied.
        if not governance_enabled():
            return
        if identity.get("role") == "org_admin":
            return
        membership = session.scalar(
            select(ProjectMemberRecord).where(
                ProjectMemberRecord.project_id == project_id,
                ProjectMemberRecord.user_id == identity["user_id"],
            )
        )
        if membership is None or membership.role != "project_manager":
            raise ControlCheckApplicationError(
                "closure_authority_required",
                "Only an organization admin or project manager may close a governed finding",
                403,
            )

    def build_readiness(session, organization_id: UUID, finding):
        finding_repo = FindingRepository(session)
        evidence_count = len(finding_repo.evidence(organization_id, finding.id))
        base = FindingActionRepository(session).closure_readiness(organization_id, finding.id, evidence_count)

        if not governance_enabled():
            return {
                **base,
                "approval_required": False,
                "approval_ready": True,
                "approval_decision": None,
                "approval_id": None,
                "can_close": bool(base["can_close"]),
                "blockers": list(base["blockers"]),
            }

        approval = GovernanceRepository(session).approval_status(organization_id, finding)
        blockers = list(base["blockers"])
        if approval.get("blocker"):
            blockers.append(approval["blocker"])
        return {
            **base,
            "approval_required": approval["approval_required"],
            "approval_ready": approval["approval_ready"],
            "approval_decision": approval["approval_decision"],
            "approval_id": approval["approval_id"],
            "can_close": bool(base["can_close"] and approval["approval_ready"]),
            "blockers": blockers,
        }

    @application.get("/v1/projects/{project_id}/actions", response_model=ActionListResponse)
    def list_project_actions(project_id: UUID, identity: dict = Depends(require_identity)):
        organization_id = identity["organization_id"]
        with session_factory() as session:
            items = FindingActionRepository(session).list_for_project(organization_id, project_id)
            return ActionListResponse(items=[ActionResponse.model_validate(item) for item in items])

    @application.get("/v1/findings/{finding_id}/actions", response_model=ActionListResponse)
    def list_finding_actions(finding_id: UUID, identity: dict = Depends(require_identity)):
        organization_id = identity["organization_id"]
        with session_factory() as session:
            finding = FindingRepository(session).get(organization_id, finding_id)
            if finding is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            items = FindingActionRepository(session).list_for_finding(organization_id, finding_id)
            return ActionListResponse(items=[ActionResponse.model_validate(item) for item in items])

    @application.post("/v1/findings/{finding_id}/actions", response_model=ActionResponse, status_code=201)
    def create_finding_action(finding_id: UUID, payload: ActionCreate, identity: dict = Depends(require_identity)):
        if payload.priority not in {"high", "medium", "low"}:
            raise ControlCheckApplicationError("invalid_action_priority", "Action priority is invalid", 422)
        organization_id = identity["organization_id"]
        actor = str(identity["user_id"])
        with session_factory() as session:
            action = FindingActionRepository(session).create(
                organization_id,
                finding_id,
                title=payload.title,
                owner=payload.owner,
                due_date=payload.due_date,
                priority=payload.priority,
                notes=payload.notes,
                actor=actor,
            )
            if action is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            session.commit()
            session.refresh(action)
            return ActionResponse.model_validate(action)

    @application.patch("/v1/actions/{action_id}", response_model=ActionResponse)
    def update_action(action_id: UUID, payload: ActionUpdate, identity: dict = Depends(require_identity)):
        patch = payload.model_dump(exclude_none=True)
        if patch.get("priority") not in {None, "high", "medium", "low"}:
            raise ControlCheckApplicationError("invalid_action_priority", "Action priority is invalid", 422)
        if patch.get("status") not in {None, "open", "in_review", "completed", "cancelled"}:
            raise ControlCheckApplicationError("invalid_action_status", "Action status is invalid", 422)
        organization_id = identity["organization_id"]
        actor = str(identity["user_id"])
        with session_factory() as session:
            action = FindingActionRepository(session).update(organization_id, action_id, patch, actor=actor)
            if action is None:
                raise ControlCheckApplicationError("action_not_found", "Corrective action was not found", 404)
            session.commit()
            session.refresh(action)
            return ActionResponse.model_validate(action)

    @application.get("/v1/findings/{finding_id}/closure-readiness", response_model=ClosureReadinessResponse)
    def closure_readiness(finding_id: UUID, identity: dict = Depends(require_identity)):
        organization_id = identity["organization_id"]
        with session_factory() as session:
            finding = FindingRepository(session).get(organization_id, finding_id)
            if finding is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            return ClosureReadinessResponse(**build_readiness(session, organization_id, finding))

    @application.post("/v1/findings/{finding_id}/close", response_model=dict)
    def close_finding(finding_id: UUID, identity: dict = Depends(require_identity)):
        organization_id = identity["organization_id"]
        with session_factory() as session:
            finding_repo = FindingRepository(session)
            finding = finding_repo.get(organization_id, finding_id)
            if finding is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            ensure_closure_authority(session, identity, finding.project_id)
            readiness = build_readiness(session, organization_id, finding)
            if not readiness["can_close"]:
                raise ControlCheckApplicationError(
                    "closure_requirements_incomplete",
                    "Finding cannot be closed until evidence and corrective-action requirements are satisfied",
                    409,
                )
            finding = finding_repo.update_status(organization_id, finding_id, "resolved")
            session.commit()
            return {"finding_id": str(finding_id), "status": finding.status, "closure_readiness": readiness}
