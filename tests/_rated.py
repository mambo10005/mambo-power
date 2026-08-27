"""Rating-derivation test helper.

Most MATPOWER-shipped OPF fixtures carry no real ``RATE_A`` — every branch reads ``RATE_A == 0``,
MATPOWER's "unlimited" convention — so the PTDF flow-limit LP rows and the N-1 "violates a limit"
check have nothing to bind against on real multi-bus data. **case30 is the exception**: all 41 of
its branches ship a real rating (32/65/65/32/32/16/65 MVA on the seven inter-zone tie lines). This
module overwrites those too. That is deliberate and worth knowing before reading a case30 number
as a MATPOWER one: every rating any test here sees is derived by the rule below, so one derivation
rule governs every fixture and no test compares a synthetic rating against a shipped one. On
case30 the overwrite is a large change — the seven tie-line ratings become 1.52-8.97 MVA — which
is what makes the corridor caps derived from them bind.

The rating is derived *at test time* from each fixture's own unmodified base-case DC dispatch —
the same "documented, test-time transformation of an already-owned fixture" pattern
:mod:`tests._brute_force_lodf` already uses. No new fixture data is committed.

Margin: :data:`RATING_MARGIN` = 1.2 (20% headroom above the base-case ``|p_from_mw|``), floored
at :data:`RATING_FLOOR_MVA` so a near-zero-flow branch does not get a near-zero rating. Chosen
by a sanity sweep across all five OPF fixtures (recorded in full in
``.bionic/docs/record/m3-s1-report.md``): for every fixture and every non-bridge branch outage,
whether the LODF-estimated post-outage flow on any *other* branch would exceed that branch's
derived rating. At 1.2 the two largest fixtures alone already show hundreds of violating
outage/branch pairs (case118: 1173 pairs across 166 distinct outages; case300: 2981 pairs
across 297 outages) — a later N-1 violation-check test (S4) has real signal to catch, not just
the unconstrained-dispatch path. A looser margin (1.5) still shows dozens of violations per
fixture, so 1.2 was picked for headroom against DC-modelling slack while staying clearly
binding, not because a tighter margin was needed to get any violations at all.
"""

from __future__ import annotations

import numpy as np

from mambo_power.model import Network
from mambo_power.numerics import NetworkArrays
from mambo_power.pf import dc as pfdc

RATING_MARGIN = 1.2
"""Derived rating = ``RATING_MARGIN * base-case |p_from_mw|`` (20% headroom)."""

RATING_FLOOR_MVA = 1.0
"""Minimum derived rating, MVA — guards a near-zero base-case flow from a near-zero rating."""


def rated_network(net: Network) -> Network:
    """A copy of *net* with each in-service, connected branch's ``rating_mva`` derived.

    DC-solves the *unmodified* ``net`` once (:func:`mambo_power.pf.dc.solve` on the in-service
    :class:`~mambo_power.numerics.NetworkArrays`), then sets ``rating_mva = max(RATING_MARGIN *
    |p_from_mw|, RATING_FLOOR_MVA)`` for every branch :class:`NetworkArrays` keeps. A branch
    :class:`NetworkArrays` drops (out of service, or attached to a bus that is) keeps whatever
    rating it already had — there is no base-case flow to derive one from. Does not mutate
    *net*; returns a fresh :class:`Network` via ``model_copy(deep=True)``.
    """
    arr = NetworkArrays.from_network(net)
    sol = pfdc.solve(arr)
    flow_mw = np.abs(sol.p_from_pu) * arr.base_mva
    rating_by_id = {
        branch_id: max(float(flow_mw[k]) * RATING_MARGIN, RATING_FLOOR_MVA)
        for k, branch_id in enumerate(arr.branch_ids)
    }
    out = net.model_copy(deep=True)
    for br in out.branches:
        if br.id in rating_by_id:
            br.rating_mva = rating_by_id[br.id]
    return out
