"""Read a ControlCheck workbook for the artifact-tool workbook builder.

This helper is intentionally read-only. Workbook authoring and export remain in
``build_validation_workbooks.mjs`` through ``@oai/artifact-tool``.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from controlcheck.loader import load_workbook


if len(sys.argv) != 2:
    raise SystemExit("usage: export_dataset_json.py WORKBOOK.xlsx")

dataset = load_workbook(Path(sys.argv[1]))
print(dataset.model_dump_json())

