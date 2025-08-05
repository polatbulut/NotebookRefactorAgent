from __future__ import annotations

from pathlib import Path
from typing import Any

from ...llm.cache import LLMCache
from ...llm.factory import create_llm
from ...llm.json_utils import extract_json


def test_writer_llm_node(state: dict[str, Any]) -> dict[str, Any]:
    """LLM-based test writer: generate minimal pytest smoke tests for public API."""
    plan = state["plan"]
    files = state.get("files", {})

    system_prompt = Path(__file__).resolve().parents[2] / "prompts" / "test_writer_system.txt"
    sp_text = (
        system_prompt.read_text()
        if system_prompt.exists()
        else (
            "You are the **Test Writer Agent**. Return JSON of tests as { 'tests/test_xxx.py': 'content' }."
        )
    )

    user_payload = {"plan": plan, "files": list(files.keys())}

    provider = str(state.get("provider", "none"))
    model = str(state.get("model", "none"))
    temperature = float(state.get("temperature", 0.1))
    max_tokens = int(state.get("max_output_tokens", 2048))
    cache_dir = Path(state.get("cache_dir", ".cache/nra"))

    cache = LLMCache(cache_dir / "tests")
    key_prompt = f"{sp_text}\n{user_payload}"
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

    tests = extract_json(text)

    for rel, content in tests.items():
        fp = Path(state["output_dir"]) / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)

    calls = list(state.get("llm_calls", []))
    calls.append(
        {
            "node": "test-writer",
            "provider": provider,
            "model": meta.get("model", model),
            "meta": meta,
        }
    )

    return {"tests": tests, "llm_calls": calls}
