from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

from omegaconf import OmegaConf
import typer

from .agent.graph import build_graph
from .llm.factory import supported_models_help
from .tools.nb_inspector import summarize_notebook

app = typer.Typer(help="Notebook Refactor Agent")

# Sub-typer for config utilities
config_app = typer.Typer(help="Configuration commands")
app.add_typer(config_app, name="config")

# ---- B008-safe Typer option defaults (avoid calling typer.Option in signature) ----
TEMPERATURE_OPT = typer.Option(0.1, "--temperature")
MAX_TOKENS_OPT = typer.Option(2048, "--max-output-tokens")
CACHE_DIR_OPT = typer.Option(Path(".cache/nra"), "--cache-dir")

# ---- Typed decorator wrappers to keep mypy happy ----
F = TypeVar("F", bound=Callable[..., Any])


def typed_command(*dargs: Any, **dkwargs: Any) -> Callable[[F], F]:
    """A typed wrapper around app.command to avoid mypy 'Untyped decorator' errors."""
    dec = app.command(*dargs, **dkwargs)  # registers the command when called

    def _decorator(fn: F) -> F:
        dec(fn)  # register for side-effect; Typer returns an object we don't need
        return fn  # return the original function to preserve type F

    return _decorator


def typed_command_for(app_obj: typer.Typer, *dargs: Any, **dkwargs: Any) -> Callable[[F], F]:
    """Same as typed_command, but for a provided Typer instance (e.g., subcommands)."""
    dec = app_obj.command(*dargs, **dkwargs)

    def _decorator(fn: F) -> F:
        dec(fn)
        return fn

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


def _plan_value(plan: Any, key: str, default: str) -> str:
    """Return a plan field from Plan dataclass or dict, with a default."""
    if isinstance(plan, dict):
        return str(plan.get(key, default))
    try:
        val = getattr(plan, key, None)
        return str(val) if val else default
    except Exception:
        return default


def _tokens_from_meta(meta: dict[str, Any]) -> tuple[int, int, int]:
    """Return (prompt, completion, total) tokens from a provider meta payload."""
    usage = cast(dict[str, Any], meta.get("usage", {}) or {})
    pt = int(usage.get("prompt_tokens", usage.get("tokens_prompt", 0)) or 0)
    ct = int(usage.get("completion_tokens", usage.get("tokens_completion", 0)) or 0)
    tt = int(usage.get("total_tokens", pt + ct) or (pt + ct))
    return pt, ct, tt


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
    provider: str = typer.Option("none", "--provider", help="LLM provider, e.g. 'groq' or 'none'"),
    model: str = typer.Option("none", "--model", help=supported_models_help()),
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
        plan_any: Any = final_state.get("plan", None)
        module_rel = _plan_value(plan_any, "module_path", "src_pkg/module.py")
        tests_rel = _plan_value(plan_any, "tests_path", "tests/test_module.py")
        reports_dir = (Path(output_dir) / ".reports").resolve()
        typer.echo(f"Module:  {(Path(output_dir) / module_rel).resolve()}")
        typer.echo(f"Tests:   {(Path(output_dir) / tests_rel).resolve()}")
        typer.echo(f"Reports: {reports_dir}")
        index_path = reports_dir / "index.txt"
        if index_path.exists():
            typer.echo(f"Index:   {index_path.resolve()}")

        # LLM token summary (if any)
        calls = cast(list[dict[str, Any]], final_state.get("llm_calls", []) or [])
        if calls:
            total_pt = total_ct = total_tt = 0
            typer.echo("\nLLM usage:")
            for c in calls:
                pt, ct, tt = _tokens_from_meta(c.get("meta", {}))
                total_pt += pt
                total_ct += ct
                total_tt += tt
                typer.echo(
                    f"- node={c.get('node')} provider={c.get('provider')} model={c.get('model')} "
                    f"tokens: prompt={pt} completion={ct} total={tt}"
                )
            typer.echo(f"Total tokens: prompt={total_pt} completion={total_ct} total={total_tt}\n")

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


# -----------------------
# config subcommands
# -----------------------

_DEFAULT_CONFIG_YAML = """\
# Notebook Refactor Agent - default config
mode: run-all
safe: true
timeout_secs: 60

# LLM
provider: none      # e.g. 'groq' or 'none'
model: none         # see: nra --help for supported models
temperature: 0.1
max_output_tokens: 2048

# Cache
cache_dir: .cache/nra
"""


@typed_command_for(config_app, name="init")
def config_init(
    path: Path = Path("configs/default.yaml"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Create a default config file at configs/default.yaml."""
    if path.exists() and not overwrite:
        typer.echo(f"Config already exists at {path}. Use --overwrite to replace.")
        raise typer.Exit(code=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DEFAULT_CONFIG_YAML)
    typer.echo(f"Wrote {path}")


if __name__ == "__main__":
    app()
