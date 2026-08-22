import os
import sys
from pathlib import Path

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
    from controlcheck.api import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI(title="ControlCheck Core API (Fallback)")
    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def fallback_handler(path_name: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "serverless_initialization_error",
                "message": str(e),
                "hint": "Check DATABASE_URL environment variable format in Vercel settings."
            }
        )

# Vercel ASGI handler
handler = app
