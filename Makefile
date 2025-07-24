install:
\tpip install -e ".[dev]"

lint:
\truff check src tests
\tblack --check src tests
\tmypy src

format:
\tblack src tests
\truff check src tests --fix
\tisort src tests

test:
\tpytest -q --cov=src --cov-report=term-missing

run:
\tpython -m notebook_refactor_agent.cli --help

