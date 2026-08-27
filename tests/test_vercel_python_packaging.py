from __future__ import annotations

import json
import shutil
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


def test_vercel_entrypoint_imports_controlcheck_from_bundled_src(tmp_path: Path) -> None:
    """The function must boot when Vercel exposes the repository, not its build env."""
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    shutil.copy2(ROOT / "api" / "index.py", api_dir / "index.py")

    starlette_dir = api_dir / "starlette"
    starlette_dir.mkdir()
    (starlette_dir / "__init__.py").write_text("", encoding="utf-8")
    (starlette_dir / "types.py").write_text(
        "ASGIApp = Receive = Scope = Send = object\n",
        encoding="utf-8",
    )

    package_dir = tmp_path / "src" / "controlcheck"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "asgi.py").write_text("app = object()\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-S", "-c", "import index; assert index.app is not None"],
        cwd=api_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
