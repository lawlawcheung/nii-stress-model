"""Smoke test: every code cell in the demo notebook runs without error.

Uses only the standard library to read the notebook, so CI doesn't need
Jupyter installed.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display in CI

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "nii_stress_demo.ipynb"


def test_notebook_runs(monkeypatch):
    monkeypatch.chdir(ROOT / "notebooks")
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    namespace: dict = {"__name__": "__main__"}
    for i, cell in enumerate(cells):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        source = "\n".join(l for l in source.splitlines() if not l.lstrip().startswith("%"))
        exec(compile(source, f"<cell {i}>", "exec"), namespace)
