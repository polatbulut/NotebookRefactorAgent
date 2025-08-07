from __future__ import annotations

from pathlib import Path
import re
import textwrap
from typing import Any, cast

import nbformat

from ...llm.factory import create_llm
from ...llm.json_utils import extract_json
from ...plan import FunctionSpec, Plan

# --------------------------------------------------------------------------- #
# weak-JSON fallback – makes best-effort to salvage ``files`` blocks that     #
# the LLM returned with unescaped new-lines                                   #
# --------------------------------------------------------------------------- #
_FILE_PAIR_RE = re.compile(r'"\s*([^"]+?)\s*"\s*:\s*"\s*(.*?)\s*"', re.DOTALL)


def _fallback_parse_files(raw: str) -> dict[str, str]:
    """
    Extract ``"files": { "path": "code", ... }`` even when the string values
    aren't valid JSON strings (because of unescaped new-lines, quotes, …).

    We look for the first `"files": { ... }` block and then greedily
    capture `"path": "code"` pairs.
    """
    out: dict[str, str] = {}

    m = re.search(r'"files"\s*:\s*{(.*?)}', raw, re.DOTALL)
    if not m:
        return out

    content = m.group(1)
    for g in _FILE_PAIR_RE.finditer(content):
        path, code = g.groups()
        # De-indent & normalise line endings a tad
        out[path.strip()] = textwrap.dedent(code.replace("\\n", "\n"))

    return out


# --------------------------------------------------------------------------- #
# node                                                                        #
# --------------------------------------------------------------------------- #
def refactor_llm_node(state: dict[str, Any]) -> dict[str, Any]:
    nb_path = Path(str(state["input_nb"]))
    nb: Any = cast(Any, nbformat.read(str(nb_path), as_version=4))

    plan: Plan = cast(Plan, state["plan"])
    functions: list[FunctionSpec] = plan.functions

    # Map ordinal code-cells to nb indices
    code_cell_indices = [i for i, c in enumerate(nb.cells) if c.get("cell_type") == "code"]

    frags: dict[int, str] = {}
    for spec in functions:
        cid = int(spec.cell_id)
        nb_idx = code_cell_indices[cid] if cid < len(code_cell_indices) else cid
        if 0 <= nb_idx < len(nb.cells):
            frags[cid] = str(nb.cells[nb_idx].get("source", ""))

    # ------------------------------------------------------------------ #
    provider = str(state.get("provider", ""))
    model = str(state.get("model", ""))
    temperature = float(state.get("temperature", 0.1))
    max_tokens = int(state.get("max_output_tokens", 4096))

    user_msg = (
        "Re-organise the following notebook cell fragments into a clean package.\n"
        "Respond **only** with JSON having keys: package_root, module_path, "
        "tests_path, files (dict of path→code – escape with \\n so it's valid JSON).\n\n"
        + "\n".join(
            f"### {spec.fn_name} (cell {spec.cell_id})\n{frags.get(spec.cell_id, '')}"
            for spec in functions
        )
    )

    llm = create_llm(provider)
    text, meta = llm.chat(
        [
            {"role": "system", "content": "You are the **Refactor Agent**."},
            {"role": "user", "content": user_msg},
        ],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    obj = extract_json(text)
    files: dict[str, str] = cast(dict[str, str], obj.get("files", {}))

    # If we still have nothing, try weak parser before giving up
    if not files:
        files = _fallback_parse_files(text)

    if not files:
        raise RuntimeError(
            "LLM did not return any parsable `files`.\n\n"
            f"First 1 kB of raw response:\n{text[:1024]}"
        )

    # ------------------------------------------------------------------ #
    # 1. Resolve target paths
    package_root = str(obj.get("package_root", plan.package_root))
    module_path = str(obj.get("module_path", plan.module_path))
    tests_path = str(obj.get("tests_path", plan.tests_path))

    # 2. Persist the files
    out_dir = Path(state["output_dir"])
    for rel, content in files.items():
        p = (out_dir / rel).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    # 3. Record artefacts & bookkeeping
    state.setdefault("artifacts", {}).update(
        {"package_root": package_root, "module_path": module_path, "tests_path": tests_path}
    )
    state.setdefault("llm_calls", []).append(
        {"node": "refactor", "provider": provider, "model": model, "meta": meta}
    )

    state["report"] = f"Refactor completed – wrote {len(files)} file(s)."
    return state
