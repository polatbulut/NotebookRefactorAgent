from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import nbformat


def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    p = Path(state["input_nb"])
    nb: Any = cast(Any, nbformat.read(str(p), as_version=4))
    code_cells: list[int] = [i for i, c in enumerate(nb.cells) if c.cell_type == "code"]
    plan = {
        "module_path": "src_pkg/module.py",
        "functions": [{"cell_id": i, "fn_name": f"cell_{i}"} for i in code_cells],
        "tests_path": "tests/test_module.py",
        "package_root": "src_pkg",
    }
    return {"plan": plan}
