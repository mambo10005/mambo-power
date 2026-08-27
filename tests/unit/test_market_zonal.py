"""Unit tests for :mod:`mambo_power.market.zonal` — the zonal/redispatch/nodal chain (M6 W4/W5,
spec AC-4 and AC-5).

**Two oracles, neither of them the code under test.**

1. *The hand fixture.* The 2-zone/3-bus network of ``.bionic/docs/record/m6-ac2-derivation.md``,
   whose zonal LP, nodal reference and every dual were solved three independent ways there (hand
   KKT, ``scipy.optimize.linprog``, and this repo's own pre-existing ``market.solve_nodal``) and
   agree to the printed precision. Every number in the first half of this file is transcribed from
   that record, not read off ``solve_zonal``'s output — including the two figures the derivation
   does *not* state, which are re-derived in the relevant test's own docstring from numbers it
   does.
2. *The nodal reference on real fixtures.* AC-4's claim is that the redispatched point **is** the
   nodal optimum, so the oracle is :func:`~mambo_power.market.nodal.solve_nodal` itself, called on
   the same scenario. That is a genuinely separate solve through a genuinely separate builder
   (``dc_opf``'s single-balance-row LP against ``redispatch_dc_opf``'s delta-column one), which is
   what keeps the comparison a theorem rather than a tautology.

**Fixtures are driven, never copied.** Zones come from ``tests/_zones.py``, ratings from
``tests/_rated.py``, bids from ``tests/_bids.py``, each unmodified. Two of the five bid loads on
each real fixture get the *interior* derivation, so demand actually moves in the redispatch
instead of sitting pinned at its own bound — without that, ``redispatch_payment``'s curtailment
term would be multiplied by zero on every fixture in this file and its sign convention would go
untested.

**Two findings from earlier slices are binding here.**

* **A20** — rated case300 is primal-degenerate at the nodal optimum: 7 branches sit exactly at
  their rating, only 5 carry a nonzero dual, and the two builders legitimately select different
  active sets. So AC-4's LMP clause is asserted *tightly* on case30 and, on case300, as a
  comparison against the same independent ``solve_nodal`` that decomposes the disagreement rather
  than tolerating it: the energy components must agree to 1e-3 $/MWh, and the congestion
  difference must be reproducible by flow duals on the at-rating branches alone and *not* by the
  priced ones alone. A blanket 1 $/MWh LMP tolerance was rejected upstream because it would admit
  real regressions to hide a known degeneracy; an earlier ``priced ⊆ at_rating`` check was removed
  for the opposite failing — computed from one solve's own rows, it is complementary slackness and
  every optimal solve passes it (audit F2).
* **A21** — ``pf.dc`` pins the slack bus at angle 0 and lets it absorb whatever mismatch the
  declared injections carry, so a rating-respecting flow vector does **not** imply a balanced
  dispatch. Every feasibility readback below therefore asserts the energy balance too.

Tolerances are measured on this build, stated where they are pinned, and never asserted as
bit-equality — spec assumption A3 and wave M5's macOS CI finding.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

import numpy as np
import pytest
from numpy.testing import assert_allclose

from mambo_power.io.matpower import load as load_matpower
from mambo_power.market.nodal import load_bid_coeffs, solve_nodal
from mambo_power.market.zonal import (
    CorridorLimit,
    MarketZonalOptions,
    _demand_value,
    _generation_cost,
    solve_zonal,
    zone_partition,
)
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    PiecewiseBid,
    PolynomialCost,
    Scenario,
    Zone,
)
from mambo_power.numerics import NetworkArrays, ptdf
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import NonConcaveBidError, NonConvexCostError
from mambo_power.opf.redispatch import redispatch_dc_opf
from mambo_power.opf.zonal import zonal_dc_opf
from mambo_power.pf import dc as pfdc
from mambo_power.results import (
    GenDispatchResult,
    GenRedispatchResult,
    LoadDispatchResult,
    MarketNodalResult,
    MarketZonalResult,
)
from tests._bids import with_bids
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network
from tests._zones import corridors, promote_areas_to_zones

# --- tolerances, each measured on this build ----------------------------------------------------

EXACT_ATOL = 1e-9
"""Tolerance for the hand fixture's small-integer numbers. Measured: every residual below is
identically 0.0 on this build, as the derivation's §7 predicts (exact rationals at this scale).
Asserted as a tolerance anyway — spec A3: a test that would fail on a last-bit difference is
testing the platform, not the market."""

CASE30_QUANTITY_ATOL = 1e-3
"""AC-4's dispatch/served-demand agreement with ``solve_nodal`` on rated case30, MW. Measured:
2.83e-5 MW on generation (rel. 4.6e-7) and 1.46e-5 MW on served demand. ~35x headroom, and still
five orders below the 43 MW of redispatch volume these tests draw conclusions from."""

CASE300_QUANTITY_ATOL = 5e-2
"""The same agreement on rated case300, MW. Measured: 9.45e-3 MW on generation (rel. 4.8e-6) and
8.28e-5 MW on served demand — looser than case30's for the reason A20 records, that case300's
nodal optimum is primal-degenerate and the two builders land on different vertices of the same
optimal face. ~5x headroom, against a 92 MW redispatch volume."""

CASE30_LMP_ATOL = 1e-3
"""AC-4's LMP agreement on rated case30, $/MWh. Measured: 8.92e-6 on prices of order 6.8 $/MWh.
Deliberately *not* applied to case300 (A20): there the same measurement is 0.32 $/MWh, and it is
degeneracy rather than disagreement — see the test that decomposes it below."""

CASE300_ENERGY_ATOL = 1e-3
"""Agreement between the chain's and ``solve_nodal``'s **energy** component of the LMP on rated
case300, $/MWh. Measured: 5.40e-6 on a price level of 40.876 $/MWh. This is the half of the price
comparison degeneracy does *not* excuse: the balance dual is the system-wide price level, it is
one number shared by every bus in both solves, and no choice among the optimal face's vertices
moves it. Pinned ~185x above the measurement and ~300x below the 0.32 $/MWh the *congestion*
components differ by, so the tolerance cannot be met by this fixture's degeneracy."""

CASE300_DEGENERATE_FACE_ATOL = 1e-6
"""Residual, $/MWh, when the chain-minus-nodal **congestion** difference is re-expressed as flow
duals living only on the branches that sit exactly at their rating. Measured: 4.02e-16 against a
difference of 0.3188 $/MWh in sup-norm — exact. Seven at-rating branches span a 7-dimensional
subspace of R^300, so landing inside it to 4e-16 is a statement about where the disagreement
lives, not an artefact of dimension; the paired assertion measures what is left of the difference
when the two *unpriced* at-rating branches are taken away (0.298 $/MWh, i.e. nearly all of it)."""

