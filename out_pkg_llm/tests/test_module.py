import importlib.util
import pathlib


def test_import_and_run() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    p = (root / pathlib.Path("src_pkg/module.py")).resolve()
    spec = importlib.util.spec_from_file_location("generated.module", p)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    fn = getattr(m, "run_all", None)
    if callable(fn):
        fn()
