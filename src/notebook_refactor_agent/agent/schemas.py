from __future__ import annotations

from pydantic import BaseModel


class FunctionSpec(BaseModel):
    cell_id: int
    fn_name: str


class Plan(BaseModel):
    module_path: str
    tests_path: str
    package_root: str
    functions: list[FunctionSpec]
