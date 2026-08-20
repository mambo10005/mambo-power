"""AC-7 oracle: our Ybus / Yf / Yt / Bbus agree with pandapower's pypower builders.

Oracle path (wave spec Design assumption (b)): ``pandapower.pypower.makeYbus.makeYbus(baseMVA,
bus, branch)`` and ``pandapower.pypower.makeBdc.makeBdc(bus, branch)`` called directly on an
internally-indexed ppc. The ppc comes from the S4 parity module's independent numpy read of
the ``.m`` bytes (``read_mpc_numpy``), re-indexed here so that ``BUS_I`` runs 0..nb-1 in row
order and the branch endpoint columns hold those positions; the branch matrix is zero-padded
to pandapower's ``branch_cols`` width because ``branch_vectors`` reads the asymmetry columns.
Bus alignment to our arrays goes through ``BUS_I`` → ``bus-<n>`` → ``NetworkArrays.bus_index``,
never through row order.

The five fixtures carry no out-of-service buses or branches (S4 report §6.14), which the test
asserts before comparing: the oracle builds Ybus over *all* ppc buses, while ``NetworkArrays``
holds the in-service subset, so the two dimensions must coincide for the comparison to be
element-by-element.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.numerics import NetworkArrays, bbus, bf, bridges, p_shift, ybus, yf_yt

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "matpower"
FIXTURES = ["case14", "case30", "case_ieee30", "case57", "case118"]
TOL = 1e-9


def _s4_module() -> ModuleType:
    """Load the S4 parity module by path (``--import-mode=importlib`` has no package)."""
    name = "_s4_matpower_vs_pandapower"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name("test_matpower_vs_pandapower.py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
    raw = _s4_module().read_mpc_numpy(path)
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
