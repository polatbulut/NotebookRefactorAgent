from __future__ import annotations

from pathlib import Path
from typing import Any


def test_writer_node(state: dict[str, Any]) -> dict[str, Any]:
    plan = state["plan"]
    lines: list[str] = []
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("import importlib.util")
    lines.append("import pathlib")
    lines.append("import re")
    lines.append("")
    lines.append("def test_import_and_run() -> None:")
    lines.append("    root = pathlib.Path(__file__).resolve().parents[1]")
    lines.append(
        "    spec = importlib.util.spec_from_file_location('src_pkg.module', root / 'src_pkg' / 'module.py')"
    )
    lines.append("    assert spec is not None and spec.loader is not None")
    lines.append("    m = importlib.util.module_from_spec(spec)")
    lines.append("    spec.loader.exec_module(m)")
    lines.append("    fn = getattr(m, 'run_all', None)")
    lines.append("    if callable(fn):")
    lines.append("        fn()")
    lines.append("    else:")
    lines.append("        c = [getattr(m, a) for a in dir(m) if re.match(r'^cell_\\d+$', a)]")
    lines.append("        for f in c:")
    lines.append("            if callable(f):")
    lines.append("                f()")
    lines.append("")
    tests = {plan["tests_path"]: "\n".join(lines) + "\n"}
    for path, content in tests.items():
        fp = Path(state["output_dir"]) / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return {"tests": tests}
