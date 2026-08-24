"""Unit test for ``tests._rated``: the rating-derivation test helper (W3, AC-4 fixture half).

Proves the helper's own guarantee — the *unmodified* base-case dispatch never violates the
ratings it just derived — on two fixtures. The margin/floor rationale and the fixture-wide
sanity-check numbers (how many outage/branch pairs *would* violate the derived ratings) are
recorded in ``.bionic/docs/record/m3-s1-report.md``, not repeated here.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from mambo_power.io.matpower import load
from mambo_power.numerics import NetworkArrays
from mambo_power.pf import dc as pfdc
from tests._fixtures import FIXTURES_DIR
from tests._rated import RATING_FLOOR_MVA, RATING_MARGIN, rated_network


@pytest.mark.parametrize("name", ["case14", "case118"])
def test_base_case_dispatch_never_violates_its_own_derived_ratings(name: str) -> None:
    net = load(FIXTURES_DIR / f"{name}.m")
    rated = rated_network(net)

    arr = NetworkArrays.from_network(rated)
    sol = pfdc.solve(arr)
    flow_mw = np.abs(sol.p_from_pu) * arr.base_mva
    rating_mva = arr.rating_pu * arr.base_mva

    assert np.all(np.isfinite(rating_mva)), "every in-service branch must get a real rating"
    assert np.all(flow_mw <= rating_mva + 1e-9)


def test_rating_is_margin_above_base_flow_with_a_floor() -> None:
    net = load(FIXTURES_DIR / "case14.m")
    base_arr = NetworkArrays.from_network(net)
    base_flow_mw = np.abs(pfdc.solve(base_arr).p_from_pu) * base_arr.base_mva

    rated = rated_network(net)
    by_id = {br.id: br.rating_mva for br in rated.branches}
    for k, branch_id in enumerate(base_arr.branch_ids):
        expected = max(float(base_flow_mw[k]) * RATING_MARGIN, RATING_FLOOR_MVA)
        assert by_id[branch_id] == pytest.approx(expected)


def test_does_not_mutate_the_input_network() -> None:
    net = load(FIXTURES_DIR / "case14.m")
    before = [br.rating_mva for br in net.branches]
    rated_network(net)
    after = [br.rating_mva for br in net.branches]
    assert before == after
    assert all(r is None for r in before), "case14 ships with no ratings (RATE_A == 0)"


def test_margin_is_a_real_headroom_not_a_no_op() -> None:
    assert RATING_MARGIN > 1.0
    assert math.isfinite(RATING_FLOOR_MVA) and RATING_FLOOR_MVA > 0.0
