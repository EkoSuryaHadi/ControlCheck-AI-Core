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

from controlcheck.api import app

# Vercel looks for 'app' or 'handler'
handler = app
