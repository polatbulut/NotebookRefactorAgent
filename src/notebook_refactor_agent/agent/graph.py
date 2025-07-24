from __future__ import annotations

from typing import Any, TypedDict


class State(TypedDict, total=False):
    nb_summary: dict[str, Any]
    plan: dict[str, Any]
    files: dict[str, str]
    tests: dict[str, str]
    metrics: dict[str, Any]
    report: str


def build_graph() -> None:
    """
    Stub for V1:
    - Create LangGraph nodes: planner, refactor, config_extractor, test_writer, quality, critic
    - Wire them together and return the compiled graph/app.

    For now, we keep this as a placeholder so mypy is happy.
    """
    raise NotImplementedError("Wire the LangGraph in V1")
