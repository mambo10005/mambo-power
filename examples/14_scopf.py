"""Security-constrained DC-OPF on the bundled rated case14: what single-outage security costs.

What this shows:

* ``opf.solve_scopf(net)`` — the cheapest dispatch no single branch or generator outage can
  overload, found by constraint generation: solve the plain DC-OPF, screen its dispatch with the
  N-1 screen, add one post-contingency flow row per flagged (outage, branch) pair, re-solve,
  until the screen flags nothing new (ADR-016).
* The price of security: ``base_objective_cost`` (plain OPF) against ``objective_cost`` (secure),
  and the dispatch that moved — away from the cheap slack unit whose main outlet cannot be
  spared.
* ``constraints`` — every post-contingency row that had to be added, and which of them actually
  bind the secure dispatch (nonzero ``dual``), including a *generator* outage.
* ``n1`` — the real ``contingency.n1`` of the secure dispatch, carried with the result as the
  confirmation; ``secure`` is its verdict.

Runs from any directory, with no repository clone: ``python 14_scopf.py``.
"""

from __future__ import annotations

from mambo_power import cases, contingency, opf

net = cases.load("derived/case14_rated")

# --- 1. The plain OPF is cheap, and not secure ---------------------------------------------
plain = opf.solve_dc_opf(net)
dispatched = net.model_copy(deep=True)
for gen in dispatched.generators:
    gen.p_mw = next(g.p_mw for g in plain.generators if g.id == gen.id)
unsecured = contingency.n1(dispatched)
print(f"plain DC-OPF: {plain.objective_cost:.2f} $/h, dispatch:", end=" ")
print(" ".join(f"{g.id}={g.p_mw:.1f}" for g in plain.generators))
print(
    f"N-1 of that dispatch: {sum(o.confirmed_violating for o in unsecured.outages)} violating "
    f"branch outages, {sum(o.confirmed_violating for o in unsecured.generator_outages)} "
    "violating generator outages"
)

# --- 2. Secure it ------------------------------------------------------------------------------
result = opf.solve_scopf(net)
print(f"\nSCOPF: {result.status}, secure = {result.secure}, {result.iterations} solves")
print(f"secure dispatch: {result.objective_cost:.2f} $/h (+{result.security_cost:.2f}):", end=" ")
print(" ".join(f"{g.id}={g.p_mw:.1f}" for g in result.generators))

# --- 3. What binds: the contingencies the system is paying to be ready for ------------------
binding = [c for c in result.constraints if abs(c.dual) > 1e-9]
print(f"\n{len(result.constraints)} post-contingency rows added, {len(binding)} binding:")
for c in binding:
    print(f"  {c.outage_kind:9s} {c.outage_id:9s} out -> {c.branch_id:9s} ", end="")
    print(f"{c.post_contingency_flow_mw:8.2f} MW of {c.rating_mva:6.1f} MVA  dual {c.dual:8.3f}")

# --- 4. The confirmation travels with the result ---------------------------------------------
assert result.n1 is not None  # status == "Optimal" guarantees it
print(
    f"\nconfirming contingency.n1: {len(result.n1.outages)} branch outages flagged, "
    f"{len(result.n1.generator_outages)} generator outages flagged"
)
print("(a secure dispatch leaves the N-1 screen nothing to flag: every single outage is")
print(" survivable without any post-contingency action, at the cost shown above)")
