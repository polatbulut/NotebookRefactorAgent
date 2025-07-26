from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

import nbformat


def refactor_node(state: dict[str, Any]) -> dict[str, Any]:
    input_nb = state["input_nb"]
    plan = state["plan"]
    nb: Any = cast(Any, nbformat.read(str(input_nb), as_version=4))

    def is_import_line(s: str) -> bool:
        t = s.strip()
        return t.startswith("import ") or t.startswith("from ")

    collected_imports: list[str] = []
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
        body_src = "\n".join(cell_body_lines)
        assigned: list[str] = []
        try:
            tree = ast.parse(body_src) if body_src else None
        except SyntaxError:
            tree = None
        if tree:
            for n in ast.walk(tree):
                if isinstance(n, ast.Assign):
                    for tgt in n.targets:
                        if isinstance(tgt, ast.Name) and tgt.id not in assigned:
                            assigned.append(tgt.id)
                        elif isinstance(tgt, ast.Tuple):
                            for e in tgt.elts:
                                if isinstance(e, ast.Name) and e.id not in assigned:
                                    assigned.append(e.id)
                elif isinstance(n, ast.AnnAssign):
                    tgt = n.target
                    if isinstance(tgt, ast.Name) and tgt.id not in assigned:
                        assigned.append(tgt.id)
                elif isinstance(n, ast.AugAssign):
                    tgt = n.target
                    if isinstance(tgt, ast.Name) and tgt.id not in assigned:
                        assigned.append(tgt.id)

        if len(assigned) == 0:
            ret_annot = "None"
        elif len(assigned) == 1:
            ret_annot = "object"
        else:
            ret_annot = "tuple[" + ", ".join(["object"] * len(assigned)) + "]"

        lines.append(f"def {fn}() -> {ret_annot}:")
        body_lines = [f"    {ln}" for ln in cell_body_lines if ln.strip() != ""]
        if len(assigned) > 0:
            if len(assigned) == 1:
                body_lines.append(f"    return {assigned[0]}")
            else:
                body_lines.append("    return " + ", ".join(assigned))
        if not body_lines:
            body_lines = ["    pass"]
        lines.extend(body_lines)
        lines.append("")

    files = {plan["module_path"]: "\n".join(lines) + "\n"}
    out_dir = Path(state["output_dir"]) / plan["package_root"]
    for path, content in files.items():
        fp = Path(state["output_dir"]) / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    (out_dir / "__init__.py").write_text("")
    return {"files": files}
