from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FunctionSpec:
    cell_id: int
    fn_name: str


@dataclass(slots=True)
class Plan:
    module_path: str | None = None
    tests_path: str | None = None
    package_root: str | None = None
    functions: list[FunctionSpec] = field(default_factory=list)
