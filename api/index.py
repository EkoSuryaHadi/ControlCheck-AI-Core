import sys
from pathlib import Path


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


_register_import_routes()


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
