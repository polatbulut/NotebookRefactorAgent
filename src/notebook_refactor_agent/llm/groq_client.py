from __future__ import annotations

import os
from typing import Any

from groq import Groq

from .interfaces import LLMClient

# Model aliases to keep older names working
_MODEL_ALIASES: dict[str, str] = {
    "llama-3.1-70b-versatile": "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant": "llama-3.3-8b-instant",
}


def _normalize_model(name: str) -> tuple[str, bool]:
    """Return (normalized_name, changed?)."""
    new = _MODEL_ALIASES.get(name, name)
    return new, new != name


class GroqLLM(LLMClient):
    def __init__(self) -> None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        self.client = Groq(api_key=api_key)

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        extra: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        model_norm, changed = _normalize_model(model)

        resp = self.client.chat.completions.create(
            model=model_norm,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        text = resp.choices[0].message.content or ""
        meta: dict[str, Any] = {
            "id": getattr(resp, "id", ""),
            "model": getattr(resp, "model", model_norm),
            "usage": {
                "prompt_tokens": getattr(getattr(resp, "usage", None), "prompt_tokens", 0),
                "completion_tokens": getattr(getattr(resp, "usage", None), "completion_tokens", 0),
                "total_tokens": getattr(getattr(resp, "usage", None), "total_tokens", 0),
            },
        }
        if changed:
            meta["model_alias_from"] = model
            meta["model_alias_to"] = model_norm
        return text, meta
