from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Any

import jwt

DEFAULT_SECRET_KEY = os.environ.get("CONTROLCHECK_JWT_SECRET", "controlcheck-jwt-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


def create_access_token(
    user_id: UUID,
    email: str,
    organization_id: UUID | None = None,
    role: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if organization_id:
        payload["org_id"] = str(organization_id)
    if role:
        payload["role"] = role
    return jwt.encode(payload, DEFAULT_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, DEFAULT_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decodes and validates a JWT token."""
    return jwt.decode(token, DEFAULT_SECRET_KEY, algorithms=[ALGORITHM])
