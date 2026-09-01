"""Unit test for ``tests._periods``: the 24-period load-profile test helper (M5 W7).

Mirrors ``tests/unit/test_rated_helper.py``'s and ``tests/unit/test_bids.py``'s own discipline:
proves the helper's guarantees directly (a genuine peak-to-trough swing, no mutation of the input
network, determinism) rather than merely exercising it as a side effect of another test.
"""

from __future__ import annotations

import pytest

from mambo_power.io.matpower import load
from mambo_power.model import Period
from tests._fixtures import FIXTURES_DIR
from tests._periods import (
    HOURS_PER_DAY,
    PEAK_HOUR,
    PEAK_MULTIPLE,
    TROUGH_HOUR,
    TROUGH_MULTIPLE,
    curve,
    derive_periods,
)


def _case14():  # type: ignore[no-untyped-def]
    return load(FIXTURES_DIR / "case14.m")


def test_derive_periods_returns_24_periods_by_default() -> None:
    net = _case14()
    periods = derive_periods(net)
    assert len(periods) == HOURS_PER_DAY == 24
    assert all(isinstance(p, Period) for p in periods)


def test_every_period_names_every_load() -> None:
    net = _case14()
    periods = derive_periods(net)
    load_ids = {ld.id for ld in net.loads}
    for period in periods:
        assert set(period.load_p_mw) == load_ids


def test_the_swing_is_real_not_a_flat_line() -> None:
    """Every load's own value across the 24 periods must span a real peak-to-trough range, not
    sit at (near-)one constant value -- the same "not a degenerate flat step" guard
    ``tests/_bids.py``'s own concavity test applies to its curve."""
    net = _case14()
    periods = derive_periods(net)
    for ld in net.loads:
        values = [p.load_p_mw[ld.id] for p in periods]
        assert max(values) == pytest.approx(ld.p_mw * PEAK_MULTIPLE, abs=1e-9)
        assert min(values) == pytest.approx(ld.p_mw * TROUGH_MULTIPLE, abs=1e-9)
        # a real, large swing -- not a rounding-scale wiggle
        assert (max(values) - min(values)) > 0.25 * ld.p_mw


def test_curve_peaks_and_troughs_where_documented() -> None:
    assert curve(PEAK_HOUR) == pytest.approx(PEAK_MULTIPLE)
    assert curve(TROUGH_HOUR) == pytest.approx(TROUGH_MULTIPLE)
    # a genuine smooth cycle: every other hour sits strictly between the two extremes
    for h in range(HOURS_PER_DAY):
        if h in (PEAK_HOUR, TROUGH_HOUR):
            continue
        assert TROUGH_MULTIPLE < curve(h) < PEAK_MULTIPLE


def test_does_not_mutate_the_input_network() -> None:
    net = _case14()
    before = [ld.p_mw for ld in net.loads]
    derive_periods(net)
    after = [ld.p_mw for ld in net.loads]
    assert before == after


def test_deterministic() -> None:
    net = _case14()
    a = derive_periods(net)
    b = derive_periods(net)
    assert [p.load_p_mw for p in a] == [p.load_p_mw for p in b]


def test_rejects_a_network_with_no_loads() -> None:
    net = _case14()
    net = net.model_copy(deep=True)
    net.loads = []
    with pytest.raises(ValueError, match="no loads"):
        derive_periods(net)


def test_rejects_a_non_positive_period_count() -> None:
    net = _case14()
    with pytest.raises(ValueError, match="n_periods"):
        derive_periods(net, n_periods=0)


def test_n_periods_is_respected_and_wraps_the_24_hour_cycle() -> None:
    net = _case14()
    periods = derive_periods(net, n_periods=48)
    assert len(periods) == 48
    # hour 0 and hour 24 (one full day later) must repeat exactly
    assert periods[0].load_p_mw == periods[24].load_p_mw
