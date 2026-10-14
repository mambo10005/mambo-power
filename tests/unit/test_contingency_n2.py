"""N-2 branch-pair screening (:mod:`mambo_power.contingency.n2`, ADR-024).

The agreement guarantee, as for N-1: on ``derived/case14_rated`` every pair of non-bridge branches
is re-solved by brute force, and (a) every pair the generalised-LODF screen flags is confirmed to
within solver precision on every flagged branch, (b) no pair the screen does not flag violates
in the re-solve, and (c) every pair the screen calls islanding fails the model's connectivity
check — while every pair it does not leaves the network connected. The triangle is the pure cut
set case: taking any two of its three branches out isolates a bus, so nothing is estimated.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from mambo_power import cases, contingency
from mambo_power.contingency.n2 import N2Options, pair_flows_mw, screen_n2
from mambo_power.jobs import SolveRequest, run
from mambo_power.model import Branch, Bus, Generator, Load, Network, validate_network
from mambo_power.numerics import NetworkArrays
from mambo_power.pf import dc as pfdc
from mambo_power.results import N2Result

TOL_MW = 1e-6


def _triangle() -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pq"),
        ],
        branches=[
            Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=50.0),
            Branch(id="br13", from_bus="b1", to_bus="b3", r=0.0, x=0.1, b=0.0, rating_mva=50.0),
            Branch(id="br23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0, rating_mva=50.0),
        ],
        generators=[
            Generator(
                id="g1",
                bus="b1",
                p_mw=90.0,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=200.0,
                q_min_mvar=0.0,
                q_max_mvar=0.0,
                v_set_pu=1.0,
            )
        ],
        loads=[Load(id="ld2", bus="b2", p_mw=90.0, q_mvar=0.0)],
    )


def _brute_force_flows(net: Network, arr: NetworkArrays, i: int, j: int) -> np.ndarray | None:
    """Signed flows in ``arr`` branch order with ``i`` and ``j`` out, or ``None`` if the pair
    disconnects the network."""
    outaged = net.model_copy(deep=True)
    ids = {arr.branch_ids[i], arr.branch_ids[j]}
    for br in outaged.branches:
        if br.id in ids:
            br.in_service = False
    if any(issue.code == "DISCONNECTED_BUS" for issue in validate_network(outaged)):
        return None
    arr_ij = NetworkArrays.from_network(outaged)
    sol = pfdc.solve(arr_ij)
    flows = np.zeros(arr.n_branch)
    for k, branch_id in enumerate(arr.branch_ids):
        if branch_id in arr_ij.branch_index:
            flows[k] = sol.p_from_pu[arr_ij.branch_index[branch_id]] * arr_ij.base_mva
    return flows


def test_every_pair_of_the_triangle_is_a_cut_set() -> None:
    result = contingency.n2(_triangle())

    assert result.outages == [] and result.bridge_branch_ids == []
    assert result.n_pairs_screened == 3
    assert sorted(map(tuple, result.islanding_pairs)) == [
        ("br12", "br13"),
        ("br12", "br23"),
        ("br13", "br23"),
    ]


def test_screen_agrees_with_brute_force_on_case14_rated() -> None:
    net = cases.load("derived/case14_rated")
    arr = NetworkArrays.from_network(net)
    result = contingency.n2(net)
    screen = screen_n2(arr)

    assert result.bridge_branch_ids == ["branch-14"]
    assert result.n_pairs_screened == 19 * 18 // 2
    assert result.outages and not result.truncated
    assert all(o.confirmed_violating for o in result.outages)
    bridges = {arr.branch_index[b] for b in result.bridge_branch_ids}
    islanding = {
        tuple(sorted(arr.branch_index[b] for b in pair)) for pair in result.islanding_pairs
    }
    flagged = {tuple(arr.branch_index[b] for b in o.outage_branch_ids): o for o in result.outages}
    rating = arr.rating_emergency_pu * arr.base_mva

    checked = 0
    for i, j in itertools.combinations(range(arr.n_branch), 2):
        if i in bridges or j in bridges:
            continue
        actual = _brute_force_flows(net, arr, i, j)
        if (i, j) in islanding:
            assert actual is None, (i, j)
            continue
        assert actual is not None, (i, j)
        checked += 1
        estimate = pair_flows_mw(arr, i, j)
        assert np.max(np.abs(estimate - actual)) < 1e-9
        violating = {
            k
            for k in range(arr.n_branch)
            if k not in (i, j) and abs(actual[k]) > rating[k] + TOL_MW
        }
        if (i, j) in flagged:
            outage = flagged[(i, j)]
            by_id = {f.branch_id: f for f in outage.flagged_branches}
            assert set(by_id) == {arr.branch_ids[k] for k in screen.flagged[(i, j)]}
            for f in outage.flagged_branches:
                assert abs(f.confirmed_flow_mw - abs(actual[arr.branch_index[f.branch_id]])) < 1e-9
                assert abs(f.estimated_flow_mw - f.confirmed_flow_mw) < 1e-9
            assert {arr.branch_ids[k] for k in violating} <= set(by_id)
        else:
            assert not violating, (i, j, violating)
    assert checked > 100


def test_emergency_ratings_are_the_post_contingency_limit() -> None:
    net = cases.load("derived/case14_rated")
    relaxed = net.model_copy(deep=True)
    for br in relaxed.branches:
        if br.rating_mva is not None:
            br.rating_emergency_mva = 1.5 * br.rating_mva

    strict = contingency.n2(net)
    loose = contingency.n2(relaxed)

    assert sum(o.confirmed_violating for o in loose.outages) < sum(
        o.confirmed_violating for o in strict.outages
    )
    for outage in loose.outages:
        for flag in outage.flagged_branches:
            original = next(b for b in net.branches if b.id == flag.branch_id)
            assert original.rating_mva is not None
            assert flag.rating_mva == pytest.approx(1.5 * original.rating_mva)


def test_confirmation_is_capped_and_says_so() -> None:
    result = contingency.n2(cases.load("derived/case14_rated"), N2Options(max_confirmed_pairs=5))
    assert len(result.outages) == 5 and result.truncated
    assert [o.outage_branch_ids for o in result.outages] == sorted(
        o.outage_branch_ids for o in result.outages
    )


def test_result_round_trips_and_the_jobs_kind_runs() -> None:
    result = contingency.n2(cases.load("derived/case14_rated"))
    assert N2Result.model_validate_json(result.model_dump_json()) == result

    reply = run(
        SolveRequest(
            kind="n2",
            network=cases.load("derived/case14_rated"),
            options={"max_confirmed_pairs": 3},
        )
    )
    assert reply.status == "ok" and isinstance(reply.result, N2Result)
    assert len(reply.result.outages) == 3 and reply.result.truncated
    assert reply.result.provenance.kind == "n2"
