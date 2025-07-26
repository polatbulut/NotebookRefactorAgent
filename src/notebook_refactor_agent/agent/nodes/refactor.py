from __future__ import annotations

import ast
import re
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

    def annotate_def_line(line: str) -> tuple[str, bool]:
        s = line.lstrip()
        indent = line[: len(line) - len(s)]
        m = re.match(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*:\s*$", s)
        if not m:
            return line, False
        name, params = m.group(1), m.group(2)
        tokens = [p.strip() for p in params.split(",")] if params.strip() else []
        new_params: list[str] = []
        used_any = False
        for tok in tokens:
            if not tok:
                continue
            if ":" in tok:
                new_params.append(tok)
                continue
            if tok.startswith("**"):
                inner = tok[2:]
                if "=" in inner:
                    left, right = inner.split("=", 1)
                    new_params.append(f"**{left.strip()}: Any={right.strip()}")
                else:
                    new_params.append(f"**{inner.strip()}: Any")
                used_any = True
            elif tok.startswith("*"):
                inner = tok[1:]
                if inner == "":
                    new_params.append(tok)
                else:
                    if "=" in inner:
                        left, right = inner.split("=", 1)
                        new_params.append(f"*{left.strip()}: Any={right.strip()}")
                    else:
                        new_params.append(f"*{inner.strip()}: Any")
                    used_any = True
            else:
                if "=" in tok:
                    left, right = tok.split("=", 1)
                    new_params.append(f"{left.strip()}: Any={right.strip()}")
                else:
                    new_params.append(f"{tok}: Any")
                used_any = True
        return f"{indent}def {name}({', '.join(new_params)}) -> Any:", used_any

    collected_imports: list[str] = []
    body_lines_all: list[str] = []
    for item in plan["functions"]:
        cid = int(item["cell_id"])
        src = str(nb.cells[cid].get("source", ""))
        for ln in src.splitlines():
            if is_import_line(ln):
                collected_imports.append(ln.strip())
            elif ln.strip() != "":
                body_lines_all.append(ln)

    processed_body_lines: list[str] = []
    needs_any = False
    for ln in body_lines_all:
        nln, used_any = annotate_def_line(ln)
        if used_any:
            needs_any = True
        processed_body_lines.append(nln)

    body_src = "\n".join(processed_body_lines)

    assigned: list[str] = []
    if body_src:
        try:
            tree = ast.parse(body_src)
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

    lines: list[str] = ["from __future__ import annotations", ""]
    if needs_any:
        lines.extend(["from typing import Any", ""])
    if collected_imports:
        lines.extend(sorted(set(collected_imports)))
        lines.append("")
    lines.append(f"def run_all() -> {ret_annot}:")
    if body_src:
        lines.extend("    " + ln for ln in processed_body_lines)
        if len(assigned) == 1:
            lines.append(f"    return {assigned[0]}")
        elif len(assigned) > 1:
            lines.append("    return " + ", ".join(assigned))
    else:
        lines.append("    pass")
    lines.append("")

    files = {plan["module_path"]: "\n".join(lines) + "\n"}
    out_dir = Path(state["output_dir"]) / plan["package_root"]
    for path, content in files.items():
        fp = Path(state["output_dir"]) / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    (out_dir / "__init__.py").write_text("")
    return {"files": files}
