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
    """LLM-based planner: proposes mapping of cells → functions/files."""
    p = Path(state["input_nb"])
    nb: Any = cast(Any, nbformat.read(str(p), as_version=4))

    # Summarize cells for the prompt
    cells: list[dict[str, Any]] = []
    for idx, c in enumerate(nb.cells):
        if c.get("cell_type") != "code":
            continue
        src: str = c.get("source", "")
        head = src.splitlines()[:3]
        cells.append({"id": idx, "type": "code", "head": head, "lines": len(src.splitlines())})

    # System prompt
    system_prompt = Path(__file__).resolve().parents[2] / "prompts" / "planner_system.txt"
    sp_text = (
        system_prompt.read_text()
        if system_prompt.exists()
        else "You are the **Planner Agent**. Return JSON with keys: modules, cell_map, configs, api, cli."
    )

    user_payload = {
        "summary": {"cells": cells},
        "style_guide": "simple single module, tests, minimal API",
    }

    provider = str(state.get("provider", "none"))
    model = str(state.get("model", "none"))
    temperature = float(state.get("temperature", 0.1))
    max_tokens = int(state.get("max_output_tokens", 2048))
    cache_dir = Path(state.get("cache_dir", ".cache/nra"))

    # Cache
    cache = LLMCache(cache_dir / "planner")
    key_prompt = json.dumps({"sp": sp_text, "user": user_payload}, ensure_ascii=False)
    cached = cache.get(provider, model, key_prompt)

    if cached:
        text, meta = cached
    else:
        messages = [
            {"role": "system", "content": sp_text},
            {"role": "user", "content": str(user_payload)},
        ]
        llm = create_llm(provider)
        text, meta = llm.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        cache.put(provider, model, key_prompt, text, meta)

    obj = extract_json(text)
    # Default to all code cells if no mapping is provided
    cell_map = cast(dict[str, dict[str, str]], obj.get("cell_map", {}))
    functions: list[FunctionSpec] = []
    if cell_map:
        for k, v in cell_map.items():
            try:
                cid = int(k)
            except Exception:
                continue
            fn = v.get("function") or f"cell_{cid}"
            functions.append(FunctionSpec(cell_id=cid, fn_name=fn))
    else:
        # fallback: keep original ordering of code cells
        code_cells: list[int] = [cast(int, c["id"]) for c in cells]
        functions = [FunctionSpec(cell_id=cid, fn_name=f"cell_{cid}") for cid in code_cells]

    plan = Plan(
        module_path=obj.get("modules", {}).get("main", "src_pkg/module.py"),
        tests_path=obj.get("cli", {}).get("tests_path", "tests/test_module.py"),
        package_root=obj.get("modules", {}).get("package_root", "src_pkg"),
        functions=functions,
    )

    # Record LLM usage for later reporting
    calls = list(state.get("llm_calls", []))
    calls.append(
        {
            "node": "planner",
            "provider": provider,
            "model": meta.get("model", model),
            "meta": meta,
        }
    )

    return {"plan": plan.model_dump(), "llm_calls": calls}
