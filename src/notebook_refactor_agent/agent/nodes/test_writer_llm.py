from __future__ import annotations

from pathlib import Path
from typing import Any

from ...llm.cache import LLMCache
from ...llm.factory import create_llm
from ...llm.json_utils import extract_json
from .writer_node import test_writer_node as writer_fallback


def test_writer_llm_node(state: dict[str, Any]) -> dict[str, Any]:
    provider = str(state.get("provider", "none"))
    model = str(state.get("model", "llama-3.1-70b-versatile"))
    temperature = float(state.get("temperature", 0.1))
    max_tokens = int(state.get("max_output_tokens", 2048))
    cache_dir = Path(state.get("cache_dir", ".cache/nra"))
    cache = LLMCache(cache_dir)

    plan = state["plan"]
    with open(Path(__file__).resolve().parents[2] / "prompts" / "test_writer.md") as f:
        system_prompt = f.read().strip()

    user_payload = {"plan": plan}
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": str(user_payload)},
    ]

    key_prompt = messages[-1]["content"]
    cached = cache.get(provider, model, key_prompt)
    if cached:
        text, _meta = cached
    else:
        llm = create_llm(provider)
        text, meta = llm.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        cache.put(provider, model, key_prompt, text, meta)

    tests = extract_json(text)
    if not tests:
        return writer_fallback(state)

    for rel, content in tests.items():
        p = Path(state["output_dir"]) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if isinstance(content, str) else str(content))
    return {"tests": tests}
