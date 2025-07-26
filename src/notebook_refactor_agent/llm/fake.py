from __future__ import annotations

from typing import Any


class FakeLLM:
    def __init__(self, goldens: dict[str, str]) -> None:
        self.goldens: dict[str, str] = goldens

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        extra: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        prompt = messages[-1]["content"] if messages else ""
        return self.goldens.get(prompt, ""), {"tokens_prompt": 0, "tokens_completion": 0}
