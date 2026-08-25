from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_python_function_excludes_non_runtime_assets() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    excluded = config["functions"]["api/index.py"]["excludeFiles"]

    for pattern in (
        "frontend/**",
        "public/**",
        "src/controlcheck/web/**",
        "data/*.xlsx",
        "data/*.inspect.ndjson",
        "data/*expected_findings*.json",
    ):
        assert pattern in excluded


def test_vercel_bundle_keeps_python_project_metadata(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / ".gitignore").write_text(
        (ROOT / ".vercelignore").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (bundle / "pyproject.toml").write_text("[project]\nname = 'probe'\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet"], cwd=bundle, check=True)

    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "pyproject.toml"],
        cwd=bundle,
        check=False,
    )

    assert ignored.returncode == 1, (
        "pyproject.toml must reach Vercel so the local requirement can be built"
    )


def test_vercel_requirements_install_the_controlcheck_project(tmp_path: Path) -> None:
    requirements = {
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "." in requirements, (
        "Vercel installs requirements.txt for the Python function, so the local "
        "ControlCheck project must be included as a runtime requirement"
    )

    target = tmp_path / "runtime"
    subprocess.run(
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
        check=True,
        capture_output=True,
        text=True,
    )

    assert (target / "controlcheck" / "asgi.py").is_file()