CASE300_FACE_IS_LOAD_BEARING_ATOL = 0.1
"""Floor, $/MWh, on that paired residual. Measured: 0.2977 on a 0.3188 sup-norm difference — 93%
of the disagreement is carried by the two at-rating-but-unpriced branches, which is what makes the
face load-bearing rather than a set the fit did not need. 3x headroom."""

WELFARE_REL_TOL = 1e-9
"""``welfare_gap`` as a fraction of the welfare being compared. Measured: 1.37e-14 on case30 and
8.28e-13 on case300, against welfare of order 3.0e5 and 1.8e6 $/h. Pinned relative, not absolute,
because the two fixtures' welfare differs by an order of magnitude."""

FLOW_TOL_MW = 1e-6
"""Feasibility slack when reading the final point back through ``pf.dc``, MW — S4's own AC-3
constant, reused deliberately so the two slices' feasibility claims are the same claim. Measured
here: 2.0e-14 MW of overload on case30 and 5.5e-10 MW on case300, with energy-balance residuals of
0.0 and 2.5e-10 MW."""

IDENTITY_ATOL = 1e-6
"""Settlement-identity closure, $/h. Measured: 8.53e-14 on case30 and 4.97e-14 on the hand
fixture, against a congestion rent of 31.85 and 800 $/h respectively."""


# --- the hand fixture (derivation §1) -----------------------------------------------------------

COST_A, COST_B = 10.0, 50.0
"""The two generators' linear costs, $/MWh (derivation §1)."""
LOAD_A, LOAD_B = 50.0, 30.0
"""The two zones' fixed loads, MW (derivation §1)."""
BRANCH_RATING = 20.0
"""The physical A-B tie's rating, MVA (derivation §5) — what the network can really carry."""


def _gen(gen_id: str, bus: str, cost: float, p_max: float = 200.0) -> Generator:
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=0.0,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=p_max,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        cost=PolynomialCost(coefficients=[cost, 0.0]),
    )


def _hand_network(
    *,
    rating: float | None = BRANCH_RATING,
    bid_load: bool = False,
    gen_b_p_max: float = 200.0,
) -> Network:
    """The derivation §1 network: bus1/bus2 in zone A, bus3 in zone B; cheap ``genA`` at bus1,
    expensive ``genB`` at bus3; 50 MW of load in zone A and 30 MW in zone B; the physical A-B tie
    ``br23`` rated ``rating`` and the intra-zone branch ``br12`` deliberately unrated.

    ``bid_load`` swaps zone B's fixed load for derivation §6's flat piecewise bid (45 $/MWh up to
    30 MW), which also exercises the piecewise branch of this module's curve evaluators.
    """
    load_b = (
        Load(
            id="loadB",
            bus="bus3",
            p_mw=LOAD_B,
            q_mvar=0.0,
            bid=PiecewiseBid(points=[(0.0, 0.0), (LOAD_B, 45.0 * LOAD_B)]),
        )
        if bid_load
        else Load(id="loadB", bus="bus3", p_mw=LOAD_B, q_mvar=0.0)
    )
    return Network(
        base_mva=100.0,
        zones=[Zone(id="A"), Zone(id="B")],
        buses=[
            Bus(id="bus1", base_kv=138.0, type="slack", area="A", zone="A"),
            Bus(id="bus2", base_kv=138.0, type="pq", area="A", zone="A"),
            Bus(id="bus3", base_kv=138.0, type="pq", area="B", zone="B"),
        ],
        branches=[
            Branch(id="br12", from_bus="bus1", to_bus="bus2", r=0.0, x=0.1, b=0.0),
            Branch(
                id="br23", from_bus="bus2", to_bus="bus3", r=0.0, x=0.1, b=0.0, rating_mva=rating
            ),
        ],
        generators=[_gen("genA", "bus1", COST_A), _gen("genB", "bus3", COST_B, gen_b_p_max)],
        loads=[Load(id="loadA", bus="bus2", p_mw=LOAD_A, q_mvar=0.0), load_b],
    )


def _hand_options(cap: float | None) -> MarketZonalOptions:
    """The A-B corridor at ``cap`` MW, or no corridor at all when ``cap`` is ``None``."""
    if cap is None:
        return MarketZonalOptions()
    return MarketZonalOptions(corridors=[CorridorLimit(zone1="A", zone2="B", cap_mw=cap)])


def _solve_hand(cap: float | None = BRANCH_RATING, **kwargs: object) -> MarketZonalResult:
    return solve_zonal(Scenario(network=_hand_network(**kwargs)), _hand_options(cap))  # type: ignore[arg-type]


_Row = TypeVar("_Row", GenDispatchResult, GenRedispatchResult, LoadDispatchResult)


def _by_id(rows: Sequence[_Row]) -> dict[str, _Row]:
    """Rows keyed by their own id — every row family in this result is id-keyed, so a test that
    looks one up by name never depends on row order."""
    return {row.id: row for row in rows}


def _settlement_from_result_alone(result: MarketZonalResult) -> tuple[float, float]:
    """Both sides of the settlement identity, computed from ``result`` and nothing else.

    This function is the whole content of M5's carry-over A23. Before this wave, a market result
    carried prices and quantities but no per-branch surface, so ``-sum_k(mu_k * f_k)`` — the
    identity's right-hand side — could not be recomputed from a result object at all; the only way
    to check it was to keep the solver's own duals alive and re-derive the flows, which is a second
    solve wearing a disguise. :attr:`~mambo_power.results.MarketZonalResult.branches` closes that,
    and this function proves it closed: it touches ``buses``, ``loads_final``, ``generators_final``
    and ``branches``, and imports nothing.

    Returns ``(price_quantity_side, flow_dual_side)``. The identity holds on a network with no bus
    shunt conductance and no phase-shifting transformer; where either exists the merchandising
    surplus also carries that unsettled withdrawal from the network itself, and the two sides
    differ by exactly it (:mod:`mambo_power.results.multiperiod` states the general form). That is
    why the fixtures asserted against below are the hand network and case30, and not case300 —
    whose ``g_shunt`` is the one non-zero one this repository ships.
    """
    lmp = {row.id: row.lmp for row in result.buses}
    load_payment = sum(lmp[row.bus] * row.p_mw for row in result.loads_final)
    generator_receipts = sum(lmp[row.bus] * row.p_mw for row in result.generators_final)
    flow_dual_side = -sum(row.flow_limit_dual * row.p_from_mw for row in result.branches)
    return load_payment - generator_receipts, flow_dual_side


# ================================================================================================
# The hand fixture: AC-5's hand-derived leg
# ================================================================================================


