from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _requirements(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_vercel_requirements_install_controlcheck_project() -> None:
    assert "." in _requirements(ROOT / "requirements.txt")


def test_vercel_excludes_non_runtime_assets() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    excluded = config["functions"]["api/index.py"]["excludeFiles"]

    for pattern in (
        "frontend/**",
        "tests/**",
        "docs/**",
        "validation/**",
        "build/**",
    ):
        assert pattern in excluded


def test_controlcheck_package_installs_into_isolated_target(tmp_path: Path) -> None:
    target = tmp_path / "runtime"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-build-isolation",
            "--target",
            str(target),
            ".",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (target / "controlcheck" / "asgi.py").is_file()
