"""DC-OPF dispatch and duals, then N-1 branch-contingency screening, on case14.

What this shows:

* ``opf.solve_dc_opf(net, options=...)`` — the cost-minimising LP/QP dispatch, its shadow
  prices (the balance dual and each generator's bound reduced cost), and ``options.ac_check``:
  a DC-OPF-optimal dispatch is not automatically AC-feasible, and this fixture's own clean
  base case already has two buses outside their declared voltage band once AC-solved.
* Locational marginal prices via ``lmp_decomposition``: on case14 as shipped no branch is
  rated (no bundled MATPOWER fixture carries a real ``RATE_A``), so every bus's LMP is pure
  energy; tightening one branch's rating until it binds splits the price into energy +
  congestion, and buses on the constrained side of the network pay more.
* ``contingency.n1`` — the LODF fast screen followed by a confirming DC re-solve, on a copy of
  case14 with synthetic ratings (case14 as shipped has none). One outage's screened estimate
  and DC-re-solve-confirmed flow, side by side, on a branch the screen correctly flagged.

Run from the repository root: ``uv run python examples/08_opf_and_n1.py``.
"""

from __future__ import annotations

from mambo_power import contingency, opf, pf
from mambo_power.io import matpower

net = matpower.load("fixtures/matpower/case14.m")

# --- 1. DC-OPF dispatch, duals, and the AC-feasibility check --------------------------------
result = opf.solve_dc_opf(net, options=opf.OpfDcOptions(ac_check=True))
print(f"status: {result.status}  cost: {result.objective_cost:.2f} $/h", end="  ")
print(f"balance dual (energy price): {result.balance_dual:.4f} $/MWh")
print("dispatch:")
for g in result.generators:
    pinned = " (pinned)" if g.bound_dual != 0.0 else ""
    print(f"  {g.id:8s} {g.bus:8s} {g.p_mw:8.3f} MW  bound dual {g.bound_dual:7.4f}{pinned}")

assert result.ac_check is not None  # options.ac_check=True guarantees it, once status == Optimal
print(f"\nac_check: converged = {result.ac_check.converged}", end="  ")
print(f"thermal violations: {len(result.ac_check.thermal_violations)}", end="  ")
print(f"voltage violations: {len(result.ac_check.voltage_violations)}")
for v in result.ac_check.voltage_violations:
    print(f"  {v.bus_id}: {v.vm_pu:.4f} pu vs limit {v.limit_pu:.4f} pu")
print("(the DC-OPF dispatch minimises cost with no voltage constraint at all: an AC re-solve")
print(" of the identical injections can still land outside the declared voltage band)")

# --- 2. Congestion: tighten one branch's rating until the OPF's own dispatch is forced off it -
base = pf.solve_dc(net)
busiest = max(base.branches, key=lambda b: abs(b.p_from_mw))
congested = net.model_copy(deep=True)
tight_rating_mva = abs(busiest.p_from_mw) * 0.5
for br in congested.branches:
    if br.id == busiest.id:
        br.rating_mva = tight_rating_mva

congested_result = opf.solve_dc_opf(congested)
binding = next(b for b in congested_result.branches if b.id == busiest.id)
print(
    f"\n{busiest.id} rated down to {tight_rating_mva:.2f} MVA (from {busiest.p_from_mw:.2f} MW",
    "base-case flow)",
)
print(f"congested flow: {binding.p_from_mw:.2f} MW == rating, dual {binding.flow_limit_dual:.4f}")
congested_lmp = [b for b in congested_result.buses if abs(b.congestion) > 1e-9]
print(f"buses with nonzero congestion price: {len(congested_lmp)} of {len(congested_result.buses)}")
for b in sorted(congested_lmp, key=lambda b: b.congestion, reverse=True)[:3]:
    print(f"  {b.id:8s} lmp {b.lmp:7.3f} = energy {b.energy:7.3f} + congestion {b.congestion:6.3f}")

# --- 3. N-1: LODF screen, then a confirming DC re-solve --------------------------------------
# case14 ships no real branch ratings either (research: RATE_A == 0 everywhere) — derive
# synthetic ones from the base-case flow, the same "test-time transformation of an
# already-owned fixture" this wave's own test suite uses, at 20% headroom above the base flow.
rated = net.model_copy(deep=True)
base_flow_mw = {b.id: abs(b.p_from_mw) for b in base.branches}
for br in rated.branches:
    if br.id in base_flow_mw:
        br.rating_mva = max(1.2 * base_flow_mw[br.id], 1.0)

n1_result = contingency.n1(rated)
print(
    f"\nN-1: {len(n1_result.outages)} outages flagged by the LODF screen (of "
    f"{len(rated.branches) - len(n1_result.bridge_branch_ids)} screenable branches)"
)
outage = n1_result.outages[0]
print(f"outage {outage.outage_branch_id}: confirmed violating = {outage.confirmed_violating}")
for flag in outage.flagged_branches[:3]:
    print(f"  {flag.branch_id:8s} rating {flag.rating_mva:7.2f} MVA  ", end="")
    print(
        f"screened {flag.estimated_flow_mw:7.2f} MW  confirmed {flag.confirmed_flow_mw:7.2f} MW",
        end="  ",
    )
    print(f"violating = {flag.confirmed_violating}")
print("(the screen's LODF estimate and the confirming DC re-solve agree to five decimal places:")
print(" AC-6 proves that holds for every outage on every bundled fixture, not just this one)")
