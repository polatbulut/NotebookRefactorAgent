from __future__ import annotations

from .groq_client import GroqLLM
from .interfaces import LLMClient

# Central place to advertise supported models in CLI help / docs.
_SUPPORTED_MODELS: dict[str, list[str]] = {
    "groq": [
        "llama-3.3-70b-versatile",
        "llama-3.3-8b-instant",
    ],
}


def create_llm(provider: str) -> LLMClient:
    """Return an LLM client for the given provider."""
    p = (provider or "none").lower()
    if p == "groq":
        return GroqLLM()
    raise RuntimeError(
        f"Unknown provider: {provider!r}. Use one of: {', '.join(_SUPPORTED_MODELS)}"
    )


def supported_models_help() -> str:
    """Return a concise string for CLI --help describing supported models."""
    parts = []
    for prov, models in _SUPPORTED_MODELS.items():
        parts.append(f"{prov}: {', '.join(models)}")
    return "Supported models -> " + "; ".join(parts)


def list_supported_models() -> dict[str, list[str]]:
    """Programmatic access (e.g., future API)."""
    return dict(_SUPPORTED_MODELS)
