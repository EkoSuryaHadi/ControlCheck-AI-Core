from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
