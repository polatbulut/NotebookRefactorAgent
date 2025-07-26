# NotebookRefactorAgent

Turn a Jupyter notebook into a tiny, runnable Python package with one function per code cell and a minimal test. The current pipeline is deterministic and built with LangGraph.

## Requirements
	•	Python 3.10+ (tested on 3.13)
	•	macOS/Linux/WSL

## Install
```bash
git clone https://github.com/<your-user>/NotebookRefactorAgent.git
cd NotebookRefactorAgent
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pre-commit install
```

### Inspect Notebook
```bash
python -m notebook_refactor_agent.cli inspect examples/messy_notebook.ipynb
```

### Refactor Notebook
```bash
python -m notebook_refactor_agent.cli refactor examples/messy_notebook.ipynb --output-dir out_pkg
```

## Development
```bash
pre-commit run -a
pytest -q
ruff check src tests
black --check src tests
mypy src
```
