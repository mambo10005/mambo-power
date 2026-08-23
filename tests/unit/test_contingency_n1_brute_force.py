"""AC-6: the LODF-screen-then-DC-reslve confirmed-violation set equals the brute force's.

On every one of the five OPF fixtures, using the derived ratings from ``tests._rated``, the set
of branch outages :func:`mambo_power.contingency.n1` confirms as violating must equal the set a
full brute-force sweep (every non-bridge outage re-solved directly, no LODF pre-filter —
``tests._brute_force_n1``) confirms: the screen must not miss a violation the re-solve would
catch, and must not confirm one the brute force would not. Timing is recorded per fixture
(record/m3-research.md §4 measured well under M1's ~10 s unit/parity tier-crossing threshold for
a bare script; this reconfirms it inside the actual pytest harness).
"""

from __future__ import annotations

import time

import pytest

from mambo_power.contingency import n1
from mambo_power.io.matpower import load
from mambo_power.numerics import NetworkArrays
from tests._brute_force_n1 import brute_force_n1
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network

OPF_FIXTURES = ["case14", "case_ieee30", "case57", "case118", "case300"]
"""The wave's own five-fixture set (wave spec W8) — not ``tests._fixtures.FIXTURES``, which also
carries ``case30`` (not part of the OPF/N-1 scope)."""


@pytest.mark.parametrize("name", OPF_FIXTURES)
def test_screen_then_confirm_agrees_with_brute_force(name: str) -> None:
    net = rated_network(load(FIXTURES_DIR / f"{name}.m"))
    arr = NetworkArrays.from_network(net)

    started = time.perf_counter()
    screened = {o.outage_branch_id for o in n1(net).outages if o.confirmed_violating}
    screen_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    brute = brute_force_n1(net, arr)
    brute_elapsed = time.perf_counter() - started

    print(
        f"{name}: screen+confirm={screen_elapsed:.3f}s brute_force={brute_elapsed:.3f}s "
        f"confirmed={len(screened)} outages"
    )

    assert screened == brute
