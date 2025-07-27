from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import typer
from omegaconf import OmegaConf

from .agent.graph import build_graph
from .tools.nb_inspector import summarize_notebook

app = typer.Typer(help="Notebook Refactor Agent")


def _load_cfg() -> dict[str, Any]:
    p = Path("configs/default.yaml")
    if p.exists():
        try:
            obj: Any = OmegaConf.to_container(OmegaConf.load(str(p)), resolve=True)
            if isinstance(obj, dict):
                return cast(dict[str, Any], obj)
            return {}
        except Exception:
            return {}
    return {}


def inspect_cmd(input_nb: Path) -> None:
    summary: Any = summarize_notebook(input_nb)
    typer.echo(summary)


def refactor_cmd(
    input_nb: Path,
    output_dir: Path = Path("out_pkg"),
    mode: str = typer.Option("run-all", "--mode", help="run-all|functions|both"),
    safe: bool = typer.Option(True, "--safe/--no-safe"),
    timeout_secs: int = typer.Option(60, "--timeout"),
    budget_usd: float = typer.Option(0.0, "--budget-usd"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    cfg = _load_cfg()
    app_graph = build_graph()
    state = {
        "input_nb": str(input_nb),
        "output_dir": str(output_dir),
        "mode": (mode or str(cfg.get("mode", "run-all"))),
        "safe": bool(safe if safe is not None else cfg.get("safe", True)),
        "timeout_secs": int(
            timeout_secs if timeout_secs is not None else cfg.get("timeout_secs", 60)
        ),
        "budget_usd": float(budget_usd),
        "dry_run": bool(dry_run),
    }
    final_state = app_graph.invoke(state)
    report = final_state.get("report", "done")
    metrics = final_state.get("metrics", {}) or {}
    typer.echo(report)
    if verbose:
        reports_dir = (output_dir / ".reports").resolve()
        typer.echo(f"Reports: {reports_dir}")
    fail = any(
        int(metrics.get(k, 0)) != 0
        for k in (
            "pytest_returncode",
            "ruff_returncode",
            "black_returncode",
            "mypy_returncode",
            "exec_returncode",
        )
    )
    raise typer.Exit(code=1 if fail else 0)


app.command(name="inspect")(inspect_cmd)
app.command(name="refactor")(refactor_cmd)

if __name__ == "__main__":
    app()
