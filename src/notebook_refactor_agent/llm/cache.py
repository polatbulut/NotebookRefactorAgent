from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class LLMCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _key(self, provider: str, model: str, prompt: str) -> Path:
        h = hashlib.sha256(f"{provider}|{model}|{prompt}".encode()).hexdigest()
        return self.root / f"{h}.json"

    def get(self, provider: str, model: str, prompt: str) -> tuple[str, dict[str, Any]] | None:
        p = self._key(provider, model, prompt)
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        return d["text"], d["meta"]

    def put(self, provider: str, model: str, prompt: str, text: str, meta: dict[str, Any]) -> None:
        p = self._key(provider, model, prompt)
        p.write_text(json.dumps({"text": text, "meta": meta}, indent=2))
