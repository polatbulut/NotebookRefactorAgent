from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, text=True)
    out, err = proc.communicate()
    return proc.returncode, out, err


def ruff_fix(path: Path) -> tuple[int, str, str]:
    return _run(["ruff", "check", str(path), "--fix"])


def black_fix(path: Path) -> tuple[int, str, str]:
    return _run(["black", str(path)])


def mypy_check(path: Path) -> tuple[int, str, str]:
    return _run(["mypy", str(path)])
