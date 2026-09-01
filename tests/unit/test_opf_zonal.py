"""Unit tests for :mod:`mambo_power.opf.zonal` — the zonal clearing LP/QP (M6 W2, AC-2).

**The oracle is hand-derived, and this file transcribes it.** Every number in the 2-zone/3-bus
section below comes from ``.bionic/docs/record/m6-ac2-derivation.md``, which solves the same LP
three independent ways — by hand from the KKT conditions, through a hand-built
``scipy.optimize.linprog`` formulation, and (for the nodal-reference columns) through this repo's
own pre-existing ``market.solve_nodal`` — and reports them agreeing to the printed precision. No
number here was read off ``zonal_dc_opf``'s own output and pasted back in; that is what makes
these assertions an oracle rather than a change-detector.

The network (derivation §1): bus1 and bus2 in zone ``"A"``, bus3 in zone ``"B"``; the cheap
generator ``genA`` (10 $/MWh) sits at bus1, the expensive ``genB`` (50 $/MWh) at bus3; loads are
50 MW in zone A (at bus2) and 30 MW in zone B. The A-B corridor is capped at 20 MW, which binds,
because zone B would otherwise import all 30 MW of its load. Zone A is deliberately **two** buses
joined by an intra-zone branch: that branch never appears in the zonal LP at all, which is what
makes "no intra-zone flow rows" (design decision D2, b2) a property this fixture can witness
rather than merely assert.

Tolerances are measured, not guessed, and each is stated where it is pinned. Nothing here asserts
bit-equality even where the run happens to be bit-exact — wave M5's macOS CI finding (spec A3) is
that a platform can move the last bits of an LP answer without anything being wrong.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_allclose

import mambo_power.opf as opf_pkg
from mambo_power.io.matpower import load
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    PiecewiseBid,
    PolynomialCost,
    Zone,
)
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import NonConcaveBidError, NonConvexCostError, OpfDcOptions, dc_opf
from mambo_power.opf.zonal import ZonalSolution, zonal_dc_opf
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network
from tests._zones import corridors, promote_areas_to_zones, zone_of_bus

# --- the derivation's own constants, named so a reader can check them against §1 by eye ---------

COST_A = 10.0
"""Zone A's cheap generator's linear cost, $/MWh (derivation §1)."""
COST_B = 50.0
"""Zone B's expensive generator's linear cost, $/MWh (derivation §1)."""
LOAD_A = 50.0
"""Zone A's fixed load, MW, at bus2 (derivation §1)."""
LOAD_B = 30.0
"""Zone B's fixed load, MW, at bus3 (derivation §1)."""
CAP = 20.0
"""The A-B corridor's transfer capacity, MW — chosen in the derivation so that it binds."""
BID_VALUE_B = 45.0
"""The §6 variant's flat bid value in zone B, $/MWh; below ``COST_B`` on purpose."""
BID_QMAX_B = 30.0
"""The §6 variant's bid quantity ceiling, MW."""

EXACT_ATOL = 1e-9
"""Tolerance for the hand-derived 3-bus numbers. The derivation's §7 notes these are exact
rationals that HiGHS lands on bit-for-bit at this scale, and they do so here too (measured: every
residual below is identically 0.0). It is still asserted as a *tolerance* rather than with
``==``: spec A3 and wave M5's macOS CI finding say an LP answer's last bits are a platform
property, and a test that would fail on a last-bit difference is testing the platform. ``1e-9``
against quantities of order 10-1200 is ~11 orders of magnitude tighter than any of the
distinctions being drawn, so it costs the assertions nothing."""

CASE30_DUAL_ATOL = 1e-4
"""Tolerance for case30's zone-price and corridor-dual identities. Measured residuals on this
build: ``|price[1] - price[3]| = 1.54e-6`` across the slack (1,3) corridor, and
``|nu - (price gap)| <= 1.95e-6`` on the two binding ones — HiGHS's own default dual-feasibility
slack (~1e-7 relative to each corridor's flow), reproduced identically on three consecutive runs.
This wave adds no solver-tuning option to tighten it (``OpfDcOptions``' docstring: an option is
added when a caller actually needs one), so the residual is pinned rather than removed. ``1e-4``
leaves ~50x headroom over the largest measured residual while staying ~1200x *below* the
0.1214 $/MWh price separation these tests are drawing a conclusion from — the assertion keeps its
teeth."""

