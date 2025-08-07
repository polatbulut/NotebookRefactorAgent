from __future__ import annotations

from dataclasses import dataclass
import json  # ← NEW
from pathlib import Path
from typing import Any, cast

import nbformat

from ...llm.cache import LLMCache
from ...llm.factory import create_llm
from ...llm.json_utils import extract_json


@dataclass
class FunctionSpec:
    cell_id: int
    fn_name: str


@dataclass
class Plan:
    module_path: str
    tests_path: str
    package_root: str
    functions: list[FunctionSpec]


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def _read_prompt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        # Fallback prompt if prompt-file is missing
        return (
            "You are the **Planner Agent**. "
            "Return JSON with keys: package_root, module_path, tests_path, "
            "cell_map – keep it compact and valid JSON."
        )


def _functions_from_cell_map(cell_map: Any, fallback_ids: list[int]) -> list[FunctionSpec]:
    """
    Accept either::

        {"0": {"function": "foo"}, "1": {"function": "bar"}}
        {"0": "foo", "1": "bar"}

    If empty / malformed, fall back to ``cell_i`` names.
    """
    out: list[FunctionSpec] = []

    if isinstance(cell_map, dict):
        for k, v in cell_map.items():
            try:
                cid = int(k)
            except Exception:
                continue

            if isinstance(v, dict):
                fn = cast(str | None, v.get("function")) or f"cell_{cid}"
            elif isinstance(v, str):
                fn = v or f"cell_{cid}"
            else:
                fn = f"cell_{cid}"

            out.append(FunctionSpec(cell_id=cid, fn_name=str(fn)))

    if out:
        out.sort(key=lambda fs: fs.cell_id)
        return out

    return [FunctionSpec(cell_id=i, fn_name=f"cell_{i}") for i in fallback_ids]


# --------------------------------------------------------------------------- #
# main node                                                                   #
# --------------------------------------------------------------------------- #
def planner_llm_node(state: dict[str, Any]) -> dict[str, Any]:
    provider = str(state.get("provider", "none"))
    model = str(state.get("model", "none"))
    temperature = float(state.get("temperature", 0.1))
    max_tokens = int(state.get("max_output_tokens", 2048))
    cache_dir = Path(str(state.get("cache_dir", ".cache/nra")))

    # 1. Read the notebook & make a light-weight summary of the code cells
    nb_path = Path(str(state["input_nb"]))
    nb: Any = cast(Any, nbformat.read(str(nb_path), as_version=4))

    cells_summary: list[dict[str, Any]] = []
    code_ord = 0
    for c in nb.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = str(c.get("source", "")) or ""
        head = [ln for ln in src.splitlines()[:2]]
        cells_summary.append(
            {
                "id": c.get("id", code_ord),
                "type": "code",
                "head": head,
                "lines": len(src.splitlines()),
            }
        )
        code_ord += 1

    # 2. Craft the messages for the LLM
    system_prompt = _read_prompt(
        Path(__file__).resolve().parents[2] / "prompts" / "planner_system_prompt.txt"
    )

    user_payload = {
        "summary": {"cells": cells_summary},
        "style_guide": (
            "Produce a single clean module + minimal tests. "
            "Return **valid JSON** ONLY – no markdown fences."
        ),
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, indent=2)},
    ]

    # 3. Call (or cache) the LLM
    cache = LLMCache(cache_dir)
    cache_key = json.dumps({"sp": system_prompt[:80], "payload": user_payload}, sort_keys=True)
    cached = cache.get(provider, model, cache_key)

    if cached:
        text, meta = cached
    else:
        llm = create_llm(provider)
        text, meta = llm.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        cache.put(provider, model, cache_key, text, meta)
        state.setdefault("llm_calls", []).append(
            {"node": "planner", "provider": provider, "model": model, "meta": meta}
        )

    # 4. Parse the JSON returned by the LLM -------------------------------- #
    obj = extract_json(text)
    cell_map = obj.get("cell_map", {})

    # ---------------------------------------------------------------------- #
    # We no longer assume the notebook cell IDs are integers.
    # Instead, build a mapping   uuid → ordinal_index   so we can translate
    # whatever the LLM sent back to positional indices if needed.
    uuid_to_ord: dict[str, int] = {
        str(cells_summary[i]["id"]): i for i in range(len(cells_summary))
    }

    def _uuid_list_to_ord(lst: list[str]) -> list[int]:
        out: list[int] = []
        for u in lst:
            if u in uuid_to_ord:
                out.append(uuid_to_ord[u])
        return out

    # Convert the cell_map (which may reference UUIDs) into FunctionSpecs
    functions: list[FunctionSpec] = []
    if isinstance(cell_map, dict):
        for logical_name, uuids in cell_map.items():
            if isinstance(uuids, list):
                for idx in _uuid_list_to_ord(uuids):
                    functions.append(FunctionSpec(cell_id=idx, fn_name=str(logical_name)))
    if not functions:
        # fallback: sequential cell_0 … cell_n
        functions = [
            FunctionSpec(cell_id=i, fn_name=f"cell_{i}")  # notebook order
            for i in range(len(cells_summary))
        ]

    # 5. Materialise the Plan ---------------------------------------------- #
    plan = Plan(
        module_path=str(obj.get("module_path", "src_pkg/module.py")),
        tests_path=str(obj.get("tests_path", "tests/test_module.py")),
        package_root=str(obj.get("package_root", "src_pkg")),
        functions=functions,
    )

    state["plan"] = plan
    return state
