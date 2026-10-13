"""Unit commitment on the multiperiod market (ADR-017).

``_two_unit_scenario`` is one bus with a 3-period load of 50 / 80 / 50 MW and two units: ``small``
(0-100 MW, $50/MWh, free to start, on before the horizon) and ``big`` (40-200 MW, $10/MWh, a
start-up cost, off before the horizon). Every candidate schedule can be costed by hand:

* commit ``big`` throughout: energy ``10 · 180 = 1800`` plus one start-up;
* never commit it: ``50 · 180 = 9000`` on ``small``, no events;
* commit it for the peak only: ``10 · 80 + 50 · 100 = 5800`` plus the same start-up — never best.

With a $5000 start-up the first wins at 6800; with $8000 the second wins at 9000, where the LP
(which cannot switch ``big`` off, and never pays a start-up) still reports 1800. The LP's prices
are those of the restricted LP with the commitment fixed: $10/MWh with ``big`` on, $50/MWh with
``small`` alone. A 20 MW ramp limit on ``big`` with the $5000 start-up leaves the start itself
unconstrained (period 0 at 50 MW) but caps period 1 at 70 MW, so ``small`` supplies the last
10 MW: ``10 · 170 + 50 · 10 + 5000 = 7200``.

The quadratic-cost half uses case14, whose costs are all quadratic: HiGHS has no MIQP, so the
wrapper linearises them into chords, and the test checks that reading (chord cost within the
chord error of the LP's quadratic cost, every unit's dispatch inside the chord grid).
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power import cases
from mambo_power.jobs import SolveRequest, run
from mambo_power.market.multiperiod import MarketMultiperiodOptions, solve_multiperiod
from mambo_power.model import Bus, Generator, Load, Network, Period, PolynomialCost, Scenario
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.multiperiod import Commitment, multiperiod_dc_opf
from mambo_power.results import MarketMultiperiodResult


def _unit(
    gen_id: str,
    p_mw: float,
    p_min_mw: float,
    p_max_mw: float,
    marginal_cost: float,
    *,
    startup: float = 0.0,
    ramp_up_mw: float | None = None,
) -> Generator:
    return Generator(
        id=gen_id,
        bus="b1",
        p_mw=p_mw,
        q_mvar=0.0,
        p_min_mw=p_min_mw,
        p_max_mw=p_max_mw,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        ramp_up_mw=ramp_up_mw,
        cost=PolynomialCost(coefficients=[marginal_cost, 0.0], startup=startup),
    )


def _two_unit_scenario(*, big_startup: float, big_ramp_up: float | None = None) -> Scenario:
    net = Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack")],
        generators=[
            _unit("small", 10.0, 0.0, 100.0, 50.0),
            _unit("big", 0.0, 40.0, 200.0, 10.0, startup=big_startup, ramp_up_mw=big_ramp_up),
        ],
        loads=[Load(id="ld", bus="b1", p_mw=50.0, q_mvar=0.0)],
    )
    return Scenario(network=net, periods=[Period(load_p_mw={"ld": p}) for p in (50.0, 80.0, 50.0)])


UC = MarketMultiperiodOptions(unit_commitment=True)


def _schedule(result: MarketMultiperiodResult, gen_id: str) -> list[int]:
    return [int(x) for x in next(c for c in result.commitment if c.id == gen_id).on]


# --- the hand case ---------------------------------------------------------------------------


def test_cheap_unit_is_started_when_its_startup_pays_for_itself() -> None:
    result = solve_multiperiod(_two_unit_scenario(big_startup=5000.0), UC)

    assert result.status == "Optimal"
    assert result.objective_cost == pytest.approx(6800.0)
    assert result.commitment_cost == pytest.approx(5000.0)
    assert result.no_load_cost == pytest.approx(0.0)
    assert _schedule(result, "big") == [1, 1, 1]
    big = next(c for c in result.commitment if c.id == "big")
    assert big.committable and not big.initial_on
    assert big.started == [True, False, False] and big.stopped == [False, False, False]
    assert big.startup_cost == pytest.approx(5000.0)
    assert [g.p_mw for p in result.periods for g in p.generators if g.id == "big"] == pytest.approx(
        [50.0, 80.0, 50.0]
    )
    # prices are the restricted LP's: big is marginal at $10 in every period
    assert [p.buses[0].lmp for p in result.periods] == pytest.approx([10.0, 10.0, 10.0])
    assert result.total_load_payment == pytest.approx(10.0 * 180.0)


def test_cheap_unit_stays_off_when_its_startup_does_not() -> None:
    result = solve_multiperiod(_two_unit_scenario(big_startup=8000.0), UC)
    plain = solve_multiperiod(_two_unit_scenario(big_startup=8000.0))

    assert result.status == "Optimal"
    assert result.objective_cost == pytest.approx(9000.0)
    assert result.commitment_cost == pytest.approx(0.0)
    assert _schedule(result, "big") == [0, 0, 0]
    assert _schedule(result, "small") == [1, 1, 1]
    for period in result.periods:
        big = next(g for g in period.generators if g.id == "big")
        assert big.committed is False and big.p_mw == pytest.approx(0.0, abs=1e-9)
    assert [p.buses[0].lmp for p in result.periods] == pytest.approx([50.0, 50.0, 50.0])
    # the LP cannot switch big off and never pays the start-up: a different, cheaper-looking
    # answer that is not available once commitment is a decision
    assert plain.objective_cost == pytest.approx(1800.0)
    assert plain.commitment == [] and plain.commitment_cost == 0.0


def test_a_start_is_exempt_from_the_ramp_but_the_next_period_is_not() -> None:
    result = solve_multiperiod(_two_unit_scenario(big_startup=5000.0, big_ramp_up=20.0), UC)

    assert result.status == "Optimal"
    assert result.objective_cost == pytest.approx(7200.0)
    assert _schedule(result, "big") == [1, 1, 1]
    dispatch = {
        gen_id: [g.p_mw for p in result.periods for g in p.generators if g.id == gen_id]
        for gen_id in ("big", "small")
    }
    assert dispatch["big"] == pytest.approx([50.0, 70.0, 50.0])
    assert dispatch["small"] == pytest.approx([0.0, 10.0, 0.0], abs=1e-9)


def test_small_free_unit_is_not_committable_and_never_flaps() -> None:
    """A unit with no minimum, no no-load and no event cost has nothing to decide: it is on in
    every period with no events, whatever it declared before the horizon."""
    result = solve_multiperiod(_two_unit_scenario(big_startup=8000.0), UC)
    small = next(c for c in result.commitment if c.id == "small")

    assert small.committable is False
    assert small.on == [True, True, True]
    assert small.started == [False, False, False] and small.stopped == [False, False, False]
    assert small.startup_cost == 0.0 and small.shutdown_cost == 0.0 and small.no_load_cost == 0.0


def test_no_load_cost_is_paid_only_while_on() -> None:
    """A constant cost term becomes a no-load cost under commitment: it is charged for the
    periods the unit is on, it makes the unit committable even with no minimum output, and it
    can tip the decision — at $300 a period ``small`` is dearer to keep than ``big`` is to start."""

    def with_no_load(no_load: float) -> Scenario:
        scenario = _two_unit_scenario(big_startup=8000.0)
        net = scenario.network.model_copy(deep=True)
        for gen in net.generators:
            if gen.id == "small":
                gen.cost = PolynomialCost(coefficients=[50.0, no_load])
        return Scenario(network=net, periods=scenario.periods)

    # $100 a period: small still serves everything, and pays its no-load three times
    result = solve_multiperiod(with_no_load(100.0), UC)
    small = next(c for c in result.commitment if c.id == "small")
    assert small.committable is True and small.on == [True, True, True]
    assert result.no_load_cost == pytest.approx(300.0)
    assert small.no_load_cost == pytest.approx(300.0)
    assert result.objective_cost == pytest.approx(9000.0 + 300.0)
    # the LP charges the constant in every period for every unit regardless
    assert solve_multiperiod(with_no_load(100.0)).objective_cost == pytest.approx(1800.0 + 300.0)

    # $300 a period: 9000 + 900 on small loses to 1800 + 8000 on big, so small is switched off
    result = solve_multiperiod(with_no_load(300.0), UC)
    assert _schedule(result, "small") == [0, 0, 0] and _schedule(result, "big") == [1, 1, 1]
    assert result.no_load_cost == pytest.approx(0.0)
    assert result.objective_cost == pytest.approx(9800.0)


# --- the builder's own contracts -------------------------------------------------------------


def test_builder_rejects_a_quadratic_cost_under_commitment() -> None:
    net = cases.load("case14")
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _ = gen_cost_coeffs(net, arr)
    n_gen = len(arr.gen_ids)
    commitment = Commitment(
        startup_cost=np.zeros(n_gen),
        shutdown_cost=np.zeros(n_gen),
        initial_on=np.ones(n_gen, dtype=np.bool_),
        no_load_cost=np.zeros(n_gen),
    )

    with pytest.raises(ValueError, match="MIQP"):
        multiperiod_dc_opf(arr, cost_coeffs, 2, commitment=commitment)


def test_builder_rejects_a_mis_shaped_or_negative_commitment_block() -> None:
    scenario = _two_unit_scenario(big_startup=1.0)
    arr = NetworkArrays.from_network(scenario.network)
    cost_coeffs, _ = gen_cost_coeffs(scenario.network, arr)

    with pytest.raises(ValueError, match="startup_cost must have shape"):
        multiperiod_dc_opf(
            arr,
            cost_coeffs,
            2,
            commitment=Commitment(
                startup_cost=np.zeros(3),
                shutdown_cost=np.zeros(2),
                initial_on=np.zeros(2, dtype=np.bool_),
                no_load_cost=np.zeros(2),
            ),
        )
    with pytest.raises(ValueError, match=">= 0"):
        multiperiod_dc_opf(
            arr,
            cost_coeffs,
            2,
            commitment=Commitment(
                startup_cost=np.array([0.0, -1.0]),
                shutdown_cost=np.zeros(2),
                initial_on=np.zeros(2, dtype=np.bool_),
                no_load_cost=np.zeros(2),
            ),
        )


def test_builder_without_a_commitment_block_is_unchanged() -> None:
    scenario = _two_unit_scenario(big_startup=5000.0)
    arr = NetworkArrays.from_network(scenario.network)
    cost_coeffs, _ = gen_cost_coeffs(scenario.network, arr)

    solution = multiperiod_dc_opf(arr, cost_coeffs, 3, period_load_mw=np.array([[50], [80], [50]]))

    assert solution.committed.shape == (0, 0)
    assert solution.commitment_cost == 0.0 and solution.no_load_cost == 0.0
    assert solution.objective_cost == pytest.approx(1800.0)


# --- quadratic costs, linearised --------------------------------------------------------------


def _case14_horizon(factors: tuple[float, ...]) -> Scenario:
    net = cases.load("case14")
    loads = {ld.id: ld.p_mw for ld in net.loads}
    return Scenario(
        network=net,
        periods=[Period(load_p_mw={k: v * f for k, v in loads.items()}) for f in factors],
    )


def test_case14_quadratic_costs_are_linearised_and_the_schedule_is_consistent() -> None:
    scenario = _case14_horizon((0.6, 0.8, 1.0, 1.1, 0.9))

    result = solve_multiperiod(scenario, MarketMultiperiodOptions(unit_commitment=True))
    plain = solve_multiperiod(scenario)

    assert result.status == "Optimal"
    # case14 has nothing to commit (no minimum, no no-load, no event cost on any unit), so the
    # schedule is all-on and the only difference from the LP is the chord approximation
    assert all(c.committable is False and all(c.on) for c in result.commitment)
    assert result.commitment_cost == 0.0
    assert result.objective_cost >= plain.objective_cost
    assert result.objective_cost == pytest.approx(plain.objective_cost, rel=1e-2)
    for period, plain_period in zip(result.periods, plain.periods, strict=True):
        assert sum(g.p_mw for g in period.generators) == pytest.approx(
            sum(g.p_mw for g in plain_period.generators)
        )
        for bus, plain_bus in zip(period.buses, plain_period.buses, strict=True):
            assert bus.lmp == pytest.approx(plain_bus.lmp, rel=0.1)


def test_more_chords_bring_the_linearised_cost_closer_to_the_quadratic_one() -> None:
    scenario = _case14_horizon((0.8, 1.0))
    plain = solve_multiperiod(scenario).objective_cost

    coarse = solve_multiperiod(
        scenario, MarketMultiperiodOptions(unit_commitment=True, quadratic_segments=2)
    ).objective_cost
    fine = solve_multiperiod(
        scenario, MarketMultiperiodOptions(unit_commitment=True, quadratic_segments=32)
    ).objective_cost

    assert plain <= fine <= coarse
    assert fine - plain < (coarse - plain) / 4


def test_case14_with_minimums_and_startups_commits_selectively() -> None:
    """Give case14's three idle units a minimum output and a small start-up cost: one of them is
    worth starting for the peak period only, the others never, and every period's dispatch
    respects p_min·on <= p <= p_max·on."""
    scenario = _case14_horizon((0.5, 0.7, 1.0, 1.2, 0.6))
    net = scenario.network.model_copy(deep=True)
    for gen in net.generators:
        if gen.p_mw == 0.0:
            gen.p_min_mw = 20.0
            assert gen.cost is not None
            gen.cost = PolynomialCost(coefficients=list(gen.cost.coefficients), startup=40.0)
    scenario = Scenario(network=net, periods=scenario.periods)

    result = solve_multiperiod(scenario, MarketMultiperiodOptions(unit_commitment=True))

    assert result.status == "Optimal"
    schedules = {c.id: c for c in result.commitment}
    assert all(schedules[g].committable for g in ("gen-3", "gen-4", "gen-5"))
    assert schedules["gen-5"].on == [False, False, False, True, False]
    assert schedules["gen-3"].on == [False] * 5 and schedules["gen-4"].on == [False] * 5
    assert result.commitment_cost == pytest.approx(40.0)
    bounds = {g.id: (g.p_min_mw, g.p_max_mw) for g in net.generators}
    for period in result.periods:
        for row in period.generators:
            p_min, p_max = bounds[row.id]
            if row.committed:
                assert p_min - 1e-6 <= row.p_mw <= p_max + 1e-6
            else:
                assert row.p_mw == pytest.approx(0.0, abs=1e-6)
    # events reconcile with the schedule
    for c in result.commitment:
        previous = c.initial_on
        for on, started, stopped in zip(c.on, c.started, c.stopped, strict=True):
            assert started == (on and not previous)
            assert stopped == (previous and not on)
            previous = on


# --- round trip and jobs ------------------------------------------------------------------------


def test_result_round_trips_and_the_jobs_kind_takes_the_option() -> None:
    scenario = _two_unit_scenario(big_startup=5000.0)
    result = solve_multiperiod(scenario, UC)

    again = MarketMultiperiodResult.model_validate_json(result.model_dump_json())
    assert again == result

    out = run(
        SolveRequest(
            kind="market.multiperiod", scenario=scenario, options={"unit_commitment": True}
        )
    )
    assert out.status == "ok" and isinstance(out.result, MarketMultiperiodResult)
    assert out.result.objective_cost == pytest.approx(6800.0)
    assert out.provenance is not None
    assert out.provenance.options == {"unit_commitment": True, "quadratic_segments": 8}
