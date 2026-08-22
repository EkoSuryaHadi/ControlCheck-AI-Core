import os
import sys
import traceback
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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
    app = create_configured_app()
    import_status["controlcheck_api"] = "OK"
except Exception as e:
    err_tb = traceback.format_exc()
    import_status["controlcheck_api"] = f"ERROR: {e}\n{err_tb}"
    
    app = FastAPI(title="ControlCheck Diagnostic API")

# Add health & diagnostic routes to whatever app is active
@app.get("/api/health")
@app.get("/health")
def health_endpoint():
    return {
        "status": "healthy",
        "service": "ControlCheck AI Serverless",
        "platform": "Vercel",
        "imports": import_status,
        "catalogue_exists": catalogue_path.exists(),
        "db_configured": bool(os.environ.get("DATABASE_URL")),
    }

@app.get("/api/diagnostic")
def diagnostic_endpoint():
    return {
        "python_version": sys.version,
        "sys_path": sys.path,
        "cwd": os.getcwd(),
        "import_status": import_status,
        "env_keys": [k for k in os.environ.keys() if "KEY" not in k and "SECRET" not in k and "PASS" not in k],
    }
