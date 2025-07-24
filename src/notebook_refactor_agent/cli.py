from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from .tools.nb_inspector import summarize_notebook

app = typer.Typer(help="Notebook Refactor Agent")


def inspect_cmd(input_nb: Path) -> None:
    """Quickly summarize a notebook (cell types, imports, literals)."""
    summary: Any = summarize_notebook(input_nb)
    typer.echo(summary)


# Register after definition to avoid mypy's "untyped decorator" error
app.command()(inspect_cmd)

if __name__ == "__main__":
    app()
