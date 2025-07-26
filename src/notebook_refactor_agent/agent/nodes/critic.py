from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def critic_node(state: dict[str, Any]) -> dict[str, Any]:
    out = Path(state["output_dir"])
    pytest = subprocess.run(["pytest", "-q", str(out / "tests")], capture_output=True, text=True)
    metrics = {"pytest_returncode": pytest.returncode}
    report = str(pytest.returncode)
    return {"metrics": metrics, "report": report}
