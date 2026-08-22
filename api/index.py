import os
import sys
import traceback
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Ensure src directory is in sys.path for serverless execution
root_dir = Path(__file__).resolve().parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Configure catalogue default path if not set
if "CONTROLCHECK_CATALOGUE" not in os.environ:
    catalogue_path = root_dir / "data" / "controlcheck_rule_catalogue_v0.2.json"
    if catalogue_path.exists():
        os.environ["CONTROLCHECK_CATALOGUE"] = str(catalogue_path)

# Set serverless upload directory to /tmp
if "CONTROLCHECK_UPLOAD_ROOT" not in os.environ:
    os.environ["CONTROLCHECK_UPLOAD_ROOT"] = "/tmp/uploads"

try:
    from controlcheck.api import create_configured_app
    app = create_configured_app()

    # Support /api/health and /health directly
    @app.get("/api/health")
    @app.get("/health")
    def health_check():
        return {
            "status": "healthy",
            "service": "ControlCheck AI Serverless Engine",
            "platform": "Vercel",
            "db_configured": bool(os.environ.get("DATABASE_URL"))
        }

except Exception as e:
    err_tb = traceback.format_exc()
    app = FastAPI(title="ControlCheck Core API (Recovery Mode)")
    
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def recovery_fallback(full_path: str, request: Request):
        return JSONResponse(
            status_code=200,
            content={
                "status": "initialization_error",
                "error": "serverless_initialization_error",
                "message": str(e),
                "traceback": err_tb.split("\n"),
                "path": full_path,
                "hint": "Check DATABASE_URL environment variable."
            }
        )
