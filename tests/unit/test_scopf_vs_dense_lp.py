"""The SCOPF family against a dense LP written out independently (ADR-016, 020, 021, 025).

``opf.solve_scopf`` generates its post-contingency rows lazily, with the N-1 and N-2 screens as
oracles, and solves through ``dc_opf``'s row-family core. This file builds the *whole* problem
up front — every single outage, every corrected dispatch, every branch pair — as one dense
``scipy.optimize.linprog`` LP from nothing but the PTDF/LODF matrices and the network's numbers,
and checks that the four modes land on the same objective and dispatch:

* preventive at the normal rating, preventive at the emergency rating, corrective (every single
  outage gets a redispatch block within each unit's ramp, held to the normal rating), and N-2
  (every non-islanding branch pair as a preventive row at the emergency rating).

The fixture is ``derived/case14_rated`` with the quadratic costs replaced by distinct linear ones
— so the corrective mode's chord linearisation (module docstring of ``opf.scopf``) is not in
play and the comparison is exact — and, for the emergency modes, a 30 % emergency rating.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest
from scipy.optimize import linprog

from mambo_power import cases
from mambo_power.contingency.n2 import ISLAND_DET_TOL
from mambo_power.model import Network, PolynomialCost
from mambo_power.numerics import NetworkArrays, bridges, lodf, ptdf
from mambo_power.opf import ScopfOptions, solve_scopf

MARGINAL = [20.0, 25.0, 30.0, 35.0, 40.0]
RAMP_MW = 20.0
HEADROOM = 1.3


def _network(*, emergency: bool) -> Network:
    net = cases.load("derived/case14_rated")
    for gen, cost in zip(net.generators, MARGINAL, strict=True):
        gen.cost = PolynomialCost(coefficients=[cost, 0.0])
        gen.ramp_up_mw = gen.ramp_down_mw = RAMP_MW
    if emergency:
        for br in net.branches:
            if br.rating_mva is not None:
                br.rating_emergency_mva = HEADROOM * br.rating_mva
    return net


class _Dense:
    """The dense LP, assembled from the matrices alone."""

    def __init__(self, net: Network) -> None:
        self.arr = arr = NetworkArrays.from_network(net)
        self.n_gen, self.n_branch = len(arr.gen_ids), arr.n_branch
        self.ptdf = ptdf(arr)
        self.lodf = lodf(arr, self.ptdf)
        self.bridges = set(bridges(arr))
        self.cost = np.array(MARGINAL)
        self.p_min = arr.gen_p_min_pu * arr.base_mva
        self.p_max = arr.gen_p_max_pu * arr.base_mva
        self.normal = arr.rating_pu * arr.base_mva
        self.emergency = arr.rating_emergency_pu * arr.base_mva
        load_bus = (arr.p_load_pu + arr.g_shunt_pu) * arr.base_mva
        self.demand = float(np.sum(load_bus))
        # flow = G @ p + const, G the PTDF through the generator-to-bus incidence
        self.G = self.ptdf[:, arr.gen_bus]
        self.const = -self.ptdf @ load_bus
        assert not np.any(arr.shift_rad), "the oracle leaves phase shifters out"
        self.singles: list[tuple[str, int]] = [
            ("branch", k) for k in range(self.n_branch) if k not in self.bridges
        ] + [("generator", g) for g in range(self.n_gen) if int(arr.gen_bus[g]) != arr.slack]

    # -- post-contingency flow as (matrix on p, constant) ---------------------------------------

    def single(self, kind: str, k: int) -> tuple[np.ndarray, np.ndarray]:
        if kind == "branch":
            col = self.lodf[:, k]
            return self.G + np.outer(col, self.G[k]), self.const + col * self.const[k]
        G = self.G.copy()
        G[:, k] = 0.0  # the lost unit's output is gone; the slack's pickup moves no flow
        return G, self.const

    def pair(self, i: int, j: int) -> tuple[np.ndarray, np.ndarray] | None:
        det = 1.0 - self.lodf[i, j] * self.lodf[j, i]
        if abs(det) <= ISLAND_DET_TOL:
            return None
        w_i = (self.lodf[:, i] + self.lodf[:, j] * self.lodf[j, i]) / det
        w_j = (self.lodf[:, j] + self.lodf[:, i] * self.lodf[i, j]) / det
        G = self.G + np.outer(w_i, self.G[i]) + np.outer(w_j, self.G[j])
        const = self.const + w_i * self.const[i] + w_j * self.const[j]
        return G, const

    # -- the LP ----------------------------------------------------------------------------------

    def solve(self, *, corrective: bool, pairs: bool) -> tuple[str, float, np.ndarray]:
        n_gen, n_branch = self.n_gen, self.n_branch
        blocks = self.singles if corrective else []
        n_var = n_gen * (1 + len(blocks))
        rated = np.isfinite(self.normal)
        A_ub: list[np.ndarray] = []
        b_ub: list[np.ndarray] = []
        A_eq: list[np.ndarray] = []
        b_eq: list[float] = []

        def limit_rows(G: np.ndarray, const: np.ndarray, rating: np.ndarray, col0: int) -> None:
            keep = rated & np.isfinite(rating)
            rows = np.zeros((2 * int(keep.sum()), n_var))
            rows[: keep.sum(), col0 : col0 + n_gen] = G[keep]
            rows[keep.sum() :, col0 : col0 + n_gen] = -G[keep]
            A_ub.append(rows)
            b_ub.append(np.concatenate([rating[keep] - const[keep], rating[keep] + const[keep]]))

        balance = np.zeros(n_var)
        balance[:n_gen] = 1.0
        A_eq.append(balance)
        b_eq.append(self.demand)
        limit_rows(self.G, self.const, self.normal, 0)
        for kind, k in self.singles:
            G, const = self.single(kind, k)
            limit_rows(G, const, self.emergency, 0)
        if pairs:
            for i, j in itertools.combinations(range(n_branch), 2):
                if i in self.bridges or j in self.bridges:
                    continue
                post = self.pair(i, j)
                if post is not None:
                    limit_rows(post[0], post[1], self.emergency, 0)
        bounds = [(float(lo), float(hi)) for lo, hi in zip(self.p_min, self.p_max, strict=True)]
        for b, (kind, k) in enumerate(blocks):
            col0 = n_gen * (1 + b)
            lo, hi = self.p_min.copy(), self.p_max.copy()
            if kind == "generator":
                lo[k] = hi[k] = 0.0
            bounds.extend((float(x), float(y)) for x, y in zip(lo, hi, strict=True))
            row = np.zeros(n_var)
            row[col0 : col0 + n_gen] = 1.0
            A_eq.append(row)
            b_eq.append(self.demand)
            if kind == "branch":
                G, const = self.single("branch", k)
            else:
                G, const = self.G, self.const  # the redispatch covers the loss: no pickup
            limit_rows(G, const, self.normal, col0)
            for g in range(n_gen):
                if kind == "generator" and g == k:
                    continue
                up = np.zeros(n_var)
                up[col0 + g], up[g] = 1.0, -1.0
                A_ub.append(np.stack([up, -up]))
                b_ub.append(np.array([RAMP_MW, RAMP_MW]))
        c = np.zeros(n_var)
        c[:n_gen] = self.cost
        res = linprog(
            c,
            A_ub=np.vstack(A_ub),
            b_ub=np.concatenate(b_ub),
            A_eq=np.vstack(A_eq),
            b_eq=np.array(b_eq),
            bounds=bounds,
            method="highs",
        )
        status = "Optimal" if res.status == 0 else ("Infeasible" if res.status == 2 else "other")
        dispatch = res.x[:n_gen] if res.status == 0 else np.full(n_gen, np.nan)
        return status, float(res.fun) if res.status == 0 else float("nan"), dispatch


@pytest.mark.parametrize(
    ("label", "emergency", "options"),
    [
        ("preventive, normal rating", False, ScopfOptions()),
        ("preventive, emergency rating", True, ScopfOptions()),
        ("corrective", True, ScopfOptions(corrective=True)),
        ("N-2 at the emergency rating", True, ScopfOptions(branch_pairs=True)),
    ],
)
def test_constraint_generation_matches_the_dense_lp(
    label: str, emergency: bool, options: ScopfOptions
) -> None:
    net = _network(emergency=emergency)
    ours = solve_scopf(net, options)
    dense = _Dense(net)
    status, cost, dispatch = dense.solve(corrective=options.corrective, pairs=options.branch_pairs)

    assert ours.status == status == "Optimal", (label, ours.status, status, ours.message)
    assert ours.objective_cost == pytest.approx(cost, rel=1e-7), label
    ours_dispatch = np.array([g.p_mw for g in ours.generators])
    assert np.allclose(ours_dispatch, dispatch, atol=1e-4), (label, ours_dispatch, dispatch)
    assert ours.secure


def test_the_dense_lp_agrees_that_n2_at_the_normal_rating_is_infeasible() -> None:
    net = _network(emergency=False)
    assert solve_scopf(net, ScopfOptions(branch_pairs=True)).status == "Infeasible"
    status, _, _ = _Dense(net).solve(corrective=False, pairs=True)
    assert status == "Infeasible"


def test_the_four_answers_bracket_each_other() -> None:
    normal = solve_scopf(_network(emergency=False)).objective_cost
    relaxed = _network(emergency=True)
    emergency = solve_scopf(relaxed).objective_cost
    corrective = solve_scopf(relaxed, ScopfOptions(corrective=True)).objective_cost
    pairs = solve_scopf(relaxed, ScopfOptions(branch_pairs=True)).objective_cost
    assert emergency <= corrective <= normal
    assert emergency <= pairs
