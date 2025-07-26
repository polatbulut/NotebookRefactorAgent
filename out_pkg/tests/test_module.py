from __future__ import annotations

import importlib.util
import pathlib


def test_import() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("src_pkg.module", root / "src_pkg" / "module.py")
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