CASE30_RTOL = 1e-9
CASE30_ATOL = 1e-8
"""Tolerance for the degenerate one-zone agreement with :func:`dc_opf` on case30. Measured:
``2.8e-14`` MW on dispatch (rel. ``4.9e-16``), ``1.1e-13`` $ on the objective, and identically
``0.0`` on the price and every generator bound dual. The two builders hand HiGHS *different LPs*
(``dc_opf`` still builds ``n_branch`` unconstrained flow-limit rows this one never does), so the
agreement is a theorem about their optima, not about their floating-point paths — hence a
tolerance, never bit-equality."""


# --- the derivation's 2-zone/3-bus fixture ------------------------------------------------------


def _gen(gen_id: str, bus: str, cost: float) -> Generator:
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=0.0,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=200.0,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        cost=PolynomialCost(coefficients=[cost, 0.0]),
    )


def _two_zone_network(*, bid_load: bool = False, corridor_rating: float | None = None) -> Network:
    """The derivation §1 network. ``bid_load`` swaps zone B's fixed load for §6's flat bid;
    ``corridor_rating`` rates the *physical* branch br23 (used only by the nodal cross-checks —
    the zonal LP never reads a branch rating)."""
    load_b = (
        Load(
            id="loadB",
            bus="bus3",
            p_mw=LOAD_B,
            q_mvar=0.0,
            bid=PiecewiseBid(points=[(0.0, 0.0), (BID_QMAX_B, BID_VALUE_B * BID_QMAX_B)]),
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
            # intra-zone A, deliberately unrated: it never enters the zonal LP at all.
            Branch(id="br12", from_bus="bus1", to_bus="bus2", r=0.0, x=0.1, b=0.0),
            # the physical A-B tie.
            Branch(
                id="br23",
                from_bus="bus2",
                to_bus="bus3",
                r=0.0,
                x=0.1,
                b=0.0,
                rating_mva=corridor_rating,
            ),
        ],
        generators=[_gen("genA", "bus1", COST_A), _gen("genB", "bus3", COST_B)],
        loads=[Load(id="loadA", bus="bus2", p_mw=LOAD_A, q_mvar=0.0), load_b],
    )


TWO_ZONE_COSTS = np.array([[0.0, COST_A, 0.0], [0.0, COST_B, 0.0]])
"""``(n_gen, 3)`` ``[c2, c1, c0]``, generator order ``[genA, genB]``."""
TWO_ZONE_MAP = {"bus1": "A", "bus2": "A", "bus3": "B"}
AB = ("A", "B")


@pytest.fixture
def two_zone() -> NetworkArrays:
    return NetworkArrays.from_network(_two_zone_network())


@pytest.fixture
def two_zone_bid() -> NetworkArrays:
    return NetworkArrays.from_network(_two_zone_network(bid_load=True))


def _solve(arr: NetworkArrays, cap: float, **kwargs: object) -> ZonalSolution:
    return zonal_dc_opf(arr, TWO_ZONE_COSTS, TWO_ZONE_MAP, {AB: cap}, **kwargs)  # type: ignore[arg-type]


def _price(sol: ZonalSolution, zone: str) -> float:
    assert sol.duals is not None
    return float(sol.duals.zone_price[sol.zone_ids.index(zone)])


# --- AC-2, the corridor-binding case (derivation §2, summary table §7) --------------------------


def test_corridor_binding_reproduces_the_hand_derived_optimum(two_zone: NetworkArrays) -> None:
    """Derivation §2: ``p_A = 70``, ``p_B = 10``, ``f_AB = 20`` at its cap, ``lambda_A = 10``,
    ``lambda_B = 50``, corridor dual ``40``, generation cost ``1200``."""
    sol = _solve(two_zone, CAP)
    assert sol.status == "Optimal"
    assert sol.zone_ids == ["A", "B"]
    assert sol.corridor_ids == [AB]
    assert sol.duals is not None

    assert_allclose(
        sol.dispatch_mw, [LOAD_A + CAP, LOAD_B - CAP], rtol=0.0, atol=EXACT_ATOL
    )  # 70, 10
    assert_allclose(sol.corridor_flow_mw, [CAP], rtol=0.0, atol=EXACT_ATOL)  # at the cap, A -> B
    assert_allclose(sol.duals.zone_price, [COST_A, COST_B], rtol=0.0, atol=EXACT_ATOL)  # 10, 50
    assert_allclose(sol.duals.corridor_cap, [COST_B - COST_A], rtol=0.0, atol=EXACT_ATOL)  # 40
    assert_allclose(
        sol.objective_cost,
        COST_A * (LOAD_A + CAP) + COST_B * (LOAD_B - CAP),
        rtol=0.0,
        atol=EXACT_ATOL,
    )  # 1200
    # both generators are strictly interior at this optimum (derivation §2: "70 and 10 are
    # strictly inside [0, 200]"), which is what makes each zone's price its own generator's cost.
    assert_allclose(sol.duals.gen_bound, [0.0, 0.0], rtol=0.0, atol=EXACT_ATOL)


