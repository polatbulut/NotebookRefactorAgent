import json
from pathlib import Path

import nbformat as nbf
import notebook_refactor_agent.agent.nodes.writer_node as writer_node
from notebook_refactor_agent.agent.nodes.critic import critic_node
from notebook_refactor_agent.agent.nodes.planner import planner_node
from notebook_refactor_agent.agent.nodes.refactor import refactor_node


def _make_nb(tmp_path: Path) -> Path:
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_code_cell("x = 1\ny = 2\nprint(x+y)")]
    p = tmp_path / "in.ipynb"
    nbf.write(nb, str(p))
    return p


def test_critic_reports(tmp_path: Path) -> None:
    p = _make_nb(tmp_path)
    plan = planner_node({"input_nb": str(p)})["plan"]
    out_dir = tmp_path / "out_pkg"
    refactor_node({"input_nb": str(p), "plan": plan, "output_dir": str(out_dir), "mode": "both"})
    writer_node.test_writer_node({"plan": plan, "output_dir": str(out_dir)})
    res = critic_node({"output_dir": str(out_dir), "timeout_secs": 5, "safe": True})
    reports = out_dir / ".reports"
    assert (reports / "index.txt").exists()
    data = json.loads((reports / "report.json").read_text())
    assert "metrics" in data
    assert res["metrics"]["pytest_returncode"] == 0
