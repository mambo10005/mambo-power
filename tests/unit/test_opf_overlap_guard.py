"""AC-1(c): the generator-side mirror of ``_extract_and_validate``'s load-side overlap guard.

The load side has always raised when a load index appears in both ``demand_bid_coeffs`` and
``demand_pwl_bids``. The generator side had no mirror: a generator index in ``pwl_costs`` whose
``cost_coeffs`` row is nonzero has its cost charged **twice** — once by the polynomial objective
term and once by the epigraph rows — and the LP is perfectly happy to solve it.

**Why that was worth a raise rather than a note.** Measured on ``case14`` against the pre-guard
build (``.bionic/tmp/m7-a2-overlap-guard-probe.py``, reproduced 2026-08-28 by this slice):

===========================  ===============  ===================
form                         status           objective ($)
===========================  ===============  ===================
correct (zeroed poly row)    ``Optimal``      7708.066811
doubly-charged               ``Optimal``      10117.766447
===========================  ===============  ===================

— a difference of **+2409.699637**, with generator 0's dispatch driven from **223.192107 MW** to
**-0.000000 MW**. Nothing raises, nothing warns, and the status stays ``Optimal``: the failure is
silent and plausible, which is the epic's most-repeated finding about which defects are expensive.
:func:`~mambo_power.opf.gen_cost_coeffs` maintains the all-zero-row convention by construction,
which is why five waves never hit it; M7 is the first wave whose coefficients are assembled per
round from strategy output rather than read off ``Generator.cost``.

The guard lives in ``_extract_and_validate``, so all three builders that call it inherit it —
:func:`~mambo_power.opf.dc_opf.dc_opf`, :func:`~mambo_power.opf.multiperiod.multiperiod_dc_opf`
and :func:`~mambo_power.opf.zonal.zonal_dc_opf` — and the tests below assert that on each.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import OpfDcOptions, _extract_and_validate, dc_opf
from mambo_power.opf.multiperiod import multiperiod_dc_opf
from mambo_power.opf.zonal import zonal_dc_opf
from tests._fixtures import FIXTURES_DIR

CASE14 = FIXTURES_DIR / "case14.m"

#: The generator the pre-guard probe measured the silent wrong answer on.
DOUBLY_CHARGED_GEN = 0

_MESSAGE = "appear in both cost_coeffs"


@pytest.fixture(scope="module")
def case14_arrays() -> NetworkArrays:
    return NetworkArrays.from_network(matpower.load(CASE14))


@pytest.fixture(scope="module")
def true_coeffs(case14_arrays: NetworkArrays) -> np.ndarray:
    """The generators' own cost coefficients, from the repo's own extractor."""
    coeffs, pwl = gen_cost_coeffs(matpower.load(CASE14), case14_arrays)
    assert pwl == {}, "case14 carries no PWL generator — the probe's premise"
    return coeffs


@pytest.fixture(scope="module")
def pwl_offer(case14_arrays: NetworkArrays, true_coeffs: np.ndarray) -> list[tuple[float, float]]:
    """A faithful 5-point sample of generator 0's own quadratic cost, as a PWL curve.

    Sampling the generator's *own* curve is what makes the correct form and the doubly-charged
    form comparable: the two differ only in whether the polynomial row was zeroed, not in what
    cost the generator is claimed to have.
    """
    c2, c1, c0 = true_coeffs[DOUBLY_CHARGED_GEN]
    arr = case14_arrays
    p_min = float(arr.gen_p_min_pu[DOUBLY_CHARGED_GEN]) * arr.base_mva
    p_max = float(arr.gen_p_max_pu[DOUBLY_CHARGED_GEN]) * arr.base_mva
    return [(float(p), float(c2 * p * p + c1 * p + c0)) for p in np.linspace(p_min, p_max, 5)]


def test_dc_opf_raises_on_a_nonzero_cost_row_beside_a_pwl_entry(
    case14_arrays: NetworkArrays, true_coeffs: np.ndarray, pwl_offer: list[tuple[float, float]]
) -> None:
    """The exact input the pre-guard build solved to a silently wrong ``Optimal``."""
    with pytest.raises(ValueError, match=_MESSAGE) as excinfo:
        dc_opf(
            case14_arrays,
            true_coeffs,
            OpfDcOptions(),
            pwl_costs={DOUBLY_CHARGED_GEN: pwl_offer},
        )
    message = str(excinfo.value)
    assert f"[{DOUBLY_CHARGED_GEN}]" in message, message
    assert "pwl_costs" in message and "all-zero" in message, message


def test_the_correct_form_of_the_same_offer_still_solves(
    case14_arrays: NetworkArrays, true_coeffs: np.ndarray, pwl_offer: list[tuple[float, float]]
) -> None:
    """The guard rejects the *overlap*, not the PWL offer.

    Zeroing the polynomial row — the all-zero-row convention ``gen_cost_coeffs`` maintains by
    construction — is the correct way to hand the same curve in, and it clears. Without this, a
    guard that rejected every ``pwl_costs`` entry outright would still pass the test above.
    """
    correct = true_coeffs.copy()
    correct[DOUBLY_CHARGED_GEN] = 0.0
    solution = dc_opf(
        case14_arrays, correct, OpfDcOptions(), pwl_costs={DOUBLY_CHARGED_GEN: pwl_offer}
    )
    assert solution.status == "Optimal", solution.message
    assert solution.dispatch_mw[DOUBLY_CHARGED_GEN] > 1.0, (
        "the correct form must actually dispatch the generator the doubly-charged form "
        f"pushed to zero, got {solution.dispatch_mw[DOUBLY_CHARGED_GEN]!r}"
    )


def test_a_zero_cost_row_beside_a_pwl_entry_passes_the_guard(
    case14_arrays: NetworkArrays, true_coeffs: np.ndarray, pwl_offer: list[tuple[float, float]]
) -> None:
    """The convention's own shape must not trip the guard — the guard's negative control."""
    coeffs = true_coeffs.copy()
    coeffs[DOUBLY_CHARGED_GEN] = 0.0
    problem = _extract_and_validate(
        coeffs,
        {DOUBLY_CHARGED_GEN: pwl_offer},
        None,
        None,
        len(case14_arrays.gen_ids),
        len(case14_arrays.load_ids),
    )
    assert problem.pwl_gen_idxs == [DOUBLY_CHARGED_GEN]


def test_gen_cost_coeffs_output_never_trips_the_guard() -> None:
    """The producer that maintains the invariant keeps passing it.

    ``gen_cost_coeffs`` zeroes the polynomial row of every PWL generator, so its own output is
    always a legal pair. ``case14_pwl.m`` is the repo's fixture that actually has PWL generators.
    """
    net = matpower.load(FIXTURES_DIR / "derived" / "case14_pwl.m")
    arr = NetworkArrays.from_network(net)
    coeffs, pwl = gen_cost_coeffs(net, arr)
    assert pwl, "case14_pwl.m must carry PWL generators for this to prove anything"
    solution = dc_opf(arr, coeffs, OpfDcOptions(), pwl_costs=pwl)
    assert solution.status == "Optimal", solution.message


def test_multiperiod_inherits_the_same_guard(
    case14_arrays: NetworkArrays, true_coeffs: np.ndarray, pwl_offer: list[tuple[float, float]]
) -> None:
    with pytest.raises(ValueError, match=_MESSAGE):
        multiperiod_dc_opf(
            case14_arrays,
            true_coeffs,
            2,
            pwl_costs={DOUBLY_CHARGED_GEN: pwl_offer},
        )


def test_zonal_inherits_the_same_guard(
    case14_arrays: NetworkArrays, true_coeffs: np.ndarray, pwl_offer: list[tuple[float, float]]
) -> None:
    zone_of_bus = {bus_id: "z1" for bus_id in case14_arrays.bus_ids}
    with pytest.raises(ValueError, match=_MESSAGE):
        zonal_dc_opf(
            case14_arrays,
            true_coeffs,
            zone_of_bus,
            {},
            pwl_costs={DOUBLY_CHARGED_GEN: pwl_offer},
        )


def test_the_load_side_mirror_still_fires(
    case14_arrays: NetworkArrays, true_coeffs: np.ndarray
) -> None:
    """The message the new guard was shaped after, asserted beside it."""
    with pytest.raises(ValueError, match="appear in both demand_bid_coeffs and demand_pwl_bids"):
        dc_opf(
            case14_arrays,
            true_coeffs,
            OpfDcOptions(),
            demand_bid_coeffs={0: (0.0, 50.0, 0.0)},
            demand_pwl_bids={0: [(0.0, 0.0), (10.0, 500.0)]},
        )