def test_the_corridor_carries_exactly_the_shortfall_the_expensive_zone_cannot_self_supply(
    two_zone: NetworkArrays,
) -> None:
    """The two balance rows, read back independently of the LP that produced them: zone A's
    generation covers its own load *plus* the export, and zone B's covers its load *minus* the
    import. A sign flip on either corridor coefficient breaks one of these two residuals."""
    sol = _solve(two_zone, CAP)
    p_a, p_b = float(sol.dispatch_mw[0]), float(sol.dispatch_mw[1])
    flow = float(sol.corridor_flow_mw[0])
    assert_allclose(p_a - flow, LOAD_A, rtol=0.0, atol=EXACT_ATOL)
    assert_allclose(p_b + flow, LOAD_B, rtol=0.0, atol=EXACT_ATOL)


# --- AC-2, the copper-plate control (derivation §3) ---------------------------------------------


def test_copper_plate_prices_equal_each_other_and_equal_the_nodal_lambda(
    two_zone: NetworkArrays,
) -> None:
    """Derivation §3: with the cap lifted the exchange column cancels between the two balance
    rows, collapsing them into the single system-wide row ``dc_opf`` builds — so both zone prices
    equal each other *and* equal ``dc_opf``'s own balance dual on the unrated network (10 $/MWh),
    with the cheap generator serving all 80 MW."""
    sol = _solve(two_zone, np.inf)
    assert sol.status == "Optimal"
    assert sol.duals is not None
    assert_allclose(sol.dispatch_mw, [LOAD_A + LOAD_B, 0.0], rtol=0.0, atol=EXACT_ATOL)  # 80, 0
    assert_allclose(sol.corridor_flow_mw, [LOAD_B], rtol=0.0, atol=EXACT_ATOL)  # 30, unconstrained
    assert_allclose(
        sol.duals.corridor_cap, [0.0], rtol=0.0, atol=EXACT_ATOL
    )  # slack corridor prices nothing

    # equal to each other ...
    assert_allclose(_price(sol, "A"), _price(sol, "B"), rtol=0.0, atol=EXACT_ATOL)
    # ... and to dc_opf's own lambda on the same network with no branch rating anywhere. Computed
    # here rather than transcribed, so this is a live agreement between two builders, not two
    # copies of one constant — though the derivation §3 pins it at 10.0, asserted next.
    nodal = dc_opf(two_zone, TWO_ZONE_COSTS, OpfDcOptions())
    assert nodal.status == "Optimal"
    assert nodal.duals is not None
    assert_allclose(_price(sol, "A"), nodal.duals.balance, rtol=0.0, atol=EXACT_ATOL)
    assert_allclose(_price(sol, "A"), COST_A, rtol=0.0, atol=EXACT_ATOL)
    # the expensive generator is off, at its lower bound, with the derivation's reduced cost 40.
    assert_allclose(sol.duals.gen_bound[1], COST_B - COST_A, rtol=0.0, atol=EXACT_ATOL)


def test_removing_the_corridor_islands_the_zones_it_does_not_make_a_copper_plate(
    two_zone: NetworkArrays,
) -> None:
    """The paired negative for the control above: *deleting* the corridor is the opposite of
    lifting its cap. With no exchange column the two balance rows stop being coupled at all and
    each zone must serve its own load from its own generation — zone B is forced onto its 50 $/MWh
    unit for all 30 MW and prices there, which is the **most separated** the two zones can be, not
    the least. Only ``cap = inf`` is the copper plate; a test that reached for "corridors removed"
    as the control would be asserting the wrong regime and would still pass a sign-flipped
    corridor column, because there would be no corridor column to sign."""
    islanded = zonal_dc_opf(two_zone, TWO_ZONE_COSTS, TWO_ZONE_MAP, {})
    assert islanded.status == "Optimal"
    assert islanded.corridor_ids == []
    assert islanded.duals is not None
    assert_allclose(
        islanded.dispatch_mw, [LOAD_A, LOAD_B], rtol=0.0, atol=EXACT_ATOL
    )  # 50, 30 — each alone
    assert_allclose(islanded.duals.zone_price, [COST_A, COST_B], rtol=0.0, atol=EXACT_ATOL)
    # and it is strictly more expensive than either capped or uncapped exchange.
    assert islanded.objective_cost > _solve(two_zone, CAP).objective_cost
    assert _solve(two_zone, CAP).objective_cost > _solve(two_zone, np.inf).objective_cost


