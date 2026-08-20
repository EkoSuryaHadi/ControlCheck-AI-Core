from __future__ import annotations

from enum import Enum


class OrgRole(str, Enum):
    ORG_ADMIN = "org_admin"
    ORG_MEMBER = "org_member"
    ORG_VIEWER = "org_viewer"


class ProjectRole(str, Enum):
    PROJECT_MANAGER = "project_manager"
    PROJECT_MEMBER = "project_member"
    PROJECT_VIEWER = "project_viewer"


def can_manage_organization(role: str) -> bool:
    return role == OrgRole.ORG_ADMIN.value


def can_edit_project(role: str) -> bool:
    return role in {
        OrgRole.ORG_ADMIN.value,
        ProjectRole.PROJECT_MANAGER.value,
        ProjectRole.PROJECT_MEMBER.value,
    }


def can_manage_project(role: str) -> bool:
    return role in {
        OrgRole.ORG_ADMIN.value,
        ProjectRole.PROJECT_MANAGER.value,
    }
