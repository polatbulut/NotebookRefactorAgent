from __future__ import annotations

import json
import re
from typing import Any


def _load_obj_maybe_dict(s: str) -> dict[str, Any]:
    try:
        obj = json.loads(s)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def extract_json(text: str) -> dict[str, Any]:
    """
    Extract the first JSON object from raw LLM text, allowing for ```json fences.
    Always returns a dict (empty on failure).
    """
    if not text:
        return {}

    # Prefer fenced blocks: ```json { ... } ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if m:
        return _load_obj_maybe_dict(m.group(1))

    # Fallback: first object-looking region
    m2 = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if m2:
        return _load_obj_maybe_dict(m2.group(1))

    # Last resort: try direct parse; else {}
    return _load_obj_maybe_dict(text)
