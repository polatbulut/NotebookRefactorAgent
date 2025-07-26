from __future__ import annotations

from typing import Any, TypedDict, cast

from langgraph.graph import END, StateGraph

from .nodes.critic import critic_node
from .nodes.planner import planner_node
from .nodes.refactor import refactor_node
from .nodes.writer_node import test_writer_node


class State(TypedDict, total=False):
    input_nb: str
    output_dir: str
    mode: str
    safe: bool
    timeout_secs: int
    plan: dict[str, Any]
    files: dict[str, str]
    tests: dict[str, str]
    metrics: dict[str, Any]
    report: str


def build_graph() -> Any:
    g = StateGraph(State)
    g.add_node("planner", cast(Any, planner_node))
    g.add_node("refactor", cast(Any, refactor_node))
    g.add_node("test_writer", cast(Any, test_writer_node))
    g.add_node("critic", cast(Any, critic_node))
    g.set_entry_point("planner")
    g.add_edge("planner", "refactor")
    g.add_edge("refactor", "test_writer")
    g.add_edge("test_writer", "critic")
    g.add_edge("critic", END)
    return g.compile()
