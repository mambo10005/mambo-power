"""DC power flow on case300 and how far it sits from the AC solution.

What this shows:

* ``pf.solve_dc(net)`` — the lossless linear model ``B'θ = P − P_shift`` with the slack
  angle fixed at 0, branch flows via ``B_f``; always converges on a connected network.
* The ``DcPowerFlowResult`` summary: angle range, the largest flows, the slack-generator
  balance (the first in-service slack-bus generator absorbs it).
* A comparison with the AC Newton-Raphson flows on the same case: the DC approximation is
  close on most branches and off by tens of MW on a few, and it knows nothing about the
  AC losses.

Run from the repository root: ``uv run python examples/03_dc_power_flow.py``.
"""

from __future__ import annotations

import numpy as np

from mambo_power import pf
from mambo_power.io import matpower

net = matpower.load("fixtures/matpower/case300.m")
dc = pf.solve_dc(net)
print("case300 DC:", dc.provenance.kind, dc.provenance.solver, "converged =", dc.converged)

angles = np.array([b.va_deg for b in dc.buses])
print(f"angles: min {angles.min():.2f} deg, max {angles.max():.2f} deg (slack at 0)")
print("largest DC flows:")
for br in sorted(dc.branches, key=lambda b: abs(b.p_from_mw), reverse=True)[:5]:
    print(f"  {br.id:10s} {br.from_bus:9s}->{br.to_bus:9s} {br.p_from_mw:9.2f} MW")

slack_bus = next(b for b in dc.buses if b.role_effective == "slack").id
slack_gens = [g for g in dc.generators if g.bus == slack_bus]
total_load = sum(ld.p_mw for ld in net.loads if ld.in_service)
total_shunt = sum(sh.g_mw for sh in net.shunts if sh.in_service)
total_gen = sum(g.p_mw for g in dc.generators)
print(f"slack bus {slack_bus}: generators {[(g.id, round(g.p_mw, 2)) for g in slack_gens]}")
print(f"generation {total_gen:.2f} MW = load {total_load:.2f} + shunt G {total_shunt:.2f} MW")

# --- Compare with the AC solution ------------------------------------------------------------
ac = pf.solve_ac(net, options=pf.AcOptions(init="flat", q_limits=False))
p_dc = dc.to_arrays().p_from_mw
p_ac = ac.to_arrays().p_from_mw
diff = p_ac - p_dc
worst = int(np.argmax(np.abs(diff)))
print(f"\nAC (flat start, no Q-limits): {ac.iterations} iterations, converged = {ac.converged}")
print(f"AC losses: {sum(b.p_from_mw + b.p_to_mw for b in ac.branches):.2f} MW")
print(f"|P_ac - P_dc| on from-side flows: median {np.median(np.abs(diff)):.2f} MW,", end=" ")
print(f"95th pct {np.percentile(np.abs(diff), 95):.2f} MW, max {np.abs(diff).max():.2f} MW")
print(f"largest gap on {dc.branches[worst].id}: AC {p_ac[worst]:.2f} MW vs DC {p_dc[worst]:.2f} MW")
print("(that branch feeds the slack bus, whose generator picks up every MW of AC losses)")
