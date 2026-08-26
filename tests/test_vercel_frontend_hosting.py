from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_deployment_has_no_python_function_or_route() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert "functions" not in config
    assert all(route.get("dest") != "/api/index.py" for route in config["routes"])


def test_vercel_ignores_the_python_entrypoint(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "api").mkdir(parents=True)
    (bundle / ".gitignore").write_text(
        (ROOT / ".vercelignore").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (bundle / "api" / "index.py").write_text("app = object()\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet"], cwd=bundle, check=True)

    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "api/index.py"],
        cwd=bundle,
        check=False,
    )

    assert ignored.returncode == 0


def test_vercel_keeps_spa_fallback_after_static_files() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert config["routes"] == [
        {"handle": "filesystem"},
        {"src": "/(.*)", "dest": "/index.html"},
    ]
