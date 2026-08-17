from uuid import uuid4

import pytest
from alembic import command

from controlcheck.persistence.database import create_session_factory
from controlcheck.persistence.models import OrganizationRecord
from controlcheck.persistence.repositories import ProjectRepository


@pytest.fixture()
def db_session(alembic_config, postgres_url):
    command.upgrade(alembic_config, "head")
    session = create_session_factory(postgres_url)()
    transaction = session.begin()
    try:
        yield session
    finally:
        transaction.rollback()
        session.close()


def seed_organization(session, suffix: str) -> OrganizationRecord:
    organization = OrganizationRecord(name=f"Organization {suffix}", slug=f"org-{suffix}-{uuid4().hex[:8]}")
    session.add(organization)
    session.flush()
    return organization


def test_project_lookup_is_organization_scoped(db_session):
    first = seed_organization(db_session, "first")
    second = seed_organization(db_session, "second")
    repository = ProjectRepository(db_session)
    project = repository.create(first.id, "PRJ-1", "Project One", "IDR")

    assert repository.get_scoped(first.id, project.id) == project
    assert repository.get_scoped(second.id, project.id) is None


def test_project_list_returns_only_organization_projects(db_session):
    first = seed_organization(db_session, "first")
    second = seed_organization(db_session, "second")
    repository = ProjectRepository(db_session)
    expected = repository.create(first.id, "PRJ-1", "Project One", "IDR")
    repository.create(second.id, "PRJ-2", "Project Two", "USD")

    assert repository.list_for_organization(first.id) == [expected]
