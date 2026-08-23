import os
import sys
import traceback
from pathlib import Path
from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

# Set serverless upload directory to /tmp
os.environ["CONTROLCHECK_UPLOAD_ROOT"] = "/tmp/uploads"

root_dir = Path(__file__).resolve().parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Configure catalogue
catalogue_path = root_dir / "data" / "controlcheck_rule_catalogue_v0.2.json"
if catalogue_path.exists():
    os.environ["CONTROLCHECK_CATALOGUE"] = str(catalogue_path)

# Diagnostics of imports
import_status = {}

def test_imports():
    modules = [
        ("fastapi", "fastapi"),
        ("pydantic", "pydantic"),
        ("sqlalchemy", "sqlalchemy"),
        ("psycopg", "psycopg"),
        ("pandas", "pandas"),
        ("openpyxl", "openpyxl"),
        ("bcrypt", "bcrypt"),
        ("jwt", "jwt"),
    ]
    for name, mod in modules:
        try:
            __import__(mod)
            import_status[name] = "OK"
        except Exception as err:
            import_status[name] = f"ERROR: {err}"

test_imports()

try:
    from controlcheck.api import create_configured_app
    from controlcheck.actions_api import install_action_routes
    from controlcheck.governance_api import install_governance_routes
    from controlcheck.reports_api import install_report_routes
    inner_app = create_configured_app()
    install_action_routes(inner_app)
    install_governance_routes(inner_app)
    install_report_routes(inner_app)
    import_status["controlcheck_api"] = "OK"
    import_status["action_governance_api"] = "OK"
    import_status["approval_escalation_api"] = "OK"
    import_status["reports_api"] = "OK"
except Exception as e:
    err_tb = traceback.format_exc()
    import_status["controlcheck_api"] = f"ERROR: {e}\n{err_tb}"
    inner_app = FastAPI(title="ControlCheck Diagnostic API")


def database_configured() -> bool:
    return bool(
        os.environ.get("CONTROLCHECK_DATABASE_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
    )


# Direct health check endpoint
@inner_app.get("/health")
@inner_app.get("/api/health")
def health_endpoint():
    return {
        "status": "healthy",
        "service": "ControlCheck AI Serverless Engine",
        "platform": "Vercel",
        "imports": import_status,
        "catalogue_exists": catalogue_path.exists(),
        "db_configured": database_configured(),
    }

@inner_app.get("/diagnostic")
@inner_app.get("/api/diagnostic")
def diagnostic_endpoint():
    return {
        "python_version": sys.version,
        "sys_path": sys.path,
        "cwd": os.getcwd(),
        "import_status": import_status,
        "db_configured": database_configured(),
        "env_keys": [k for k in os.environ.keys() if "KEY" not in k and "SECRET" not in k and "PASS" not in k],
    }

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