# --- AC-2's paired negative, in one test (derivation §4) ----------------------------------------


def test_lifting_the_cap_moves_zone_b_price_by_exactly_the_corridor_dual_and_zone_a_not_at_all(
    two_zone: NetworkArrays,
) -> None:
    """Derivation §4, the load-bearing identity: ``lambda_B(binding) - lambda_B(copper) == 40 ==
    the corridor's own capacity dual``, while ``lambda_A`` does not move at all (zone A's cheap
    unit is interior and price-setting in both regimes, dispatching 70 then 80, both < 200).

    This is the pairing that makes the corridor column load-bearing in *both* directions at once:
    a wrong-signed corridor coefficient fails to reproduce ``40`` here, and a missing corridor
    bound fails to separate the prices in the first place. Neither the binding case nor the
    copper-plate case alone can catch both."""
    binding = _solve(two_zone, CAP)
    copper = _solve(two_zone, np.inf)
    assert binding.duals is not None and copper.duals is not None

    separation = _price(binding, "B") - _price(copper, "B")
    assert_allclose(separation, COST_B - COST_A, rtol=0.0, atol=EXACT_ATOL)  # 40
    assert_allclose(separation, float(binding.duals.corridor_cap[0]), rtol=0.0, atol=EXACT_ATOL)
    assert_allclose(_price(binding, "A") - _price(copper, "A"), 0.0, rtol=0.0, atol=EXACT_ATOL)


# --- AC-2's bid-load variant (derivation §6) ----------------------------------------------------


def test_bid_load_variant_prices_zone_b_at_the_bid_not_the_local_generator(
    two_zone_bid: NetworkArrays,
) -> None:
    """Derivation §6: zone B's fixed load becomes a flat 45 $/MWh bid for up to 30 MW. Since
    ``45 < 50`` the local generator is never worth running, so ``p_B = 0`` and the corridor still
    caps the import at 20 MW — but the price is now set by the *interior bid* at 45, not by the
    idle generator at 50, and the corridor dual falls to ``45 - 10 = 35``.

    Note the objective: ``objective_cost`` is generation cost only (``ZonalSolution`` docstring,
    matching ``OpfSolution``), so it reads ``10 * 70 = 700`` here. The derivation's §6 figure of
    ``-200`` is the *LP's* objective, which also nets in the bid's ``45 * 20 = 900`` of value;
    ``700 - 900 = -200`` reconciles the two exactly."""
    sol = zonal_dc_opf(
        two_zone_bid,
        TWO_ZONE_COSTS,
        TWO_ZONE_MAP,
        {AB: CAP},
        demand_pwl_bids={1: [(0.0, 0.0), (BID_QMAX_B, BID_VALUE_B * BID_QMAX_B)]},
    )
    assert sol.status == "Optimal"
    assert sol.duals is not None
    assert_allclose(sol.dispatch_mw, [LOAD_A + CAP, 0.0], rtol=0.0, atol=EXACT_ATOL)  # 70, 0
    assert_allclose(
        sol.demand_dispatch_mw, [CAP], rtol=0.0, atol=EXACT_ATOL
    )  # 20, corridor-capped not bid-capped
    assert_allclose(sol.corridor_flow_mw, [CAP], rtol=0.0, atol=EXACT_ATOL)
    assert_allclose(
        sol.duals.zone_price, [COST_A, BID_VALUE_B], rtol=0.0, atol=EXACT_ATOL
    )  # 10, 45
    assert_allclose(sol.duals.corridor_cap, [BID_VALUE_B - COST_A], rtol=0.0, atol=EXACT_ATOL)  # 35
    assert_allclose(
        sol.objective_cost, COST_A * (LOAD_A + CAP), rtol=0.0, atol=EXACT_ATOL
    )  # 700, gen cost only
    # p_B sits at its lower bound with the derivation's reduced cost 50 - 45 = 5.
    assert_allclose(sol.duals.gen_bound[1], COST_B - BID_VALUE_B, rtol=0.0, atol=EXACT_ATOL)
    # and the LP objective the derivation quotes reconciles: 700 - 45*20 == -200.
    assert_allclose(
        sol.objective_cost - BID_VALUE_B * float(sol.demand_dispatch_mw[0]),
        -200.0,
        rtol=0.0,
        atol=EXACT_ATOL,
    )


