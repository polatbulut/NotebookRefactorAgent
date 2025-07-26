from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RunState(BaseModel):
    input_nb: str
    output_dir: str
    plan: dict[str, Any] | None = None
    files: dict[str, str] | None = None
    tests: dict[str, str] | None = None
    metrics: dict[str, Any] | None = None
    report: str | None = None
