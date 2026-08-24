"""AC-5: ``opf.solve_dc_opf`` on the new PWL-cost derived fixture (``case14_pwl.m``, S1) matches
an independently-constructed oracle within tolerance, and converges to a sane dispatch.

**Oracle path.** pandapower's own ``from_ppc`` converter (the same pipeline
``tests/parity/test_opf_vs_pandapower.py`` uses for AC-1) already parses MATPOWER MODEL-1
gencost rows into a ``pwl_cost`` table, and ``pp.rundcopp`` genuinely honours piecewise costs —
confirmed directly (a hand-built 2-bus pandapower network with a convex PWL generator dispatches
exactly the hand-computed optimum, matching the standard economic-dispatch answer to the cent).
**But** ``case14_pwl.m`` mixes MODEL-1 (gen-2, gen-3, converted by S1) with MODEL-2 *quadratic*
costs on the untouched generators (gen-1/4/5 keep case14's real nonzero ``c2``) — and
pandapower's own OPF objective builder (``pandapower/opf/make_objective.py:_init_gencost``)
raises ``ValueError: Quadratic costs can be mixed with piecewise linear costs`` the moment *any*
generator in the whole network has a nonzero quadratic term alongside *any* PWL generator,
confirmed directly against this exact fixture (not assumed from reading the source only).
Per spec Assumption (b), this falls back to the documented alternative: a **hand-built
economic-dispatch oracle**, independent of both pandapower and ``dc_opf``'s own HiGHS
construction.

**Why economic dispatch (not a general LP solve) is a valid independent oracle here**: no branch
in case14 (or case14_pwl, which touches only ``gencost``) carries a rating (record/
m3-research.md §6) — ``dc_opf``'s PTDF flow-limit rows never bind, so the DC-OPF collapses
exactly to the classic **equal-marginal-cost economic dispatch** problem: minimise total
generation cost subject only to system-wide balance and each generator's own ``[p_min, p_max]``.
That problem's optimum is found by bisecting a single shadow price ``lambda`` until aggregate
supply equals total load (``.bionic/tmp/probe_case14_pwl_lambda2.py``, not committed) — a
textbook algorithm sharing no code with ``dc_opf``'s LP-over-HiGHS construction.

**A genuine tie was found in the hand-picked breakpoints, not smoothed over.** gen-2's third
segment slope (30 $/MWh, 90-140 MW) exactly equals gen-3's second segment slope (30 $/MWh,
30-70 MW), and the equilibrium price lambda* = 30 lands exactly on this tie — before gen-4/gen-5
(flat marginal cost 40 $/MWh) ever turn on. At lambda* = 30 there are **multiple LP optima**:
~22.8 MW of remaining demand can be met by any split between gen-2's third segment and gen-3's
second segment, all at identical total cost. The three strictly-convex quadratic generators
(gen-1, gen-4, gen-5) are NOT ambiguous — their dispatch is pinned uniquely by lambda* — so this
test asserts exact dispatch for those three, an interval for gen-2/gen-3 (each's "certain"
segments must be fully used; the tied residual may split either way), and an exact total
objective cost (well-defined regardless of the split).
"""

from __future__ import annotations

import pytest

from mambo_power.io import matpower
from mambo_power.opf import solve_dc_opf
from tests._fixtures import FIXTURES_DIR

CASE14_PWL = FIXTURES_DIR / "derived" / "case14_pwl.m"

TOTAL_LOAD_MW = 259.0
COST_REL_TOL = 1e-4
# Margin over measured: HiGHS's own balance dual on this fixture is 30.0039, not exactly the
# theoretical tie price 30.0 (default LP/QP solve tolerance, sharpened by the near-degenerate
# flat supply segment at the tie) -- which, through gen-1's own (shallow) marginal-cost slope,
# cascades into a ~0.045 MW gap between HiGHS's dispatch and the exact-lambda=30 numbers below
# (measured: gen-1 116.2446, residual split 22.755 vs. the exact 116.2 / 22.8 asserted here).
DISPATCH_ABS_TOL_MW = 0.1

EXPECTED_COST = 6239.0
GEN1_EXACT_MW = 116.2  # (lambda* - c1) / (2*c2) = (30 - 20) / (2*0.0430292599)
GEN4_EXACT_MW = 0.0  # marginal cost at p=0 is 40 > lambda* = 30
GEN5_EXACT_MW = 0.0
GEN2_FLOOR_MW = 90.0  # seg1 (slope 20) + seg2 (slope 25), both < lambda* -> fully used
GEN3_FLOOR_MW = 30.0  # seg1 (slope 20) < lambda* -> fully used
RESIDUAL_MW = 22.8  # split ambiguously between gen-2 seg3 and gen-3 seg2 (both cost exactly 30)


@pytest.fixture(scope="module")
def result():
    net = matpower.load(CASE14_PWL)
    return solve_dc_opf(net)


def test_converges_optimal(result) -> None:
    assert result.status == "Optimal", result.message


def test_dispatch_is_sane(result) -> None:
    """Beyond the oracle comparison: balance, bounds, no NaNs."""
    by_id = {g.id: g for g in result.generators}
    assert set(by_id) == {"gen-1", "gen-2", "gen-3", "gen-4", "gen-5"}
    total = sum(g.p_mw for g in by_id.values())
    assert total == pytest.approx(TOTAL_LOAD_MW, abs=1e-3)
    bounds = {"gen-1": 332.4, "gen-2": 140.0, "gen-3": 100.0, "gen-4": 100.0, "gen-5": 100.0}
    for gen_id, p_max in bounds.items():
        assert -1e-6 <= by_id[gen_id].p_mw <= p_max + 1e-6, (gen_id, by_id[gen_id].p_mw)


def test_objective_cost_matches_hand_built_economic_dispatch_oracle(result) -> None:
    rel = abs(result.objective_cost - EXPECTED_COST) / EXPECTED_COST
    assert rel <= COST_REL_TOL, (result.objective_cost, EXPECTED_COST, rel)


def test_quadratic_generators_dispatch_matches_the_uniquely_pinned_oracle_value(result) -> None:
    """gen-1/gen-4/gen-5 are strictly convex -> their optimum is unique, unlike gen-2/gen-3's
    tied segment (module docstring)."""
    by_id = {g.id: g.p_mw for g in result.generators}
    assert by_id["gen-1"] == pytest.approx(GEN1_EXACT_MW, abs=DISPATCH_ABS_TOL_MW)
    assert by_id["gen-4"] == pytest.approx(GEN4_EXACT_MW, abs=DISPATCH_ABS_TOL_MW)
    assert by_id["gen-5"] == pytest.approx(GEN5_EXACT_MW, abs=DISPATCH_ABS_TOL_MW)


def test_pwl_generators_fully_use_their_strictly_cheaper_segments_and_split_the_tied_residual(
    result,
) -> None:
    by_id = {g.id: g.p_mw for g in result.generators}
    gen2, gen3 = by_id["gen-2"], by_id["gen-3"]
    assert gen2 >= GEN2_FLOOR_MW - DISPATCH_ABS_TOL_MW
    assert gen3 >= GEN3_FLOOR_MW - DISPATCH_ABS_TOL_MW
    residual = (gen2 - GEN2_FLOOR_MW) + (gen3 - GEN3_FLOOR_MW)
    assert residual == pytest.approx(RESIDUAL_MW, abs=DISPATCH_ABS_TOL_MW)
