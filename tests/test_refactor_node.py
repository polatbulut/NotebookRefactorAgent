import importlib.util
from pathlib import Path
from types import ModuleType

import nbformat as nbf
from notebook_refactor_agent.agent.nodes.planner import planner_node
from notebook_refactor_agent.agent.nodes.refactor import refactor_node


def _make_nb(tmp_path: Path) -> Path:
    nb = nbf.v4.new_notebook()
    nb.cells = [
        nbf.v4.new_code_cell("x = 1\ny = 2"),
        nbf.v4.new_code_cell("def foo(a=1, *args, **kwargs):\n    b = a + 1\n    return b"),
    ]
    p = tmp_path / "in.ipynb"
    nbf.write(nb, str(p))
    return p


def _import_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_mod", str(path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_refactor_node_modes(tmp_path: Path) -> None:
    for mode in ("run-all", "functions", "both"):
        p = _make_nb(tmp_path)
        plan = planner_node({"input_nb": str(p)})["plan"]
        out_dir = tmp_path / f"out_pkg_{mode}"
        state = {"input_nb": str(p), "plan": plan, "output_dir": str(out_dir), "mode": mode}
        refactor_node(state)
        mod_path = out_dir / "src_pkg" / "module.py"
        assert mod_path.exists()
        m = _import_module(mod_path)
        if mode in ("run-all", "both"):
            assert hasattr(m, "run_all")
        if mode in ("functions", "both"):
            assert any(n.startswith("cell_") for n in dir(m))
