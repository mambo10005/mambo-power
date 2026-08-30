"""AC-9: every script under ``examples/`` runs to completion from the repository root.

The scripts are the documentation's executed code — ``docs/examples/index.md`` embeds them
byte-for-byte with ``pymdownx.snippets`` — so a script that stops running is a docs page that
lies. Each one is run in a fresh interpreter (as a reader would run it), with the repository
root as the working directory (they read ``fixtures/``), and must exit 0, print something, and
finish inside a generous budget. The CI ``examples`` job runs the same loop for visibility;
this test is what the local floor covers.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"
EXAMPLES = sorted(EXAMPLES_DIR.glob("*.py"))
BUDGET_S = 60.0  # each script is ~1 s locally; the budget only guards against a hang
# Scripts whose whole point is running an external engine pay that engine's cold import: example 13
# imports pandapower (~13 s) and PyPSA (~6 s) and runs pp.rundcpp, pp.networks.case14() and a
# PyPSA optimize -- ~50 s in-process on the Windows dev machine, more on a cold CI runner. The
# budget is still a hang guard, sized for what the script actually does.
BUDGETS_S: dict[str, float] = {"13_interop": 240.0}


def test_examples_directory_is_populated() -> None:
    names = [p.name for p in EXAMPLES]
    assert len(names) >= 7, names
    assert names == sorted(names)
    assert all(name[:2].isdigit() and name[2] == "_" for name in names), names


def test_every_example_is_embedded_in_the_docs() -> None:
    gallery = (REPO_ROOT / "docs" / "examples" / "index.md").read_text(encoding="utf-8")
    missing = [p.name for p in EXAMPLES if f'--8<-- "examples/{p.name}"' not in gallery]
    assert missing == [], f"not embedded in docs/examples/index.md: {missing}"


@pytest.mark.parametrize("script", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_example_runs_to_completion(script: Path) -> None:
    budget = BUDGETS_S.get(script.stem, BUDGET_S)
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=budget,
        check=False,
    )
    elapsed = time.perf_counter() - started
    assert proc.returncode == 0, f"{script.name} exited {proc.returncode}\n{proc.stderr}"
    assert proc.stdout.strip(), f"{script.name} printed nothing"
    assert "Traceback" not in proc.stderr, proc.stderr
    assert elapsed < budget
    print(f"{script.name}: {elapsed:.2f} s, {len(proc.stdout.splitlines())} lines")
