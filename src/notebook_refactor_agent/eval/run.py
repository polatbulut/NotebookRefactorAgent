from __future__ import annotations
import argparse
import ast
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from ..agent.graph import build_graph


def _run(cmd: List[str], cwd: Path | None = None) -> Tuple[int, str, str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, text=True)
    out, err = p.communicate()
    return p.returncode, out, err


def _count_functions(py_file: Path) -> int:
    if not py_file.exists():
        return 0
    tree = ast.parse(py_file.read_text())
    return sum(isinstance(n, ast.FunctionDef) for n in ast.walk(tree))


def _print_table(rows: List[Dict[str, Any]]) -> None:
    headers = ["case", "pass", "secs", "pytest", "ruff", "black", "mypy", "funcs", "files"]
    widths = {h: len(h) for h in headers}
    for r in rows:
        widths["case"] = max(widths["case"], len(str(r["case"])))
        widths["pass"] = max(widths["pass"], len("✅" if r["pass"] else "❌"))
        widths["secs"] = max(widths["secs"], len(f'{r["secs"]:.2f}'))
        for k in ["pytest", "ruff", "black", "mypy", "funcs", "files"]:
            widths[k] = max(widths[k], len(str(r[k])))
    line = "  ".join(h.ljust(widths[h]) for h in headers)
    print(line)
    print("-" * len(line))
    for r in rows:
        vals = [
            str(r["case"]).ljust(widths["case"]),
            ("✅" if r["pass"] else "❌").ljust(widths["pass"]),
            f'{r["secs"]:.2f}'.ljust(widths["secs"]),
            str(r["pytest"]).ljust(widths["pytest"]),
            str(r["ruff"]).ljust(widths["ruff"]),
            str(r["black"]).ljust(widths["black"]),
            str(r["mypy"]).ljust(widths["mypy"]),
            str(r["funcs"]).ljust(widths["funcs"]),
            str(r["files"]).ljust(widths["files"]),
        ]
        print("  ".join(vals))


def _evaluate(accept: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
    ok = True
    if "pytest_returncode" in accept:
        ok = ok and metrics.get("pytest_returncode", 1) == int(accept["pytest_returncode"])
    if "ruff_ok" in accept:
        ok = ok and (metrics.get("ruff_returncode", 1) == 0) == bool(accept["ruff_ok"])
    if "black_ok" in accept:
        ok = ok and (metrics.get("black_returncode", 1) == 0) == bool(accept["black_ok"])
    if "mypy_ok" in accept:
        ok = ok and (metrics.get("mypy_returncode", 1) == 0) == bool(accept["mypy_ok"])
    if "min_functions" in accept:
        ok = ok and metrics.get("function_count", 0) >= int(accept["min_functions"])
    return ok


def run_suite(suite_path: Path) -> int:
    cfg = yaml.safe_load(suite_path.read_text())
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = Path(cfg.get("run_root", "eval_runs")) / ts
    base.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"run_root": str(base), "cases": []}
    for case in cfg.get("cases", []):
        case_id = str(case["id"])
        nb_path = Path(case["input"])
        out_dir = base / case_id
        t0 = time.monotonic()
        app = build_graph()
        state = {"input_nb": str(nb_path), "output_dir": str(out_dir)}
        app.invoke(state)

        _run(["black", str(out_dir)])
        _run(["ruff", "check", str(out_dir), "--fix"])

        pytest_rc, _, _ = _run(["pytest", "-q", str(out_dir / "tests")])
        ruff_rc, _, _ = _run(["ruff", "check", str(out_dir)])
        black_rc, _, _ = _run(["black", "--check", str(out_dir)])
        mypy_rc, _, _ = _run(["mypy", str(out_dir)])

        mod_path = out_dir / "src_pkg" / "module.py"
        fn_count = _count_functions(mod_path)
        py_files = list(out_dir.rglob("*.py"))
        dt = time.monotonic() - t0

        metrics = {
            "pytest_returncode": pytest_rc,
            "ruff_returncode": ruff_rc,
            "black_returncode": black_rc,
            "mypy_returncode": mypy_rc,
            "function_count": fn_count,
            "file_count": len(py_files),
            "seconds": dt,
        }
        passed = _evaluate(case.get("acceptance", {}), metrics)
        rows.append(
            {
                "case": case_id,
                "pass": passed,
                "secs": dt,
                "pytest": pytest_rc,
                "ruff": ruff_rc,
                "black": black_rc,
                "mypy": mypy_rc,
                "funcs": fn_count,
                "files": len(py_files),
            }
        )
        summary["cases"].append({"id": case_id, "metrics": metrics, "passed": passed})

    (base / "summary.json").write_text(json.dumps(summary, indent=2))
    with (base / "summary.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "pass", "seconds", "pytest_rc", "ruff_rc", "black_rc", "mypy_rc", "function_count", "file_count"])
        for r in rows:
            w.writerow([r["case"], r["pass"], f'{r["secs"]:.3f}', r["pytest"], r["ruff"], r["black"], r["mypy"], r["funcs"], r["files"]])
    _print_table(rows)
    return 0 if all(r["pass"] for r in rows) else 1


def main() -> None:
    import sys
    p = argparse.ArgumentParser()
    p.add_argument("suite", nargs="?", default="eval/suite.yaml")
    args = p.parse_args()
    rc = run_suite(Path(args.suite))
    sys.exit(rc)


if __name__ == "__main__":
    main()
