from __future__ import annotations

from pathlib import Path
from typing import Any

from notebook_refactor_agent.tools.nb_inspector import summarize_notebook


def test_summarize_notebook_runs(tmp_path: Path) -> None:
    nb_content = """{
      "cells": [{"cell_type": "code", "source": "x = 1", "metadata": {}, "outputs": []}],
      "metadata": {},
      "nbformat": 4,
      "nbformat_minor": 2
    }"""
    nb_path = tmp_path / "tiny.ipynb"
    nb_path.write_text(nb_content)
    s: dict[str, Any] = summarize_notebook(nb_path)
    assert "cells" in s
    assert s["cells"][0]["type"] == "code"
