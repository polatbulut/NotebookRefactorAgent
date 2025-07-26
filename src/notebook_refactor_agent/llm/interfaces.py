from __future__ import annotations

from typing import Any, Protocol


class LLMClient(Protocol):
    def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        extra: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        pass
