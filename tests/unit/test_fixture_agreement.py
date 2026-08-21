"""Agreement checks over the five MATPOWER fixtures (review Duplication 3, critic issue 6).

* ``NetworkArrays`` carries generator quantities twice — per-bus sums and per-generator
  arrays. ``bincount`` of the per-generator arrays must reproduce the per-bus sums on every
  fixture (the multi-generator case is covered by ``test_numerics_arrays``; no fixture has
  one).
* The importer maps ``RATE_A == 0`` to ``rating_mva=None``, so the new ``rating_mva > 0``
  rule stays silent on every fixture.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.numerics import NetworkArrays
from tests._fixtures import FIXTURES, FIXTURES_DIR


@pytest.fixture(scope="module", params=FIXTURES)
def arr(request: pytest.FixtureRequest) -> NetworkArrays:
    return NetworkArrays.from_network(matpower.load(FIXTURES_DIR / f"{request.param}.m"))


def test_per_bus_generator_sums_agree_with_per_generator_arrays(arr: NetworkArrays) -> None:
    pairs = [
        (arr.p_gen_pu, arr.gen_p_pu),
        (arr.q_gen_pu, arr.gen_q_pu),
        (arr.p_min_pu, arr.gen_p_min_pu),
        (arr.p_max_pu, arr.gen_p_max_pu),
        (arr.q_min_pu, arr.gen_q_min_pu),
        (arr.q_max_pu, arr.gen_q_max_pu),
    ]
    assert arr.gen_bus.size > 0
    for per_bus, per_gen in pairs:
        summed = np.bincount(arr.gen_bus, weights=per_gen, minlength=arr.n_bus)
        np.testing.assert_allclose(summed, per_bus, rtol=0, atol=1e-15)


def test_fixture_ratings_are_absent_or_positive(arr: NetworkArrays) -> None:
    # RATE_A 0 -> None -> inf in pu; a 0 would now be BAD_RANGE, and no fixture trips it.
    assert np.all(arr.rating_pu > 0)
