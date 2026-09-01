"""AC Newton-Raphson power flow on case14 and case118, with and without Q-limit enforcement.

What this shows:

* ``pf.solve_ac(net, options=AcOptions(...))`` — flat start, tolerance 1e-8 pu on the mismatch
  infinity norm, sparse Jacobian factorised with ``scipy.sparse.linalg.splu``.
* ``AcPowerFlowResult`` diagnostics: ``iterations`` (summed over Q-limit rounds),
  ``q_limit_rounds``, ``max_mismatch_mva``, and ``GenResult.q_limited`` (``"min"``/``"max"``)
  for the generators pinned at a reactive limit. On case118 with limits on, six buses are
  pinned (the same set pandapower pins); with limits off nothing is pinned and bus 103 sits
  at its 1.01 setpoint.
* Bus voltages and a branch-loading table from the typed result.
* Warm start: copy the solved state into ``Bus.vm_pu`` / ``Bus.va_deg`` and solve again with
  ``init="auto"`` — a start already inside tolerance reports 0 iterations.

Run from the repository root: ``uv run python examples/02_ac_power_flow.py``.
"""

from __future__ import annotations

from mambo_power import pf
from mambo_power.io import matpower
from mambo_power.results import AcPowerFlowResult


def summarise(label: str, result: AcPowerFlowResult) -> None:
    pinned = [(g.id, g.bus, g.q_limited) for g in result.generators if g.q_limited != "none"]
    print(f"--- {label}")
    print(
        f"converged={result.converged} iterations={result.iterations} "
        f"q_limit_rounds={result.q_limit_rounds} max_mismatch={result.max_mismatch_mva:.2e} MVA"
    )
    print("pinned generators:", pinned if pinned else "none")


for name in ("case14", "case118"):
    net = matpower.load(f"fixtures/matpower/{name}.m")
    for q_limits in (True, False):
        options = pf.AcOptions(init="flat", q_limits=q_limits)
        summarise(f"{name}, q_limits={q_limits}", pf.solve_ac(net, options=options))

# --- A closer look at case118 with limits enforced ------------------------------------------
net = matpower.load("fixtures/matpower/case118.m")
result = pf.solve_ac(net, options=pf.AcOptions(init="flat"))
print("\nfirst 5 bus voltages (case118, q_limits on):")
for bus in result.buses[:5]:
    print(f"  {bus.id:8s} {bus.vm_pu:7.4f} pu {bus.va_deg:8.3f} deg  role={bus.role_effective}")

print("\nbus 103 (limited gen) with and without Q-limits:")
off = pf.solve_ac(net, options=pf.AcOptions(init="flat", q_limits=False))
vm_on = next(b.vm_pu for b in result.buses if b.id == "bus-103")
vm_off = next(b.vm_pu for b in off.buses if b.id == "bus-103")
print(f"  vm on={vm_on:.5f} pu   vm off={vm_off:.5f} pu (= its 1.01 setpoint)")

# case118 ships no thermal ratings (RATE_A = 0 -> rating_mva None -> loading_pct None), so
# stamp a uniform 250 MVA rating to show the loading column; ratings do not affect the solve.
for branch in net.branches:
    branch.rating_mva = 250.0
result = pf.solve_ac(net, options=pf.AcOptions(init="flat"))
print("\nfive most loaded branches (case118, q_limits on, 250 MVA on every branch):")
rated = [b for b in result.branches if b.loading_pct is not None]
for br in sorted(rated, key=lambda b: b.loading_pct or 0.0, reverse=True)[:5]:
    flow = complex(br.p_from_mw, br.q_from_mvar)
    print(
        f"  {br.id:10s} {br.from_bus:8s}->{br.to_bus:8s} "
        f"P={br.p_from_mw:8.2f} MW  Q={br.q_from_mvar:8.2f} MVAr  "
        f"|S|={abs(flow):7.2f} MVA  loading={br.loading_pct:5.2f} %"
    )
losses = sum(b.p_from_mw + b.p_to_mw for b in result.branches)
print(f"total active losses: {losses:.3f} MW")

# --- Warm start ------------------------------------------------------------------------------
# Copy the q_limits=False solution into the buses; "auto" then starts from it and the mismatch
# is already inside tolerance: 0 iterations. (With limits on, a pinned bus is PV again at the
# start, its magnitude snaps back to the setpoint, and one re-pin round is needed.)
state = {b.id: (b.vm_pu, b.va_deg) for b in off.buses}
for bus in net.buses:
    bus.vm_pu, bus.va_deg = state[bus.id]
warm = pf.solve_ac(net, options=pf.AcOptions(init="auto", q_limits=False))
print(
    f"\nwarm start from the solved state: iterations={warm.iterations} "
    f"rounds={warm.q_limit_rounds} converged={warm.converged}"
)
print("provenance:", warm.provenance.kind, warm.provenance.solver, warm.provenance.options)
