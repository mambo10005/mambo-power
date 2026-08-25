"""Unit test for ``tests._bids``: the bid-derivation test helper (M4 W6, AC-6 fixture half).

Mirrors ``tests/unit/test_rated_helper.py``'s own discipline for ``tests/_rated.py``: proves the
helper's guarantees directly (anchored to the load's own committed ``p_mw``, genuinely concave,
not a degenerate flat step) rather than merely exercising it as a side effect of another test.
"""

from __future__ import annotations

import pytest

from mambo_power import opf
from mambo_power.io.matpower import load
from mambo_power.model import PolynomialBid
from tests._bids import (
    INTERIOR_FLOOR_MULTIPLE,
    INTERIOR_TOP_MULTIPLE,
    VOLL_PER_MWH,
    baseline_clearing_price,
    bid_for_load,
    fleet_max_marginal_cost,
    interior_bid_for_load,
    with_bids,
)
from tests._fixtures import FIXTURES_DIR


def _case14():  # type: ignore[no-untyped-def]
    return load(FIXTURES_DIR / "case14.m")


def test_fleet_max_marginal_cost_is_the_worst_generator_marginal_cost_at_its_own_pmax() -> None:
    net = _case14()
    # hand-computed from case14.m's own gencost/gen blocks (c1 + 2*c2*p_max per generator):
    # gen1 20+2*0.0430292599*332.4=48.6..., gen2 20+2*0.25*140=90, gen3/4/5 40+2*0.01*100=42.
    # gen2 is the fleet's worst (highest) marginal cost at its own upper bound.
    assert fleet_max_marginal_cost(net) == pytest.approx(90.0, abs=1e-6)


def test_bid_for_load_is_anchored_to_the_load_s_own_committed_p_mw() -> None:
    net = _case14()
    load_id = "load-9"  # bus 9, Pd=29.5 (case14.m's own bus table)
    bid = bid_for_load(net, load_id)
    assert isinstance(bid, PolynomialBid)
    v2, v1, v0 = bid.coefficients
    assert v0 == 0.0
    assert v1 == VOLL_PER_MWH
    # marginal value at the load's own anchor (p_mw) lands exactly on the fleet's max marginal
    # cost -- the module's own documented anchor rule, proved not assumed.
    p_anchor = next(ld for ld in net.loads if ld.id == load_id).p_mw
    marginal_value_at_anchor = v1 + 2 * v2 * p_anchor
    assert marginal_value_at_anchor == pytest.approx(fleet_max_marginal_cost(net), abs=1e-9)


def test_bid_for_load_is_genuinely_concave_and_non_trivial_not_a_degenerate_flat_step() -> None:
    """v2 < 0 (strict concavity -- NonConcaveBidError's guard would reject v2 > 0, but a flat
    step (v2 == 0) would also pass that guard while proving nothing about the hypograph/QP
    encoding). Marginal value must swing by a real, large margin across the bid's own domain,
    not a barely-perceptible slope."""
    net = _case14()
    bid = bid_for_load(net, "load-9")
    v2, v1, _ = bid.coefficients
    assert v2 < 0.0
    p_anchor = next(ld for ld in net.loads if ld.id == "load-9").p_mw
    marginal_value_swing = v1 - (v1 + 2 * v2 * p_anchor)
    assert marginal_value_swing > 1000.0, "marginal value must swing by a real margin, not a hair"


def test_bid_for_load_voll_exceeds_every_fixture_generator_s_marginal_cost() -> None:
    """A load bid whose top-of-range value doesn't clear the fleet's own ceiling would silently
    produce a non-concave (v2 > 0) curve instead of failing loudly -- this is the invariant
    :func:`tests._bids.bid_for_load` itself checks and raises on."""
    net = _case14()
    assert VOLL_PER_MWH > fleet_max_marginal_cost(net)