def test_a_corridor_at_the_true_rating_sells_a_schedule_the_network_can_carry() -> None:
    """Derivation §2 and §5 together: with the corridor capped at exactly the physical tie's
    rating (20 MW), the zonal clearing's schedule is already network-feasible, so the redispatch
    stage has nothing to do and the operator pays nothing.

    Every number is the record's: zone prices ``(10, 50)`` (§2's ``λ_A``/``λ_B``), zonal dispatch
    ``(70, 10)`` (§2), final LMPs ``(10, 10, 50)`` and final dispatch ``(70, 10)`` (§5, computed
    there by ``market.solve_nodal`` on the same physical network and shown reactance-independent).
    That the zonal and final points coincide is §5's own observation about this fixture — zone A's
    only internal branch is unrated and zone B is a single bus, so it has zero zonal relaxation gap
    by construction — which makes ``redispatch_payment == 0`` a derived consequence rather than a
    number read off the code.
    """
    result = _solve_hand(cap=BRANCH_RATING)
    assert result.status == "Optimal"

    assert [row.id for row in result.zones] == ["A", "B"]
    assert [row.price for row in result.zones] == pytest.approx([10.0, 50.0], abs=EXACT_ATOL)
    zonal = _by_id(result.generators)
    assert zonal["genA"].p_mw == pytest.approx(70.0, abs=EXACT_ATOL)
    assert zonal["genB"].p_mw == pytest.approx(10.0, abs=EXACT_ATOL)

    final = _by_id(result.generators_final)
    assert final["genA"].p_mw == pytest.approx(70.0, abs=EXACT_ATOL)
    assert final["genB"].p_mw == pytest.approx(10.0, abs=EXACT_ATOL)
    lmp = {row.id: row.lmp for row in result.buses}
    assert lmp["bus1"] == pytest.approx(10.0, abs=EXACT_ATOL)
    assert lmp["bus2"] == pytest.approx(10.0, abs=EXACT_ATOL)
    assert lmp["bus3"] == pytest.approx(50.0, abs=EXACT_ATOL)

    for row in result.redispatch_generators:
        assert row.delta_up_mw == pytest.approx(0.0, abs=EXACT_ATOL)
        assert row.delta_down_mw == pytest.approx(0.0, abs=EXACT_ATOL)
    assert result.redispatch_payment == pytest.approx(0.0, abs=EXACT_ATOL)
    assert result.welfare_gap == pytest.approx(0.0, abs=EXACT_ATOL)


def test_an_overstated_corridor_sells_a_schedule_the_network_cannot_carry() -> None:
    """The hand-derived redispatch case, and the one AC-5 asks to be derived and pinned.

    The corridor is declared at 30 MW while the physical tie ``br23`` is still rated 20 — the
    honest picture of a zonal market whose transfer capacity overstates what the grid delivers.

    *Zonal stage* (derivation §3, the copper-plate branch: 30 MW exceeds the 30 MW zone B would
    ever import, so the corridor never binds and the two balance rows collapse into one): merit
    order against ``c_A = 10 < c_B = 50`` gives ``p_A = 80``, ``p_B = 0``, ``f_AB = 30``, both zone
    prices ``10``, generation cost ``10·80 + 50·0 = 800``.

    *Final stage* (derivation §5, the nodal reference with ``br23`` rated 20): ``p_A = 70``,
    ``p_B = 10``, LMPs ``(10, 10, 50)``, generation cost ``10·70 + 50·10 = 1200``.

    So, by hand, from those two:

    * ``redispatch_payment = cost(final) - cost(zonal) = 1200 - 800 = 400`` — no bid loads here, so
      the curtailment term is zero and the whole payment is the extra generation cost.
    * ``generation_cost_gap = cost(zonal) - cost(nodal) = 800 - 1200 = -400`` — **negative**, which
      is the field's not-sign-constrained warning made concrete on a two-line fixture: the zonal
      clearing is welfare-better *and* generation-cheaper here, and neither implies the other.
    * ``welfare_gap = 0`` — no elastic demand, so welfare is ``-cost`` at both points, and D1's
      theorem makes the final cost the nodal cost.
    * ``welfare(zonal) - welfare(nodal) = -800 - (-1200) = 400`` — equal to the payment, which is
      the identity the module docstring claims and the relaxation argument predicts.
    """
    result = _solve_hand(cap=30.0)
    assert result.status == "Optimal"

    assert [row.price for row in result.zones] == pytest.approx([10.0, 10.0], abs=EXACT_ATOL)
    zonal, final = _by_id(result.generators), _by_id(result.generators_final)
    assert zonal["genA"].p_mw == pytest.approx(80.0, abs=EXACT_ATOL)
    assert zonal["genB"].p_mw == pytest.approx(0.0, abs=EXACT_ATOL)
    assert final["genA"].p_mw == pytest.approx(70.0, abs=EXACT_ATOL)
    assert final["genB"].p_mw == pytest.approx(10.0, abs=EXACT_ATOL)

    moves = _by_id(result.redispatch_generators)
    assert moves["genA"].delta_down_mw == pytest.approx(10.0, abs=EXACT_ATOL)
    assert moves["genA"].delta_up_mw == pytest.approx(0.0, abs=EXACT_ATOL)
    assert moves["genB"].delta_up_mw == pytest.approx(10.0, abs=EXACT_ATOL)
    assert moves["genB"].delta_down_mw == pytest.approx(0.0, abs=EXACT_ATOL)

    assert result.redispatch_payment == pytest.approx(400.0, abs=EXACT_ATOL)
    assert result.generation_cost_gap == pytest.approx(-400.0, abs=EXACT_ATOL)
    assert result.welfare_gap == pytest.approx(0.0, abs=EXACT_ATOL)


def test_the_three_figures_are_three_different_numbers_on_the_hand_fixture() -> None:
    """AC-5(b)'s hand leg. The three gap figures are separate fields carrying separate meanings,
    and on the overstated-corridor fixture they take three visibly different values — ``+400``
    (a settlement), ``0`` (the exactness row) and ``-400`` (an unsigned diagnostic). A result type
    that conflated any two of them could not produce this triple, and neither could a chain that
    computed ``welfare_gap`` from the zonal point instead of the final one.
    """
    result = _solve_hand(cap=30.0)
    figures = (result.redispatch_payment, result.welfare_gap, result.generation_cost_gap)
    assert figures == pytest.approx((400.0, 0.0, -400.0), abs=EXACT_ATOL)
    assert len({round(value, 6) for value in figures}) == 3


def test_the_settlement_identity_closes_on_the_hand_fixture_from_the_result_alone() -> None:
    """AC-5(c) on hand-checkable numbers. At the final point the loads pay
    ``10·50 + 50·30 = 2000``, the generators receive ``10·70 + 50·10 = 1200``, so the operator's
    surplus is ``800``; the only binding branch is ``br23``, carrying 20 MW at a flow-limit dual
    of ``-40`` (derivation §2's corridor dual ``ν = c_B - c_A = 40``, in the row-dual sign
    convention), so ``-sum_k(mu_k * f_k) = -(-40 · 20) = 800``. Both sides come out of the result
    object, via :func:`_settlement_from_result_alone`.
    """
    result = _solve_hand(cap=30.0)
    price_quantity, flow_dual = _settlement_from_result_alone(result)
    assert price_quantity == pytest.approx(800.0, abs=EXACT_ATOL)
    assert flow_dual == pytest.approx(800.0, abs=EXACT_ATOL)


