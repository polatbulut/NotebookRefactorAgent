from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import nbformat


def refactor_node(state: dict[str, Any]) -> dict[str, Any]:
    input_nb = state["input_nb"]
    plan = state["plan"]
    nb: Any = cast(Any, nbformat.read(str(input_nb), as_version=4))

    collected_imports: list[str] = []

    def is_import_line(s: str) -> bool:
        t = s.strip()
        return t.startswith("import ") or t.startswith("from ")

    lines: list[str] = ["from __future__ import annotations", ""]
    for item in plan["functions"]:
        cid = int(item["cell_id"])
        src = str(nb.cells[cid].get("source", ""))
        for ln in src.splitlines():
            if is_import_line(ln):
                collected_imports.append(ln.strip())
    if collected_imports:
        unique_imports = sorted(set(collected_imports))
        lines.extend(unique_imports)
        lines.append("")

    for item in plan["functions"]:
        cid = int(item["cell_id"])
        fn = str(item["fn_name"])
        src = str(nb.cells[cid].get("source", ""))
        cell_body_lines = [ln for ln in src.splitlines() if not is_import_line(ln)]
        body_lines = [f"    {ln}" for ln in cell_body_lines if ln.strip() != ""]
        body = "\n".join(body_lines) if body_lines else "    pass"
        lines.append(f"def {fn}() -> None:")
        lines.append(body)
        lines.append("")

    files = {plan["module_path"]: "\n".join(lines) + "\n"}
    out_dir = Path(state["output_dir"]) / plan["package_root"]
    for path, content in files.items():
        fp = Path(state["output_dir"]) / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    (out_dir / "__init__.py").write_text("")
    return {"files": files}
