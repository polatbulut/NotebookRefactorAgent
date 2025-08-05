from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import nbformat

from ...llm.cache import LLMCache
from ...llm.factory import create_llm
from ...llm.json_utils import extract_json
from ..schemas import FunctionSpec, Plan


def planner_llm_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LLM-backed planner. Produces a Plan from a notebook summary.
    """
    p = Path(state["input_nb"])
    nb: dict[str, Any] = cast(dict[str, Any], nbformat.read(str(p), as_version=4))
    provider = str(state.get("provider", "groq"))
    model = str(state.get("model", "llama-3.3-70b-versatile"))
    temperature = float(state.get("temperature", 0.1))
    max_tokens = int(state.get("max_output_tokens", 2048))
    cache_dir = Path(state.get("cache_dir", ".cache/nra"))

    # Build a minimal summary of code cells for the prompt
    cells_summary: list[dict[str, Any]] = []
    for i, c in enumerate(nb["cells"]):
        ctype = c.get("cell_type")
        if ctype != "code":
            continue
        src = str(c.get("source", ""))
        cells_summary.append(
            {
                "id": i,
                "type": ctype,
                "head": src.splitlines()[:3],
                "lines": len(src.splitlines()),
            }
        )

    # Also keep explicit indices for a robust fallback
    code_cells: list[int] = [i for i, c in enumerate(nb["cells"]) if c.get("cell_type") == "code"]

    # Prompts
    system_prompt = Path(Path(__file__).resolve().parents[2] / "prompts" / "planner.md").read_text(
        encoding="utf-8"
    )
    user_payload = {
        "summary": {"cells": cells_summary},
        "style_guide": "simple single module, tests, minimal API",
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload)},
    ]

    # Cache key is the user content (summary+style guide)
    key_prompt = messages[-1]["content"]
    cache = LLMCache(root=cache_dir)
    cached = cache.get(provider, model, key_prompt)
    if cached:
        text, _meta = cached
    else:
        llm = create_llm(provider)
        text, meta = llm.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        cache.put(provider, model, key_prompt, text, meta)

    obj = extract_json(text)

    # Build function specs from cell_map if present
    functions: list[FunctionSpec] = []
    cell_map: dict[str, Any] | list[Any] | None = (
        obj.get("cell_map") if isinstance(obj, dict) else None
    )
    if isinstance(cell_map, dict):
        for k, v in cell_map.items():
            try:
                cid = int(k)
            except Exception:
                continue
            v = v or {}
            fn = str(v.get("function", f"cell_{cid}"))
            functions.append(FunctionSpec(cell_id=cid, fn_name=fn))

    plan = Plan(
        module_path=(
            obj.get("modules", {}).get("main", "src_pkg/module.py")
            if isinstance(obj.get("modules", {}), dict)
            else "src_pkg/module.py"
        ),
        tests_path=(
            obj.get("cli", {}).get("tests_path", "tests/test_module.py")
            if isinstance(obj.get("cli", {}), dict)
            else "tests/test_module.py"
        ),
        package_root=(
            obj.get("modules", {}).get("package_root", "src_pkg")
            if isinstance(obj.get("modules", {}), dict)
            else "src_pkg"
        ),
        functions=(
            functions
            if functions
            else [FunctionSpec(cell_id=i, fn_name=f"cell_{i}") for i in code_cells]
        ),
    )
    return {"plan": plan.model_dump()}