def test_the_piecewise_bid_variant_prices_zone_b_at_the_bid_not_the_local_generator() -> None:
    """Derivation §6, run through the whole chain: zone B's fixed load becomes a flat 45 $/MWh
    piecewise bid for up to 30 MW. Since ``c_B = 50 > 45`` the local generator is never worth
    running, so the corridor-capped 20 MW of cheap imports is all zone B gets, its served demand
    is interior (20 < 30) and its own stationarity sets the zone price at the **bid** value 45,
    not at ``c_B``. This is also the file's only piecewise curve, so it is what exercises the
    piecewise branch of the module's cost/value evaluators end to end.
    """
    result = _solve_hand(cap=BRANCH_RATING, bid_load=True)
    assert result.status == "Optimal"
    assert [row.price for row in result.zones] == pytest.approx([10.0, 45.0], abs=EXACT_ATOL)
    assert _by_id(result.generators)["genA"].p_mw == pytest.approx(70.0, abs=EXACT_ATOL)
    assert _by_id(result.generators)["genB"].p_mw == pytest.approx(0.0, abs=EXACT_ATOL)
    assert _by_id(result.loads)["loadB"].p_mw == pytest.approx(20.0, abs=EXACT_ATOL)


# ================================================================================================
# The real fixtures: AC-4 and AC-5
# ================================================================================================


def _elastic_zoned_network(case: str) -> Network:
    """A rated, zone-promoted, partly-elastic copy of ``case`` — the wave's standard multi-zone
    fixture, assembled only from the committed factories.

    Ratings come from ``tests/_rated.py``, zones from ``tests/_zones.py`` (a no-op on case300,
    which ships four real ones), bids from ``tests/_bids.py``. Five loads get bids and two of those
    get the *interior* derivation, so served demand clears strictly inside its own bounds and
    therefore actually moves between the zonal and final points — the same construction S4's own
    redispatch tests use, and for the same reason.
    """
    net = rated_network(promote_areas_to_zones(load_matpower(FIXTURES_DIR / f"{case}.m")))
    bid_ids = [ld.id for ld in net.loads if ld.p_mw > 0][:5]
    return with_bids(net, bid_ids, interior_load_ids=bid_ids[:2])


def _cleared(case: str) -> tuple[Network, MarketZonalResult, MarketNodalResult]:
    """``(network, solve_zonal result, solve_nodal result)`` on ``case``, corridors derived from
    the fixture's own cut-set ratings by ``tests/_zones.py``."""
    net = _elastic_zoned_network(case)
    caps = corridors(net)
    options = MarketZonalOptions(
        corridors=[CorridorLimit(zone1=z1, zone2=z2, cap_mw=cap) for (z1, z2), cap in caps.items()]
    )
    scenario = Scenario(network=net)
    return net, solve_zonal(scenario, options), solve_nodal(scenario)


@pytest.fixture(scope="module")
def case30() -> tuple[Network, MarketZonalResult, MarketNodalResult]:
    return _cleared("case30")


@pytest.fixture(scope="module")
def case300() -> tuple[Network, MarketZonalResult, MarketNodalResult]:
    return _cleared("case300")


