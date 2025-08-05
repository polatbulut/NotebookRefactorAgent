from __future__ import annotations

from .interfaces import LLMClient

# Keep a small registry just for help text / validation
_SUPPORTED: dict[str, list[str]] = {
    "none": [],
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.3-8b-instant",
    ],
}


def supported_models_help() -> str:
    parts: list[str] = []
    for prov, models in _SUPPORTED.items():
        parts.append(f"{prov}: {', '.join(models) if models else 'none'}")
    return " | ".join(parts)


def create_llm(provider: str) -> LLMClient:
    """Return an LLM client for the given provider.

    Import provider SDKs lazily so environments that don't use an LLM
    (e.g., CI eval runs) don't need optional dependencies installed.
    """
    prov = (provider or "none").strip().lower()
    if prov == "groq":
        # Lazy import to avoid requiring 'groq' unless actually used.
        from .groq_client import GroqLLM  # local import

        return GroqLLM()
    raise ValueError(f"Unsupported provider: {provider!r}")
