from __future__ import annotations

import secrets
from collections.abc import Callable

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .api_models import TenantContext
from .errors import ControlCheckApplicationError
from .settings import ApplicationSettings


_bearer = HTTPBearer(auto_error=False)


def _authenticate(
    settings: ApplicationSettings,
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    expected = settings.api_key
    supplied = credentials.credentials if credentials is not None else None
    if (
        not settings.is_production
        or (
            expected is not None
            and supplied is not None
            and secrets.compare_digest(supplied, expected)
        )
    ):
        return
    raise ControlCheckApplicationError(
        "authentication_required", "Authentication is required", 401
    )


def build_access_dependency(settings: ApplicationSettings) -> Callable[..., None]:
    def require_access(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> None:
        _authenticate(settings, credentials)

    return require_access


def build_tenant_dependency(
    settings: ApplicationSettings,
) -> Callable[..., TenantContext]:
    def require_tenant(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        x_organization_id: str | None = Header(None),
    ) -> TenantContext:
        _authenticate(settings, credentials)
        if settings.is_production:
            if settings.organization_id is None:  # Protected by settings validation.
                raise RuntimeError("Production organization is not configured")
            return TenantContext(organization_id=settings.organization_id)

        if x_organization_id is None:
            raise ControlCheckApplicationError(
                "missing_tenant_context", "X-Organization-ID is required", 400
            )
        try:
            return TenantContext(organization_id=x_organization_id)
        except ValueError as exc:
            raise ControlCheckApplicationError(
                "invalid_tenant_context", "X-Organization-ID must be a UUID", 400
            ) from exc

    return require_tenant
