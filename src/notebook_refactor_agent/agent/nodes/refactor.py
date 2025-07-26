from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import nbformat


def refactor_node(state: dict[str, Any]) -> dict[str, Any]:
    input_nb = state["input_nb"]
    plan = state["plan"]
    nb: Any = cast(Any, nbformat.read(str(input_nb), as_version=4))
    lines = ["from __future__ import annotations", ""]
    for item in plan["functions"]:
        cid = int(item["cell_id"])
        fn = str(item["fn_name"])
        src = nb.cells[cid].get("source", "")
        body = (
            "\n".join(
                f"    {line}" if str(line).strip() else "    pass" for line in str(src).splitlines()
            )
            or "    pass"
        )
        lines.append(f"def {fn}() -> None:")
        lines.append(body if body.strip() else "    pass")
        lines.append("")
    files = {plan["module_path"]: "\n".join(lines) + "\n"}
    out_dir = Path(state["output_dir"]) / plan["package_root"]
    for path, content in files.items():
        fp = Path(state["output_dir"]) / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    (out_dir / "__init__.py").write_text("")
    return {"files": files}
