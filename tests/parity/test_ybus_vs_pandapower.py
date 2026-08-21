"""AC-7 oracle: our Ybus / Yf / Yt / Bbus / PTDF / LODF agree with pandapower's pypower builders.

Oracle path (wave spec Design assumption (b)): ``pandapower.pypower.makeYbus.makeYbus(baseMVA,
bus, branch)``, ``makeBdc.makeBdc(bus, branch)``, ``makePTDF.makePTDF(baseMVA, bus, branch)``
and ``makeLODF.makeLODF(branch, PTDF)`` called directly on an internally-indexed ppc. The ppc
comes from the shared independent numpy read of the ``.m`` bytes
(:func:`tests.parity._mpc_reader.read_mpc_numpy`), re-indexed here so that ``BUS_I`` runs
0..nb-1 in row order and the branch endpoint columns hold those positions; the branch matrix
is zero-padded to pandapower's ``branch_cols`` width because ``branch_vectors`` reads the
asymmetry columns. Bus alignment to our arrays goes through ``BUS_I`` → ``bus-<n>`` →
``NetworkArrays.bus_index``, never through row order.

The five fixtures carry no out-of-service buses or branches (S4 report §6.14), which the test
asserts before comparing: the oracle builds Ybus over *all* ppc buses, while ``NetworkArrays``
holds the in-service subset, so the two dimensions must coincide for the comparison to be
element-by-element.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.numerics import NetworkArrays, bbus, bf, bridges, lodf, p_shift, ptdf, ybus, yf_yt
from tests._brute_force_lodf import brute_force_lodf
from tests._fixtures import FIXTURES, FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy

TOL = 1e-9


def internal_ppc(raw: dict[str, Any]) -> tuple[float, np.ndarray, np.ndarray, dict[str, int]]:
    """Re-index the raw matrices to 0-based positions; return (baseMVA, bus, branch, id→pos)."""
    from pandapower.pypower.idx_brch import branch_cols
    from pandapower.pypower.idx_bus import bus_cols

    bus = np.zeros((raw["bus"].shape[0], bus_cols))
    bus[:, : raw["bus"].shape[1]] = raw["bus"]
    position = {int(n): k for k, n in enumerate(raw["bus"][:, 0])}
    bus[:, 0] = np.arange(bus.shape[0])

    branch = np.zeros((raw["branch"].shape[0], branch_cols))
    branch[:, : raw["branch"].shape[1]] = raw["branch"]
    branch[:, 0] = [position[int(n)] for n in raw["branch"][:, 0]]
    branch[:, 1] = [position[int(n)] for n in raw["branch"][:, 1]]
    id_to_pos = {f"bus-{n}": k for n, k in position.items()}
    return float(raw["baseMVA"]), bus, branch, id_to_pos


@pytest.fixture(scope="module", params=FIXTURES)
def case(request: pytest.FixtureRequest) -> dict[str, Any]:
    path = FIXTURES_DIR / f"{request.param}.m"
    raw = read_mpc_numpy(path)
    net = matpower.load(path)
    arr = NetworkArrays.from_network(net)
    base, bus, branch, id_to_pos = internal_ppc(raw)
    # Precondition for an element-by-element comparison (see module docstring).
    assert all(b.in_service for b in net.buses), request.param
    assert all(br.in_service for br in net.branches), request.param
    assert arr.n_bus == bus.shape[0] and arr.n_branch == branch.shape[0]
    # Permutation taking oracle bus positions to ours: ours[k] == theirs[perm[k]].
    perm = np.array([id_to_pos[bus_id] for bus_id in arr.bus_ids])
    return {
        "name": request.param,
        "base": base,
        "bus": bus,
        "branch": branch,
        "net": net,
        "arr": arr,
        "perm": perm,
    }


def test_ybus_yf_yt_match_pandapower(case: dict[str, Any]) -> None:
    from pandapower.pypower.makeYbus import makeYbus

    arr, perm = case["arr"], case["perm"]
    y_pp, yf_pp, yt_pp = makeYbus(case["base"], case["bus"], case["branch"])
    y_pp = y_pp.toarray()[np.ix_(perm, perm)]
    yf_pp = yf_pp.toarray()[:, perm]
    yt_pp = yt_pp.toarray()[:, perm]

    ours = ybus(arr).toarray()
    worst = float(np.abs(ours - y_pp).max())
    assert worst <= TOL, f"{case['name']}: max |Ybus diff| = {worst:.3e}"
    yf, yt = yf_yt(arr)
    assert float(np.abs(yf.toarray() - yf_pp).max()) <= TOL
    assert float(np.abs(yt.toarray() - yt_pp).max()) <= TOL


def test_bbus_bf_pshift_match_pandapower(case: dict[str, Any]) -> None:
    from pandapower.pypower.makeBdc import makeBdc

    arr, perm = case["arr"], case["perm"]
    b_pp, bf_pp, pbusinj_pp, _, _ = makeBdc(case["bus"], case["branch"])
    b_pp = b_pp.toarray()[np.ix_(perm, perm)]
    bf_pp = bf_pp.toarray()[:, perm]
    pbusinj_pp = np.asarray(pbusinj_pp).ravel()[perm]

    assert float(np.abs(bbus(arr).toarray() - b_pp).max()) <= TOL
    assert float(np.abs(bf(arr).toarray() - bf_pp).max()) <= TOL
    assert float(np.abs(p_shift(arr) - pbusinj_pp).max()) <= TOL


def test_bus_type_codes_round_trip_from_raw(case: dict[str, Any]) -> None:
    """Duplication 4: importer decode (``_BUS_TYPES``) and arrays encode (``BUS_TYPE_CODE``) agree.

    The raw BUS_TYPE column is permuted into our bus order before comparing.
    """
    raw_types = case["bus"][:, 1].astype(int)[case["perm"]]
    np.testing.assert_array_equal(case["arr"].bus_type, raw_types)


def test_ptdf_lodf_match_pandapower(case: dict[str, Any]) -> None:
    """Critic issue 5: independent PTDF/LODF oracle; bridge columns are undefined on both sides."""
    from pandapower.pypower.makeLODF import makeLODF
    from pandapower.pypower.makePTDF import makePTDF

    arr, perm = case["arr"], case["perm"]
    h_pp_raw = np.asarray(makePTDF(case["base"], case["bus"], case["branch"]))  # slack = REF bus
    h = ptdf(arr)
    worst = float(np.abs(h - h_pp_raw[:, perm]).max())
    assert worst <= TOL, f"{case['name']}: max |PTDF diff| = {worst:.3e}"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # pypower divides by zero on bridge columns
        l_pp = np.asarray(makeLODF(case["branch"], h_pp_raw))
    l_ours = lodf(arr)
    bridge = bridges(arr)
    keep = [k for k in range(arr.n_branch) if k not in bridge]
    worst = float(np.abs(l_ours[:, keep] - l_pp[:, keep]).max())
    assert worst <= TOL, f"{case['name']}: max |LODF diff| = {worst:.3e}"
    # pandapower's makeLODF representation of a bridge (singular) column is platform-dependent --
    # non-finite on Linux/Windows, finite and bounded on macOS Accelerate (CI runs 32434672637,
    # 32435150722). We assert nothing about it; only that OUR column is NaN.
    for k in bridge:
        assert np.isnan(l_ours[:, k]).all()


def test_lodf_matches_brute_force_outage(case: dict[str, Any]) -> None:
    """AC-7 on every fixture: LODF equals the single-outage PTDF difference, branch by branch."""
    arr = case["arr"]
    rng = np.random.default_rng(11)
    p = rng.normal(size=arr.n_bus)
    p[arr.slack] -= p.sum()
    expected = brute_force_lodf(case["net"], arr, p)
    keep = [k for k in range(arr.n_branch) if k not in bridges(arr)]
    np.testing.assert_allclose(lodf(arr)[:, keep], expected[:, keep], rtol=0, atol=1e-8)


def test_bridges_are_consistent_with_a_removal_bfs(case: dict[str, Any]) -> None:
    """Independent bridge oracle: remove each branch, BFS from the slack, check reach."""
    arr = case["arr"]
    expected: list[int] = []
    for k in range(arr.n_branch):
        adjacency: list[list[int]] = [[] for _ in range(arr.n_bus)]
        for m in range(arr.n_branch):
            if m != k:
                adjacency[arr.f[m]].append(arr.t[m])
                adjacency[arr.t[m]].append(arr.f[m])
        seen = {arr.slack}
        stack = [arr.slack]
        while stack:
            node = stack.pop()
            for nxt in adjacency[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        if len(seen) != arr.n_bus:
            expected.append(k)
    assert bridges(arr) == expected
