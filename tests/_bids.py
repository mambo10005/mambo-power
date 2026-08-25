"""Bid-derivation test helper (M4 W6, spec Assumption a; AC-6 fixture half).

No MATPOWER fixture carries any demand-bid data at all -- record/m4-research.md §5: the ``.m``
bus table has exactly 13 columns (``bus_i type Pd Qd Gs Bs area Vm Va baseKV zone Vmax Vmin``),
confirmed by direct read; there is no MATPOWER concept of a load bid curve. This module derives
a concave quadratic bid curve **at test time** from each fixture's own already-committed
``Load.p_mw`` and ``Generator.cost`` data, the same "documented, test-time transformation of an
already-owned fixture" pattern :mod:`tests._rated` already uses for branch ratings (spec Design
item 7) -- no new fixture data is committed.

**VOLL and curve shape (spec Assumption a, pinned here).** :data:`VOLL_PER_MWH` = 10,000 $/MWh
-- a round, literature-standard value-of-lost-load figure (in the range major US ISOs use as an
administrative offer cap / VOLL proxy, e.g. ERCOT's $9,000/MWh system-wide offer cap; PJM's
$3,500/MWh scarcity-pricing offer cap is the same order of magnitude, lower end). Chosen to be
clearly above any fixture's own generation-fleet marginal cost at full output (confirmed, not
assumed -- :func:`bid_for_load` raises if it isn't), so a derived bid is genuinely
price-taking-capable across its whole domain, not accidentally bid-limited by an unrealistically
low VOLL.

Each load's marginal value descends **linearly** from ``VOLL_PER_MWH`` at ``p=0`` down to the
fixture's own generation-fleet max marginal cost (:func:`fleet_max_marginal_cost`: the highest,
over every in-service generator, of that generator's own marginal cost *at its own upper
bound* -- the ceiling the market-clearing price can never exceed, since no generator can be
dispatched past its own ``p_max``) at ``p = load.p_mw`` (the load's own already-committed
historical demand, never a chosen/invented number) -- producing the quadratic value curve
``value(p) = v1*p + v2*p**2`` with ``v1 = VOLL_PER_MWH`` and ``v2 = (fleet_max_marginal_cost -
VOLL_PER_MWH) / (2 * load.p_mw)``. ``v2 < 0`` whenever ``VOLL_PER_MWH`` exceeds the fleet's max
marginal cost (guaranteed by the check above), so the curve is strictly, non-trivially concave
(marginal value strictly decreasing across the whole bid domain, swinging by thousands of
$/MWh from top to bottom on every fixture this wave uses) -- not a degenerate flat step, the
failure mode spec Assumption (a) warns against; proved directly in
``tests/unit/test_bids.py``, not merely hoped.

**A mathematical consequence, not a defect**: because the anchor rule's low end
(``fleet_max_marginal_cost``) is by construction an upper bound on the market-clearing price
achievable on that fixture (a convex generator's own marginal cost is non-decreasing in its
output, so no generator's marginal cost at its *actual* dispatch can exceed its marginal cost at
its own ``p_max``), every bid this module derives satisfies record/m4-research.md §4.2's
price-taker condition and so is *always* dispatched at its own full ``p_mw`` -- the same
conclusion S4's AC-5 test already proves via a hand-picked constant bid, now confirmed
independently through pandapower's own oracle instead of ``opf.dc_opf``'s own price-taker
reduction (``tests/parity/test_market_nodal_vs_pandapower.py``).
"""

from __future__ import annotations

from collections.abc import Iterable

from mambo_power.model import Network, PolynomialBid

VOLL_PER_MWH = 10_000.0
"""Marginal value at ``p=0`` for every derived bid (module docstring)."""


def fleet_max_marginal_cost(net: Network) -> float:
    """``max`` over in-service, cost-carrying generators of that generator's own marginal cost
    at its own ``p_max_mw`` (``c1 + 2*c2*p_max_mw`` for a
    :class:`~mambo_power.model.PolynomialCost`) -- the anchor for a derived bid's low end
    (module docstring). Only :class:`~mambo_power.model.PolynomialCost` is supported (every
    fixture this wave uses carries polynomial, not piecewise, generator costs -- record/
    m3-research.md, M4 module docstrings on ``opf.dc_opf``); raises ``NotImplementedError`` on a
    piecewise generator cost rather than silently ignoring it. Raises ``ValueError`` if no
    in-service generator has a cost (nothing to anchor against).
    """
    marginal_costs: list[float] = []
    for gen in net.generators:
        if not gen.in_service or gen.cost is None:
            continue
        if gen.cost.kind == "piecewise":
            raise NotImplementedError(
                f'generator "{gen.id}" has a piecewise cost; fleet_max_marginal_cost only '
                "supports polynomial generator costs"
            )
        coeffs = list(gen.cost.coefficients)
        row = [0.0, 0.0, 0.0]
        row[3 - len(coeffs) :] = coeffs
        c2, c1, _c0 = row
        marginal_costs.append(c1 + 2.0 * c2 * gen.p_max_mw)
    if not marginal_costs:
        raise ValueError("no in-service generator has a cost -- nothing to anchor a bid against")
    return max(marginal_costs)


def bid_for_load(net: Network, load_id: str) -> PolynomialBid:
    """The quadratic bid curve the module docstring derives for ``load_id``, anchored to that
    load's own already-committed ``p_mw`` and ``net``'s :func:`fleet_max_marginal_cost`.

    Raises ``ValueError`` if ``load_id`` doesn't resolve, its ``p_mw`` isn't strictly positive
    (the anchor rule divides by it), or :data:`VOLL_PER_MWH` doesn't clearly exceed the fleet's
    own ceiling (the invariant a valid concave curve depends on -- module docstring).
    """
    try:
        load = next(ld for ld in net.loads if ld.id == load_id)
    except StopIteration:
        raise ValueError(f'no load with id "{load_id}" in this network') from None
    if load.p_mw <= 0.0:
        raise ValueError(
            f'load "{load_id}" has p_mw={load.p_mw!r} -- bid_for_load needs a strictly '
            "positive anchor to derive a curve against"
        )
    fleet_mc = fleet_max_marginal_cost(net)
    if not VOLL_PER_MWH > fleet_mc:
        raise ValueError(
            f"VOLL_PER_MWH={VOLL_PER_MWH!r} does not exceed this network's own "
            f"fleet_max_marginal_cost={fleet_mc!r} -- the derived curve would not be concave "
            "(module docstring)"
        )
    v1 = VOLL_PER_MWH
    v2 = (fleet_mc - v1) / (2.0 * load.p_mw)
    return PolynomialBid(coefficients=[v2, v1, 0.0])


def with_bids(net: Network, load_ids: Iterable[str] | None = None) -> Network:
    """A copy of ``net`` with :func:`bid_for_load`'s derivation set on each id in ``load_ids``
    (default: every load in ``net``). Mirrors ``tests/_rated.py``'s ``rated_network`` -- does
    not mutate ``net``, returns a fresh :class:`~mambo_power.model.Network` via
    ``model_copy(deep=True)``.
    """
    targets = set(load_ids) if load_ids is not None else {ld.id for ld in net.loads}
    bids = {load_id: bid_for_load(net, load_id) for load_id in targets}
    out = net.model_copy(deep=True)
    for ld in out.loads:
        if ld.id in bids:
            ld.bid = bids[ld.id]
    return out
