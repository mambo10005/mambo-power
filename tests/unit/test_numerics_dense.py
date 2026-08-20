"""AC-7 dense re-derivation oracle for Ybus, Bbus, PTDF and LODF.

Everything here is computed a second time with plain dense numpy written out explicitly in
this file — a double loop over branches for Ybus and Bbus, ``numpy.linalg.solve`` for the
DC angles, and an actual network rebuild with one branch removed for LODF. No helper is
shared with ``mambo_power.numerics``.

The case is a 5-bus meshed core (buses 1-5, seven branches including a tapped and
phase-shifted transformer and a parallel pair) plus one radial bus 6 hanging off bus 5, so
that exactly one branch is a bridge and the undefined-LODF path is exercised.
"""

from __future__ import annotations

import cmath
import math

import numpy as np
import pytest

from mambo_power.model import Branch, Bus, Generator, Load, Network, Shunt
from mambo_power.numerics import NetworkArrays, bbus, bf, bridges, lodf, p_shift, ptdf, ybus, yf_yt

BASE = 100.0


def six_bus() -> Network:
    return Network(
        base_mva=BASE,
        buses=[
            Bus(id="bus-1", base_kv=230.0, type="slack"),
            Bus(id="bus-2", base_kv=230.0, type="pv"),
            Bus(id="bus-3", base_kv=230.0, type="pq"),
            Bus(id="bus-4", base_kv=115.0, type="pq"),
            Bus(id="bus-5", base_kv=115.0, type="pq"),
            Bus(id="bus-6", base_kv=115.0, type="pq"),
        ],
        branches=[
            Branch(id="br-12", from_bus="bus-1", to_bus="bus-2", r=0.02, x=0.06, b=0.06),
            Branch(id="br-13", from_bus="bus-1", to_bus="bus-3", r=0.08, x=0.24, b=0.05),
            Branch(id="br-23", from_bus="bus-2", to_bus="bus-3", r=0.06, x=0.18, b=0.04),
            Branch(id="br-24", from_bus="bus-2", to_bus="bus-4", r=0.06, x=0.18, b=0.04),
            Branch(
                id="xf-34",
                from_bus="bus-3",
                to_bus="bus-4",
                r=0.01,
                x=0.12,
                b=0.0,
                tap_ratio=0.97,
                shift_deg=5.0,
                rating_mva=120.0,
            ),
            Branch(id="br-45a", from_bus="bus-4", to_bus="bus-5", r=0.03, x=0.10, b=0.02),
            Branch(id="br-45b", from_bus="bus-4", to_bus="bus-5", r=0.04, x=0.15, b=0.03),
            Branch(id="br-35", from_bus="bus-3", to_bus="bus-5", r=0.05, x=0.20, b=0.03),
            Branch(id="br-56", from_bus="bus-5", to_bus="bus-6", r=0.02, x=0.08, b=0.01),
        ],
        generators=[
            Generator(
                id="gen-1",
                bus="bus-1",
                p_mw=0.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=500.0,
                q_min_mvar=-300.0,
                q_max_mvar=300.0,
                v_set_pu=1.06,
            ),
            Generator(
                id="gen-2",
                bus="bus-2",
                p_mw=40.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=100.0,
                q_min_mvar=-40.0,
                q_max_mvar=50.0,
                v_set_pu=1.0,
            ),
        ],
        loads=[
            Load(id="load-2", bus="bus-2", p_mw=20.0, q_mvar=10.0),
            Load(id="load-3", bus="bus-3", p_mw=45.0, q_mvar=15.0),
            Load(id="load-4", bus="bus-4", p_mw=40.0, q_mvar=5.0),
            Load(id="load-5", bus="bus-5", p_mw=60.0, q_mvar=10.0),
            Load(id="load-6", bus="bus-6", p_mw=15.0, q_mvar=5.0),
        ],
        shunts=[Shunt(id="shunt-3", bus="bus-3", g_mw=2.0, b_mvar=15.0)],
    )


@pytest.fixture(scope="module")
def net() -> Network:
    return six_bus()


@pytest.fixture(scope="module")
def arr(net: Network) -> NetworkArrays:
    return NetworkArrays.from_network(net)


# --- dense re-derivations written out in full ---------------------------------------------------