def _quantities(
    result: MarketZonalResult, nodal: object
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """``(p_final, p_nodal, d_final, d_nodal)`` gathered **by id**, so the comparison never rests
    on two result objects happening to order their rows the same way."""
    final_p = {row.id: row.p_mw for row in result.generators_final}
    nodal_p = {row.id: row.p_mw for row in nodal.generators}
    final_d = {row.id: row.p_mw for row in result.loads_final}
    nodal_d = {row.id: row.p_mw for row in nodal.loads}
    gen_ids, load_ids = sorted(final_p), sorted(final_d)
    return (
        np.array([final_p[i] for i in gen_ids]),
        np.array([nodal_p[i] for i in gen_ids]),
        np.array([final_d[i] for i in load_ids]),
        np.array([nodal_d[i] for i in load_ids]),
    )


@pytest.mark.parametrize(
    ("fixture_name", "atol"),
    [("case30", CASE30_QUANTITY_ATOL), ("case300", CASE300_QUANTITY_ATOL)],
)
def test_ac4_the_redispatched_point_is_the_nodal_optimum(
    fixture_name: str, atol: float, request: pytest.FixtureRequest
) -> None:
    """AC-4's primal clause on both multi-zone fixtures, with elastic bids in play: the final
    dispatch and the final served demand agree with ``market.solve_nodal`` on the same scenario.

    This is design decision D1's theorem measured on real data. It is not a foregone conclusion
    from the code's structure: the redispatch LP reaches this point through delta columns bounded
    by a *shifted* box, starting from a zonal schedule that (on case30) is tens of MW away, while
    ``dc_opf`` reaches it through single dispatch columns from nothing. Agreement is a statement
    about the two LPs' optima, which is why it is asserted to a measured tolerance and never
    bitwise (spec A3).
    """
    _net, result, nodal = request.getfixturevalue(fixture_name)
    assert result.status == "Optimal"
    p_final, p_nodal, d_final, d_nodal = _quantities(result, nodal)
    assert_allclose(p_final, p_nodal, rtol=0.0, atol=atol)
    assert_allclose(d_final, d_nodal, rtol=0.0, atol=atol)


def test_ac4_final_lmps_equal_the_nodal_lmps_on_case30(
    case30: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """AC-4's price clause, asserted tightly on the fixture where it can be (A20). The final LMPs
    come from ``lmp_decomposition`` over the *redispatch* LP's balance and flow-limit duals; the
    reference comes from the same decomposition over ``dc_opf``'s. Measured agreement: 8.9e-6
    $/MWh on prices of order 6.8."""
    _net, result, nodal = case30
    final = {row.id: row.lmp for row in result.buses}
    reference = {row.id: row.lmp for row in nodal.buses}
    assert set(final) == set(reference)
    ids = sorted(final)
    assert_allclose(
        np.array([final[i] for i in ids]),
        np.array([reference[i] for i in ids]),
        rtol=0.0,
        atol=CASE30_LMP_ATOL,
    )


def _at_rating_branch_indices(
    net: Network, result: MarketZonalResult, arr: NetworkArrays
) -> tuple[list[int], set[str]]:
    """``(column indices into the PTDF, ids)`` of the branches sitting exactly at their rating at
    the chain's final point, in ``arr.branch_ids`` order."""
    rating = {br.id: br.rating_mva for br in net.branches if br.rating_mva is not None}
    flow = {row.id: row.p_from_mw for row in result.branches}
    ids = {
        bid
        for bid in arr.branch_ids
        if bid in rating and abs(abs(flow[bid]) - rating[bid]) <= CASE300_QUANTITY_ATOL
    }
    return [k for k, bid in enumerate(arr.branch_ids) if bid in ids], ids


def _congestion_residual_off(
    difference: np.ndarray, ptdf_matrix: np.ndarray, branch_rows: Sequence[int]
) -> float:
    """Sup-norm of what is left of ``difference`` (a per-bus congestion vector) after the best fit
    by flow duals living **only** on ``branch_rows``.

    A congestion component is by construction ``PTDFᵀ mu`` for a dual vector ``mu`` supported on the
    binding branches, so two solves' congestion components differ by ``PTDFᵀ(mu_a − mu_b)``. Asking
    which branch rows can reproduce that difference asks *where the two solvers disagreed*, and a
    least-squares fit answers it without either solver having to hand over its dual vector.
    """
    if not branch_rows:
        return float(np.max(np.abs(difference)))
    columns = ptdf_matrix[list(branch_rows), :].T
    coefficients, *_ = np.linalg.lstsq(columns, difference, rcond=None)
    return float(np.max(np.abs(columns @ coefficients - difference)))


def test_ac4_case300_prices_agree_except_across_the_degenerate_face(
    case300: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """AC-4's price clause on case300, where a flat LMP tolerance cannot be asserted (A20) — so
    the disagreement is *located* instead of excused.

    case300's nodal optimum is **primal-degenerate**: strictly more branches sit exactly at their
    rating than carry a nonzero flow-limit dual, so the optimal face has several vertices and the
    chain and ``solve_nodal`` legitimately select different ones. Measured, their LMPs differ by up
    to 0.319 $/MWh on a ~41 $/MWh system. The earlier form of this test asserted only ``priced ⊆
    at_rating`` from the chain's own primal and dual rows — that is complementary slackness, which
    every optimal solve satisfies including one that landed on the wrong point, so it could not
    distinguish agreement from a defect (audit F2). Three clauses replace it, and all three read a
    **second, independent** solve:

    1. **The energy components agree** to :data:`CASE300_ENERGY_ATOL`. Degeneracy is freedom in the
       *dual of the flow rows*; the balance dual is the system-wide price level and every vertex of
       the optimal face shares it. This is the price comparison case300 was missing.
    2. **The congestion difference is confined to the at-rating branches** — re-expressible as flow
       duals on those seven alone, to :data:`CASE300_DEGENERATE_FACE_ATOL` in a 300-dimensional
       space. Prices differ *only* in how a fixed amount of congestion is attributed among branches
       that are all genuinely binding.
    3. **The unpriced part of that face carries the disagreement.** Refit over the branches the
       chain actually prices and at least :data:`CASE300_FACE_IS_LOAD_BEARING_ATOL` of the
       difference survives — so clause 2 is a real constraint on where the difference lives, not a
       subspace large enough to absorb anything. Measured, the fit puts −0.319 $/MWh on
       ``branch-48`` and −0.319 on ``branch-360``: one solve prices the pair one way round and the
       other the other way, which is the degeneracy, named.
    """
    net, result, nodal = case300
    arr = NetworkArrays.from_network(net)
    ptdf_matrix = ptdf(arr)

    chain = {row.id: row for row in result.buses}
    reference = {row.id: row for row in nodal.buses}
    assert set(chain) == set(reference)
    bus_ids = list(arr.bus_ids)

    # 1. the price level itself, against an independent solve.
    assert_allclose(
        np.array([chain[i].energy for i in bus_ids]),
        np.array([reference[i].energy for i in bus_ids]),
        rtol=0.0,
        atol=CASE300_ENERGY_ATOL,
    )

    at_rating_rows, at_rating = _at_rating_branch_indices(net, result, arr)
    priced = {row.id for row in result.branches if row.flow_limit_dual != 0.0}
    assert priced, "case300 should have at least one congested branch at the final point"
    assert priced <= at_rating, f"priced but not at rating: {sorted(priced - at_rating)}"
    assert len(at_rating) > len(priced), (
        "expected strictly more at-rating branches than priced ones -- that inequality *is* the "
        f"degeneracy A20 records, and clause 3 below has nothing to measure without it; got "
        f"{len(at_rating)} at rating and {len(priced)} priced"
    )

    difference = np.array(
        [chain[i].congestion - reference[i].congestion for i in bus_ids], dtype=float
    )
    assert np.max(np.abs(difference)) > CASE300_FACE_IS_LOAD_BEARING_ATOL, (
        "the two solves' congestion components agree on this build -- clauses 2 and 3 are then "
        "vacuous and AC-4's price clause should simply be asserted flat on case300"
    )

    # 2. the disagreement lives on the at-rating branches, and
    # 3. specifically on the ones neither solve had to price.
    assert (
        _congestion_residual_off(difference, ptdf_matrix, at_rating_rows)
        <= CASE300_DEGENERATE_FACE_ATOL
    ), "the congestion difference is not explained by duals on the at-rating branches"
    priced_rows = [k for k, bid in enumerate(arr.branch_ids) if bid in priced]
    assert (
        _congestion_residual_off(difference, ptdf_matrix, priced_rows)
        > CASE300_FACE_IS_LOAD_BEARING_ATOL
    ), (
        "the priced branches alone reproduce the difference -- then clause 2 says nothing about "
        "the degenerate face and this test is fitting noise"
    )


@pytest.mark.parametrize("fixture_name", ["case30", "case300"])
def test_ac4_welfare_gap_is_zero(fixture_name: str, request: pytest.FixtureRequest) -> None:
    """AC-4's ``welfare_gap ~ 0`` clause on both fixtures. Under D1 the redispatch objective is the
    true welfare function over nodal's exact feasible set, so the gap is zero by theorem; measured
    residuals are 1.4e-14 and 8.3e-13 relative. Pinned relative because the two fixtures' welfare
    differs by an order of magnitude, and asserted on both because this is the one field that would
    move if the redispatch LP's feasible set ever stopped being nodal's.
    """
    net, result, _nodal = request.getfixturevalue(fixture_name)
    assert result.status == "Optimal"
    assert abs(result.welfare_gap) <= WELFARE_REL_TOL * abs(_welfare(net, result, final=True))


def _welfare(net: Network, result: MarketZonalResult, *, final: bool) -> float:
    """Welfare (bid value served minus generation cost, $/h) at either of the result's two dispatch
    layers, evaluated on the network's own true curves.

    Deliberately re-extracts the curves from the network through the same public extractors the
    chain uses (:func:`~mambo_power.opf.gen_cost_coeffs`,
    :func:`~mambo_power.market.nodal.load_bid_coeffs`) and evaluates them with the module's own
    helpers, so this is the same definition of welfare the fields under test use — the tests below
    are about the *relationship* between two welfare numbers, and a second, subtly different
    definition of welfare would test nothing but the difference between the definitions.
    """
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    bid_coeffs, pwl_bids = load_bid_coeffs(net, arr)
    elastic = sorted(set(bid_coeffs) | set(pwl_bids))
    gen_rows = result.generators_final if final else result.generators
    load_rows = result.loads_final if final else result.loads
    p_by_id = {row.id: row.p_mw for row in gen_rows}
    d_by_id = {row.id: row.p_mw for row in load_rows}
    p_mw = np.array([p_by_id[gen_id] for gen_id in arr.gen_ids])
    d_mw = np.array([d_by_id[arr.load_ids[i]] for i in elastic])
    return _demand_value(bid_coeffs, pwl_bids, d_mw, elastic) - _generation_cost(
        cost_coeffs, pwl_costs, p_mw
    )


def _nodal_welfare(net: Network, nodal: MarketNodalResult) -> float:
    """Welfare at the nodal optimum, evaluated on the same true curves and by the same helpers as
    :func:`_welfare` — so AC-5(a)'s inequality compares two numbers that differ only in the
    dispatch they are evaluated at, never in how welfare is defined."""
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    bid_coeffs, pwl_bids = load_bid_coeffs(net, arr)
    elastic = sorted(set(bid_coeffs) | set(pwl_bids))
    p_by_id = {row.id: row.p_mw for row in nodal.generators}
    d_by_id = {row.id: row.p_mw for row in nodal.loads}
    p_mw = np.array([p_by_id[gen_id] for gen_id in arr.gen_ids])
    d_mw = np.array([d_by_id[arr.load_ids[i]] for i in elastic])
    return _demand_value(bid_coeffs, pwl_bids, d_mw, elastic) - _generation_cost(
        cost_coeffs, pwl_costs, p_mw
    )


@pytest.mark.parametrize("fixture_name", ["case30", "case300"])
def test_ac5a_the_zonal_clearing_is_a_relaxation_so_its_welfare_is_never_lower(
    fixture_name: str, request: pytest.FixtureRequest
) -> None:
    """AC-5(a). The zonal LP drops every branch flow row and replaces them with corridor bounds
    that do not imply them, so its feasible set contains the nodal one and its optimal welfare can
    only be at least nodal's. The inequality holds on both fixtures; on rated case30 — where two
    of three corridors bind (S3 measured (1,2) at 1.52 and (2,3) at 19.46 MVA) — it holds
    **strictly**, with a real amount of redispatch behind it rather than a rounding-scale
    difference.
    """
    net, result, nodal = request.getfixturevalue(fixture_name)
    zonal_welfare = _welfare(net, result, final=False)
    final_welfare = _welfare(net, result, final=True)
    slack = WELFARE_REL_TOL * abs(zonal_welfare)
    # AC-5(a) literally: against nodal, from an independent ``solve_nodal`` on the same scenario.
    assert zonal_welfare >= _nodal_welfare(net, nodal) - slack
    # ...and against the chain's own final point, which D1 makes the same number. Both are stated
    # because they are different claims: the first is the relaxation argument, the second is the
    # relaxation argument *plus* D1, and a regression could break either alone.
    assert zonal_welfare >= final_welfare - slack
    if fixture_name == "case30":
        margin = zonal_welfare - final_welfare
        assert margin > 1.0, f"expected a strict, non-trivial relaxation gap; got {margin} $/h"
        volume = sum(
            row.delta_up_mw + row.delta_down_mw for row in result.redispatch_generators
        ) + sum(row.delta_restore_mw + row.delta_curtail_mw for row in result.redispatch_loads)
        assert volume > 1.0, f"a strict welfare gap with no redispatch behind it: {volume} MW"


def test_ac5a_redispatch_payment_is_the_welfare_the_zonal_clearing_could_not_deliver(
    case30: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """The settlement figure tied back to the relaxation argument that bounds its sign.
    ``redispatch_payment`` is defined as ``[cost(final) - cost(zonal)] + [value(d_zonal) -
    value(d_final)]`` — extra generation cost plus curtailment compensation at bid value — which
    rearranges exactly to ``welfare(zonal) - welfare(final)``. Asserting the rearrangement holds
    against welfare computed here, from the result's own two dispatch layers, is what makes the
    field's non-negativity a consequence of AC-5(a) rather than a separate hope. Measured residual:
    5.6e-12 $/h against a payment of 14.5.
    """
    net, result, _nodal = case30
    expected = _welfare(net, result, final=False) - _welfare(net, result, final=True)
    assert result.redispatch_payment == pytest.approx(expected, abs=IDENTITY_ATOL)
    assert result.redispatch_payment > 0.0


def test_ac5b_the_three_figures_differ_on_case30(
    case30: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """AC-5(b) on the real fixture: three fields, three different numbers, each with its own
    meaning intact.

    Measured on this build: ``redispatch_payment = +14.51`` (a settlement the operator pays),
    ``welfare_gap = -4.1e-9`` (zero, the exactness row) and ``generation_cost_gap = -13.57``
    (a diagnostic, negative here — the zonal clearing's schedule is genuinely *cheaper* to generate
    than nodal's while being infeasible, exactly the inversion research §4(b) warned a conflated
    field would hide). The three are asserted apart by their own scale, not by a shared epsilon:
    the payment is strictly positive, the cost gap strictly negative, and the welfare gap is
    negligible against both.
    """
    net, result, _nodal = case30
    scale = abs(_welfare(net, result, final=True))
    assert result.redispatch_payment > 1.0
    assert result.generation_cost_gap < -1.0
    assert abs(result.welfare_gap) <= WELFARE_REL_TOL * scale
    assert result.redispatch_payment != pytest.approx(result.generation_cost_gap, abs=1.0)


def test_ac5c_the_settlement_identity_closes_from_the_result_object_alone_on_case30(
    case30: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """AC-5(c) — M5's carry-over A23, closed on real fixture data.

    Both sides of the identity come out of :func:`_settlement_from_result_alone`, which reads only
    the result's ``buses``, ``loads_final``, ``generators_final`` and ``branches`` rows: no second
    solve, no PTDF, nothing from :mod:`mambo_power.numerics` or :mod:`mambo_power.opf`. Measured
    closure: 8.5e-14 $/h against a congestion rent of 31.85.
    """
    _net, result, _nodal = case30
    price_quantity, flow_dual = _settlement_from_result_alone(result)
    assert price_quantity == pytest.approx(flow_dual, abs=IDENTITY_ATOL)
    assert abs(flow_dual) > 1.0, "a congestion rent of zero would make this identity vacuous"


# ================================================================================================
# Feasibility readback (A21): flows respect ratings *and* the point balances
# ================================================================================================


def _readback(net: Network, result: MarketZonalResult) -> tuple[float, float]:
    """``(max overload MW, energy-balance residual MW)`` for the result's final point, read back
    through ``pf.dc`` on a copy of ``net`` carrying that dispatch and that served demand.

    Both halves, never just the first: ``pf.dc`` pins the slack bus at angle 0 and lets it absorb
    whatever mismatch the declared injections carry, so an **unbalanced** dispatch still produces a
    finite, possibly rating-respecting flow vector (A21 — S4's own sabotage sweep found exactly
    that shape of defect passing a flow-only readback on case30).
    """
    dispatched = net.model_copy(deep=True)
    p_by_id = {row.id: row.p_mw for row in result.generators_final}
    for gen in dispatched.generators:
        if gen.id in p_by_id:
            gen.p_mw = p_by_id[gen.id]
    d_by_id = {row.id: row.p_mw for row in result.loads_final}
    for load in dispatched.loads:
        if load.id in d_by_id:
            load.p_mw = d_by_id[load.id]
    arr = NetworkArrays.from_network(dispatched)
    flow_mw = np.abs(pfdc.solve(arr).p_from_pu) * arr.base_mva
    overload = float(np.nanmax(flow_mw - arr.rating_pu * arr.base_mva))
    balance = float(
        sum(p_by_id.values())
        - sum(load.p_mw for load in dispatched.loads)
        - float(np.sum(arr.g_shunt_pu) * arr.base_mva)
    )
    return overload, balance


@pytest.mark.parametrize("fixture_name", ["case30", "case300"])
def test_the_final_point_is_pf_dc_feasible_and_closes_the_energy_balance(
    fixture_name: str, request: pytest.FixtureRequest
) -> None:
    """W5(a) read back through an independent code path: the redispatched dispatch, carried on the
    network and solved by ``pf.dc``, overloads no branch rating — and, per A21, also balances.
    Measured: 2.0e-14 MW of overload and 0.0 MW of imbalance on case30; 5.5e-10 and 2.5e-10 on
    case300."""
    net, result, _nodal = request.getfixturevalue(fixture_name)
    overload, balance = _readback(net, result)
    assert overload <= FLOW_TOL_MW
    assert abs(balance) <= FLOW_TOL_MW


def test_the_branch_rows_are_the_flows_pf_dc_computes_at_the_final_dispatch(
    case30: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """The first market result to carry branch rows carries the *right* ones: each row's
    ``p_from_mw`` is what ``pf.dc`` — a different code path, built from the B-bus rather than from
    the PTDF the LP used — computes at the same dispatch. Measured: 2.3e-14 MW."""
    net, result, _nodal = case30
    dispatched = net.model_copy(deep=True)
    p_by_id = {row.id: row.p_mw for row in result.generators_final}
    for gen in dispatched.generators:
        if gen.id in p_by_id:
            gen.p_mw = p_by_id[gen.id]
    d_by_id = {row.id: row.p_mw for row in result.loads_final}
    for load in dispatched.loads:
        if load.id in d_by_id:
            load.p_mw = d_by_id[load.id]
    arr = NetworkArrays.from_network(dispatched)
    expected = pfdc.solve(arr).p_from_pu * arr.base_mva
    by_id = {row.id: row.p_from_mw for row in result.branches}
    assert_allclose(
        np.array([by_id[branch_id] for branch_id in arr.branch_ids]),
        expected,
        rtol=0.0,
        atol=FLOW_TOL_MW,
    )


# ================================================================================================
# Result shape, curve evaluation, and the error paths
# ================================================================================================


def test_every_row_family_covers_its_whole_entity_set(
    case30: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """Each row list is id-keyed and complete: one zone price per zone, one row per generator in
    each of the three generator families, one row per load in each of the three load families
    (bid or not — a non-bid load still has a served quantity and still enters the settlement sum),
    one bus row and one branch row per element ``NetworkArrays`` keeps."""
    net, result, _nodal = case30
    arr = NetworkArrays.from_network(net)
    assert [row.id for row in result.zones] == sorted(set(zone_partition(net, arr).values()))
    for rows in (result.generators, result.generators_final, result.redispatch_generators):
        assert [row.id for row in rows] == list(arr.gen_ids)
    for rows in (result.loads, result.loads_final, result.redispatch_loads):
        assert [row.id for row in rows] == list(arr.load_ids)
    assert [row.id for row in result.buses] == list(arr.bus_ids)
    assert [row.id for row in result.branches] == list(arr.branch_ids)


def test_the_deltas_are_nonnegative_one_sided_and_reconstruct_the_final_point(
    case30: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """The redispatch rows are the move between the result's own two dispatch layers, not an
    independent report of it: ``p_final == p_zonal + delta_up - delta_down`` exactly, both fields
    are nonnegative, and at most one of each pair is nonzero (the netted canonical representative
    ``RedispatchSolution`` reports). Same on the demand side."""
    _net, result, _nodal = case30
    zonal_p = {row.id: row.p_mw for row in result.generators}
    final_p = {row.id: row.p_mw for row in result.generators_final}
    for row in result.redispatch_generators:
        assert row.delta_up_mw >= 0.0 and row.delta_down_mw >= 0.0
        assert min(row.delta_up_mw, row.delta_down_mw) == pytest.approx(0.0, abs=EXACT_ATOL)
        assert final_p[row.id] == pytest.approx(
            zonal_p[row.id] + row.delta_up_mw - row.delta_down_mw, abs=EXACT_ATOL
        )
    zonal_d = {row.id: row.p_mw for row in result.loads}
    final_d = {row.id: row.p_mw for row in result.loads_final}
    moved = 0.0
    for row in result.redispatch_loads:
        assert row.delta_restore_mw >= 0.0 and row.delta_curtail_mw >= 0.0
        assert min(row.delta_restore_mw, row.delta_curtail_mw) == pytest.approx(0.0, abs=EXACT_ATOL)
        assert final_d[row.id] == pytest.approx(
            zonal_d[row.id] + row.delta_restore_mw - row.delta_curtail_mw, abs=EXACT_ATOL
        )
        moved += row.delta_restore_mw + row.delta_curtail_mw
    assert moved > 0.0, (
        "no load moved at all -- the interior bids in this fixture exist precisely so that "
        "redispatch_payment's curtailment term is not multiplied by zero here"
    )


def test_the_curve_evaluators_agree_with_the_figures_the_builders_report(
    case30: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """The module evaluates the true cost and bid curves itself, so that its three points (zonal,
    final, nodal) are measured the same way; the LP builders compute their own figures through a
    completely different construction — the polynomial terms from the solved dispatch, the
    piecewise terms from the epigraph/hypograph *columns* HiGHS returns. This asserts the two
    constructions agree, which is what makes using the module's own evaluator a shared definition
    rather than a private one. Measured residual on this build: identically 0.0 for all three.
    """
    net, _result, _nodal = case30
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    bid_coeffs, pwl_bids = load_bid_coeffs(net, arr)
    elastic = sorted(set(bid_coeffs) | set(pwl_bids))
    caps = corridors(net)
    zonal = zonal_dc_opf(
        arr,
        cost_coeffs,
        zone_partition(net, arr),
        caps,
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids or None,
    )
    final = redispatch_dc_opf(
        arr,
        cost_coeffs,
        zonal.dispatch_mw,
        zonal.demand_dispatch_mw,
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids or None,
    )
    assert _generation_cost(cost_coeffs, pwl_costs, zonal.dispatch_mw) == pytest.approx(
        zonal.objective_cost, rel=1e-12
    )
    assert _generation_cost(cost_coeffs, pwl_costs, final.dispatch_mw) == pytest.approx(
        final.objective_cost, rel=1e-12
    )
    assert _demand_value(bid_coeffs, pwl_bids, final.demand_dispatch_mw, elastic) == pytest.approx(
        final.demand_value, rel=1e-12
    )


def test_the_piecewise_evaluator_agrees_with_the_builders_on_a_piecewise_curve() -> None:
    """The agreement above runs on quadratic curves, because that is what every committed fixture
    carries. The piecewise branch of the evaluators — which reproduces the epigraph's "maximum over
    the segments' affine extensions" rather than interpolating — is exercised here instead, on the
    derivation §6 network's flat piecewise bid, against the value ``redispatch_dc_opf`` reads off
    its own hypograph column."""
    net = _hand_network(bid_load=True)
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    bid_coeffs, pwl_bids = load_bid_coeffs(net, arr)
    assert pwl_bids, "this fixture exists to carry a piecewise bid"
    elastic = sorted(set(bid_coeffs) | set(pwl_bids))
    final = redispatch_dc_opf(
        arr,
        cost_coeffs,
        np.array([70.0, 0.0]),
        np.array([20.0]),
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids or None,
    )
    assert final.status == "Optimal"
    assert _demand_value(bid_coeffs, pwl_bids, final.demand_dispatch_mw, elastic) == pytest.approx(
        final.demand_value, abs=EXACT_ATOL
    )


def test_the_result_round_trips_through_json(
    case30: tuple[Network, MarketZonalResult, MarketNodalResult],
) -> None:
    """``results/``'s standing contract, on the wave's new result type: exact JSON round trip,
    unknown fields rejected, non-finite numbers rejected."""
    _net, result, _nodal = case30
    assert MarketZonalResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValueError, match="[Ee]xtra"):
        MarketZonalResult.model_validate({**result.model_dump(), "not_a_field": 1})


def test_the_options_round_trip_through_json_which_a_tuple_keyed_mapping_would_not() -> None:
    """Why :attr:`~mambo_power.market.zonal.MarketZonalOptions.corridors` is a list of rows rather
    than the ``{(z1, z2): cap}`` mapping the builder takes.

    A pydantic model carrying ``dict[tuple[str, str], float]`` *serialises* — it writes the key
    ``("A", "B")`` as the string ``"A,B"`` — and then refuses to validate that string back into a
    tuple, so the round trip fails one-way and silently looks fine until something reads it. The
    epic's ``jobs`` criterion is exact JSON round-trip on every kind, so the shape stored is the
    one that survives, and :meth:`~mambo_power.market.zonal.MarketZonalOptions.corridor_map`
    derives the mapping on the way to the builder. Both halves are asserted here: the round trip
    holds, and the mapping it produces is the one the builder is handed.
    """
    options = _hand_options(BRANCH_RATING)
    assert MarketZonalOptions.model_validate_json(options.model_dump_json()) == options
    assert options.corridor_map() == {("A", "B"): BRANCH_RATING}


def test_a_bus_with_no_zone_is_rejected_rather_than_defaulted() -> None:
    """A zonal clearing cannot proceed on a partition with a hole: that bus's load and generation
    must enter *some* zone's balance row, and picking one would clear a market for a network the
    caller did not describe. Raised up front, naming the count and the first offender."""
    net = _hand_network()
    net.buses[1].zone = None
    with pytest.raises(ValueError, match="carry no zone"):
        solve_zonal(Scenario(network=net), _hand_options(BRANCH_RATING))


def test_the_shared_guards_fire_before_any_solve() -> None:
    """Cost convexity and bid concavity are the shared extractor's (ADR-008), reached through the
    zonal stage, so ``solve_zonal`` raises exactly what ``solve_nodal`` raises on the same
    network."""
    non_convex = _hand_network()
    non_convex.generators[0].cost = PolynomialCost(coefficients=[-1.0, 10.0, 0.0])
    with pytest.raises(NonConvexCostError):
        solve_zonal(Scenario(network=non_convex), _hand_options(BRANCH_RATING))

    non_concave = _hand_network()
    non_concave.loads[1].bid = PiecewiseBid(points=[(0.0, 0.0), (10.0, 100.0), (20.0, 300.0)])
    with pytest.raises(NonConcaveBidError):
        solve_zonal(Scenario(network=non_concave), _hand_options(BRANCH_RATING))


def test_an_infeasible_zonal_stage_is_reported_not_raised() -> None:
    """No corridor at all means every zone must supply itself. Zone B's generator is capped below
    its own 30 MW of load here, so the zonal clearing has no feasible point — reported through
    ``status``/``message`` with the stage named, never raised (this package's standing
    convention)."""
    result = solve_zonal(Scenario(network=_hand_network(gen_b_p_max=10.0)), MarketZonalOptions())
    assert result.status != "Optimal"
    assert result.message is not None and "zonal clearing stage" in result.message
    assert result.zones == [] and result.branches == []
    assert result.redispatch_payment == 0.0


def test_an_infeasible_redispatch_stage_is_reported_with_its_own_stage_named() -> None:
    """The zonal clearing succeeds — a generous corridor lets zone A's cheap generator serve
    everything — but the physical tie is rated a millionth of a MW, so no redispatch onto the real
    network exists with zone B's local generation capped at 10 MW against its own 30 MW of fixed
    load. (A rating of exactly 0 is rejected by the model's own validator, hence the epsilon; the
    LP sees the same impossibility either way.) The failure is attributed to the stage that
    produced it, which is the whole reason the message names a stage at all."""
    result = solve_zonal(
        Scenario(network=_hand_network(rating=1e-6, gen_b_p_max=10.0)), _hand_options(100.0)
    )
    assert result.status != "Optimal"
    assert result.message is not None and "redispatch stage" in result.message


def test_no_corridors_means_each_zone_supplies_itself() -> None:
    """An empty corridor list is a meaningful market design, not a missing argument: with no
    exchange column the per-zone balance rows decouple entirely and each zone self-supplies, which
    on this fixture drives the two prices to their *most* separated (10 and 50 — the local marginal
    unit in each zone). It is emphatically not the copper plate; only an unbounded corridor is
    (S3's finding A22(i))."""
    result = solve_zonal(Scenario(network=_hand_network()), MarketZonalOptions())
    assert result.status == "Optimal"
    assert [row.price for row in result.zones] == pytest.approx([10.0, 50.0], abs=EXACT_ATOL)
    zonal = _by_id(result.generators)
    assert zonal["genA"].p_mw == pytest.approx(LOAD_A, abs=EXACT_ATOL)
    assert zonal["genB"].p_mw == pytest.approx(LOAD_B, abs=EXACT_ATOL)
