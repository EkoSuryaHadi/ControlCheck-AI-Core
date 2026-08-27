import sys
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from starlette.types import ASGIApp, Receive, Scope, Send

from controlcheck.asgi import app as inner_app


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
