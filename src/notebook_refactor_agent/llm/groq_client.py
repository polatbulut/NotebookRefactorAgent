from __future__ import annotations

import os
from typing import Any

from groq import Groq

from .interfaces import LLMClient

# Aliases / deprecations guard.
# If Groq decommissions a model, map it here to a stable alternative.
_MODEL_ALIASES: dict[str, str] = {
    "llama-3.1-70b-versatile": "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant": "llama-3.3-8b-instant",
}


def _normalize_model(name: str) -> tuple[str, bool]:
    """Return (normalized_name, changed?)."""
    new = _MODEL_ALIASES.get(name, name)
    return new, (new != name)


class GroqLLM(LLMClient):
    """Thin Groq chat client wrapper with minimal, typed surface."""

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
        model_norm, _ = _normalize_model(model)
        resp = self.client.chat.completions.create(
            model=model_norm,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        meta = {
            "id": resp.id,
            "model": resp.model,
            "usage": {
                "prompt_tokens": int(getattr(resp.usage, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(resp.usage, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(resp.usage, "total_tokens", 0) or 0),
            },
        }
        return text, meta
