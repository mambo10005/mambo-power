"""Independent read of a MATPOWER ``.m`` file for the parity oracles.

Deliberately written with different tools from :mod:`mambo_power.io.matpower` — ``re`` +
``numpy.loadtxt`` over regex-extracted ``mpc.<name> = [ ... ];`` blocks, no shared helper — so
that an importer bug cannot be mirrored into the oracle (review Duplication 5: intended
duplication, do not fold into the importer). Shared by the AC-6 column parity and the AC-7
matrix parity modules.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import numpy as np


def read_mpc_numpy(path: Path) -> dict[str, Any]:
    """Read baseMVA and the numeric matrices with regex + ``numpy.loadtxt`` (1-based, raw)."""
    text = re.sub(r"%[^\n]*", "", path.read_text(encoding="utf-8"))
    base = re.search(r"mpc\.baseMVA\s*=\s*([^;\s]+)", text)
    assert base is not None

    def block(name: str) -> np.ndarray | None:
        match = re.search(rf"mpc\.{name}\s*=\s*\[(.*?)\];", text, re.S)
        if match is None:
            return None
        return np.loadtxt(io.StringIO(match.group(1).replace(";", "\n")), ndmin=2)

    ppc: dict[str, Any] = {"version": "2", "baseMVA": float(base.group(1))}
    for name in ("bus", "gen", "branch", "gencost"):
        matrix = block(name)
        if matrix is not None:
            ppc[name] = matrix
    return ppc
