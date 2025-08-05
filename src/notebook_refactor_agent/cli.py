from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

from omegaconf import OmegaConf
import typer

from .agent.graph import build_graph
from .tools.nb_inspector import summarize_notebook

app = typer.Typer(help="Notebook Refactor Agent")

# ---- B008-safe Typer option defaults (avoid calling typer.Option in signature) ----
TEMPERATURE_OPT = typer.Option(0.1, "--temperature")
MAX_TOKENS_OPT = typer.Option(2048, "--max-output-tokens")
CACHE_DIR_OPT = typer.Option(Path(".cache/nra"), "--cache-dir")

# ---- Typed decorator wrapper to keep mypy happy ----
F = TypeVar("F", bound=Callable[..., Any])


def typed_command(*dargs: Any, **dkwargs: Any) -> Callable[[F], F]:
    """A typed wrapper around app.command to avoid mypy 'Untyped decorator' errors."""

    def _decorator(fn: F) -> F:
        return cast(F, app.command(*dargs, **dkwargs)(fn))

    return _decorator


def _load_cfg() -> dict[str, Any]:
    p = Path("configs/default.yaml")
    if p.exists():
        try:
            obj: Any = OmegaConf.to_container(OmegaConf.load(str(p)), resolve=True)
            return cast(dict[str, Any], obj) if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


@typed_command(name="inspect")
def inspect_cmd(input_nb: Path) -> None:
    """Print a quick JSON-like summary of a notebook."""
    summary: Any = summarize_notebook(input_nb)
    typer.echo(summary)


@typed_command(name="refactor")
def refactor_cmd(
    input_nb: Path,
    output_dir: Path = Path("out_pkg"),
    mode: str = typer.Option("run-all", "--mode", help="run-all|functions|both"),
    safe: bool = typer.Option(True, "--safe/--no-safe"),
    timeout_secs: int = typer.Option(60, "--timeout"),
    provider: str = typer.Option("none", "--provider"),
    model: str = typer.Option("none", "--model"),
    temperature: float = TEMPERATURE_OPT,
    max_output_tokens: int = MAX_TOKENS_OPT,
    cache_dir: Path = CACHE_DIR_OPT,
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Refactor a notebook into a small package and tests, optionally using an LLM."""
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
        "provider": provider or str(cfg.get("provider", "none")),
        "model": model or str(cfg.get("model", "none")),
        "temperature": float(
            temperature if temperature is not None else cfg.get("temperature", 0.1)
        ),
        "max_output_tokens": int(
            max_output_tokens
            if max_output_tokens is not None
            else cfg.get("max_output_tokens", 2048)
        ),
        "cache_dir": str(
            cache_dir if cache_dir is not None else cfg.get("cache_dir", ".cache/nra")
        ),
    }

    final_state: dict[str, Any] = app_graph.invoke(state)

    report = final_state.get("report", "done")
    metrics = final_state.get("metrics", {}) or {}
    typer.echo(report)
    if verbose:
        plan = final_state.get("plan", {}) or {}
        module_rel = plan.get("module_path", "src_pkg/module.py")
        tests_rel = plan.get("tests_path", "tests/test_module.py")
        reports_dir = (Path(output_dir) / ".reports").resolve()
        typer.echo(f"Module:  {(Path(output_dir) / module_rel).resolve()}")
        typer.echo(f"Tests:   {(Path(output_dir) / tests_rel).resolve()}")
        typer.echo(f"Reports: {reports_dir}")
        index_path = reports_dir / "index.txt"
        if index_path.exists():
            typer.echo(f"Index:   {index_path.resolve()}")

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


if __name__ == "__main__":
    app()
