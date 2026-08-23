"""AC-7: case300 AC Newton-Raphson (Q-limits off, flat start) solves cold in under 1.0 s wall.

"Cold" means the first ``solve_ac`` call in a fresh interpreter — SuperLU's first factorisation,
numpy/scipy first-touch costs and pydantic model construction all included — so the
measurement runs in a subprocess and prints the time. The contracted surface is the CI ubuntu
3.12 job (spec AC-7); a local failure is reported with its number, never loosened here.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable

import pytest

from tests._fixtures import FIXTURES_DIR

THRESHOLD_S = 1.0

SCRIPT = r"""
import time, warnings
from mambo_power.io import matpower
from mambo_power.pf import AcOptions, solve_ac
net = matpower.load(r"{path}")
warnings.simplefilter("ignore")
t0 = time.perf_counter()
result = solve_ac(net, options=AcOptions(init="flat", q_limits=False))
cold = time.perf_counter() - t0
t0 = time.perf_counter()
solve_ac(net, options=AcOptions(init="flat", q_limits=False))
warm = time.perf_counter() - t0
print(f"{{int(result.converged)}} {{result.iterations}} {{cold:.4f}} {{warm:.4f}}")
"""


@pytest.mark.parity
def test_case300_cold_solve_under_one_second(
    record_property: Callable[[str, object], None],
) -> None:
    script = SCRIPT.format(path=FIXTURES_DIR / "case300.m")
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True, timeout=300
    )
    converged, iterations, cold, warm = proc.stdout.split()[-4:]
    cold_s, warm_s = float(cold), float(warm)
    figure = f"case300 AC cold {cold_s:.4f} s, warm {warm_s:.4f} s, {iterations} iterations"
    # AC-7 wants the measured figure in the CI log, not only the verdict: the print reaches
    # the log under `-s` (the dedicated ubuntu 3.12 CI step), the recorded properties reach
    # any junit/xml reporter, and the assertion message carries it on failure.
    print(figure)
    record_property("case300_ac_cold_s", cold_s)
    record_property("case300_ac_warm_s", warm_s)
    record_property("case300_ac_iterations", int(iterations))
    assert converged == "1" and int(iterations) > 0, figure
    assert cold_s < THRESHOLD_S, (
        f"{figure}; AC-7 threshold {THRESHOLD_S} s — CI ubuntu is the contracted surface"
    )
