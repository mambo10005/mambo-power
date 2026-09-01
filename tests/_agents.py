"""Strategic-bidding fixture builder (M7 W7, spec ``## Requirements`` W7; AC-4/AC-5's fixture
half).

Every later M7 slice drives these three factories -- nobody hand-assembles a strategic-bidding
network. Mirrors ``tests/_rated.py``'s and ``tests/_bids.py``'s own pattern: a small, documented
network built at test time from plain parameters, not a MATPOWER import.

**Shared demand side.** All three fixtures face the same single elastic load: marginal value
``100 - 0.1*p``, i.e. ``q(price) = 1000 - 10*price`` (spec AC-4's own demand curve). As a
:class:`~mambo_power.model.PolynomialBid`, marginal value is the derivative of
``coefficients = [v2, v1, v0]``'s value curve, ``2*v2*p + v1``, so ``v1 = 100.0`` and
``v2 = -0.05`` (``2 * -0.05 = -0.1``). The load's own ``p_mw`` is set to :data:`LOAD_P_MAX_MW`
(1000.0) -- the quantity at which the demand curve's marginal value reaches zero -- rather than
to some smaller historical figure: ``Load.p_mw`` is the *maximum* the elastic column can serve
(``Load.p_mw``'s own field description), so a smaller cap would silently truncate the demand
curve's top end and cap the market below the fixture's own closed-form optimum before any
strategy runs.

**Network shape.** :func:`_network` builds a star: bus ``b1`` (slack) hosts the first generator;
every further generator gets its own bus; the shared load sits on its own bus; every branch is
built with no ``rating_mva`` (``None`` = unlimited, ``Branch.rating_mva``'s own field
description), so nothing here ever congests -- these fixtures exercise strategic bidding, not
the flow-limit rows M2/M5/M6 already own. Every generator's true cost is linear
(:class:`~mambo_power.model.PolynomialCost` ``[c1, 0.0]``, i.e. ``cost(p) = c1*p``), matching
the closed-form profit expressions AC-4's provenance derives by hand.

**The three fixtures** (spec W7):

(a) :func:`smooth_pivotal_network` -- one strategic generator, 900 MW at true $20/MWh, with *no*
    competing unit. Deliberate and disclosed (spec "Not Doing", AC-4, A4): the absence of a rival
    is what makes the profit peak reachable by a *local* best-response climb -- a competing unit
    between the strategic unit's cost and its profit peak creates a discontinuity the climb
    provably stalls short of (measured $9,497.52 against a derivable $12,250, spec A4). Closed
    form: profit ``(price - 20)(1000 - 10*price)`` peaks at ``price = $60.00``, ``q = 400 MW``,
    profit ``$16,000/h``.
(b) :func:`non_pivotal_control_network` -- the same strategic unit, plus a 900 MW rival at a true
    $22/MWh. The rival, not demand, now stops the climb -- a smaller, real markup.
(c) :func:`duopoly_network` -- two 300 MW generators, both at a true $20/MWh -- the only shape
    in this wave where best response can fail to settle in one round (spec AC-5's own framing).

**Clearing the fixtures.** The market loop (``market.agents.solve_agents``) is a later slice
(spec W3/S4); this module's own unit test verifies these fixtures' economics by clearing them
directly through ``opf.dc_opf``, the same path ``market.nodal.solve_nodal`` uses
(``gen_cost_coeffs`` + ``load_bid_coeffs`` + ``dc_opf``) rather than through any loop.
:func:`clear_with_offers` is that shared clearing step, exported here so a later slice's own
tests can reuse it instead of re-deriving it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from mambo_power.market.nodal import load_bid_coeffs
from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialBid, PolynomialCost
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import OpfDcOptions, OpfSolution, dc_opf

LOAD_P_MAX_MW = 1000.0
"""``Load.p_mw`` for the shared elastic load -- the quantity at which the shared demand curve's
marginal value reaches zero (module docstring); not a smaller, arbitrary historical figure,
since a smaller cap would truncate the curve below the fixtures' own closed-form optima."""

DEMAND_BID = PolynomialBid(coefficients=[-0.05, 100.0, 0.0])
"""The shared elastic load's bid: marginal value ``100 - 0.1*p``, i.e.
``q(price) = 1000 - 10*price`` (module docstring)."""

STRATEGIC_P_MAX_MW = 900.0
"""Capacity, MW, of the strategic generator in both :func:`smooth_pivotal_network` and
:func:`non_pivotal_control_network` (spec AC-4)."""

STRATEGIC_TRUE_COST = 20.0
"""True marginal cost, $/MWh, of every strategic generator in this module's fixtures (spec
AC-4, AC-5) -- linear (``PolynomialCost([cost, 0.0])``), so profit is exact and closed-form."""

RIVAL_P_MAX_MW = 900.0
"""Capacity, MW, of the price-taking rival in :func:`non_pivotal_control_network` (spec AC-4's
paired control)."""

RIVAL_TRUE_COST = 22.0
"""True marginal cost, $/MWh, of the rival in :func:`non_pivotal_control_network` -- the
quantity that stops the strategic climb at $21.50 instead of demand's own $60.00 peak."""

DUOPOLY_P_MAX_MW = 300.0
"""Capacity, MW, of each of the two symmetric generators in :func:`duopoly_network` (spec
AC-5)."""


