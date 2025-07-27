from __future__ import annotations

import importlib.util
import pathlib
import re

def test_import_and_run() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('src_pkg.module', root / 'src_pkg' / 'module.py')
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    fn = getattr(m, 'run_all', None)
    if callable(fn):
        fn()
    else:
        c = [getattr(m, a) for a in dir(m) if re.match(r'^cell_\d+$', a)]
        for f in c:
            if callable(f):
                f()

