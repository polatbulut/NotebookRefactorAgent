from __future__ import annotations

from pathlib import Path
from typing import Any

import nbformat


def summarize_notebook(path: str | Path) -> dict[str, Any]:
    """
    Return a simple, type-safe summary of a notebook:
    - cell types
    - first 3 lines of source
    - line counts
    """
    nb = nbformat.read(str(path), as_version=4)
    summary: dict[str, Any] = {"cells": []}
    for i, cell in enumerate(nb.cells):
        ctype = cell.get("cell_type")
        src: str = cell.get("source", "")
        summary["cells"].append(
            {
                "id": i,
                "type": ctype,
                "lines": len(src.splitlines()),
                "head": src.splitlines()[:3],
            }
        )
    return summary
