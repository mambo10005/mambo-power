"""Corrective load shedding in the SCOPF (ADR-033): a corrected state may leave fixed load
unserved at ``ScopfOptions.load_shed_cost`` $/MWh.

The hand case is ``test_opf_scopf_corrective.py``'s triangle with ``br13`` rated 60 MVA normal
and 90 emergency, ``g3`` capped at ``P = 15`` MW with corrective ramp ``Δ``. After the ``br12``
outage every MW for ``b2`` crosses ``br13``: the corrected flow is ``90 − s − x^c`` for ``s`` MW
shed at ``b2`` and ``x^c <= min(P, x + Δ)``, so ``s >= 30 − x^c``. No redispatch reaches 30, so
without shedding the corrective problem is infeasible; with it the LP trades base cost
(``10 $/MW`` for every MW of ``x``) against shedding:

* ``VOLL = 1000, Δ = 10``: ``x^c = 15`` needs ``x >= 5``; cost ``950``, shed ``15`` (``15 000``);
* ``VOLL = 1000, Δ`` unlimited: ``x = 0``, ``x^c = 15``; cost ``900``, shed ``15``;
* ``VOLL = 5, Δ = 10``: a MW of base shift costs 10 and saves 5 of shedding, so ``x = 0``,
  ``x^c = 10``, shed ``20`` (``100``).

Every corrected state is confirmed by a DC re-solve with the outage applied, the redispatch
written in and the shed load taken off the bus — ``br13`` sits exactly at its rating.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from mambo_power import cases
from mambo_power.jobs import SolveRequest, run
from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialCost
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import ScopfOptions, gen_cost_coeffs, solve_scopf
from mambo_power.opf.dc_opf import CorrectiveRows, OpfDcOptions, dc_opf
from mambo_power.results import ScopfDcResult


def _gen(gen_id: str, bus: str, cost: float, p_max: float, ramp: float | None) -> Generator:
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=0.0,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=p_max,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        ramp_up_mw=ramp,
        ramp_down_mw=ramp,
        cost=PolynomialCost(coefficients=[cost, 0.0]),
    )


def _triangle(g3_ramp: float | None, g3_max: float = 15.0) -> Network:
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pv"),
        ],
        branches=[
            Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=100.0),
            Branch(
                id="br13",
                from_bus="b1",
                to_bus="b3",
                r=0.0,
                x=0.1,
                b=0.0,
                rating_mva=60.0,
                rating_emergency_mva=90.0,
            ),
            Branch(id="br23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0, rating_mva=100.0),
        ],
        generators=[_gen("g1", "b1", 10.0, 200.0, None), _gen("g3", "b3", 20.0, g3_max, g3_ramp)],
        loads=[Load(id="ld2", bus="b2", p_mw=90.0, q_mvar=0.0)],
    )


def _shed(voll: float) -> ScopfOptions:
    return ScopfOptions(corrective=True, load_shed_cost=voll)


@pytest.mark.parametrize(
    ("voll", "ramp", "cost", "x", "x_c", "shed"),
    [
        (1000.0, 10.0, 950.0, 5.0, 15.0, 15.0),
        (1000.0, None, 900.0, 0.0, 15.0, 15.0),
        (5.0, 10.0, 900.0, 0.0, 10.0, 20.0),
    ],
)
def test_the_triangle_sheds_what_no_redispatch_can_cover(
    voll: float, ramp: float | None, cost: float, x: float, x_c: float, shed: float
) -> None:
    net = _triangle(ramp)
    without = solve_scopf(net, ScopfOptions(corrective=True))
    assert without.status == "Infeasible"

    result = solve_scopf(net, _shed(voll))
    assert result.status == "Optimal", result.message
    assert result.objective_cost == pytest.approx(cost)
    assert result.shed_cost == pytest.approx(voll * shed)
    assert {g.id: g.p_mw for g in result.generators} == pytest.approx({"g1": 90 - x, "g3": x})
    (correction,) = [c for c in result.corrections if c.outage_id == "br12"]
    assert {r.id: r.p_mw for r in correction.redispatch} == pytest.approx(
        {"g1": 90.0 - shed - x_c, "g3": x_c}
    )
    assert [(s.bus, s.shed_mw) for s in correction.shed] == [("b2", pytest.approx(shed))]
    assert correction.shed_mw == pytest.approx(shed)
    assert correction.confirmed_max_loading == pytest.approx(1.0)  # br13 exactly at 60 MW
    assert result.corrected_secure and result.secure
    (row,) = correction.constraints
    assert (row.outage_id, row.branch_id) == ("br12", "br13")
    assert abs(row.post_contingency_flow_mw) == pytest.approx(60.0)
    assert all(c.shed == [] and c.shed_mw == 0.0 for c in result.corrections if c is not correction)


def test_shedding_is_never_used_when_redispatch_suffices() -> None:
    # g3 uncapped: the corrective answer of test_opf_scopf_corrective.py (E = 90, Δ = 10 -> 1100)
    net = _triangle(10.0, g3_max=200.0)
    with_shed = solve_scopf(net, _shed(1000.0))
    plain = solve_scopf(net, ScopfOptions(corrective=True))
    assert with_shed.status == plain.status == "Optimal"
    assert with_shed.objective_cost == pytest.approx(plain.objective_cost) == pytest.approx(1100.0)
    assert with_shed.shed_cost == 0.0
    assert all(c.shed == [] and c.shed_mw == 0.0 for c in with_shed.corrections)


def test_shedding_requires_corrective_and_a_positive_price() -> None:
    with pytest.raises(ValidationError, match="requires corrective"):
        ScopfOptions(load_shed_cost=1000.0)
    with pytest.raises(ValidationError):
        ScopfOptions(corrective=True, load_shed_cost=0.0)
    reply = run(
        SolveRequest(kind="opf.scopf", network=_triangle(10.0), options={"load_shed_cost": 5.0})
    )
    assert reply.status == "failed" and reply.error is not None
    assert reply.error.code == "BAD_OPTIONS"


def test_result_round_trips_and_the_job_carries_the_shedding() -> None:
    net = _triangle(10.0)
    result = solve_scopf(net, _shed(1000.0))
    assert ScopfDcResult.model_validate_json(result.model_dump_json()) == result
    reply = run(
        SolveRequest(
            kind="opf.scopf",
            network=net,
            options={"corrective": True, "load_shed_cost": 1000.0},
        )
    )
    assert reply.status == "ok" and isinstance(reply.result, ScopfDcResult)
    assert reply.result.shed_cost == pytest.approx(15000.0)
    assert reply.result.provenance.options["load_shed_cost"] == 1000.0


def test_case14_rated_with_tight_ramps_is_only_securable_by_shedding() -> None:
    net = cases.load("derived/case14_rated")
    for br in net.branches:
        if br.rating_mva is not None:
            br.rating_mva *= 0.9
            br.rating_emergency_mva = 1.4 * br.rating_mva
    for g in net.generators:
        g.ramp_up_mw = g.ramp_down_mw = 10.0

    assert solve_scopf(net, ScopfOptions(corrective=True)).status == "Infeasible"
    result = solve_scopf(net, _shed(5000.0))
    assert result.status == "Optimal", result.message
    assert result.secure and result.corrected_secure
    shed_total = sum(c.shed_mw for c in result.corrections)
    assert shed_total > 0.0
    assert result.shed_cost == pytest.approx(5000.0 * shed_total)
    for c in result.corrections:
        assert c.shed_mw == pytest.approx(sum(s.shed_mw for s in c.shed))
        assert c.confirmed_max_loading <= 1.0 + 1e-9
        bus_load = {ld.bus: ld.p_mw for ld in net.loads}
        for s in c.shed:
            assert 0.0 < s.shed_mw <= bus_load[s.bus] + 1e-9  # only the bus's own load
    # a lost unit is what the others' 10 MW ramps cannot pick up: generator outages shed
    lost = [c for c in result.corrections if c.outage_kind == "generator"]
    assert lost and any(c.shed_mw > 0.0 for c in lost)


def test_builder_validates_the_shed_bound_and_pays_the_price() -> None:
    net = _triangle(10.0)
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _ = gen_cost_coeffs(net, arr)
    good = CorrectiveRows(
        lost_gen=np.array([-1]),
        ramp_up_mw=np.array([np.inf, 10.0]),
        ramp_down_mw=np.array([np.inf, 10.0]),
        block_of_row=np.zeros(0, dtype=np.int64),
        bus_sensitivity=np.zeros((0, 3)),
        const_mw=np.zeros(0),
        rating_mw=np.zeros(0),
        shed_cost=1000.0,
        shed_max_mw=np.array([0.0, 90.0, 0.0]),
    )
    solution = dc_opf(arr, cost_coeffs, OpfDcOptions(), corrective=good)
    assert solution.status == "Optimal"
    assert solution.corrective_shed_mw.shape == (1, 3)
    assert solution.corrective_shed_cost == 0.0  # no corrected flow row: nothing to shed for
    bad = CorrectiveRows(
        lost_gen=good.lost_gen,
        ramp_up_mw=good.ramp_up_mw,
        ramp_down_mw=good.ramp_down_mw,
        block_of_row=good.block_of_row,
        bus_sensitivity=good.bus_sensitivity,
        const_mw=good.const_mw,
        rating_mw=good.rating_mw,
        shed_cost=1000.0,
        shed_max_mw=np.array([90.0]),
    )
    with pytest.raises(ValueError, match="shed_max_mw must have shape"):
        dc_opf(arr, cost_coeffs, OpfDcOptions(), corrective=bad)
