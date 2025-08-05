from __future__ import annotations

from .groq_client import GroqLLM
from .interfaces import LLMClient


def create_llm(provider: str) -> LLMClient:
    p = (provider or "none").lower()
    if p in ("none", "", "off"):
        raise RuntimeError("LLM usage requested but provider is 'none'")
    if p == "groq":
        return GroqLLM()
    raise RuntimeError(f"Unsupported LLM provider: {provider!r}")
