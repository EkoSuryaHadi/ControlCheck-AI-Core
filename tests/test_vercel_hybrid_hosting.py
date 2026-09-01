from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _git_check_ignore(tmp_path: Path, paths: list[str]) -> set[str]:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / ".gitignore").write_text(
        (ROOT / ".vercelignore").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "--quiet"], cwd=bundle, check=True)
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=bundle,
        input="\n".join(paths),
        capture_output=True,
        text=True,
        check=False,
    )
    return set(result.stdout.splitlines())


def test_vercel_routes_api_before_spa_fallback() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert config["routes"] == [
        {"src": "/api/mpp-convert", "dest": "/api/mpp-convert.js"},
        {"src": "/api/(.*)", "dest": "/api/index.py"},
        {"handle": "filesystem"},
        {"src": "/(.*)", "dest": "/index.html"},
    ]
    assert "api/index.py" in config["functions"]
    assert "api/mpp-convert.js" in config["functions"]


def test_vercel_keeps_python_entrypoint_and_project_metadata(tmp_path: Path) -> None:
    ignored = _git_check_ignore(
        tmp_path,
        [
            "api/index.py",
            "api/mpp-convert.js",
            "pyproject.toml",
            "package.json",
            "data/controlcheck_rule_catalogue_v0.2.json",
        ],
    )

    assert ignored == set()
