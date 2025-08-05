from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import nbformat

from ...llm.cache import LLMCache
from ...llm.factory import create_llm
from ...llm.json_utils import extract_json


def refactor_llm_node(state: dict[str, Any]) -> dict[str, Any]:
    """LLM-based code generator: create production-ready module from notebook fragments."""
    input_nb = Path(state["input_nb"])
    plan = state["plan"]
    nb: Any = cast(Any, nbformat.read(str(input_nb), as_version=4))

    # Collect original code fragments per planned function
    frags: dict[int, str] = {}
    for item in plan.get("functions", []):
        cid = int(item["cell_id"])
        src = str(nb.cells[cid].get("source", ""))
        frags[cid] = src

    system_prompt = Path(__file__).resolve().parents[2] / "prompts" / "refactor_system.txt"
    sp_text = (
        system_prompt.read_text()
        if system_prompt.exists()
        else (
            "You are the **Refactor Agent**. Return JSON of generated files: { 'path.py': 'content' }"
        )
    )

    user_payload = {"plan": plan, "fragments": frags}

    provider = str(state.get("provider", "none"))
    model = str(state.get("model", "none"))
    temperature = float(state.get("temperature", 0.1))
    max_tokens = int(state.get("max_output_tokens", 2048))
    cache_dir = Path(state.get("cache_dir", ".cache/nra"))

    cache = LLMCache(cache_dir / "refactor")
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

    files = extract_json(text)  # { "path/to/file.py": "content..." }

    # Materialize files
    for rel, content in files.items():
        fp = Path(state["output_dir"]) / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)

    # Record LLM usage
    calls = list(state.get("llm_calls", []))
    calls.append(
        {"node": "refactor", "provider": provider, "model": meta.get("model", model), "meta": meta}
    )

    return {"files": files, "llm_calls": calls}
