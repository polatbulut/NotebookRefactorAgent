from __future__ import annotations

import ast
from pathlib import Path
import re
from typing import Any, cast

import nbformat


def refactor_node(state: dict[str, Any]) -> dict[str, Any]:
    input_nb = state["input_nb"]
    plan = state["plan"]
    mode = str(state.get("mode", "run-all"))
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
    cell_bodies: list[list[str]] = []
    needs_any = False
    for item in plan["functions"]:
        cid = int(item["cell_id"])
        src = str(nb.cells[cid].get("source", ""))
        body_lines: list[str] = []
        for ln in src.splitlines():
            if is_import_line(ln):
                collected_imports.append(ln.strip())
            elif ln.strip() != "":
                nln, used_any = annotate_def_line(ln)
                if used_any:
                    needs_any = True
                body_lines.append(nln)
        cell_bodies.append(body_lines)

    def assigned_names(lines: list[str]) -> list[str]:
        if not lines:
            return []
        try:
            tree = ast.parse("\n".join(lines))
        except SyntaxError:
            return []
        out: list[str] = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign):
                for tgt in n.targets:
                    if isinstance(tgt, ast.Name) and tgt.id not in out:
                        out.append(tgt.id)
                    elif isinstance(tgt, ast.Tuple):
                        for e in tgt.elts:
                            if isinstance(e, ast.Name) and e.id not in out:
                                out.append(e.id)
            elif isinstance(n, ast.AnnAssign):
                tgt = n.target
                if isinstance(tgt, ast.Name) and tgt.id not in out:
                    out.append(tgt.id)
            elif isinstance(n, ast.AugAssign):
                tgt = n.target
                if isinstance(tgt, ast.Name) and tgt.id not in out:
                    out.append(tgt.id)
        return out

    lines: list[str] = ["from __future__ import annotations", ""]
    if needs_any:
        lines.extend(["from typing import Any", ""])
    if collected_imports:
        lines.extend(sorted(set(collected_imports)))
        lines.append("")

    if mode in ("functions", "both"):
        for idx, body in enumerate(cell_bodies):
            names = assigned_names(body)
            if len(names) == 0:
                ret_annot = "None"
            elif len(names) == 1:
                ret_annot = "object"
            else:
                ret_annot = "tuple[" + ", ".join(["object"] * len(names)) + "]"
            lines.append(f"def cell_{idx}() -> {ret_annot}:")
            if body:
                lines.extend("    " + ln for ln in body)
                if len(names) == 1:
                    lines.append(f"    return {names[0]}")
                elif len(names) > 1:
                    lines.append("    return " + ", ".join(names))
            else:
                lines.append("    pass")
            lines.append("")

    if mode in ("run-all", "both"):
        flat_body = [ln for body in cell_bodies for ln in body]
        names_all = assigned_names(flat_body)
        if len(names_all) == 0:
            ret_annot = "None"
        elif len(names_all) == 1:
            ret_annot = "object"
        else:
            ret_annot = "tuple[" + ", ".join(["object"] * len(names_all)) + "]"
        lines.append(f"def run_all() -> {ret_annot}:")
        if mode == "run-all":
            if flat_body:
                lines.extend("    " + ln for ln in flat_body)
                if len(names_all) == 1:
                    lines.append(f"    return {names_all[0]}")
                elif len(names_all) > 1:
                    lines.append("    return " + ", ".join(names_all))
            else:
                lines.append("    pass")
        else:
            for idx in range(len(cell_bodies)):
                lines.append(f"    cell_{idx}()")
        lines.append("")

    files = {plan["module_path"]: "\n".join(lines) + "\n"}
    out_dir = Path(state["output_dir"]) / plan["package_root"]
    for path, content in files.items():
        fp = Path(state["output_dir"]) / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    (out_dir / "__init__.py").write_text("")
    return {"files": files}
