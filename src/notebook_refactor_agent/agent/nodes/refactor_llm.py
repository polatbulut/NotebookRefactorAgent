from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import nbformat

from ...llm.cache import LLMCache
from ...llm.factory import create_llm
from ...llm.json_utils import extract_json


def refactor_llm_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LLM-backed refactor. Produces files from notebook fragments and a plan.
    """
    input_nb = Path(state["input_nb"])
    plan = state["plan"]
    nb: Any = cast(Any, nbformat.read(str(input_nb), as_version=4))

    provider = str(state.get("provider", "groq"))
    model = str(state.get("model", "llama-3.3-70b-versatile"))
    temperature = float(state.get("temperature", 0.1))
    max_tokens = int(state.get("max_output_tokens", 2048))
    cache_dir = Path(state.get("cache_dir", ".cache/nra"))

    # Gather original code cells as fragments
    fragments: dict[int, str] = {}
    for i, c in enumerate(nb["cells"]):
        if c.get("cell_type") == "code":
            fragments[i] = str(c.get("source", ""))

    system_prompt = Path(Path(__file__).resolve().parents[2] / "prompts" / "refactor.md").read_text(
        encoding="utf-8"
    )
    user_payload = {"plan": plan, "fragments": fragments}

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload)},
    ]

    key_prompt = messages[-1]["content"]
    cache = LLMCache(root=cache_dir)
    cached = cache.get(provider, model, key_prompt)
    if cached:
        text, _meta = cached
    else:
        llm = create_llm(provider)
        text, meta = llm.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        cache.put(provider, model, key_prompt, text, meta)

    files_map = extract_json(text)
    if not isinstance(files_map, dict):
        files_map = {}

    # Write files under output_dir and ensure package root has __init__.py
    output_dir = Path(state["output_dir"])
    for rel, content in files_map.items():
        fp = output_dir / str(rel)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(str(content))

    pkg_root = Path(plan.get("package_root", "src_pkg"))
    (output_dir / pkg_root / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / pkg_root / "__init__.py").write_text("")

    return {"files": {str(k): str(v) for k, v in files_map.items()}}
