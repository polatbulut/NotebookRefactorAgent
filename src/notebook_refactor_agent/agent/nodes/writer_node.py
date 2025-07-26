from __future__ import annotations

from pathlib import Path
from typing import Any


def test_writer_node(state: dict[str, Any]) -> dict[str, Any]:
    plan = state["plan"]
    lines = []
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("import importlib.util")
    lines.append("import pathlib")
    lines.append("")
    lines.append("def test_import() -> None:")
    lines.append("    root = pathlib.Path(__file__).resolve().parents[1]")
    lines.append(
        "    spec = importlib.util.spec_from_file_location('src_pkg.module', root / 'src_pkg' / 'module.py')"
    )
    lines.append("    assert spec is not None and spec.loader is not None")
    lines.append("    m = importlib.util.module_from_spec(spec)")
    lines.append("    spec.loader.exec_module(m)")
    lines.append("")
    tests = {plan["tests_path"]: "\n".join(lines) + "\n"}
    for path, content in tests.items():
        fp = Path(state["output_dir"]) / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return {"tests": tests}
