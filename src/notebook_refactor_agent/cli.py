from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from .agent.graph import build_graph
from .tools.nb_inspector import summarize_notebook

app = typer.Typer(help="Notebook Refactor Agent")


def inspect_cmd(input_nb: Path) -> None:
    summary: Any = summarize_notebook(input_nb)
    typer.echo(summary)


def refactor_cmd(input_nb: Path, output_dir: Path = Path("out_pkg")) -> None:
    app_graph = build_graph()
    state = {"input_nb": str(input_nb), "output_dir": str(output_dir)}
    final_state = app_graph.invoke(state)
    typer.echo(final_state.get("report", "done"))


app.command(name="inspect")(inspect_cmd)
app.command(name="refactor")(refactor_cmd)

if __name__ == "__main__":
    app()
