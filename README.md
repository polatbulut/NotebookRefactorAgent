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

## LLM Mode (Groq)

This project can plan/refactor/write-tests using an LLM.

### Setup

1. Create a Groq API key at https://console.groq.com/
2. Export it in your shell:

```bash
export GROQ_API_KEY="gsk_..."
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


## Run
```bash
nra refactor examples/messy_notebook.ipynb \
  --output-dir out_pkg_llm \
  --provider groq \
  --model llama-3.3-70b-versatile \
  --temperature 0.1 \
  --max-output-tokens 4096 \
  --verbose
```