# --- argument forms: the same solve, however the caller spells it ------------------------------


def test_corridor_key_order_is_normalised_not_honoured(two_zone: NetworkArrays) -> None:
    """``{("B", "A"): cap}`` and ``{("A", "B"): cap}`` are the same corridor: the key is an
    *unordered* pair, normalised to sorted order, and the reported ``corridor_ids`` and flow sign
    follow the normalised key in both cases. Without this a caller's arbitrary tuple ordering
    would silently reverse what a positive flow means."""
    forward = _solve(two_zone, CAP)
    reversed_key = zonal_dc_opf(two_zone, TWO_ZONE_COSTS, TWO_ZONE_MAP, {("B", "A"): CAP})
    assert reversed_key.corridor_ids == forward.corridor_ids == [AB]
    assert_allclose(
        reversed_key.corridor_flow_mw, forward.corridor_flow_mw, rtol=0.0, atol=EXACT_ATOL
    )
    assert reversed_key.duals is not None and forward.duals is not None
    assert_allclose(
        reversed_key.duals.zone_price, forward.duals.zone_price, rtol=0.0, atol=EXACT_ATOL
    )


def test_positional_zone_of_bus_matches_the_mapping_form(two_zone: NetworkArrays) -> None:
    """A sequence of labels in ``NetworkArrays`` bus order is the same partition as the
    ``{bus id: zone id}`` mapping, and solves identically."""
    positional = zonal_dc_opf(two_zone, TWO_ZONE_COSTS, ["A", "A", "B"], {AB: CAP})
    mapping = _solve(two_zone, CAP)
    assert positional.zone_ids == mapping.zone_ids
    assert_allclose(positional.dispatch_mw, mapping.dispatch_mw, rtol=0.0, atol=EXACT_ATOL)
    assert positional.duals is not None and mapping.duals is not None
    assert_allclose(
        positional.duals.zone_price, mapping.duals.zone_price, rtol=0.0, atol=EXACT_ATOL
    )


def test_a_zero_cap_corridor_is_allowed_and_islands_the_zones(two_zone: NetworkArrays) -> None:
    """A cap of exactly 0 is a tie that can carry nothing — legal, and distinguishable from a
    deleted corridor by the fact that its capacity price is still readable (here 40 $/MWh: the
    first MW of transfer would be worth exactly the price gap it closes)."""
    sol = _solve(two_zone, 0.0)
    assert sol.status == "Optimal"
    assert sol.duals is not None
    assert_allclose(sol.corridor_flow_mw, [0.0], rtol=0.0, atol=EXACT_ATOL)
    assert_allclose(sol.dispatch_mw, [LOAD_A, LOAD_B], rtol=0.0, atol=EXACT_ATOL)
    assert_allclose(sol.duals.corridor_cap, [COST_B - COST_A], rtol=0.0, atol=EXACT_ATOL)


# --- the degenerate case: one zone, no corridors, == dc_opf on an unrated network ---------------


def test_one_zone_no_corridors_equals_dc_opf_on_the_unrated_three_bus_network(
    two_zone: NetworkArrays,
) -> None:
    """Module docstring, "Degenerate case". With every bus in one zone the per-zone rows collapse
    to ``dc_opf``'s single system-wide row, and with no branch rating ``dc_opf``'s flow rows cannot
    bind — so the two builders solve the same problem through structurally different LPs."""
    one_zone = dict.fromkeys(two_zone.bus_ids, "Z")
    zonal = zonal_dc_opf(two_zone, TWO_ZONE_COSTS, one_zone, {})
    nodal = dc_opf(two_zone, TWO_ZONE_COSTS, OpfDcOptions())
    assert zonal.status == nodal.status == "Optimal"
    assert zonal.zone_ids == ["Z"]
    assert zonal.duals is not None and nodal.duals is not None
    assert_allclose(zonal.dispatch_mw, nodal.dispatch_mw, rtol=0.0, atol=EXACT_ATOL)
    assert_allclose(zonal.duals.zone_price[0], nodal.duals.balance, rtol=0.0, atol=EXACT_ATOL)
    assert_allclose(zonal.objective_cost, nodal.objective_cost, rtol=0.0, atol=EXACT_ATOL)


