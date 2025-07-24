from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from .tools.nb_inspector import summarize_notebook

app = typer.Typer(help="Notebook Refactor Agent")


@app.command()  # type: ignore[misc]  # Typer's decorator confuses mypy
def inspect(input_nb: Path) -> None:
    """Quickly summarize a notebook (cell types, imports, literals)."""
    summary: Any = summarize_notebook(input_nb)
    typer.echo(summary)


if __name__ == "__main__":
    app()