def test_with_bids_does_not_mutate_the_input_network() -> None:
    net = _case14()
    before = [ld.bid for ld in net.loads]
    with_bids(net)
    after = [ld.bid for ld in net.loads]
    assert before == after
    assert all(b is None for b in before)


def test_with_bids_defaults_to_every_load() -> None:
    net = _case14()
    bid_net = with_bids(net)
    assert all(ld.bid is not None for ld in bid_net.loads)
    assert len(bid_net.loads) == len(net.loads)


def test_with_bids_honors_an_explicit_subset() -> None:
    net = _case14()
    bid_net = with_bids(net, load_ids=["load-9"])
    by_id = {ld.id: ld.bid for ld in bid_net.loads}
    assert by_id["load-9"] is not None
    assert all(bid is None for lid, bid in by_id.items() if lid != "load-9")


def test_baseline_clearing_price_is_the_fixed_load_market_price() -> None:
    """case14 rates no branch, so its fixed-load solve clears at one uniform price system-wide
    -- the value interior_bid_for_load brackets. Pinned against a direct fixed-load solve, not
    a remembered number."""
    net = _case14()
    baseline = baseline_clearing_price(net)
    direct = opf.solve_dc_opf(net)
    assert direct.status == "Optimal"
    assert baseline == pytest.approx(max(b.lmp for b in direct.buses), abs=1e-9)
    # strictly between the cheapest generator's marginal cost and the fleet ceiling: a real
    # clearing price, not a bound artifact.
    assert 0.0 < baseline < fleet_max_marginal_cost(net)


def test_interior_bid_for_load_brackets_the_baseline_clearing_price() -> None:
    """The property the whole rule exists for: marginal value starts strictly above the baseline
    price and ends strictly below it, so the load's own optimality condition is met strictly
    inside [0, p_mw] instead of at a bound."""
    net = _case14()
    load_id = "load-9"
    baseline = baseline_clearing_price(net)
    bid = interior_bid_for_load(net, load_id)
    assert isinstance(bid, PolynomialBid)
    v2, v1, v0 = bid.coefficients
    assert v0 == 0.0
    p_anchor = next(ld for ld in net.loads if ld.id == load_id).p_mw

    mv_at_zero = v1
    mv_at_anchor = v1 + 2.0 * v2 * p_anchor
    assert mv_at_zero == pytest.approx(INTERIOR_TOP_MULTIPLE * baseline, abs=1e-6)
    assert mv_at_anchor == pytest.approx(INTERIOR_FLOOR_MULTIPLE * baseline, abs=1e-6)
    assert mv_at_anchor < baseline < mv_at_zero  # the bracket, stated as the assertion


def test_interior_bid_for_load_is_genuinely_concave() -> None:
    net = _case14()
    v2, _v1, _v0 = interior_bid_for_load(net, "load-9").coefficients
    assert v2 < 0.0  # strictly decreasing marginal value across the whole domain


def test_interior_bid_for_load_rejects_an_unknown_load() -> None:
    net = _case14()
    with pytest.raises(ValueError, match="no load with id"):
        interior_bid_for_load(net, "load-nope")


def test_with_bids_applies_the_interior_rule_only_to_the_named_subset() -> None:
    net = _case14()
    out = with_bids(net, interior_load_ids=["load-9"])
    by_id = {ld.id: ld.bid for ld in out.loads}
    assert by_id["load-9"] == interior_bid_for_load(net, "load-9")
    for load_id, bid in by_id.items():
        if load_id != "load-9":
            assert bid == bid_for_load(net, load_id)


def test_with_bids_rejects_an_interior_id_outside_the_bid_set() -> None:
    """A typo here would silently return the all-price-taking fixture the caller was trying to
    avoid -- the exact failure the parity test's power depends on not happening quietly."""
    net = _case14()
    with pytest.raises(ValueError, match="not in this call's bid set"):
        with_bids(net, load_ids=["load-2"], interior_load_ids=["load-9"])
