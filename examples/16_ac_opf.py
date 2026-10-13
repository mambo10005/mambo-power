"""AC optimal power flow on case14, next to the DC-OPF it refines.

What this shows:

* ``opf.solve_ac_opf(net)`` — the cheapest dispatch of the full AC network: active and
  reactive output, every voltage inside its band, losses covered, apparent-power flows inside
  their ratings (ADR-018). Solved as a sequence of HiGHS LPs with a power-flow restoration.
* What the DC-OPF leaves out: its dispatch is cheaper on paper because it ignores losses and
  voltage, and ``ac_check`` has already said it is not AC-feasible as dispatched.
* AC LMPs: one price per bus even with no line limit binding, rising with distance from the
  slack by the marginal cost of losses and voltage support — the DC LMP is flat.
* The bounds that bind: generator reactive limits and bus voltage bands, each with its dual.

Runs from any directory, with no repository clone: ``python 16_ac_opf.py``.
"""

from __future__ import annotations

from mambo_power import cases, opf

net = cases.load("case14")

# --- 1. DC and AC, side by side ----------------------------------------------------------------
dc = opf.solve_dc_opf(net, options=opf.OpfDcOptions(ac_check=True))
ac = opf.solve_ac_opf(net)
assert dc.ac_check is not None and ac.status == "Optimal"
print(f"DC-OPF: {dc.objective_cost:9.2f} $/h; its AC check finds", end=" ")
print(f"{len(dc.ac_check.voltage_violations)} voltage violations")
print(f"AC-OPF: {ac.objective_cost:9.2f} $/h after {ac.iterations} LP steps, ", end="")
print(f"losses {ac.losses_mw:.2f} MW, mismatch {ac.max_mismatch_pu:.1e} pu")

# --- 2. The dispatch, with reactive power the DC-OPF has no notion of --------------------------
print("\ndispatch           DC p_mw   AC p_mw   AC q_mvar")
dc_p = {g.id: g.p_mw for g in dc.generators}
for g in ac.generators:
    print(f"  {g.id:8s} {g.bus:7s} {dc_p[g.id]:8.2f}  {g.p_mw:8.2f}  {g.q_mvar:9.2f}")

# --- 3. Prices: flat in DC, shaped by losses and voltage in AC ---------------------------------
dc_lmp = {b.id: b.lmp for b in dc.buses}
print("\nLMP ($/MWh)       DC      AC     vm_pu   on band")
for b in ac.buses:
    on_band = "yes" if b.v_bound_dual != 0.0 else ""
    print(f"  {b.id:8s} {dc_lmp[b.id]:7.2f} {b.lmp_p:7.2f}   {b.vm_pu:.4f}   {on_band}")
spread = max(b.lmp_p for b in ac.buses) - min(b.lmp_p for b in ac.buses)
print(f"AC LMP spread {spread:.2f} $/MWh with no branch limit binding; DC spread 0.00")

# --- 4. What binds -------------------------------------------------------------------------------
pinned_q = [g.id for g in ac.generators if g.q_bound_dual != 0.0]
on_band = [b.id for b in ac.buses if b.v_bound_dual != 0.0]
print(f"\nreactive limits binding: {pinned_q}")
print(f"voltage bands binding:   {on_band}")
print("(a voltage band or a reactive limit that binds is what the AC LMPs are paying for)")
