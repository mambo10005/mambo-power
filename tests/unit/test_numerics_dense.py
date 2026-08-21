"""AC-7 dense re-derivation oracle for Ybus, Bbus, PTDF and LODF.

Everything here is computed a second time with plain dense numpy written out explicitly in
this file — a double loop over branches for Ybus and Bbus, ``numpy.linalg.solve`` for the
DC angles, and an actual network rebuild with one branch removed for LODF. No helper is
shared with ``mambo_power.numerics``.

Every check runs on the hand-built 6-bus case *and* on each of the five MATPOWER fixtures
(AC-7: "for every fixture"). The 6-bus case is a 5-bus meshed core (buses 1-5, seven
branches including a tapped and phase-shifted transformer and a parallel pair) plus one radial
bus 6 hanging off bus 5, so that exactly one branch is a bridge and the undefined-LODF path is
exercised; the fixtures carry no phase shifter, so the assertions that need one stay on the
6-bus case (``six_arr``). The brute-force LODF (one network rebuild per branch) runs here on
the 6-bus case only and on the fixtures in the parity tier, to keep this tier under its time
budget.
"""

from __future__ import annotations

import cmath
import math

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.model import Branch, Bus, Generator, Load, Network, Shunt
from mambo_power.numerics import NetworkArrays, bbus, bf, bridges, lodf, p_shift, ptdf, ybus, yf_yt
from tests._brute_force_lodf import brute_force_lodf
from tests._fixtures import FIXTURES, FIXTURES_DIR

BASE = 100.0
CASES = ["six_bus", *FIXTURES]


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


@pytest.fixture(scope="module", params=CASES)
def net(request: pytest.FixtureRequest) -> Network:
    if request.param == "six_bus":
        return six_bus()
    loaded = matpower.load(FIXTURES_DIR / f"{request.param}.m")
    # The dense helpers index buses by position in ``net.buses``; that equals the arrays'
    # position only when nothing is out of service, which holds for every fixture.
    assert all(b.in_service for b in loaded.buses), request.param
    assert all(br.in_service for br in loaded.branches), request.param
    return loaded


@pytest.fixture(scope="module")
def arr(net: Network) -> NetworkArrays:
    return NetworkArrays.from_network(net)


@pytest.fixture(scope="module")
def six_arr() -> NetworkArrays:
    return NetworkArrays.from_network(six_bus())


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


def dense_ptdf(net: Network, slack: int) -> np.ndarray:
    """Column ``j``: flows for a unit injection at bus ``j`` withdrawn at ``slack``, by solving
    the reduced dense ``B θ = P`` directly (one right-hand side per bus)."""
    bmat, bfm, _, _ = dense_bbus(net)
    nb = bmat.shape[0]
    keep = [k for k in range(nb) if k != slack]
    p = np.eye(nb)
    p[slack, :] -= 1.0
    theta = np.zeros((nb, nb))
    theta[keep] = np.linalg.solve(bmat[np.ix_(keep, keep)], p[keep])
    return bfm @ theta


# --- Ybus / Yf / Yt ----------------------------------------------------------------------------


def test_ybus_matches_dense_double_loop(net: Network, arr: NetworkArrays) -> None:
    y_dense, _, _ = dense_ybus(net)
    y_sparse = ybus(arr)
    assert y_sparse.shape == (arr.n_bus, arr.n_bus)
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


def test_ybus_is_not_symmetric_with_phase_shift(six_arr: NetworkArrays) -> None:
    y = ybus(six_arr).toarray()
    i, j = six_arr.bus_index["bus-3"], six_arr.bus_index["bus-4"]
    assert abs(y[i, j] - y[j, i]) > 1e-6


# --- Bbus / Bf / phase-shift injection -----------------------------------------------------------


def test_bbus_matches_dense_double_loop(net: Network, arr: NetworkArrays) -> None:
    b_dense, bf_dense, _, pinj_dense = dense_bbus(net)
    b_sparse = bbus(arr)
    assert b_sparse.dtype == np.float64
    np.testing.assert_allclose(b_sparse.toarray(), b_dense, rtol=0, atol=1e-12)
    np.testing.assert_allclose(bf(arr).toarray(), bf_dense, rtol=0, atol=1e-12)
    np.testing.assert_allclose(p_shift(arr), pinj_dense, rtol=0, atol=1e-12)


def test_phase_shifter_contributes_to_p_shift(six_arr: NetworkArrays) -> None:
    _, _, _, pinj_dense = dense_bbus(six_bus())
    assert abs(pinj_dense).max() > 0.0  # the shifter really contributes
    np.testing.assert_allclose(p_shift(six_arr), pinj_dense, rtol=0, atol=1e-12)


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
    np.testing.assert_allclose(ptdf(arr), dense_ptdf(net, arr.slack), rtol=0, atol=1e-10)


def test_ptdf_with_explicit_slack(net: Network, arr: NetworkArrays) -> None:
    other = arr.n_bus - 1 if arr.slack != arr.n_bus - 1 else 0
    h = ptdf(arr, slack=other)
    np.testing.assert_array_equal(h[:, other], 0.0)
    np.testing.assert_allclose(h, dense_ptdf(net, other), rtol=0, atol=1e-10)


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


def test_bridges_is_exactly_the_radial_branch(six_arr: NetworkArrays) -> None:
    assert bridges(six_arr) == [six_arr.branch_index["br-56"]]


def test_lodf_bridge_columns_are_nan_and_diagonal_minus_one(arr: NetworkArrays) -> None:
    l_mat = lodf(arr)
    assert l_mat.shape == (arr.n_branch, arr.n_branch)
    bridge = bridges(arr)
    for k in range(arr.n_branch):
        if k in bridge:
            assert np.isnan(l_mat[:, k]).all()
        else:
            assert l_mat[k, k] == -1.0
            assert np.isfinite(l_mat[:, k]).all()
    nan_columns = [k for k in range(arr.n_branch) if np.isnan(l_mat[:, k]).any()]
    assert nan_columns == bridge


def test_lodf_matches_brute_force_outage(six_arr: NetworkArrays) -> None:
    # The same check over the five fixtures (177 rebuilds on case118) lives in the parity tier:
    # tests/parity/test_ybus_vs_pandapower.py::test_lodf_matches_brute_force_outage.
    rng = np.random.default_rng(11)
    p = rng.normal(size=six_arr.n_bus)
    p[six_arr.slack] -= p.sum()
    expected = brute_force_lodf(six_bus(), six_arr, p)
    keep = [k for k in range(six_arr.n_branch) if k not in bridges(six_arr)]
    assert len(keep) == six_arr.n_branch - 1
    np.testing.assert_allclose(lodf(six_arr)[:, keep], expected[:, keep], rtol=0, atol=1e-8)


def test_lodf_accepts_precomputed_ptdf(arr: NetworkArrays) -> None:
    h = ptdf(arr)
    np.testing.assert_array_equal(
        np.nan_to_num(lodf(arr, ptdf_matrix=h), nan=123.0),
        np.nan_to_num(lodf(arr), nan=123.0),
    )


def test_dense_oracle_case_has_parallel_branches(six_arr: NetworkArrays) -> None:
    pairs = list(zip(six_arr.f.tolist(), six_arr.t.tolist(), strict=True))
    assert len(pairs) != len(set(pairs))
