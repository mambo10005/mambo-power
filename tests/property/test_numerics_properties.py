"""Hypothesis properties of the network matrices on random connected networks.

Strategy: a random labelled tree on 3-30 buses (bus 0 is the slack, every other bus PQ)
plus 0..n random extra edges (parallel edges and multi-edges allowed), random r / x / b and
an optional off-nominal tap per branch, no phase shifters. The tree guarantees connectivity;
the extra edges create cycles so that bridge detection sees both kinds of branch.

``derandomize=True`` keeps CI reproducible; ``max_examples`` stays modest so the tier is fast.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from mambo_power.model import Branch, Bus, Generator, Network
from mambo_power.numerics import NetworkArrays, bbus, bridges, lodf, ptdf, ybus

SETTINGS = settings(max_examples=40, deadline=None, derandomize=True)


@st.composite
def networks(draw: Any) -> Network:
    n = draw(st.integers(min_value=3, max_value=30))
    edges: list[tuple[int, int]] = []
    for child in range(1, n):
        edges.append((draw(st.integers(min_value=0, max_value=child - 1)), child))
    n_extra = draw(st.integers(min_value=0, max_value=n))
    for _ in range(n_extra):
        u = draw(st.integers(min_value=0, max_value=n - 1))
        v = draw(st.integers(min_value=0, max_value=n - 1))
        if u != v:
            edges.append((u, v))
    branches = []
    for k, (u, v) in enumerate(edges):
        r = draw(st.floats(min_value=0.0, max_value=0.1))
        x = draw(st.floats(min_value=0.01, max_value=1.0))
        b = draw(st.floats(min_value=0.0, max_value=0.5))
        tap = draw(st.one_of(st.none(), st.floats(min_value=0.9, max_value=1.1)))
        branches.append(
            Branch(
                id=f"branch-{k}",
                from_bus=f"bus-{u}",
                to_bus=f"bus-{v}",
                r=r,
                x=x,
                b=b,
                tap_ratio=tap,
            )
        )
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id=f"bus-{i}", base_kv=110.0, type="slack" if i == 0 else "pq") for i in range(n)
        ],
        branches=branches,
        generators=[
            Generator(
                id="gen-0",
                bus="bus-0",
                p_mw=0.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=1000.0,
                q_min_mvar=-1000.0,
                q_max_mvar=1000.0,
                v_set_pu=1.0,
            )
        ],
    )


def bridges_by_removal(arr: NetworkArrays) -> list[int]:
    """Independent oracle: a branch is a bridge iff removing it disconnects the graph."""
    out: list[int] = []
    for k in range(arr.n_branch):
        adjacency: list[list[int]] = [[] for _ in range(arr.n_bus)]
        for m in range(arr.n_branch):
            if m != k:
                adjacency[arr.f[m]].append(arr.t[m])
                adjacency[arr.t[m]].append(arr.f[m])
        seen = {0}
        stack = [0]
        while stack:
            node = stack.pop()
            for nxt in adjacency[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if len(seen) != arr.n_bus:
            out.append(k)
    return out


@SETTINGS
@given(networks())
def test_ybus_symmetric_without_phase_shift(net: Network) -> None:
    y = ybus(NetworkArrays.from_network(net)).toarray()
    np.testing.assert_allclose(y, y.T, rtol=0, atol=1e-9)


@SETTINGS
@given(networks())
def test_bbus_row_sums_are_zero(net: Network) -> None:
    b = bbus(NetworkArrays.from_network(net)).toarray()
    np.testing.assert_allclose(b.sum(axis=1), 0.0, rtol=0, atol=1e-9)
    np.testing.assert_allclose(b, b.T, rtol=0, atol=1e-9)


@SETTINGS
@given(networks())
def test_reduced_bbus_is_nonsingular(net: Network) -> None:
    arr = NetworkArrays.from_network(net)
    b = bbus(arr).toarray()
    keep = [k for k in range(arr.n_bus) if k != arr.slack]
    reduced = b[np.ix_(keep, keep)]
    assert np.linalg.matrix_rank(reduced) == arr.n_bus - 1
    assert np.isfinite(np.linalg.cond(reduced))


@SETTINGS
@given(networks())
def test_ptdf_slack_column_is_zero(net: Network) -> None:
    arr = NetworkArrays.from_network(net)
    h = ptdf(arr)
    assert h.shape == (arr.n_branch, arr.n_bus)
    assert np.all(h[:, arr.slack] == 0.0)
    assert np.isfinite(h).all()


@SETTINGS
@given(networks())
def test_bridges_and_nan_lodf_columns_agree_with_removal(net: Network) -> None:
    arr = NetworkArrays.from_network(net)
    expected = bridges_by_removal(arr)
    assert bridges(arr) == expected
    l_mat = lodf(arr)
    nan_columns = [k for k in range(arr.n_branch) if np.isnan(l_mat[:, k]).any()]
    assert nan_columns == expected
    for k in range(arr.n_branch):
        if k not in expected:
            assert l_mat[k, k] == -1.0
            assert np.isfinite(l_mat[:, k]).all()