def test_one_zone_no_corridors_equals_dc_opf_on_unrated_case30() -> None:
    """The same degeneracy on real fixture data, where the dispatch is a genuine 30-bus
    merit-order answer rather than a two-generator one. Asserted at :data:`CASE30_RTOL` /
    :data:`CASE30_ATOL`, whose docstring records the measured residuals (``2.8e-14`` MW on
    dispatch)."""
    net = promote_areas_to_zones(load(FIXTURES_DIR / "case30.m"))
    for branch in net.branches:
        branch.rating_mva = None  # unrated: dc_opf's flow rows exist but cannot bind
    arr = NetworkArrays.from_network(net)
    coeffs, pwl = gen_cost_coeffs(net, arr)
    zonal = zonal_dc_opf(arr, coeffs, dict.fromkeys(arr.bus_ids, "Z"), {}, pwl_costs=pwl or None)
    nodal = dc_opf(arr, coeffs, OpfDcOptions(), pwl_costs=pwl or None)
    assert zonal.status == nodal.status == "Optimal"
    assert zonal.duals is not None and nodal.duals is not None
    assert_allclose(zonal.dispatch_mw, nodal.dispatch_mw, rtol=CASE30_RTOL, atol=CASE30_ATOL)
    assert_allclose(
        zonal.duals.zone_price[0], nodal.duals.balance, rtol=CASE30_RTOL, atol=CASE30_ATOL
    )
    assert_allclose(zonal.objective_cost, nodal.objective_cost, rtol=CASE30_RTOL, atol=CASE30_ATOL)
    assert_allclose(
        zonal.duals.gen_bound, nodal.duals.gen_bound, rtol=CASE30_RTOL, atol=CASE30_ATOL
    )


# --- AC-2's real fixture: promoted, rated case30 ------------------------------------------------


@pytest.fixture(scope="module")
def case30_zonal() -> tuple[Network, NetworkArrays, dict[tuple[str, str], float], ZonalSolution]:
    """case30 with its AREA column promoted to real zones and its ratings derived, cleared
    zonally. Both transformations come from the committed helpers (``tests/_zones.py``,
    ``tests/_rated.py``) — never a hand-copy of their output, so a change in either is felt here.
    """
    net = rated_network(promote_areas_to_zones(load(FIXTURES_DIR / "case30.m")))
    arr = NetworkArrays.from_network(net)
    coeffs, pwl = gen_cost_coeffs(net, arr)
    caps = corridors(net)
    sol = zonal_dc_opf(arr, coeffs, zone_of_bus(net), caps, pwl_costs=pwl or None)
    return net, arr, caps, sol


def test_case30_clears_with_two_of_its_three_corridors_at_their_caps(
    case30_zonal: tuple[Network, NetworkArrays, dict[tuple[str, str], float], ZonalSolution],
) -> None:
    """AC-2's real-fixture leg. case30's three promoted zones are tied by all three corridors
    (caps 1.52 / 16.58 / 19.46 MVA, plan A19), and **two of them bind**: (1,2) at its 1.52 MVA cap
    — the one A19 predicted — and (2,3) at its 19.46 MVA cap in the **reverse** direction
    (``flow < 0``, i.e. zone 3 -> zone 2), which is what exercises the negative-flow half of the
    capacity-price derivation. The (1,3) corridor stays slack."""
    _, _, caps, sol = case30_zonal
    assert sol.status == "Optimal"
    assert sol.zone_ids == ["1", "2", "3"]
    assert sol.corridor_ids == [("1", "2"), ("1", "3"), ("2", "3")]
    assert sol.duals is not None

    cap_vec = np.array([caps[key] for key in sol.corridor_ids])
    at_cap = np.isclose(np.abs(sol.corridor_flow_mw), cap_vec, rtol=0.0, atol=1e-7)
    assert at_cap.tolist() == [True, False, True], (
        f"expected the (1,2) and (2,3) corridors at their caps and (1,3) slack; got flows "
        f"{sol.corridor_flow_mw} against caps {cap_vec}"
    )
    # direction, not just magnitude: (1,2) runs 1 -> 2 positive, (2,3) runs 3 -> 2 negative.
    assert float(sol.corridor_flow_mw[0]) > 0.0
    assert float(sol.corridor_flow_mw[2]) < 0.0
    # a binding corridor prices; the slack one does not.
    assert float(sol.duals.corridor_cap[1]) == 0.0
    assert float(sol.duals.corridor_cap[0]) > 1e-3
    assert float(sol.duals.corridor_cap[2]) > 1e-3


