from __future__ import annotations

from typing import Any, TypedDict, cast

from langgraph.graph import END, StateGraph

from .nodes.critic import critic_node
from .nodes.planner import planner_node
from .nodes.planner_llm import planner_llm_node
from .nodes.refactor import refactor_node
from .nodes.refactor_llm import refactor_llm_node
from .nodes.test_writer_llm import test_writer_llm_node
from .nodes.writer_node import test_writer_node


class State(TypedDict, total=False):
    input_nb: str
    output_dir: str
    mode: str
    safe: bool
    timeout_secs: int
    provider: str
    model: str
    temperature: float
    max_output_tokens: int
    cache_dir: str

    plan: dict[str, Any]
    files: dict[str, str]
    tests: dict[str, str]
    metrics: dict[str, Any]
    report: str


def _use_llm(state: dict[str, Any]) -> bool:
    p = (state.get("provider") or "").strip().lower()
    return p not in ("", "none", "off")


def _planner_dispatch(state: dict[str, Any]) -> dict[str, Any]:
    return planner_llm_node(state) if _use_llm(state) else planner_node(state)


def _refactor_dispatch(state: dict[str, Any]) -> dict[str, Any]:
    return refactor_llm_node(state) if _use_llm(state) else refactor_node(state)


def _test_writer_dispatch(state: dict[str, Any]) -> dict[str, Any]:
    return test_writer_llm_node(state) if _use_llm(state) else test_writer_node(state)


def build_graph() -> Any:
    g = StateGraph(State)
    g.add_node("planner", cast(Any, _planner_dispatch))
    g.add_node("refactor", cast(Any, _refactor_dispatch))
    g.add_node("test_writer", cast(Any, _test_writer_dispatch))
    g.add_node("critic", cast(Any, critic_node))
    g.set_entry_point("planner")
    g.add_edge("planner", "refactor")
    g.add_edge("refactor", "test_writer")
    g.add_edge("test_writer", "critic")
    g.add_edge("critic", END)
    return g.compile()
