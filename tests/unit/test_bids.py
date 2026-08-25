"""Unit test for ``tests._bids``: the bid-derivation test helper (M4 W6, AC-6 fixture half).

Mirrors ``tests/unit/test_rated_helper.py``'s own discipline for ``tests/_rated.py``: proves the
helper's guarantees directly (anchored to the load's own committed ``p_mw``, genuinely concave,
not a degenerate flat step) rather than merely exercising it as a side effect of another test.
"""

from __future__ import annotations

import pytest

from mambo_power.io.matpower import load
from mambo_power.model import PolynomialBid
from tests._bids import VOLL_PER_MWH, bid_for_load, fleet_max_marginal_cost, with_bids
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