def _network(
    generators: Sequence[tuple[str, float, float]], bid: PolynomialBid | None = None
) -> Network:
    """A star network: bus ``b1`` (slack) hosts ``generators[0]``, every further generator gets
    its own bus, and the shared elastic load sits on the last bus (module docstring). Each
    element of ``generators`` is ``(id, p_max_mw, true_cost_per_mwh)``; every generator gets
    ``p_min_mw=0.0`` and a linear :class:`~mambo_power.model.PolynomialCost`. ``bid`` defaults to
    :data:`DEMAND_BID`; a sabotage test overriding the demand curve passes its own.
    """
    n = len(generators)
    buses = [Bus(id="b1", base_kv=138.0, type="slack")]
    buses += [Bus(id=f"b{i}", base_kv=138.0, type="pq") for i in range(2, n + 2)]
    branches = [
        Branch(id=f"l{i}", from_bus="b1", to_bus=f"b{i}", r=0.0, x=0.05, b=0.0)
        for i in range(2, n + 2)
    ]
    gens = []
    for k, (gen_id, p_max_mw, true_cost) in enumerate(generators):
        bus = "b1" if k == 0 else f"b{k + 1}"
        gens.append(
            Generator(
                id=gen_id,
                bus=bus,
                p_mw=0.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=p_max_mw,
                q_min_mvar=-9999.0,
                q_max_mvar=9999.0,
                v_set_pu=1.0,
                cost=PolynomialCost(coefficients=[true_cost, 0.0]),
            )
        )
    load = Load(id="d1", bus=f"b{n + 1}", p_mw=LOAD_P_MAX_MW, q_mvar=0.0, bid=bid or DEMAND_BID)
    return Network(base_mva=100.0, buses=buses, branches=branches, generators=gens, loads=[load])


def smooth_pivotal_network(
    strategic_id: str = "strategic",
    p_max_mw: float = STRATEGIC_P_MAX_MW,
    true_cost: float = STRATEGIC_TRUE_COST,
) -> Network:
    """The smooth-pivotal fixture (module docstring (a)): one strategic generator, no rival."""
    return _network([(strategic_id, p_max_mw, true_cost)])


def non_pivotal_control_network(
    strategic_id: str = "strategic",
    rival_id: str = "rival",
    strategic_p_max_mw: float = STRATEGIC_P_MAX_MW,
    strategic_true_cost: float = STRATEGIC_TRUE_COST,
    rival_p_max_mw: float = RIVAL_P_MAX_MW,
    rival_true_cost: float = RIVAL_TRUE_COST,
) -> Network:
    """The non-pivotal control fixture (module docstring (b)): :func:`smooth_pivotal_network`'s
    own strategic unit, plus a price-taking rival that stops the climb well short of demand's
    own peak."""
    return _network(
        [
            (strategic_id, strategic_p_max_mw, strategic_true_cost),
            (rival_id, rival_p_max_mw, rival_true_cost),
        ]
    )


def duopoly_network(
    gen_a_id: str = "agent_a",
    gen_b_id: str = "agent_b",
    p_max_mw: float = DUOPOLY_P_MAX_MW,
    true_cost: float = STRATEGIC_TRUE_COST,
) -> Network:
    """The two-reactive-agent duopoly fixture (module docstring (c)): two symmetric generators,
    both true cost :data:`STRATEGIC_TRUE_COST` by default -- the only shape in this wave where
    best response can fail to settle in one round (spec AC-5)."""
    return _network([(gen_a_id, p_max_mw, true_cost), (gen_b_id, p_max_mw, true_cost)])


def clear_with_offers(net: Network, offers: Mapping[str, float]) -> OpfSolution:
    """Clear ``net`` through ``opf.dc_opf`` directly, the same path
    ``market.nodal.solve_nodal`` uses (module docstring): ``gen_cost_coeffs`` for the true costs,
    ``load_bid_coeffs`` for the shared demand bid, then ``dc_opf``.

    ``offers`` maps a generator id to a strategic linear offer, $/MWh: that generator's
    ``cost_coeffs`` row is replaced with ``[0.0, offer, 0.0]`` (constant marginal cost) before
    the solve, in place of its true :class:`~mambo_power.model.PolynomialCost`. A generator id
    in ``net`` but absent from ``offers`` clears at its own true cost unchanged -- this is how
    :func:`non_pivotal_control_network`'s rival stays a price-taker while only the strategic
    unit's own offer is swept.

    Raises ``KeyError`` if ``offers`` names a generator id not present in ``net``.
    """
    arr = NetworkArrays.from_network(net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(net, arr)
    gen_index = {gen_id: i for i, gen_id in enumerate(arr.gen_ids)}
    for gen_id, offer in offers.items():
        i = gen_index[gen_id]  # KeyError on an unknown id -- deliberate, not caught
        cost_coeffs[i] = [0.0, offer, 0.0]
    demand_bid_coeffs, demand_pwl_bids = load_bid_coeffs(net, arr)
    return dc_opf(
        arr,
        cost_coeffs,
        OpfDcOptions(),
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=demand_bid_coeffs or None,
        demand_pwl_bids=demand_pwl_bids or None,
    )