def dense_ybus(net: Network) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Explicit double loop: MATPOWER branch model, from-side tap, shunt on the diagonal."""
    pos = {bus.id: k for k, bus in enumerate(net.buses)}
    nb, nl = len(net.buses), len(net.branches)
    y = np.zeros((nb, nb), dtype=complex)
    yf = np.zeros((nl, nb), dtype=complex)
    yt = np.zeros((nl, nb), dtype=complex)
    for k, br in enumerate(net.branches):
        i, j = pos[br.from_bus], pos[br.to_bus]
        ys = 1.0 / complex(br.r, br.x)
        bc = 1j * br.b / 2.0
        ratio = 1.0 if br.tap_ratio is None else br.tap_ratio
        shift = 0.0 if br.shift_deg is None else math.radians(br.shift_deg)
        a = ratio * cmath.exp(1j * shift)
        yff = (ys + bc) / (a * a.conjugate())
        yft = -ys / a.conjugate()
        ytf = -ys / a
        ytt = ys + bc
        y[i, i] += yff
        y[i, j] += yft
        y[j, i] += ytf
        y[j, j] += ytt
        yf[k, i], yf[k, j] = yff, yft
        yt[k, i], yt[k, j] = ytf, ytt
    for sh in net.shunts:
        y[pos[sh.bus], pos[sh.bus]] += complex(sh.g_mw, sh.b_mvar) / net.base_mva
    return y, yf, yt


def dense_bbus(net: Network) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Explicit double loop: b = 1/(x * tap), phase-shift injections as in MATPOWER makeBdc."""
    pos = {bus.id: k for k, bus in enumerate(net.buses)}
    nb, nl = len(net.buses), len(net.branches)
    bmat = np.zeros((nb, nb))
    bfm = np.zeros((nl, nb))
    susc = np.zeros(nl)
    pinj = np.zeros(nb)
    for k, br in enumerate(net.branches):
        i, j = pos[br.from_bus], pos[br.to_bus]
        ratio = 1.0 if br.tap_ratio is None else br.tap_ratio
        bk = 1.0 / (br.x * ratio)
        susc[k] = bk
        bmat[i, i] += bk
        bmat[j, j] += bk
        bmat[i, j] -= bk
        bmat[j, i] -= bk
        bfm[k, i], bfm[k, j] = bk, -bk
        shift = 0.0 if br.shift_deg is None else math.radians(br.shift_deg)
        pinj[i] += -bk * shift
        pinj[j] -= -bk * shift
    return bmat, bfm, susc, pinj


def dense_ptdf_column(net: Network, bus: int, slack: int) -> np.ndarray:
    """Flows for a unit injection at ``bus`` withdrawn at ``slack`` by solving B θ = P directly."""
    bmat, bfm, _, _ = dense_bbus(net)
    nb = bmat.shape[0]
    keep = [k for k in range(nb) if k != slack]
    p = np.zeros(nb)
    p[bus] += 1.0
    p[slack] -= 1.0
    theta = np.zeros(nb)
    theta[keep] = np.linalg.solve(bmat[np.ix_(keep, keep)], p[keep])
    return bfm @ theta


# --- Ybus / Yf / Yt ----------------------------------------------------------------------------


def test_ybus_matches_dense_double_loop(net: Network, arr: NetworkArrays) -> None:
    y_dense, _, _ = dense_ybus(net)
    y_sparse = ybus(arr)
    assert y_sparse.shape == (6, 6)
    assert y_sparse.dtype == np.complex128
    np.testing.assert_allclose(y_sparse.toarray(), y_dense, rtol=0, atol=1e-12)


def test_yf_yt_match_dense_and_assemble_ybus(net: Network, arr: NetworkArrays) -> None:
    _, yf_dense, yt_dense = dense_ybus(net)
    yf, yt = yf_yt(arr)
    np.testing.assert_allclose(yf.toarray(), yf_dense, rtol=0, atol=1e-12)
    np.testing.assert_allclose(yt.toarray(), yt_dense, rtol=0, atol=1e-12)
    nb, nl = arr.n_bus, arr.n_branch
    cf = np.zeros((nl, nb))
    ct = np.zeros((nl, nb))
    cf[np.arange(nl), arr.f] = 1.0
    ct[np.arange(nl), arr.t] = 1.0
    ysh = np.diag(arr.g_shunt_pu + 1j * arr.b_shunt_pu)
    rebuilt = cf.T @ yf.toarray() + ct.T @ yt.toarray() + ysh
    np.testing.assert_allclose(rebuilt, ybus(arr).toarray(), rtol=0, atol=1e-12)


def test_ybus_is_not_symmetric_with_phase_shift(arr: NetworkArrays) -> None:
    y = ybus(arr).toarray()
    i, j = arr.bus_index["bus-3"], arr.bus_index["bus-4"]
    assert abs(y[i, j] - y[j, i]) > 1e-6


# --- Bbus / Bf / phase-shift injection -----------------------------------------------------------


def test_bbus_matches_dense_double_loop(net: Network, arr: NetworkArrays) -> None:
    b_dense, bf_dense, _, pinj_dense = dense_bbus(net)
    b_sparse = bbus(arr)
    assert b_sparse.dtype == np.float64
    np.testing.assert_allclose(b_sparse.toarray(), b_dense, rtol=0, atol=1e-12)
    np.testing.assert_allclose(bf(arr).toarray(), bf_dense, rtol=0, atol=1e-12)
    np.testing.assert_allclose(p_shift(arr), pinj_dense, rtol=0, atol=1e-12)
    assert abs(pinj_dense).max() > 0.0  # the shifter really contributes


