"""Per-load 24-period profile helper (M5 W7, AC-6 fixture half).

No MATPOWER fixture carries anything beyond a single base-case ``Pd`` -- the format has no
multi-period concept at all (record/m5-research.md §8.3, the same "the format doesn't have the
section" gap ``tests/_bids.py``'s and ``tests/_rated.py``'s own module docstrings already name for
demand bids and branch ratings). This module derives a synthetic 24-hour load profile **at test
time** from each fixture's own already-committed ``Load.p_mw``, the same documented,
test-time-transformation discipline, committing no new fixture data.

**A single system-wide curve, not two phase-shifted archetypes -- and why the first design was
wrong.** An earlier version of this module alternated two phase-shifted diurnal curves across
``Network.loads`` (an odd-vs-even split, aiming for genuine locational diversity -- the concern
spec Design item 4's rejected "scalar system-wide load scaling" alternative names). Measured
directly against ``tests/_rated.py``'s own derived ratings on case14: any per-load *divergence*
from the network's own base-case load ratios -- even a 2-hour phase shift between two otherwise
identical curves, and even holding the *peak* multiplier at exactly 1.0 -- makes the 24-period LP
genuinely infeasible, not merely more costly. ``tests/_rated.py``'s ``RATING_MARGIN`` (1.2) is
applied uniformly to *every* branch's own base-case flow; case14's meshed core has several branches
sitting at that exact 20% headroom in the base case (e.g. ``branch-19``, rated 1.809 MVA against a
1.507 MVA base flow), and redispatch alone cannot keep every one of them under its own rating once
the per-bus injection pattern departs from the ratio the ratings were derived from -- confirmed by
bisection (scratchpad probe, not committed): uniform (single-curve) scaling stays feasible up to a
1.2x peak / 0.7x trough swing, while a divergent two-curve profile is already infeasible at a
2-hour phase shift with an unchanged 1.0x peak. A **single** curve applied to every load keeps
every branch's flow *proportional* to the same one multiplier, which is what keeps the whole
24-period horizon simultaneously feasible.

This is *not* the same failure spec Design item 4 warns against ("congestion binds in all or none,
storage arbitrage loses locational content"): a single curve's amplitude still varies by
:data:`PEAK_MULTIPLE` over :data:`TROUGH_MULTIPLE` across the day, and measured directly
(``tests/parity/test_market_multiperiod_vs_pypsa.py``'s own AC-6 fixture-fidelity test), some
hours congest a rated branch and most do not -- a real binding/non-binding split, not an
all-or-nothing one. What a single curve *does* give up is locational diversity in the load
*pattern itself*; ``tests/_storage.py``'s own siting rule supplies the remaining locational
content this wave's AC-6 fixture needs (the unit sees genuine LMP spread from congestion rent even
though every load moves in lockstep).

**Curve shape (pinned here, the same "genuine design choice, not invented, documented" pattern
``tests/_bids.py``'s ``VOLL_PER_MWH`` and ``tests/_rated.py``'s ``RATING_MARGIN`` both use).** A
raised cosine -- ``mult(h) = TROUGH_MULTIPLE + (PEAK_MULTIPLE - TROUGH_MULTIPLE) *
(1 - cos(2*pi*(h - trough_hour)/24)) / 2`` -- a smooth single-cycle swing from
:data:`TROUGH_MULTIPLE` at :data:`TROUGH_HOUR` to :data:`PEAK_MULTIPLE` twelve hours later.
:data:`PEAK_MULTIPLE` = 1.2 and :data:`TROUGH_MULTIPLE` = 0.7 are the widest swing found feasible
by the bisection above, with a small margin kept back (the feasibility boundary measured between
a 1.2x/0.7x swing, which solves, and materially wider swings, which do not) -- pinned here rather
than pushed to the exact boundary, matching ``tests/_rated.py``'s own "headroom against modelling
slack" reasoning for its own margin choice.
"""

from __future__ import annotations

import math

from mambo_power.model import Network, Period

HOURS_PER_DAY = 24
"""The horizon length this module derives -- R7's own "24-period horizon"."""

PEAK_MULTIPLE = 1.2
"""Multiplier on every load's own ``p_mw`` at :data:`PEAK_HOUR` (module docstring)."""
TROUGH_MULTIPLE = 0.7
"""Multiplier on every load's own ``p_mw`` at :data:`TROUGH_HOUR` (module docstring)."""
PEAK_HOUR = 18
"""18:00 -- a conventional evening-peak hour."""
TROUGH_HOUR = 6
"""06:00, twelve hours from :data:`PEAK_HOUR` -- the raised cosine's own trough."""


def curve(hour: int) -> float:
    """``[TROUGH_MULTIPLE, PEAK_MULTIPLE]`` at ``hour`` (0-23), peaking at :data:`PEAK_HOUR`
    (module docstring)."""
    phase = 2.0 * math.pi * (hour - TROUGH_HOUR) / HOURS_PER_DAY
    shape = (1.0 - math.cos(phase)) / 2.0  # 0 at TROUGH_HOUR, 1 at PEAK_HOUR
    return TROUGH_MULTIPLE + (PEAK_MULTIPLE - TROUGH_MULTIPLE) * shape


def derive_periods(net: Network, n_periods: int = HOURS_PER_DAY) -> list[Period]:
    """``n_periods`` (default 24) :class:`~mambo_power.model.Period` objects, each carrying every
    one of ``net``'s loads at that hour's own :func:`curve` multiplier times that load's own
    committed ``p_mw`` (module docstring). Every period names every load explicitly (not a
    partial override), so a peak-to-trough swing is visible on every load, not just the ones a
    period happens to mention.

    Does not mutate ``net``. Raises ``ValueError`` if ``net`` has no loads (nothing to derive a
    profile against) or if ``n_periods < 1``.
    """
    if not net.loads:
        raise ValueError("net has no loads -- nothing to derive a period profile against")
    if n_periods < 1:
        raise ValueError(f"n_periods must be >= 1, got {n_periods}")

    periods = []
    for t in range(n_periods):
        hour = t % HOURS_PER_DAY
        m = curve(hour)
        periods.append(Period(load_p_mw={ld.id: ld.p_mw * m for ld in net.loads}))
    return periods
