"""Corrective SCOPF (ADR-021): post-contingency redispatch within each unit's ramp.

The hand case is ``test_opf_scopf.py``'s triangle with ``br13`` rated 60 MVA normal and ``E``
emergency, and ``g3`` allowed to move ``Δ`` MW after a contingency. The ``br12`` outage puts
``90 − x`` on ``br13`` at once (``x = g3``'s base dispatch) and ``90 − x^c`` after the correction
``x^c <= x + Δ``, so the base dispatch needs ``x >= max(90 − E, 30 − Δ)``; the ``br23`` outage puts
``x`` on ``br13``, which never binds here. Cost ``10·(90 − x) + 20·x = 900 + 10x``:

* ``E = None`` (normal rating after the outage too), any ``Δ``: ``x >= 30``, 1200 — the
  preventive answer, since the immediate flow already has to meet the normal rating;
* ``E = 90, Δ = 10``: ``x >= 20``, 1100, the corrective ramp binding;
* ``E = 90, Δ = 30`` or unlimited: ``x >= 0``, 900 — the plain OPF, corrected after the fact;
* ``E = 75, Δ = 20``: ``x >= 15``, 1050, the emergency rating binding, not the ramp.

In every case the correction itself is ``g3 = 30, g1 = 60`` (``br13`` exactly at 60 MW after
the outage), and the price at ``b2`` is $20/MWh when the ramp binds: a marginal MW of load there
can only be served after the outage by moving ``g3``'s base dispatch up.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power import cases
from mambo_power.jobs import SolveRequest, run
from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialCost
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import ScopfOptions, gen_cost_coeffs, solve_dc_opf, solve_scopf
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf
from mambo_power.opf.scopf import scopf_dc
from mambo_power.results import ScopfDcResult


def _gen(gen_id: str, bus: str, marginal_cost: float, ramp: float | None) -> Generator:
    return Generator(
        id=gen_id,
        bus=bus,
        p_mw=0.0,
        q_mvar=0.0,
        p_min_mw=0.0,
        p_max_mw=200.0,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        ramp_up_mw=ramp,
        ramp_down_mw=ramp,
        cost=PolynomialCost(coefficients=[marginal_cost, 0.0]),
    )


def _triangle(emergency: float | None, g3_ramp: float | None) -> Network:
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
                rating_emergency_mva=emergency,
            ),
            Branch(id="br23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0, rating_mva=100.0),
        ],
        generators=[_gen("g1", "b1", 10.0, None), _gen("g3", "b3", 20.0, g3_ramp)],
        loads=[Load(id="ld2", bus="b2", p_mw=90.0, q_mvar=0.0)],
    )


CORRECTIVE = ScopfOptions(corrective=True)


@pytest.mark.parametrize(
    ("emergency", "ramp", "cost", "g3"),
    [(None, 10.0, 1200.0, 30.0), (90.0, 10.0, 1100.0, 20.0), (90.0, 30.0, 900.0, 0.0),
     (90.0, None, 900.0, 0.0), (75.0, 20.0, 1050.0, 15.0)],
)  # fmt: skip
def test_triangle_matches_the_hand_derivation(
    emergency: float | None, ramp: float | None, cost: float, g3: float
) -> None:
    result = solve_scopf(_triangle(emergency, ramp), CORRECTIVE)

    assert result.status == "Optimal" and result.secure and result.corrected_secure
    assert result.objective_cost == pytest.approx(cost)
    assert {g.id: g.p_mw for g in result.generators} == pytest.approx({"g1": 90 - g3, "g3": g3})
    (correction,) = result.corrections
    assert (correction.outage_kind, correction.outage_id) == ("branch", "br12")
    assert {r.id: r.p_mw for r in correction.redispatch} == pytest.approx({"g1": 60.0, "g3": 30.0})
    assert {r.id: r.delta_mw for r in correction.redispatch} == pytest.approx(
        {"g1": g3 - 30.0, "g3": 30.0 - g3}
    )
    assert correction.confirmed_max_loading == pytest.approx(1.0)
    (row,) = correction.constraints
    assert (row.branch_id, row.rating_mva) == ("br13", 60.0)
    assert abs(row.post_contingency_flow_mw) == pytest.approx(60.0)


def test_corrective_sits_between_the_two_preventive_answers_and_the_ramp_prices_the_load() -> None:
    # preventive at the emergency rating asks only that the immediate flow fit it (900);
    # corrective also asks for a ramp-limited way back under the normal rating (1100);
    # preventive at the normal rating asks the immediate flow to fit that (1200)
    assert solve_scopf(_triangle(90.0, 10.0)).objective_cost == pytest.approx(900.0)
    corrective = solve_scopf(_triangle(90.0, 10.0), CORRECTIVE)
    assert corrective.objective_cost == pytest.approx(1100.0)
    assert solve_scopf(_triangle(None, 10.0)).objective_cost == pytest.approx(1200.0)
    assert solve_scopf(_triangle(None, 10.0), CORRECTIVE).objective_cost == pytest.approx(1200.0)
    lmp = {b.id: b.lmp for b in corrective.buses}
    assert lmp == pytest.approx({"b1": 10.0, "b2": 20.0, "b3": 20.0})
    (correction,) = corrective.corrections
    (row,) = correction.constraints
    assert row.dual != 0.0


def test_preventive_rows_still_hold_the_immediate_flow_to_the_emergency_rating() -> None:
    # E = 75, Δ = 20: the ramp would allow x = 10 but the immediate flow 90 − x <= 75 needs 15
    result = solve_scopf(_triangle(75.0, 20.0), CORRECTIVE)

    (immediate,) = result.constraints
    assert (immediate.outage_id, immediate.branch_id, immediate.rating_mva) == (
        "br12",
        "br13",
        75.0,
    )
    assert abs(immediate.post_contingency_flow_mw) == pytest.approx(75.0)
    assert immediate.dual != 0.0
    assert result.n1 is not None and result.n1.outages == []


def test_case14_rated_corrective_sits_between_the_two_preventive_answers_and_is_confirmed() -> None:
    # preventive at the normal rating (no emergency rating) is the most constrained: the
    # immediate flow must already be inside the normal rating. Corrective at a 30 % emergency
    # rating relaxes that to "inside the emergency rating now, inside the normal rating after a
    # ramp-limited redispatch", and preventive at the emergency rating drops the second half.
    strict = solve_scopf(cases.load("derived/case14_rated"))
    net = cases.load("derived/case14_rated")
    for br in net.branches:
        if br.rating_mva is not None:
            br.rating_emergency_mva = 1.3 * br.rating_mva
    for g in net.generators:
        g.ramp_up_mw = g.ramp_down_mw = 20.0
    relaxed = solve_scopf(net)
    corrective = solve_scopf(net, CORRECTIVE)

    assert strict.status == relaxed.status == corrective.status == "Optimal"
    assert corrective.secure and corrective.corrected_secure
    assert relaxed.objective_cost < corrective.objective_cost < strict.objective_cost
    assert corrective.corrections
    base = {g.id: g.p_mw for g in corrective.generators}
    for c in corrective.corrections:
        assert c.confirmed_max_loading <= 1.0 + 1e-6
        for r in c.redispatch:
            assert r.p_mw == pytest.approx(base[r.id] + r.delta_mw)
            if c.outage_kind == "generator" and r.id == c.outage_id:
                assert r.p_mw == pytest.approx(0.0, abs=1e-9)  # the lost unit, ramp or not
            else:
                assert abs(r.delta_mw) <= 20.0 + 1e-6
    # the corrective problem is an LP over chords of the quadratic costs (module docstring):
    # its base cost over-estimates the QP's by the chord error, under 0.1 % at 16 chords
    quadratic = solve_dc_opf(net).objective_cost
    assert quadratic < corrective.base_objective_cost < 1.001 * quadratic


def test_builder_without_a_corrective_block_is_unchanged_and_rejects_bad_ramps() -> None:
    net = _triangle(90.0, 10.0)
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _ = gen_cost_coeffs(net, arr)

    plain = dc_opf(arr, cost_coeffs, OpfDcOptions())
    assert plain.duals is not None
    assert plain.corrective_dispatch_mw.shape == (0, 0)
    assert plain.duals.corrective_balance.size == 0 and plain.duals.corrective_flow.size == 0

    secured = scopf_dc(arr, cost_coeffs, ScopfOptions())
    assert secured.corrective is None and secured.corrected_outages == []

    with pytest.raises(ValueError, match="ramp_up_mw must have shape"):
        scopf_dc(arr, cost_coeffs, CORRECTIVE, ramp_up_mw=np.zeros(3))
    with pytest.raises(ValueError, match="ramp_down_mw must be >= 0"):
        scopf_dc(arr, cost_coeffs, CORRECTIVE, ramp_down_mw=np.array([np.inf, -1.0]))
    # nan and inf both mean unlimited
    free = scopf_dc(arr, cost_coeffs, CORRECTIVE, ramp_up_mw=np.array([np.nan, np.inf]))
    assert free.solution.objective_cost == pytest.approx(900.0)


def test_result_round_trips_and_the_jobs_kind_takes_the_option() -> None:
    result = solve_scopf(_triangle(90.0, 10.0), CORRECTIVE)
    assert ScopfDcResult.model_validate_json(result.model_dump_json()) == result

    reply = run(
        SolveRequest(kind="opf.scopf", network=_triangle(90.0, 10.0), options={"corrective": True})
    )
    assert reply.status == "ok" and isinstance(reply.result, ScopfDcResult)
    assert reply.result.objective_cost == pytest.approx(1100.0)
    assert reply.result.provenance.options["corrective"] is True
