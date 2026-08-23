from __future__ import annotations

import os
from datetime import date
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict

from .auth import decode_token
from .errors import ControlCheckApplicationError
from .persistence.action_repository import FindingActionRepository
from .persistence.database import create_session_factory
from .persistence.repositories import FindingRepository


class ActionCreate(BaseModel):
    title: str
    owner: str
    due_date: date
    priority: str = "medium"
    notes: str | None = None
    actor: str | None = None


class ActionUpdate(BaseModel):
    title: str | None = None
    owner: str | None = None
    due_date: date | None = None
    priority: str | None = None
    status: str | None = None
    notes: str | None = None
    actor: str | None = None


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
    completed_at: object | None = None
    created_at: object
    updated_at: object


class ActionListResponse(BaseModel):
    items: list[ActionResponse]


class ClosureReadinessResponse(BaseModel):
    can_close: bool
    evidence_ready: bool
    actions_ready: bool
    action_count: int
    open_action_count: int
    completed_action_count: int
    blockers: list[str]


def install_action_routes(application) -> None:
    database_url = os.environ.get("DATABASE_URL") or os.environ.get("CONTROLCHECK_DATABASE_URL")
    if not database_url:
        return
    session_factory = create_session_factory(database_url)

    def require_org(
        x_organization_id: str | None = Header(None),
        authorization: str | None = Header(None),
    ) -> UUID:
        if authorization and authorization.startswith("Bearer "):
            try:
                payload = decode_token(authorization[7:].strip())
                if payload.get("org_id"):
                    return UUID(payload["org_id"])
            except Exception as exc:
                raise ControlCheckApplicationError("invalid_token", "Authentication token is invalid or expired", 401) from exc
        if not x_organization_id:
            raise ControlCheckApplicationError("missing_tenant_context", "Organization context is required", 400)
        try:
            return UUID(x_organization_id)
        except ValueError as exc:
            raise ControlCheckApplicationError("invalid_tenant_context", "Organization context must be a UUID", 400) from exc

    @application.get("/v1/projects/{project_id}/actions", response_model=ActionListResponse)
    def list_project_actions(project_id: UUID, organization_id: UUID = Depends(require_org)):
        with session_factory() as session:
            items = FindingActionRepository(session).list_for_project(organization_id, project_id)
            return ActionListResponse(items=[ActionResponse.model_validate(item) for item in items])

    @application.get("/v1/findings/{finding_id}/actions", response_model=ActionListResponse)
    def list_finding_actions(finding_id: UUID, organization_id: UUID = Depends(require_org)):
        with session_factory() as session:
            finding = FindingRepository(session).get(organization_id, finding_id)
            if finding is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            items = FindingActionRepository(session).list_for_finding(organization_id, finding_id)
            return ActionListResponse(items=[ActionResponse.model_validate(item) for item in items])

    @application.post("/v1/findings/{finding_id}/actions", response_model=ActionResponse, status_code=201)
    def create_finding_action(finding_id: UUID, payload: ActionCreate, organization_id: UUID = Depends(require_org)):
        if payload.priority not in {"high", "medium", "low"}:
            raise ControlCheckApplicationError("invalid_action_priority", "Action priority is invalid", 422)
        with session_factory() as session:
            action = FindingActionRepository(session).create(
                organization_id,
                finding_id,
                title=payload.title,
                owner=payload.owner,
                due_date=payload.due_date,
                priority=payload.priority,
                notes=payload.notes,
                actor=payload.actor,
            )
            if action is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            session.commit()
            session.refresh(action)
            return ActionResponse.model_validate(action)

    @application.patch("/v1/actions/{action_id}", response_model=ActionResponse)
    def update_action(action_id: UUID, payload: ActionUpdate, organization_id: UUID = Depends(require_org)):
        patch = payload.model_dump(exclude_none=True)
        actor = patch.pop("actor", None)
        if patch.get("priority") not in {None, "high", "medium", "low"}:
            raise ControlCheckApplicationError("invalid_action_priority", "Action priority is invalid", 422)
        if patch.get("status") not in {None, "open", "in_review", "completed", "cancelled"}:
            raise ControlCheckApplicationError("invalid_action_status", "Action status is invalid", 422)
        with session_factory() as session:
            action = FindingActionRepository(session).update(organization_id, action_id, patch, actor=actor)
            if action is None:
                raise ControlCheckApplicationError("action_not_found", "Corrective action was not found", 404)
            session.commit()
            session.refresh(action)
            return ActionResponse.model_validate(action)

    @application.get("/v1/findings/{finding_id}/closure-readiness", response_model=ClosureReadinessResponse)
    def closure_readiness(finding_id: UUID, organization_id: UUID = Depends(require_org)):
        with session_factory() as session:
            finding_repo = FindingRepository(session)
            if finding_repo.get(organization_id, finding_id) is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            evidence_count = len(finding_repo.evidence(organization_id, finding_id))
            result = FindingActionRepository(session).closure_readiness(organization_id, finding_id, evidence_count)
            return ClosureReadinessResponse(**result)

    @application.post("/v1/findings/{finding_id}/close", response_model=dict)
    def close_finding(finding_id: UUID, organization_id: UUID = Depends(require_org)):
        with session_factory() as session:
            finding_repo = FindingRepository(session)
            finding = finding_repo.get(organization_id, finding_id)
            if finding is None:
                raise ControlCheckApplicationError("finding_not_found", "Finding was not found", 404)
            evidence_count = len(finding_repo.evidence(organization_id, finding_id))
            readiness = FindingActionRepository(session).closure_readiness(organization_id, finding_id, evidence_count)
            if not readiness["can_close"]:
                raise ControlCheckApplicationError(
                    "closure_governance_blocked",
                    "Finding cannot be closed until evidence and corrective action requirements are satisfied",
                    409,
                )
            finding = finding_repo.update_status(organization_id, finding_id, "resolved")
            session.commit()
            return {"finding_id": str(finding_id), "status": finding.status, "closure_readiness": readiness}