def test_bbus_is_symmetric_with_zero_row_sums(arr: NetworkArrays) -> None:
    b = bbus(arr).toarray()
    np.testing.assert_allclose(b, b.T, rtol=0, atol=1e-12)
    np.testing.assert_allclose(b.sum(axis=1), 0.0, rtol=0, atol=1e-12)


# --- PTDF --------------------------------------------------------------------------------------


def test_ptdf_slack_column_is_zero(arr: NetworkArrays) -> None:
    h = ptdf(arr)
    assert h.shape == (arr.n_branch, arr.n_bus)
    e_slack = np.zeros(arr.n_bus)
    e_slack[arr.slack] = 1.0
    np.testing.assert_array_equal(h @ e_slack, 0.0)


def test_ptdf_columns_equal_direct_dc_solve(net: Network, arr: NetworkArrays) -> None:
    h = ptdf(arr)
    for bus in range(arr.n_bus):
        expected = dense_ptdf_column(net, bus, arr.slack)
        np.testing.assert_allclose(h[:, bus], expected, rtol=0, atol=1e-10)


def test_ptdf_with_explicit_slack(net: Network, arr: NetworkArrays) -> None:
    other = arr.bus_index["bus-4"]
    h = ptdf(arr, slack=other)
    np.testing.assert_array_equal(h[:, other], 0.0)
    for bus in range(arr.n_bus):
        expected = dense_ptdf_column(net, bus, other)
        np.testing.assert_allclose(h[:, bus], expected, rtol=0, atol=1e-10)


def test_ptdf_flows_conserve_at_every_bus(arr: NetworkArrays) -> None:
    """Sum-of-flows-around-a-cut: net flow out of bus i equals its injection."""
    h = ptdf(arr)
    nb, nl = arr.n_bus, arr.n_branch
    cft = np.zeros((nl, nb))
    cft[np.arange(nl), arr.f] += 1.0
    cft[np.arange(nl), arr.t] -= 1.0
    rng = np.random.default_rng(7)
    p = rng.normal(size=nb)
    p[arr.slack] -= p.sum()
    flows = h @ p
    np.testing.assert_allclose(cft.T @ flows, p, rtol=0, atol=1e-10)


# --- LODF and bridges ----------------------------------------------------------------------------


def test_bridges_is_exactly_the_radial_branch(arr: NetworkArrays) -> None:
    assert bridges(arr) == [arr.branch_index["br-56"]]


def test_lodf_bridge_column_is_nan_and_diagonal_minus_one(arr: NetworkArrays) -> None:
    l_mat = lodf(arr)
    assert l_mat.shape == (arr.n_branch, arr.n_branch)
    k_bridge = arr.branch_index["br-56"]
    assert np.isnan(l_mat[:, k_bridge]).all()
    for k in range(arr.n_branch):
        if k != k_bridge:
            assert l_mat[k, k] == -1.0
    nan_columns = [k for k in range(arr.n_branch) if np.isnan(l_mat[:, k]).any()]
    assert nan_columns == bridges(arr)


def test_lodf_matches_brute_force_outage(net: Network, arr: NetworkArrays) -> None:
    h = ptdf(arr)
    l_mat = lodf(arr)
    rng = np.random.default_rng(11)
    p = rng.normal(size=arr.n_bus)
    p[arr.slack] -= p.sum()
    pre = h @ p
    for k in range(arr.n_branch):
        if k in bridges(arr):
            continue
        assert abs(pre[k]) > 1e-6, "test injection must load every branch"
        outaged = net.model_copy(deep=True)
        outaged.branches = [
            br.model_copy(update={"in_service": br.id != arr.branch_ids[k]}) for br in net.branches
        ]
        outaged = Network.model_validate(outaged.model_dump())
        arr_k = NetworkArrays.from_network(outaged)
        assert arr_k.bus_ids == arr.bus_ids
        post = ptdf(arr_k) @ p
        expected = np.zeros(arr.n_branch)
        for l_idx, branch_id in enumerate(arr.branch_ids):
            if l_idx == k:
                expected[l_idx] = -1.0
            else:
                expected[l_idx] = (post[arr_k.branch_index[branch_id]] - pre[l_idx]) / pre[k]
        np.testing.assert_allclose(l_mat[:, k], expected, rtol=0, atol=1e-8)


def test_lodf_accepts_precomputed_ptdf(arr: NetworkArrays) -> None:
    h = ptdf(arr)
    np.testing.assert_array_equal(
        np.nan_to_num(lodf(arr, ptdf_matrix=h), nan=123.0),
        np.nan_to_num(lodf(arr), nan=123.0),
    )


def test_dense_oracle_case_has_parallel_branches(arr: NetworkArrays) -> None:
    pairs = list(zip(arr.f.tolist(), arr.t.tolist(), strict=True))
    assert len(pairs) != len(set(pairs))
