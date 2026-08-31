import os
import sys
from pathlib import Path
from uuid import UUID


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from starlette.types import ASGIApp, Receive, Scope, Send

from controlcheck.asgi import app as inner_app


def _register_import_routes() -> None:
    """Register upload routes only when the real FastAPI app is available.

    Vercel packaging tests intentionally import this module with a minimal
    controlcheck.asgi stub and Python's site packages disabled. Keeping the
    feature-specific dependencies lazy preserves that deployment contract.
    """
    if not hasattr(inner_app, "post"):
        return

    from fastapi import UploadFile

    from controlcheck.ingestion.preflight_validator import validate_workbook_bytes
    from controlcheck.limits import PUBLIC_BETA_MAX_UPLOAD_BYTES

    @inner_app.post("/v1/imports/preflight")
    async def import_preflight(file: UploadFile, preset: str = "standard"):
        if not file.filename:
            return {"error": {"code": "missing_filename", "message": "Filename is required."}}

        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > PUBLIC_BETA_MAX_UPLOAD_BYTES:
                return {
                    "error": {
                        "code": "file_too_large",
                        "message": "File exceeds the public beta upload limit.",
                    }
                }

        try:
            return validate_workbook_bytes(bytes(data), file.filename, preset=preset)
        except ValueError as exc:
            return {"error": {"code": "invalid_import_file", "message": str(exc)}}


def _register_account_repair_route() -> None:
    """Repair legacy users that exist without an organization membership.

    Older beta accounts may predate mandatory workspace creation. They can
    authenticate successfully but receive a token without ``org_id``, which
    makes the current frontend unable to enter a tenant-scoped workspace.
    This endpoint accepts that freshly-issued user token, creates a personal
    workspace only when one is missing, and returns a replacement token.
    """
    if not hasattr(inner_app, "post"):
        return

    from fastapi import Header, HTTPException
    from sqlalchemy import select

    from controlcheck.auth import create_access_token, create_refresh_token, decode_token
    from controlcheck.persistence.database import create_session_factory
    from controlcheck.persistence.models import OrganizationMemberRecord, OrganizationRecord, UserRecord

    database_url = (
        os.environ.get("CONTROLCHECK_DATABASE_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
    )
    if not database_url:
        return
    session_factory = create_session_factory(database_url)

    @inner_app.post("/v1/auth/ensure-workspace")
    def ensure_workspace(authorization: str | None = Header(None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Bearer token is required")

        try:
            payload = decode_token(authorization[7:].strip())
            user_id = UUID(str(payload.get("sub") or ""))
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Authentication token is invalid or expired") from exc

        with session_factory() as session:
            user = session.get(UserRecord, user_id)
            if user is None or user.status != "active":
                raise HTTPException(status_code=401, detail="Account is not active")

            membership = session.scalar(
                select(OrganizationMemberRecord).where(OrganizationMemberRecord.user_id == user.id)
            )
            if membership is None:
                slug = f"workspace-{user.id.hex}"
                organization = session.scalar(
                    select(OrganizationRecord).where(OrganizationRecord.slug == slug)
                )
                if organization is None:
                    display_name = (user.full_name or user.email.split("@", 1)[0] or "ControlCheck User").strip()
                    organization = OrganizationRecord(
                        name=f"{display_name} Workspace"[:200],
                        slug=slug,
                    )
                    session.add(organization)
                    session.flush()

                membership = OrganizationMemberRecord(
                    organization_id=organization.id,
                    user_id=user.id,
                    role="org_admin",
                )
                session.add(membership)
                session.flush()

            session.commit()
            access_token = create_access_token(
                user.id,
                user.email,
                organization_id=membership.organization_id,
                role=membership.role,
            )
            return {
                "access_token": access_token,
                "refresh_token": create_refresh_token(user.id),
            }


_register_import_routes()
_register_account_repair_route()


class StripApiPrefixASGI:
    """Strips /api prefix from request paths so FastAPI routes match cleanly."""

    def __init__(self, asgi_app: ASGIApp):
        self.app = asgi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            if path == "/api":
                scope = dict(scope)
                scope["path"] = "/health"
            elif path.startswith("/api/"):
                scope = dict(scope)
                stripped = path[4:]
                scope["path"] = stripped if stripped else "/"
        await self.app(scope, receive, send)


app = StripApiPrefixASGI(inner_app)
