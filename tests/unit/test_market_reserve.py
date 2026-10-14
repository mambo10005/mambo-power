"""Spinning reserve on the multiperiod market (ADR-023).

One bus, two units — ``cheap`` ($10/MWh, 0–200 MW) and ``dear`` ($50/MWh, 0–100 MW) — and a
150 MW load. Without a requirement ``cheap`` serves everything for 1500 $/h. A 60 MW reserve:

* with both units free to hold it, costs nothing — ``dear`` is idle with 100 MW of headroom, the
  requirement row does not bind, the reserve price is 0;
* with ``dear`` barred from holding any (``reserve_max_mw = 0``), ``cheap`` must keep 60 MW
  unused: 140 MW of energy from it and 10 MW from ``dear``, 1400 + 500 = 1900 $/h, and the
  reserve price is $40/MW — one more MW of reserve moves one MW of energy from $10 to $50;
* under unit commitment with ``cheap`` capped at 40 MW of reserve, a 60 MW requirement is what
  commits ``dear`` (start-up 1000, minimum 20 MW): 130 + 20 MW of energy, 40 + 20 MW of
  reserve, 1300 + 1000 + 1000 = 3300 $; a 40 MW requirement leaves ``dear`` off.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power.jobs import SolveRequest, run
from mambo_power.market.multiperiod import MarketMultiperiodOptions, solve_multiperiod
from mambo_power.model import Bus, Generator, Load, Network, Period, PolynomialCost, Scenario
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.multiperiod import multiperiod_dc_opf
from mambo_power.results import MarketMultiperiodResult


def _unit(
    gen_id: str,
    p_mw: float,
    p_min_mw: float,
    p_max_mw: float,
    marginal_cost: float,
    *,
    startup: float = 0.0,
    reserve_max_mw: float | None = None,
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
        reserve_max_mw=reserve_max_mw,
        cost=PolynomialCost(coefficients=[marginal_cost, 0.0], startup=startup),
    )


def _scenario(
    reserve: tuple[float | None, ...],
    *,
    dear_cap: float | None = None,
    cheap_cap: float | None = None,
    dear_min: float = 0.0,
    dear_startup: float = 0.0,
    loads: tuple[float, ...] | None = None,
) -> Scenario:
    net = Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack")],
        generators=[
            _unit("cheap", 150.0, 0.0, 200.0, 10.0, reserve_max_mw=cheap_cap),
            _unit(
                "dear", 0.0, dear_min, 100.0, 50.0, startup=dear_startup, reserve_max_mw=dear_cap
            ),
        ],
        loads=[Load(id="ld", bus="b1", p_mw=150.0, q_mvar=0.0)],
    )
    loads = loads or tuple(150.0 for _ in reserve)
    return Scenario(
        network=net,
        periods=[
            Period(load_p_mw={"ld": p}, reserve_mw=r) for p, r in zip(loads, reserve, strict=True)
        ],
    )


def _gen(result: MarketMultiperiodResult, t: int, gen_id: str):  # type: ignore[no-untyped-def]
    return next(g for g in result.periods[t].generators if g.id == gen_id)


def test_reserve_is_free_while_the_fleet_has_headroom() -> None:
    result = solve_multiperiod(_scenario((60.0,)))

    assert result.status == "Optimal"
    assert result.objective_cost == pytest.approx(1500.0)
    period = result.periods[0]
    assert period.reserve_requirement_mw == 60.0 and period.reserve_price == pytest.approx(0.0)
    assert period.total_reserve_payment == pytest.approx(0.0)
    assert _gen(result, 0, "cheap").reserve_mw + _gen(result, 0, "dear").reserve_mw >= 60.0 - 1e-9
    assert _gen(result, 0, "cheap").p_mw == pytest.approx(150.0)
    assert result.total_reserve_payment == pytest.approx(0.0)


def test_reserve_is_priced_when_only_the_cheap_unit_may_hold_it() -> None:
    result = solve_multiperiod(_scenario((60.0, 60.0), dear_cap=0.0))

    assert result.status == "Optimal"
    assert result.objective_cost == pytest.approx(2 * 1900.0)
    for t in range(2):
        period = result.periods[t]
        assert _gen(result, t, "cheap").p_mw == pytest.approx(140.0)
        assert _gen(result, t, "dear").p_mw == pytest.approx(10.0)
        assert _gen(result, t, "cheap").reserve_mw == pytest.approx(60.0)
        assert _gen(result, t, "dear").reserve_mw == pytest.approx(0.0)
        assert period.reserve_price == pytest.approx(40.0)
        assert period.total_reserve_payment == pytest.approx(40.0 * 60.0)
        # the energy market is the energy market: dear is marginal, the identity untouched
        assert period.buses[0].lmp == pytest.approx(50.0)
        assert period.total_load_payment == pytest.approx(50.0 * 150.0)
        assert period.congestion_rent == pytest.approx(0.0, abs=1e-9)
    assert result.total_reserve_payment == pytest.approx(2 * 2400.0)


def test_a_period_without_a_requirement_requires_nothing() -> None:
    result = solve_multiperiod(_scenario((60.0, None), dear_cap=0.0))

    assert [p.reserve_requirement_mw for p in result.periods] == [60.0, 0.0]
    assert [p.reserve_price for p in result.periods] == pytest.approx([40.0, 0.0])
    assert _gen(result, 1, "cheap").p_mw == pytest.approx(150.0)
    assert result.objective_cost == pytest.approx(1900.0 + 1500.0)


def test_no_requirement_anywhere_leaves_the_result_as_before() -> None:
    plain = solve_multiperiod(_scenario((None, None), dear_cap=0.0))
    assert plain.objective_cost == pytest.approx(3000.0)
    assert all(p.reserve_price == 0.0 and p.reserve_requirement_mw == 0.0 for p in plain.periods)
    assert all(g.reserve_mw == 0.0 for p in plain.periods for g in p.generators)


def test_a_reserve_requirement_can_commit_a_unit() -> None:
    uc = MarketMultiperiodOptions(unit_commitment=True)
    off = solve_multiperiod(
        _scenario((40.0,), cheap_cap=40.0, dear_min=20.0, dear_startup=1000.0), uc
    )
    on = solve_multiperiod(
        _scenario((60.0,), cheap_cap=40.0, dear_min=20.0, dear_startup=1000.0), uc
    )

    assert off.objective_cost == pytest.approx(1500.0)
    assert not _gen(off, 0, "dear").committed and _gen(off, 0, "dear").reserve_mw == 0.0
    assert on.status == "Optimal"
    assert on.objective_cost == pytest.approx(3300.0)
    assert _gen(on, 0, "dear").committed
    assert _gen(on, 0, "cheap").p_mw == pytest.approx(130.0)
    assert _gen(on, 0, "dear").p_mw == pytest.approx(20.0)
    assert _gen(on, 0, "cheap").reserve_mw == pytest.approx(40.0)
    assert _gen(on, 0, "dear").reserve_mw == pytest.approx(20.0)
    assert on.commitment_cost == pytest.approx(1000.0)


def test_builder_validates_the_reserve_arguments() -> None:
    net = _scenario((60.0,)).network
    arr = NetworkArrays.from_network(net)
    cost_coeffs, _ = gen_cost_coeffs(net, arr)

    with pytest.raises(ValueError, match="reserve_mw must have shape"):
        multiperiod_dc_opf(arr, cost_coeffs, 2, reserve_mw=np.array([60.0]))
    with pytest.raises(ValueError, match="reserve_mw must be finite and >= 0"):
        multiperiod_dc_opf(arr, cost_coeffs, 1, reserve_mw=np.array([-1.0]))
    with pytest.raises(ValueError, match="reserve_max_mw must be >= 0"):
        multiperiod_dc_opf(
            arr, cost_coeffs, 1, reserve_mw=np.array([1.0]), reserve_max_mw=np.array([-1.0, 0.0])
        )
    # nan and inf both mean uncapped, 0 excludes the unit
    solution = multiperiod_dc_opf(
        arr, cost_coeffs, 1, reserve_mw=np.array([60.0]), reserve_max_mw=np.array([np.nan, 0.0])
    )
    assert solution.duals is not None
    assert solution.duals.reserve.tolist() == pytest.approx([40.0])
    assert solution.reserve_mw.tolist() == [[60.0, 0.0]]
    # an infeasible requirement is an answer, not an exception
    short = multiperiod_dc_opf(arr, cost_coeffs, 1, reserve_mw=np.array([400.0]))
    assert short.status != "Optimal"


def test_result_round_trips_and_the_jobs_kind_carries_the_reserve() -> None:
    scenario = _scenario((60.0,), dear_cap=0.0)
    result = solve_multiperiod(scenario)
    assert MarketMultiperiodResult.model_validate_json(result.model_dump_json()) == result
    assert Scenario.model_validate_json(scenario.model_dump_json()) == scenario

    reply = run(SolveRequest(kind="market.multiperiod", scenario=scenario))
    assert reply.status == "ok" and isinstance(reply.result, MarketMultiperiodResult)
    assert reply.result.periods[0].reserve_price == pytest.approx(40.0)


# --- zonal reserve (ADR-028) -------------------------------------------------------------------
#
# Two zones on two buses joined by an unlimited line: ``cheap`` ($10/MWh, 0–200 MW) in zone A,
# ``dear`` ($50/MWh, 0–100 MW) in zone B, 150 MW of load in B. Without a requirement cheap
# serves everything (1500 $/h) and dear sits on 100 MW of headroom.


def _zonal(
    zone_a: float | None, zone_b: float | None, *, cheap_cap: float | None = None
) -> Scenario:
    from mambo_power.model import Branch, Zone

    def unit(gen_id: str, bus: str, p_max: float, cost: float) -> Generator:
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
            reserve_max_mw=cheap_cap if gen_id == "cheap" else None,
            cost=PolynomialCost(coefficients=[cost, 0.0]),
        )

    net = Network(
        base_mva=100.0,
        zones=[Zone(id="A"), Zone(id="B")],
        buses=[
            Bus(id="a", base_kv=138.0, type="slack", zone="A"),
            Bus(id="b", base_kv=138.0, type="pq", zone="B"),
        ],
        branches=[Branch(id="ab", from_bus="a", to_bus="b", r=0.0, x=0.1, b=0.0)],
        generators=[unit("cheap", "a", 200.0, 10.0), unit("dear", "b", 100.0, 50.0)],
        loads=[Load(id="ld", bus="b", p_mw=150.0, q_mvar=0.0)],
    )
    zones = {k: v for k, v in (("A", zone_a), ("B", zone_b)) if v is not None}
    return Scenario(
        network=net, periods=[Period(load_p_mw={"ld": 150.0}, zone_reserve_mw=zones or None)]
    )


def test_a_zonal_requirement_is_met_inside_the_zone_and_priced_there() -> None:
    # zone A needs 60 MW held by cheap alone: cheap backs off to 140 and dear serves 10 at
    # $50 — the same $40/MW the system-wide case prices, now as zone A's premium; zone B's
    # 30 MW is free (dear has 100 MW of headroom)
    result = solve_multiperiod(_zonal(60.0, 30.0))

    assert result.status == "Optimal"
    assert result.objective_cost == pytest.approx(1900.0)
    period = result.periods[0]
    assert period.reserve_requirement_mw == 0.0 and period.reserve_price == 0.0
    assert period.zone_reserve_requirements_mw == {"A": 60.0, "B": 30.0}
    assert period.zone_reserve_prices == pytest.approx({"A": 40.0, "B": 0.0})
    assert _gen(result, 0, "cheap").reserve_mw == pytest.approx(60.0)
    assert _gen(result, 0, "dear").reserve_mw >= 30.0 - 1e-9
    assert period.total_reserve_payment == pytest.approx(40.0 * 60.0)
    assert result.total_reserve_payment == pytest.approx(2400.0)


def test_headroom_in_another_zone_does_not_deliver() -> None:
    # cheap may hold at most 50 MW; zone A needs 60: dear's 100 MW of headroom is in zone B
    # and counts for nothing there — no feasible dispatch, reported as such
    result = solve_multiperiod(_zonal(60.0, None, cheap_cap=50.0))
    assert result.status != "Optimal"
    # the same cap with a system-wide requirement instead is fine: dear's headroom counts
    system = _zonal(None, None, cheap_cap=50.0)
    assert system.periods is not None
    system.periods[0].reserve_mw = 60.0
    assert solve_multiperiod(system).status == "Optimal"


def test_zone_references_are_checked_on_the_scenario() -> None:
    scenario = _zonal(60.0, None)
    assert scenario.periods is not None
    with pytest.raises(ValueError, match="zone id\\(s\\) not present"):
        Scenario(
            network=scenario.network,
            periods=[Period(load_p_mw={"ld": 150.0}, zone_reserve_mw={"C": 1.0})],
        )
    with pytest.raises(ValueError, match=">= 0"):
        Scenario(
            network=scenario.network,
            periods=[Period(load_p_mw={"ld": 150.0}, zone_reserve_mw={"A": -1.0})],
        )
    assert Scenario.model_validate_json(scenario.model_dump_json()) == scenario