def test_case30_zones_joined_by_a_slack_corridor_price_identically(
    case30_zonal: tuple[Network, NetworkArrays, dict[tuple[str, str], float], ZonalSolution],
) -> None:
    """The documented reason two of case30's three zone prices coincide: zones 1 and 3 are joined
    by the **slack** (1,3) corridor, and an exchange column strictly inside its bounds forces its
    two balance-row duals equal (module docstring, "Zone price"). Zone 2 — importing at cap from
    both sides — is the one that separates. So the fixture yields *two* distinct prices, not
    three, and it is a theorem rather than an accident."""
    _, _, _, sol = case30_zonal
    assert sol.duals is not None
    price = dict(zip(sol.zone_ids, (float(p) for p in sol.duals.zone_price), strict=True))
    assert_allclose(price["1"], price["3"], rtol=0.0, atol=CASE30_DUAL_ATOL)
    # and zone 2 is genuinely separated — by ~0.121 $/MWh, three orders of magnitude above the
    # tolerance the equality above is asserted at, so "coincide" and "differ" are not the same
    # reading here.
    assert price["2"] - price["1"] > 1000 * CASE30_DUAL_ATOL


def test_case30_each_binding_corridors_dual_equals_the_price_gap_it_holds_open(
    case30_zonal: tuple[Network, NetworkArrays, dict[tuple[str, str], float], ZonalSolution],
) -> None:
    """The case30-scale restatement of the 3-bus paired negative: on a binding corridor the
    capacity price equals the absolute price difference across it, and on a slack one it is
    exactly 0. Both binding corridors hold open the *same* gap (zone 2 against zones 1 and 3,
    which price together), so their duals agree with each other too."""
    _, _, _, sol = case30_zonal
    assert sol.duals is not None
    price = dict(zip(sol.zone_ids, (float(p) for p in sol.duals.zone_price), strict=True))
    for key, dual in zip(sol.corridor_ids, sol.duals.corridor_cap, strict=True):
        z1, z2 = key
        expected = abs(price[z2] - price[z1])
        assert_allclose(
            float(dual),
            expected,
            rtol=0.0,
            atol=CASE30_DUAL_ATOL,
            err_msg=f"corridor {key}: capacity dual should equal |price gap|",
        )


def test_case30_every_zone_balances_at_the_solution(
    case30_zonal: tuple[Network, NetworkArrays, dict[tuple[str, str], float], ZonalSolution],
) -> None:
    """Each zone's balance row read back from the *result object* alone and recomputed here from
    the network arrays: generation in the zone, minus net export on its corridors, equals that
    zone's fixed load plus shunt. Reconstructed independently (not by re-reading the LP's rows),
    so a corridor entering the wrong zone's row, or entering it with the wrong sign, shows up as a
    nonzero residual. Measured residual on this build: ``1.4e-14`` MW."""
    net, arr, _, sol = case30_zonal
    assert sol.status == "Optimal"
    position = {zone: i for i, zone in enumerate(sol.zone_ids)}
    bus_zone = np.array([position[zone_of_bus(net)[bus]] for bus in arr.bus_ids])
    n_zone = len(sol.zone_ids)

    generation = np.bincount(bus_zone[arr.gen_bus], weights=sol.dispatch_mw, minlength=n_zone)
    fixed = np.bincount(
        bus_zone, weights=(arr.p_load_pu + arr.g_shunt_pu) * arr.base_mva, minlength=n_zone
    )
    net_export = np.zeros(n_zone)
    for (z1, z2), flow in zip(sol.corridor_ids, sol.corridor_flow_mw, strict=True):
        net_export[position[z1]] += flow  # positive flow leaves z1 ...
        net_export[position[z2]] -= flow  # ... and arrives in z2
    assert_allclose(generation - net_export, fixed, rtol=0.0, atol=1e-9)


# --- shared extraction and validation (ADR-008): this builder implements none of it -------------


