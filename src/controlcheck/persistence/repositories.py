from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import OrganizationRecord, ProjectRecord


class OrganizationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, organization_id: UUID) -> OrganizationRecord | None:
        return self.session.scalar(
            select(OrganizationRecord).where(OrganizationRecord.id == organization_id)
        )


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        organization_id: UUID,
        code: str,
        name: str,
        currency: str,
    ) -> ProjectRecord:
        project = ProjectRecord(
            organization_id=organization_id,
            code=code,
            name=name,
            currency=currency,
        )
        self.session.add(project)
        self.session.flush()
        return project

    def list_for_organization(self, organization_id: UUID) -> list[ProjectRecord]:
        return list(
            self.session.scalars(
                select(ProjectRecord)
                .where(ProjectRecord.organization_id == organization_id)
                .order_by(ProjectRecord.created_at, ProjectRecord.id)
            )
        )

    def get_scoped(self, organization_id: UUID, project_id: UUID) -> ProjectRecord | None:
        return self.session.scalar(
            select(ProjectRecord).where(
                ProjectRecord.id == project_id,
                ProjectRecord.organization_id == organization_id,
            )
        )
