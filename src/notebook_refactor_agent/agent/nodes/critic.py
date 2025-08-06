from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType
from typing import Any

try:
    import resource as _resource

    res: ModuleType | None = _resource
except Exception:
    res = None

from ...plan import Plan


def _run(cmd: list[str], cwd: Path) -> dict[str, Any]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return {"returncode": p.returncode, "stdout": p.stdout or "", "stderr": p.stderr or ""}


def _get_plan_value(plan: Any, key: str, default: str) -> str:
    """Return a plan field from a Plan dataclass or dict, with a default."""
    if isinstance(plan, Plan):
        val = getattr(plan, key, None)
        return str(val) if val else default
    if isinstance(plan, dict):
        return str(plan.get(key, default))
    return default


def _safe_exec(
    out_dir: Path,
    timeout_secs: int,
    safe: bool,
    module_rel: str = "src_pkg/module.py",
    mem_mb: int = 512,
) -> dict[str, Any]:
    env = os.environ.copy()
    if safe:
        # Remove proxy env vars and signal "no network" to any cooperating code
        for k in list(env.keys()):
            lk = k.lower()
            if lk.endswith("_proxy") or lk in ("http_proxy", "https_proxy", "no_proxy"):
                env.pop(k, None)
        env["NO_NETWORK"] = "1"

    # Script imports the generated module (relative to out_dir) and calls run_all() if present.
    script = (
        "import importlib.util, pathlib\n"
        f"p = (pathlib.Path({module_rel!r})).resolve()\n"
        "spec = importlib.util.spec_from_file_location('generated.module', p)\n"
        "assert spec and spec.loader\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "fn = getattr(m, 'run_all', None)\n"
        "fn() if callable(fn) else None\n"
    )

    def _limits() -> None:
        if res is None:
            return
        try:
            cpu = max(1, int(timeout_secs))
            res.setrlimit(res.RLIMIT_CPU, (cpu, cpu))
        except Exception:
            pass
        try:
            if hasattr(res, "RLIMIT_AS"):
                mem = int(mem_mb) * 1024 * 1024
                res.setrlimit(res.RLIMIT_AS, (mem, mem))
        except Exception:
            pass

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", script],
            cwd=out_dir,
            capture_output=True,
            text=True,
            timeout=timeout_secs,
            env=env,
            preexec_fn=_limits if safe and res is not None else None,
        )
        dt = time.monotonic() - t0
        return {
            "returncode": proc.returncode,
            "seconds": dt,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except subprocess.TimeoutExpired:
        dt = time.monotonic() - t0
        return {"returncode": 124, "seconds": dt, "stdout": "", "stderr": ""}


def critic_node(state: dict[str, Any]) -> dict[str, Any]:
    out = Path(state["output_dir"])
    reports = out / ".reports"
    reports.mkdir(parents=True, exist_ok=True)  # also ensures `out` exists

    # Read plan (dataclass or dict) and resolve paths for reporting & execution.
    plan_any: Any = state.get("plan", {})
    module_rel = _get_plan_value(plan_any, "module_path", "src_pkg/module.py")
    tests_rel = _get_plan_value(plan_any, "tests_path", "tests/test_module.py")

    # Run tools relative to the output dir; pass "." (not the absolute out path).
    r_pytest = _run(["pytest", "-q", "tests"], cwd=out)
    r_ruff = _run(["ruff", "check", "."], cwd=out)
    r_black = _run(["black", "--check", "."], cwd=out)
    r_mypy = _run(["mypy", "."], cwd=out)

    timeout_secs = int(state.get("timeout_secs", 60))
    safe = bool(state.get("safe", True))
    r_exec = _safe_exec(out, timeout_secs, safe, module_rel=module_rel)

    # Write tool outputs
    (reports / "pytest.txt").write_text(r_pytest["stdout"] + r_pytest["stderr"])
    (reports / "ruff.txt").write_text(r_ruff["stdout"] + r_ruff["stderr"])
    (reports / "black.txt").write_text(r_black["stdout"] + r_black["stderr"])
    (reports / "mypy.txt").write_text(r_mypy["stdout"] + r_mypy["stderr"])
    (reports / "exec.txt").write_text(
        str(r_exec.get("seconds", 0.0)) + "\n" + r_exec["stdout"] + r_exec["stderr"]
    )

    # Metrics + JSON report
    metrics = {
        "pytest_returncode": int(r_pytest["returncode"]),
        "ruff_returncode": int(r_ruff["returncode"]),
        "black_returncode": int(r_black["returncode"]),
        "mypy_returncode": int(r_mypy["returncode"]),
        "exec_returncode": int(r_exec["returncode"]),
        "exec_seconds": float(r_exec.get("seconds", 0.0)),
        "exec_stdout_len": len(r_exec.get("stdout", "")),
        "exec_stderr_len": len(r_exec.get("stderr", "")),
    }
    report = (
        f"pytest={metrics['pytest_returncode']} ruff={metrics['ruff_returncode']} "
        f"black={metrics['black_returncode']} mypy={metrics['mypy_returncode']} "
        f"exec={metrics['exec_returncode']} secs={metrics['exec_seconds']:.2f}"
    )
    (reports / "report.json").write_text(
        json.dumps({"metrics": metrics, "report": report}, indent=2)
    )

    # Human-friendly index
    base = out.resolve()
    lines: list[str] = []
    lines.append("Notebook Refactor Agent Report")
    lines.append("")
    lines.append(f"Summary: {report}")
    lines.append("")
    lines.append("Generated")
    lines.append(f"- module: {(base / module_rel).resolve()}")
    lines.append(f"- tests:  {(base / tests_rel).resolve()}")
    lines.append("")
    lines.append("Reports")
    lines.append(f"- pytest: {(reports / 'pytest.txt').resolve()}")
    lines.append(f"- ruff:   {(reports / 'ruff.txt').resolve()}")
    lines.append(f"- black:  {(reports / 'black.txt').resolve()}")
    lines.append(f"- mypy:   {(reports / 'mypy.txt').resolve()}")
    lines.append(f"- exec:   {(reports / 'exec.txt').resolve()}")
    lines.append(f"- json:   {(reports / 'report.json').resolve()}")
    lines.append("")
    (reports / "index.txt").write_text("\n".join(lines) + "\n")

    return {"metrics": metrics, "report": report}
