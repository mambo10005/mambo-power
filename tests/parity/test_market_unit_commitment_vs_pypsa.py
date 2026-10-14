"""ADR-017 / ADR-019 parity: ``market.solve_multiperiod`` with ``unit_commitment`` agrees with
PyPSA's committable generators on the hand cases the unit tier costs by hand.

PyPSA's ``optimize`` models unit commitment with ``committable`` generators carrying
``start_up_cost`` / ``shut_down_cost``, ``min_up_time`` / ``min_down_time``,
``up_time_before`` / ``down_time_before`` and ``p_min_pu``, and (where the installed version has
it) ``stand_by_cost`` for the no-load cost. The two formulations share nothing but the problem —
PyPSA's is the linopy MILP over its own binaries — so agreement on the objective and on the
schedule is evidence about the formulation (``tests/parity/test_opf_vs_pypsa.py``'s standard).

**Conventions bridged.** Our status before the horizon is the unit's declared ``p_mw``
(above zero = on); PyPSA's is ``up_time_before > 0``. Our ``initial_state_periods`` counts the
period just before the horizon; PyPSA's ``up_time_before`` / ``down_time_before`` count the same
way. A unit that states no history carries no obligation in, which is ``up_time_before =
min_up_time`` (on) or ``down_time_before = min_down_time`` (off) on PyPSA's side. Our
``min_up_periods = None`` is PyPSA's ``min_up_time = 0``. A polynomial cost's constant term is
our no-load cost and PyPSA's ``stand_by_cost``; scenarios that need it are skipped when the
installed PyPSA has no such column.

Every scenario is one bus and two units — ``small`` (0–100 MW, $50/MWh, on) and ``big``
(40–200 MW, $10/MWh, off, with the start-up, no-load and minimum times each scenario names) —
over the 3-period loads it names; ``tests/unit/test_market_unit_commitment.py`` derives each
expected cost by hand, and this file checks that PyPSA lands on the same one.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pytest

from mambo_power.market.multiperiod import MarketMultiperiodOptions, solve_multiperiod
from mambo_power.model import Bus, Generator, Load, Network, Period, PolynomialCost, Scenario
from mambo_power.results import MarketMultiperiodResult

pytest.importorskip("pypsa")

COST_REL_TOL = 1e-6


@dataclass(frozen=True)
class Case:
    name: str
    loads: tuple[float, ...]
    big_startup: float = 0.0
    big_no_load: float = 0.0
    big_p_mw: float = 0.0  # > 0: on before the horizon
    min_up: int | None = None
    min_down: int | None = None
    initial_state_periods: int | None = None
    expected_cost: float = 0.0
    expected_big_on: tuple[int, ...] = ()


CASES = [
    Case(
        "startup pays",
        (50, 80, 50),
        big_startup=5000,
        expected_cost=6800,
        expected_big_on=(1, 1, 1),
    ),
    Case(
        "startup does not",
        (50, 80, 50),
        big_startup=8000,
        expected_cost=9000,
        expected_big_on=(0, 0, 0),
    ),
    Case(
        "min up holds a started unit on",
        (50, 80, 60),
        big_no_load=2500,
        min_up=2,
        expected_cost=8900,
        expected_big_on=(0, 1, 1),
    ),
    Case(
        "min down carried in (2)",
        (50, 80, 50),
        big_startup=1000,
        min_down=2,
        initial_state_periods=1,
        expected_cost=4800,
        expected_big_on=(0, 1, 1),
    ),
    Case(
        "min down carried in (3)",
        (50, 80, 50),
        big_startup=1000,
        min_down=3,
        initial_state_periods=1,
        expected_cost=8000,
        expected_big_on=(0, 0, 1),
    ),
    Case(
        "min up carried in",
        (50, 80, 50),
        big_no_load=3000,
        big_p_mw=50,
        min_up=3,
        initial_state_periods=1,
        expected_cost=9800,
        expected_big_on=(1, 1, 0),
    ),
]


def _scenario(case: Case) -> Scenario:
    def unit(
        gen_id: str, p_mw: float, p_min: float, p_max: float, cost: PolynomialCost, **f: object
    ) -> Generator:
        return Generator(
            id=gen_id,
            bus="b1",
            p_mw=p_mw,
            q_mvar=0.0,
            p_min_mw=p_min,
            p_max_mw=p_max,
            q_min_mvar=0.0,
            q_max_mvar=0.0,
            v_set_pu=1.0,
            cost=cost,
            **f,  # type: ignore[arg-type]
        )

    net = Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack")],
        generators=[
            unit("small", 10.0, 0.0, 100.0, PolynomialCost(coefficients=[50.0, 0.0])),
            unit(
                "big",
                case.big_p_mw,
                40.0,
                200.0,
                PolynomialCost(coefficients=[10.0, case.big_no_load], startup=case.big_startup),
                min_up_periods=case.min_up,
                min_down_periods=case.min_down,
                initial_state_periods=case.initial_state_periods,
            ),
        ],
        loads=[Load(id="ld", bus="b1", p_mw=50.0, q_mvar=0.0)],
    )
    return Scenario(network=net, periods=[Period(load_p_mw={"ld": float(p)}) for p in case.loads])


def _pypsa_solve(scenario: Scenario) -> tuple[float, dict[str, list[int]], dict[str, list[float]]]:
    import pandas as pd
    import pypsa

    net = scenario.network
    periods = scenario.periods or []
    n = pypsa.Network()
    n.set_snapshots(list(range(len(periods))))
    n.add("Bus", "b1", v_nom=138.0)
    has_stand_by = "stand_by_cost" in n.generators.columns
    for g in net.generators:
        cost = g.cost
        assert isinstance(cost, PolynomialCost)
        marginal, no_load = cost.coefficients[0], cost.coefficients[1]
        if no_load and not has_stand_by:
            pytest.skip("installed PyPSA has no stand_by_cost: no oracle for a no-load cost")
        on_before = g.p_mw > 0.0
        min_up = g.min_up_periods or 0
        min_down = g.min_down_periods or 0
        history = g.initial_state_periods
        if on_before:
            up_before = min_up if history is None else history
            down_before = 0
        else:
            up_before = 0
            down_before = min_down if history is None else history
        attrs = dict(
            bus="b1",
            p_nom=g.p_max_mw,
            p_min_pu=g.p_min_mw / g.p_max_mw,
            marginal_cost=marginal,
            committable=True,
            start_up_cost=cost.startup,
            shut_down_cost=cost.shutdown,
            min_up_time=min_up,
            min_down_time=min_down,
            up_time_before=up_before,
            down_time_before=down_before,
        )
        if has_stand_by:
            attrs["stand_by_cost"] = no_load
        n.add("Generator", g.id, **attrs)
    n.add("Load", "ld", bus="b1")
    n.loads_t.p_set = pd.DataFrame({"ld": [p.load_p_mw["ld"] for p in periods]}, index=n.snapshots)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        status, _ = n.optimize(solver_name="highs")
    assert status == "ok", status
    schedule = {
        gid: [int(round(float(x))) for x in n.generators_t.status[gid].to_numpy()]
        for gid in n.generators.index
    }
    dispatch = {
        gid: [float(x) for x in n.generators_t.p[gid].to_numpy()] for gid in n.generators.index
    }
    return float(n.objective), schedule, dispatch


@dataclass
class Solved:
    case: Case
    ours: MarketMultiperiodResult
    pypsa_cost: float
    pypsa_schedule: dict[str, list[int]]
    pypsa_dispatch: dict[str, list[float]]


@pytest.fixture(scope="module", params=CASES, ids=[c.name for c in CASES])
def solved(request: pytest.FixtureRequest) -> Solved:
    case: Case = request.param
    scenario = _scenario(case)
    ours = solve_multiperiod(scenario, MarketMultiperiodOptions(unit_commitment=True))
    assert ours.status == "Optimal", ours.message
    pypsa_cost, pypsa_schedule, pypsa_dispatch = _pypsa_solve(scenario)
    return Solved(case, ours, pypsa_cost, pypsa_schedule, pypsa_dispatch)


def test_objective_matches_pypsa_and_the_hand_derivation(solved: Solved) -> None:
    case, ours, pypsa_cost = solved.case, solved.ours, solved.pypsa_cost
    assert ours.objective_cost == pytest.approx(case.expected_cost)
    assert abs(ours.objective_cost - pypsa_cost) <= COST_REL_TOL * abs(pypsa_cost), (
        case.name,
        ours.objective_cost,
        pypsa_cost,
    )


def test_schedule_matches_pypsa(solved: Solved) -> None:
    case, ours = solved.case, solved.ours
    big = next(c for c in ours.commitment if c.id == "big")
    assert tuple(int(x) for x in big.on) == case.expected_big_on
    assert solved.pypsa_schedule["big"] == list(case.expected_big_on), (
        case.name,
        solved.pypsa_schedule,
    )


def test_dispatch_matches_pypsa(solved: Solved) -> None:
    """With ``big`` on it serves everything it can at $10 against $50, and off it serves
    nothing: given the schedule the dispatch is unique, so the two must agree period by period."""
    for gen_id in ("big", "small"):
        ours = np.array(
            [next(g.p_mw for g in p.generators if g.id == gen_id) for p in solved.ours.periods]
        )
        theirs = np.array(solved.pypsa_dispatch[gen_id])
        assert np.allclose(ours, theirs, atol=1e-6), (solved.case.name, gen_id, ours, theirs)
