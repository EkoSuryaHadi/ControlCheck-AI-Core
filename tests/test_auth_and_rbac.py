from unittest.mock import MagicMock
from uuid import uuid4

from controlcheck.auth.passwords import hash_password, verify_password
from controlcheck.auth.rbac import can_edit_project, can_manage_organization, can_manage_project
from controlcheck.auth.tokens import create_access_token, create_refresh_token, decode_token
from controlcheck.persistence.models import UserRecord, OrganizationMemberRecord
from controlcheck.persistence.repositories import UserRepository


def test_password_hashing_and_verification():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_tokens_lifecycle():
    user_id = uuid4()
    org_id = uuid4()
    email = "admin@example.com"
    role = "org_admin"

    access_token = create_access_token(user_id, email, organization_id=org_id, role=role)
    payload = decode_token(access_token)

    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["org_id"] == str(org_id)
    assert payload["role"] == role
    assert payload["type"] == "access"

    refresh_token = create_refresh_token(user_id)
    refresh_payload = decode_token(refresh_token)

    assert refresh_payload["sub"] == str(user_id)
    assert refresh_payload["type"] == "refresh"


def test_rbac_permissions():
    assert can_manage_organization("org_admin") is True
    assert can_manage_organization("org_member") is False

    assert can_manage_project("org_admin") is True
    assert can_manage_project("project_manager") is True
    assert can_manage_project("project_viewer") is False

    assert can_edit_project("project_member") is True
    assert can_edit_project("project_viewer") is False


def test_user_repository_crud():
    mock_session = MagicMock()
    user_id = uuid4()
    org_id = uuid4()
    email = "test@example.com"
    pwd_hash = hash_password("secret123")

    repo = UserRepository(mock_session)

    user = repo.create_user(email=email, password_hash=pwd_hash, full_name="Test User")
    assert user.email == email
    assert user.status == "active"
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
