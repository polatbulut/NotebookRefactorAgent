from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import nbformat

from ...llm.cache import LLMCache
from ...llm.factory import create_llm
from ...llm.json_utils import extract_json
from ...plan import FunctionSpec, Plan


def _read_prompt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        # Fallback system prompt that is stable enough if file missing
        return (
            "You are the **Planner Agent**. Return JSON with keys: "
            "modules, cell_map, configs, api, cli. Keep it compact and valid JSON."
        )


def _functions_from_cell_map(cell_map: Any, fallback_ids: list[int]) -> list[FunctionSpec]:
    """
    Accept both:
      - dict[str, dict{function: str}]
      - dict[str, str]
    If invalid or empty, fall back to default names for the given cell ids.
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
        # Keep a stable ordering by cell id
        out.sort(key=lambda fs: fs.cell_id)
        return out

    # Fallback: derive names from ids
    return [FunctionSpec(cell_id=i, fn_name=f"cell_{i}") for i in fallback_ids]


def planner_llm_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LLM-backed planner: summarizes the notebook and asks an LLM for a packaging plan.
    Produces a Plan and stores it on state["plan"].
    """
    provider = str(state.get("provider", "none"))
    model = str(state.get("model", "none"))
    temperature = float(state.get("temperature", 0.1))
    max_tokens = int(state.get("max_output_tokens", 2048))
    cache_dir = Path(str(state.get("cache_dir", ".cache/nra")))

    # Load notebook
    p = Path(str(state["input_nb"]))
    nb: Any = cast(Any, nbformat.read(str(p), as_version=4))

    # Summarize code cells minimally for the prompt
    cells: list[dict[str, Any]] = []
    idx = 0
    for c in nb.get("cells", []):
        if c.get("cell_type") != "code":
            continue
        src = c.get("source", "") or ""
        head = [ln for ln in src.splitlines()[:2]]
        cells.append(
            {
                "id": idx if "id" not in c else c.get("id", idx),
                "type": "code",
                "head": head,
                "lines": len(src.splitlines()),
            }
        )
        idx += 1

    # Build messages
    system_prompt_path = (
        Path(__file__).resolve().parents[2] / "prompts" / "planner_system_prompt.txt"
    )
    sp_text = _read_prompt(system_prompt_path)

    user_payload = {
        "summary": {"cells": cells},
        "style_guide": "simple single module, tests, minimal API",
    }

    messages = [
        {"role": "system", "content": sp_text},
        {"role": "user", "content": str(user_payload)},
    ]

    # Cache + LLM call
    cache = LLMCache(cache_dir)
    key_prompt = str({"sp": sp_text[:80], "payload": user_payload})  # small cache key
    cached = cache.get(provider, model, key_prompt)
    if cached:
        text, _meta = cached
    else:
        llm = create_llm(provider)
        text, meta = llm.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        cache.put(provider, model, key_prompt, text, meta)
        # accumulate usage
        calls = cast(list[dict[str, Any]], state.get("llm_calls", []) or [])
        calls.append(
            {
                "node": "planner",
                "provider": provider,
                "model": model,
                "meta": meta,
            }
        )
        state["llm_calls"] = calls

    obj = extract_json(text)

    # Resolve functions robustly from cell_map (string or dict values)
    cell_map = obj.get("cell_map", {})
    # Prepare fallback ids in source order
    fallback_ids: list[int] = []
    for c in cells:
        val: Any = c.get("id", None)
        if val is None:
            continue
        try:
            cid = int(str(val))
        except Exception:
            continue
        fallback_ids.append(cid)

    functions = _functions_from_cell_map(cell_map, fallback_ids)

    # Build Plan (with safe defaults if keys missing)
    plan = Plan(
        module_path=(
            obj.get("modules", {}).get("main", "src_pkg/module.py")
            if isinstance(obj.get("modules"), dict)
            else "src_pkg/module.py"
        ),
        tests_path=(
            obj.get("cli", {}).get("tests_path", "tests/test_module.py")
            if isinstance(obj.get("cli"), dict)
            else "tests/test_module.py"
        ),
        package_root=(
            obj.get("modules", {}).get("package_root", "src_pkg")
            if isinstance(obj.get("modules"), dict)
            else "src_pkg"
        ),
        functions=functions or [FunctionSpec(cell_id=i, fn_name=f"cell_{i}") for i in fallback_ids],
    )

    state["plan"] = plan
    return state