def test_cost_and_bid_guards_come_from_the_shared_extractor(two_zone: NetworkArrays) -> None:
    """``zonal_dc_opf`` raises ``dc_opf``'s own errors on ``dc_opf``'s own inputs, because it
    calls ``dc_opf``'s own ``_extract_and_validate`` (spec ownership table, row 1) rather than
    re-deriving the guards. All three fire before any HiGHS object exists."""
    non_convex = np.array([[-1.0, COST_A, 0.0], [0.0, COST_B, 0.0]])
    with pytest.raises(NonConvexCostError):
        zonal_dc_opf(two_zone, non_convex, TWO_ZONE_MAP, {AB: CAP})
    with pytest.raises(NonConcaveBidError):
        zonal_dc_opf(
            two_zone,
            TWO_ZONE_COSTS,
            TWO_ZONE_MAP,
            {AB: CAP},
            demand_bid_coeffs={1: (1.0, 45.0, 0.0)},  # v2 > 0
        )
    with pytest.raises(ValueError, match="cost_coeffs must have shape"):
        zonal_dc_opf(two_zone, np.zeros((5, 3)), TWO_ZONE_MAP, {AB: CAP})


# --- the partition and corridor map are validated, and say why ---------------------------------


def test_a_bus_with_no_zone_is_rejected(two_zone: NetworkArrays) -> None:
    """A partition with a hole is an error, not a defaulted zone: the omitted bus's load and
    generation would otherwise vanish from every balance row."""
    partial = {"bus1": "A", "bus2": "A"}
    with pytest.raises(ValueError, match="missing 1 of 3 buses"):
        zonal_dc_opf(two_zone, TWO_ZONE_COSTS, partial, {AB: CAP})


def test_a_positional_partition_of_the_wrong_length_is_rejected(two_zone: NetworkArrays) -> None:
    with pytest.raises(ValueError, match="has 2 entries but the network has 3 buses"):
        zonal_dc_opf(two_zone, TWO_ZONE_COSTS, ["A", "B"], {AB: CAP})


@pytest.mark.parametrize(
    ("bad_corridors", "match"),
    [
        pytest.param({("A", "C"): CAP}, "which no bus is assigned to", id="unknown-zone"),
        pytest.param({("A", "A"): CAP}, "names the same zone twice", id="self-pair"),
        pytest.param({AB: CAP, ("B", "A"): CAP}, "appears twice in corridors", id="both-orders"),
        pytest.param({AB: -1.0}, "negative cap", id="negative-cap"),
        pytest.param({AB: float("nan")}, "NaN cap", id="nan-cap"),
        pytest.param({("A",): CAP}, "is not a .zone1, zone2. pair", id="not-a-pair"),
    ],
)
def test_a_malformed_corridor_map_is_rejected(
    two_zone: NetworkArrays, bad_corridors: dict[object, float], match: str
) -> None:
    """Each rejection names the offending key. The unknown-zone case is the one with teeth: a
    corridor to a zone no bus is in would add a column entering exactly one balance row, which is
    an unbounded free source of power in that zone rather than a transfer."""
    with pytest.raises(ValueError, match=match):
        zonal_dc_opf(two_zone, TWO_ZONE_COSTS, TWO_ZONE_MAP, bad_corridors)  # type: ignore[arg-type]


# --- non-optimal statuses are reported, never raised -------------------------------------------


def test_an_infeasible_zonal_clearing_is_reported_not_raised() -> None:
    """A zone whose load exceeds its own generation plus everything its corridors can import has
    no feasible clearing. ``zonal_dc_opf`` reports that through ``status``/``message`` and returns
    zero-filled arrays with ``duals is None``, mirroring ``dc_opf``'s never-raise convention."""
    net = _two_zone_network()
    for generator in net.generators:
        if generator.id == "genB":
            generator.p_max_mw = 0.0  # zone B can generate nothing ...
    arr = NetworkArrays.from_network(net)
    sol = zonal_dc_opf(arr, TWO_ZONE_COSTS, TWO_ZONE_MAP, {AB: 0.0})  # ... and import nothing
    assert sol.status != "Optimal"
    assert sol.duals is None
    assert sol.message is not None and sol.status in sol.message
    assert sol.zone_ids == ["A", "B"]  # still echoed back, as the docstring promises
    assert sol.dispatch_mw.shape == (2,)
    assert not sol.dispatch_mw.any()
    assert sol.corridor_flow_mw.shape == (1,)
    assert sol.objective_cost == 0.0


# --- the package re-export is the same object --------------------------------------------------


def test_the_package_reexports_the_builder(two_zone: NetworkArrays) -> None:
    """``mambo_power.opf.zonal_dc_opf`` is the module's own function, not a wrapper — the same
    re-export shape ``multiperiod_dc_opf`` already has, and what ``market.zonal`` (W4) will
    import."""
    assert opf_pkg.zonal_dc_opf is zonal_dc_opf
    assert opf_pkg.ZonalSolution is ZonalSolution
    assert "zonal_dc_opf" in opf_pkg.__all__
