import sys
from pathlib import Path
from starlette.types import ASGIApp, Receive, Scope, Send

root_dir = Path(__file__).resolve().parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from controlcheck.actions_api import install_action_routes
from controlcheck.api import create_configured_app
from controlcheck.governance_api import install_governance_routes
from controlcheck.reports_api import install_report_routes


inner_app = create_configured_app()
install_action_routes(inner_app)
install_governance_routes(inner_app)
install_report_routes(inner_app)

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
