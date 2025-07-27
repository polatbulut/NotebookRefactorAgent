from pathlib import Path

import nbformat as nbf
from notebook_refactor_agent.agent.nodes.planner import planner_node


def _make_nb(tmp_path: Path, cells: list[str]) -> Path:
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_code_cell(c) for c in cells]
    p = tmp_path / "in.ipynb"
    nbf.write(nb, str(p))
    return p


def test_planner_node_smoke(tmp_path: Path) -> None:
    p = _make_nb(tmp_path, ["x=1", "y=2"])
    out = planner_node({"input_nb": str(p)})
    assert "plan" in out
    plan = out["plan"]
    assert plan["module_path"].endswith("src_pkg/module.py")
    assert plan["tests_path"].endswith("tests/test_module.py")
    assert plan["package_root"] == "src_pkg"
    fns = {int(f["cell_id"]) for f in plan["functions"]}
    assert fns == {0, 1}
