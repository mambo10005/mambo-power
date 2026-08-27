"""AC-4, AC-5 and the per-period settlement identity for ``market.multiperiod`` (spec W5).

Three claims are proved here, and each one is written so that it *could* fail:

* **AC-4** -- a ``T=1`` :func:`~mambo_power.market.multiperiod.solve_multiperiod` reproduces
  :func:`~mambo_power.market.nodal.solve_nodal`'s dispatch, duals and LMPs **exactly** on a real
  MATPOWER fixture (``numpy.testing.assert_array_equal``, not ``assert_allclose``), and
  ``market.nodal`` itself is untouched by a ``Scenario`` that carries periods.
* **AC-5** -- ``record/m5-research.md`` §7.2/§7.3's closed-form storage-arbitrage optimum,
  reproduced through the *market* layer (``Generator.cost``, ``Storage``, ``Scenario.periods``),
  including the settlement layer independently reproducing ``profit*``.
* **The settlement identity, per period.** ``load_payment + storage_charge_payment -
  generator_receipts - storage_discharge_revenue == -sum_k mu_k*f_k + sum_k mu_k*pf_shift_k -
  sum_n LMP_n*g_shunt_n``. The right-hand side is built by a **separate code path** -- a direct
  array-level ``multiperiod_dc_opf`` call and an independently recomputed PTDF -- so the test
  proves the identity rather than restating the subtraction ``solve_multiperiod`` just performed.
  Two paired negative readings show the identity **breaks** without storage's terms (by exactly
  its net revenue) and without the shunt term (by exactly the shunt's unsettled withdrawal), so
  neither is decoration.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.market.multiperiod import MarketMultiperiodOptions, solve_multiperiod
from mambo_power.market.nodal import solve_nodal
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    Period,
    PolynomialBid,
    PolynomialCost,
    Scenario,
    Shunt,
    Storage,
)
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.numerics.bbus import pf_shift
from mambo_power.numerics.ptdf import ptdf as compute_ptdf
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.multiperiod import multiperiod_dc_opf
from mambo_power.results import MarketMultiperiodResult
from tests._bids import with_bids
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network

# --- local fixture builders (no shared tests/_periods.py: that file is S6/S7's) ----------------


def _gen(
    gid: str,
    bus: str,
    p_min_mw: float,
    p_max_mw: float,
    c1: float,
    *,
    ramp_up_mw: float | None = None,
    ramp_down_mw: float | None = None,
) -> Generator:
    return Generator(
        id=gid,
        bus=bus,
        p_mw=0.0,
        q_mvar=0.0,
        p_min_mw=p_min_mw,
        p_max_mw=p_max_mw,
        q_min_mvar=0.0,
        q_max_mvar=0.0,
        v_set_pu=1.0,
        ramp_up_mw=ramp_up_mw,
        ramp_down_mw=ramp_down_mw,
        cost=PolynomialCost(coefficients=[c1, 0.0]),
    )


def _two_bus(
    generators: list[Generator],
    load_mw: float,
    storage: list[Storage] | None = None,
    rating_mva: float | None = None,
    shunt_g_mw: float | None = None,
) -> Network:
    """b1 (slack) -- br12 -- b2; every generator at b1, the single load (and any storage) at b2."""
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
        ],
        branches=[
            Branch(
                id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0, rating_mva=rating_mva
            )
        ],
        generators=generators,
        loads=[Load(id="ld2", bus="b2", p_mw=load_mw, q_mvar=0.0)],
        storage=storage or [],
        shunts=[Shunt(id="sh2", bus="b2", g_mw=shunt_g_mw, b_mvar=0.0)]
        if shunt_g_mw is not None
        else [],
    )


def _profile(load_id: str, values: list[float]) -> list[Period]:
    return [Period(load_p_mw={load_id: v}) for v in values]


# --- AC-5's network: research §7.1/§7.3, at the market layer ------------------------------------
#
#   b1 (slack): gcheap c1=10 [0,40];  gexp c1=50 [0,200]      br12 unrated
#   b2:         ld2 profile [20, 100];  st2 P=20 MW, E=15 MWh, soc_init=0, eta_c=eta_d=0.9
#
# Closed form (research §7.2), c_L=10, c_H=50, eta_c=eta_d=0.9, P_max=20, E_max=15:
#   c_H*eta_c*eta_d = 40.5 > 10 = c_L        -> arbitrage is on
#   charge*    = min(20, 15/0.9) = 50/3 = 16.666667      (the energy cap binds, not the rating)
#   discharge* = 0.81 * 50/3 = 13.5
#   profit*    = 50/3 * (40.5 - 10) = 50/3 * 30.5 = 508.333333
# and the two prices are formed by the builder's own balance rows, not assumed: gcheap is
# interior at t=0 (36.6667 of 40 MW) so LMP_0 = 10; at t=1 it is at its cap and gexp is interior
# so LMP_1 = 50.  Dispatch [[110/3, 0], [40, 46.5]], objective 3091.666667.
#
# Settlement, derived from those numbers before the module existed:
#   t=0  payment 20*10 = 200      receipts 36.666667*10 = 366.666667
#        charge payment 16.666667*10 = 166.666667   discharge revenue 0
#        rent = 200 + 166.666667 - 366.666667 - 0 = 0        (unrated branch: no congestion)
#        *without* settling storage the same subtraction reads 200 - 366.666667 = -166.666667
#   t=1  payment 100*50 = 5000    receipts 86.5*50 = 4325
#        charge payment 0         discharge revenue 13.5*50 = 675
#        rent = 5000 + 0 - 4325 - 675 = 0
#        *without* settling storage: 5000 - 4325 = +675
#   horizon storage net revenue = 675 - 166.666667 = 508.333333 = profit*

ARBITRAGE_PROFIT = 50.0 / 3.0 * 30.5  # 508.333333...


def _arbitrage_network(storage: bool = True) -> Network:
    units = [
        Storage(
            id="st2",
            bus="b2",
            p_max_mw=20.0,
            energy_mwh=15.0,
            soc_initial=0.0,
            efficiency_charge=0.9,
            efficiency_discharge=0.9,
        )
    ]
    return _two_bus(
        [_gen("gcheap", "b1", 0.0, 40.0, 10.0), _gen("gexp", "b1", 0.0, 200.0, 50.0)],
        load_mw=20.0,
        storage=units if storage else [],
    )


def _arbitrage_scenario(storage: bool = True) -> Scenario:
    return Scenario(network=_arbitrage_network(storage), periods=_profile("ld2", [20.0, 100.0]))


# --- a congested storage horizon: three periods, three different answers ------------------------
#
#   b1 (slack): g1 c1=10 [0, 200]     br12 rated 40 MVA
#   b2:         ld2 profile [10, 50, 30];  st2 P=50 MW, E=20 MWh, soc_init=0, eta=0.9/0.9
#
# At t=1 the 50 MW load at b2 can draw at most 40 MW across br12, so >= 10 MW must be injected
# locally and the flow row binds; at t=0 (10 MW) and t=2 (30 MW) it does not.  So the per-period
# congestion rent is *structurally* different across the horizon, not the same number repeated.


def _congested_scenario(profile: list[float]) -> Scenario:
    net = _two_bus(
        [_gen("g1", "b1", 0.0, 200.0, 10.0)],
        load_mw=10.0,
        storage=[
            Storage(
                id="st2",
                bus="b2",
                p_max_mw=50.0,
                energy_mwh=20.0,
                soc_initial=0.0,
                efficiency_charge=0.9,
                efficiency_discharge=0.9,
            )
        ],
        rating_mva=40.0,
    )
    return Scenario(network=net, periods=_profile("ld2", profile))


# --- a real fixture: rated branches, a non-uniform per-load profile, and a storage unit ---------


def _wavy_periods(net: Network, n_periods: int, amplitude: float = 0.12) -> list[Period]:
    """Per-load, per-period overrides that are deliberately **not** a uniform system-wide scale.

    Load ``i`` in period ``t`` is scaled by ``1 + amplitude*sin(2*pi*(t/T + i/n_load))``, so the
    *spatial* pattern of demand differs period to period -- the failure mode the wave spec's
    rejected-alternative list names ("congestion binds in all or none").
    """
    loads = list(net.loads)
    return [
        Period(
            load_p_mw={
                ld.id: ld.p_mw
                * (1.0 + amplitude * math.sin(2.0 * math.pi * (t / n_periods + i / len(loads))))
                for i, ld in enumerate(loads)
            }
        )
        for t in range(n_periods)
    ]


def _with_storage(net: Network, bus: str, p_max_mw: float, energy_mwh: float) -> Network:
    out = net.model_copy(deep=True)
    out.storage = [
        *out.storage,
        Storage(
            id="st-derived",
            bus=bus,
            p_max_mw=p_max_mw,
            energy_mwh=energy_mwh,
            soc_initial=0.5,
            efficiency_charge=0.95,
            efficiency_discharge=0.92,
        ),
    ]
    return out


# --- the independent right-hand side of the settlement identity ---------------------------------


def _identity_rhs(net: Network, scenario: Scenario, *, include_shunt: bool = True) -> list[float]:
    """``-sum_k mu_kt*f_kt + sum_k mu_kt*pf_shift_k - sum_n LMP_nt*g_shunt_n`` per period.

    Built entirely from a **second, array-level** solve (``multiperiod_dc_opf``) and a PTDF
    recomputed from :func:`~mambo_power.numerics.ptdf.ptdf` -- never from ``solve_multiperiod``'s
    own payment/receipt subtraction. That is what makes the assertions below a proof of the
    identity rather than a restatement of arithmetic already performed.
    """
    arr = NetworkArrays.from_network(net)
    coeffs, pwl = gen_cost_coeffs(net, arr)
    loads_by_id = {ld.id: ld for ld in net.loads}
    periods = scenario.periods or []
    load_mw = np.array(
        [
            [period.load_p_mw.get(load_id, loads_by_id[load_id].p_mw) for load_id in arr.load_ids]
            for period in periods
        ],
        dtype=np.float64,
    ).reshape(len(periods), len(arr.load_ids))
    gens_by_id = {g.id: g for g in net.generators}
    ramp_up = np.array([gens_by_id[g].ramp_up_mw or np.inf for g in arr.gen_ids], dtype=np.float64)
    ramp_down = np.array(
        [gens_by_id[g].ramp_down_mw or np.inf for g in arr.gen_ids], dtype=np.float64
    )
    sol = multiperiod_dc_opf(
        arr,
        coeffs,
        len(periods),
        period_load_mw=load_mw,
        ramp_up_mw=ramp_up,
        ramp_down_mw=ramp_down,
        pwl_costs=pwl or None,
    )
    assert sol.status == "Optimal", sol.message
    assert sol.duals is not None

    ptdf_matrix = compute_ptdf(arr)  # recomputed, not sol.ptdf
    g_shunt_mw = arr.g_shunt_pu * arr.base_mva
    pf_shift_mw = pf_shift(arr) * arr.base_mva

    out: list[float] = []
    for t in range(len(periods)):
        inj = np.bincount(arr.gen_bus, weights=sol.dispatch_mw[t], minlength=arr.n_bus)
        inj = inj - np.bincount(arr.load_bus, weights=load_mw[t], minlength=arr.n_bus)
        if len(arr.storage_ids):
            net_storage = sol.storage_discharge_mw[t] - sol.storage_charge_mw[t]
            inj = inj + np.bincount(arr.storage_bus, weights=net_storage, minlength=arr.n_bus)
        inj = inj - g_shunt_mw
        mu = sol.duals.flow_limit[t]
        flows = ptdf_matrix @ inj + pf_shift_mw
        lmp = sol.duals.balance[t] + mu @ ptdf_matrix
        shunt_term = float(lmp @ g_shunt_mw) if include_shunt else 0.0
        out.append(float(-mu @ flows + mu @ pf_shift_mw) - shunt_term)
    return out


def _rent_lhs(result: MarketMultiperiodResult) -> list[float]:
    return [p.congestion_rent for p in result.periods]


def _rent_lhs_without_storage(result: MarketMultiperiodResult) -> list[float]:
    """M4's *nodal* form of the identity -- load payment minus generator receipts, storage left
    unsettled. Kept as a named negative control, not as a claim."""
    return [p.total_load_payment - p.total_generator_receipts for p in result.periods]


# --- AC-4: T=1 reduces to market.nodal, exactly -------------------------------------------------


@pytest.mark.parametrize("case", ["case14", "case30"])
def test_ac4_period_less_scenario_reproduces_market_nodal_exactly(case: str) -> None:
    """AC-4 -- ``Scenario.periods is None`` is a one-period horizon carrying the network's own
    loads, and it reproduces ``solve_nodal`` **bit for bit** (``assert_array_equal``)."""
    net = rated_network(matpower.load(FIXTURES_DIR / f"{case}.m"))
    scenario = Scenario(network=net)

    nodal = solve_nodal(scenario)
    multi = solve_multiperiod(scenario)

    assert nodal.status == "Optimal"
    assert multi.status == "Optimal"
    assert multi.n_periods == 1
    assert len(multi.periods) == 1
    period = multi.periods[0]

    assert [g.id for g in period.generators] == [g.id for g in nodal.generators]
    np.testing.assert_array_equal(
        [g.p_mw for g in period.generators], [g.p_mw for g in nodal.generators]
    )
    np.testing.assert_array_equal(
        [g.bound_dual for g in period.generators], [g.bound_dual for g in nodal.generators]
    )
    assert [ld.id for ld in period.loads] == [ld.id for ld in nodal.loads]
    np.testing.assert_array_equal([ld.p_mw for ld in period.loads], [ld.p_mw for ld in nodal.loads])
    assert [b.id for b in period.buses] == [b.id for b in nodal.buses]
    np.testing.assert_array_equal([b.lmp for b in period.buses], [b.lmp for b in nodal.buses])
    np.testing.assert_array_equal([b.energy for b in period.buses], [b.energy for b in nodal.buses])
    np.testing.assert_array_equal(
        [b.congestion for b in period.buses], [b.congestion for b in nodal.buses]
    )
    assert period.total_load_payment == nodal.total_load_payment
    assert period.total_generator_receipts == nodal.total_generator_receipts
    assert period.congestion_rent == nodal.congestion_rent
    assert multi.total_load_payment == nodal.total_load_payment
    assert multi.congestion_rent == nodal.congestion_rent


@pytest.mark.parametrize("case", ["case14", "case30"])
def test_ac4_an_explicit_single_period_also_reproduces_market_nodal_exactly(case: str) -> None:
    """AC-4's other reading: a horizon of **one explicit** ``Period`` whose overrides restate
    every load's own ``p_mw``.

    This is exact as *measured*, not as structurally guaranteed, and the distinction is real
    rather than theoretical. ``opf.multiperiod`` computes the period's bus-aggregate fixed load
    two different ways: with ``period_load_mw=None`` it evaluates ``dc_opf``'s literal
    ``arr.p_load_pu * base_mva`` (a per-unit round trip), and with an explicit profile it
    re-aggregates the MW values directly, skipping that round trip. Those two vectors are **not**
    bitwise equal on any fixture in this repository -- they differ by ~1e-15 MW on 2 buses of
    case14 and on 37 buses of case300 -- so the two routes hand HiGHS LP data that is a hair
    apart. The *answers* nonetheless come back bit-identical on both fixtures here, on every
    dispatch, LMP and settlement figure. Which is why ``solve_multiperiod`` routes a period-less
    scenario through ``None`` rather than through a materialised profile: only that route's
    exactness is structural. A fixture where the two answers diverged would land this test on
    ``assert_allclose``, and that would be information rather than a regression.
    """
    net = rated_network(matpower.load(FIXTURES_DIR / f"{case}.m"))
    nodal = solve_nodal(Scenario(network=net))
    explicit = solve_multiperiod(
        Scenario(
            network=net,
            periods=[Period(load_p_mw={ld.id: ld.p_mw for ld in net.loads})],
        )
    )

    assert nodal.status == "Optimal"
    assert explicit.status == "Optimal"
    period = explicit.periods[0]
    np.testing.assert_array_equal(
        [g.p_mw for g in period.generators], [g.p_mw for g in nodal.generators]
    )
    np.testing.assert_array_equal([b.lmp for b in period.buses], [b.lmp for b in nodal.buses])
    np.testing.assert_array_equal([ld.p_mw for ld in period.loads], [ld.p_mw for ld in nodal.loads])
    assert period.congestion_rent == nodal.congestion_rent


def test_ac4_exactness_holds_with_elastic_bids_in_play() -> None:
    """AC-4 on a fixture where the *elastic* demand columns exist too, so the reduction covers
    the demand-side rows and not only the fixed-load path."""
    net = with_bids(rated_network(matpower.load(FIXTURES_DIR / "case14.m")))
    scenario = Scenario(network=net)

    nodal = solve_nodal(scenario)
    multi = solve_multiperiod(scenario)

    assert nodal.status == "Optimal"
    assert multi.status == "Optimal"
    period = multi.periods[0]
    np.testing.assert_array_equal([ld.p_mw for ld in period.loads], [ld.p_mw for ld in nodal.loads])
    np.testing.assert_array_equal(
        [ld.bound_dual for ld in period.loads], [ld.bound_dual for ld in nodal.loads]
    )
    np.testing.assert_array_equal(
        [g.p_mw for g in period.generators], [g.p_mw for g in nodal.generators]
    )
    np.testing.assert_array_equal([b.lmp for b in period.buses], [b.lmp for b in nodal.buses])


def test_ac4_market_nodal_ignores_periods_entirely() -> None:
    """Second half of AC-4: ``market.nodal`` is untouched by this slice. A ``Scenario`` carrying
    periods clears through ``solve_nodal`` to *exactly* the same numbers as the period-less one --
    nodal never silently started reading period data."""
    net = rated_network(matpower.load(FIXTURES_DIR / "case14.m"))
    plain = solve_nodal(Scenario(network=net))
    with_periods = solve_nodal(Scenario(network=net, periods=_wavy_periods(net, 3)))

    assert plain.model_dump(exclude={"provenance"}) == with_periods.model_dump(
        exclude={"provenance"}
    )


# --- AC-5: the analytic arbitrage optimum, through the market layer ------------------------------


def test_ac5_analytic_arbitrage_optimum() -> None:
    """AC-5 -- research §7.2/§7.3's closed form, reproduced by ``solve_multiperiod``."""
    result = solve_multiperiod(_arbitrage_scenario())

    assert result.status == "Optimal"
    assert result.n_periods == 2
    charge = [p.storage[0].charge_mw for p in result.periods]
    discharge = [p.storage[0].discharge_mw for p in result.periods]
    soc = [p.storage[0].soc_mwh for p in result.periods]
    np.testing.assert_allclose(charge, [50.0 / 3.0, 0.0], atol=1e-7)
    np.testing.assert_allclose(discharge, [0.0, 13.5], atol=1e-7)
    np.testing.assert_allclose(soc, [15.0, 0.0], atol=1e-7)

    dispatch = [[g.p_mw for g in p.generators] for p in result.periods]
    np.testing.assert_allclose(dispatch, [[110.0 / 3.0, 0.0], [40.0, 46.5]], atol=1e-7)
    assert result.objective_cost == pytest.approx(3091.6666667, abs=1e-6)

    lmp = [[b.lmp for b in p.buses] for p in result.periods]
    np.testing.assert_allclose(lmp, [[10.0, 10.0], [50.0, 50.0]], atol=1e-7)

    # The dual side of the same closed form, and a second oracle: research §7.3's independent
    # scipy.optimize.linprog probe of this exact instance reports mu_soc = -11.111111 for the
    # binding energy cap, which is -c_L/eta_c = -10/0.9 = -100/9. The t=1 SoC dual is the mirror
    # relation -eta_d*c_H = -45, and the energy-bound reduced cost is -(y_soc0 - y_soc1).
    soc_duals = [p.storage[0].soc_dual for p in result.periods]
    np.testing.assert_allclose(soc_duals, [-100.0 / 9.0, -45.0], atol=1e-7)
    assert result.periods[0].storage[0].energy_bound_dual == pytest.approx(
        -(-100.0 / 9.0 - -45.0), abs=1e-7
    )


def test_ac5_horizon_saving_equals_the_closed_form_profit() -> None:
    """AC-5, end to end: the generation cost storage removes from the system is exactly
    ``profit* = charge*(c_H*eta_c*eta_d - c_L) = 508.333333``."""
    with_storage = solve_multiperiod(_arbitrage_scenario(storage=True))
    without = solve_multiperiod(_arbitrage_scenario(storage=False))

    assert with_storage.status == "Optimal"
    assert without.status == "Optimal"
    assert without.objective_cost == pytest.approx(3600.0, abs=1e-6)
    assert without.objective_cost - with_storage.objective_cost == pytest.approx(
        ARBITRAGE_PROFIT, abs=1e-6
    )


def test_ac5_settlement_reproduces_the_closed_form_profit_independently() -> None:
    """The settlement layer arrives at ``profit*`` from prices and quantities alone -- a second,
    independent route to research §7.2's closed form (the cost-difference route is the test
    above)."""
    result = solve_multiperiod(_arbitrage_scenario())

    assert result.status == "Optimal"
    per_period_charge_payment = [p.total_storage_charge_payment for p in result.periods]
    per_period_discharge_revenue = [p.total_storage_discharge_revenue for p in result.periods]
    np.testing.assert_allclose(per_period_charge_payment, [500.0 / 3.0, 0.0], atol=1e-6)
    np.testing.assert_allclose(per_period_discharge_revenue, [0.0, 675.0], atol=1e-6)

    horizon_net_revenue = (
        result.total_storage_discharge_revenue - result.total_storage_charge_payment
    )
    assert horizon_net_revenue == pytest.approx(ARBITRAGE_PROFIT, abs=1e-6)


# --- the settlement identity, per period --------------------------------------------------------


def test_settlement_identity_holds_per_period_on_the_arbitrage_horizon() -> None:
    scenario = _arbitrage_scenario()
    result = solve_multiperiod(scenario)

    assert result.status == "Optimal"
    rhs = _identity_rhs(scenario.network, scenario)
    np.testing.assert_allclose(_rent_lhs(result), rhs, atol=1e-6)
    np.testing.assert_allclose(rhs, [0.0, 0.0], atol=1e-6)  # unrated branch: no congestion


def test_leaving_storage_unsettled_breaks_the_identity_by_its_net_revenue() -> None:
    """The paired negative reading. M4's nodal form of the identity -- load payment minus
    generator receipts -- is **wrong** here, and wrong by exactly storage's per-period net
    revenue. Without this the identity test above would read the same on a horizon where
    storage never moved."""
    scenario = _arbitrage_scenario()
    result = solve_multiperiod(scenario)

    broken = _rent_lhs_without_storage(result)
    np.testing.assert_allclose(broken, [-500.0 / 3.0, 675.0], atol=1e-6)
    assert min(abs(v) for v in broken) > 100.0  # not a rounding-scale discrepancy

    storage_net = [
        p.total_storage_discharge_revenue - p.total_storage_charge_payment for p in result.periods
    ]
    np.testing.assert_allclose(broken, storage_net, atol=1e-6)


def test_settlement_identity_holds_per_period_with_binding_congestion() -> None:
    """Three periods whose flow rows bind differently: the identity has to hold on each of them
    separately, and the three rents are not the same number."""
    scenario = _congested_scenario([10.0, 50.0, 30.0])
    result = solve_multiperiod(scenario)

    assert result.status == "Optimal"
    rhs = _identity_rhs(scenario.network, scenario)
    lhs = _rent_lhs(result)
    np.testing.assert_allclose(lhs, rhs, atol=1e-6)

    # power: the flow row binds in the middle period and not the others, so this is genuinely a
    # per-period assertion and not one period's answer repeated three times.
    assert len({round(v, 6) for v in lhs}) > 1, f"all three rents identical: {lhs}"
    assert max(abs(v) for v in lhs) > 1.0, f"no congestion rent anywhere: {lhs}"
    charge = [p.storage[0].charge_mw for p in result.periods]
    discharge = [p.storage[0].discharge_mw for p in result.periods]
    assert max(charge) > 1.0
    assert max(discharge) > 1.0


def test_the_shunt_term_of_the_identity_is_load_bearing() -> None:
    """A bus shunt withdraws real power and nobody settles it, so the identity's general form
    carries a ``-sum_n LMP_n*g_shunt_n`` term. ``market.nodal``'s M4-era statement omitted it and
    was correct only because none of its fixtures had a shunt.

    Here a 5 MW shunt sits at ``b2`` behind a 40 MVA-rated branch. The identity closes **with**
    the term and is off by exactly the shunt's unsettled withdrawal without it, so the term is a
    real part of the claim rather than a hedge.
    """
    net = _two_bus(
        [_gen("g1", "b1", 0.0, 200.0, 10.0), _gen("g2", "b2", 0.0, 200.0, 40.0)],
        load_mw=10.0,
        rating_mva=40.0,
        shunt_g_mw=5.0,
    )
    scenario = Scenario(network=net, periods=_profile("ld2", [20.0, 60.0, 45.0]))

    result = solve_multiperiod(scenario)
    assert result.status == "Optimal", result.message

    np.testing.assert_allclose(_rent_lhs(result), _identity_rhs(net, scenario), atol=1e-6)

    without_shunt_term = _identity_rhs(net, scenario, include_shunt=False)
    gap = [a - b for a, b in zip(_rent_lhs(result), without_shunt_term, strict=True)]
    lmp_b2 = [next(b.lmp for b in p.buses if b.id == "b2") for p in result.periods]
    np.testing.assert_allclose(gap, [-5.0 * v for v in lmp_b2], atol=1e-6)
    assert min(abs(v) for v in gap) > 1.0, f"the shunt term made no difference: {gap}"


def test_settlement_identity_holds_per_period_on_a_real_fixture() -> None:
    """The same identity on case30: rated branches, quadratic fixture costs, a non-uniform
    four-period load profile, and a storage unit -- congestion, storage and a moving spatial
    pattern all active at once.

    ``case14`` was tried first and **rejected**: every period cleared with zero congestion rent
    there (its rated base case has no binding branch even under a moving profile), so the
    identity would have read ``0 == 0`` four times over and proved nothing. The storage unit
    goes at the bus whose LMP carries the largest congestion component in a storage-free probe,
    which is where a unit has something to arbitrage against.
    """
    base = rated_network(matpower.load(FIXTURES_DIR / "case30.m"))
    periods = _wavy_periods(base, 4)

    probe = solve_multiperiod(Scenario(network=base, periods=periods))
    assert probe.status == "Optimal", probe.message
    congested_bus = max(
        (b for p in probe.periods for b in p.buses), key=lambda b: abs(b.congestion)
    ).id

    net = _with_storage(base, bus=congested_bus, p_max_mw=15.0, energy_mwh=30.0)
    scenario = Scenario(network=net, periods=_wavy_periods(net, 4))

    result = solve_multiperiod(scenario)
    assert result.status == "Optimal", result.message

    rhs = _identity_rhs(net, scenario)
    lhs = _rent_lhs(result)
    np.testing.assert_allclose(lhs, rhs, rtol=1e-9, atol=1e-6)

    # Power, three ways. The four rents must be distinct and non-trivial (otherwise this is one
    # period's assertion repeated four times), and storage's settlement terms must be doing real
    # work here (otherwise the identity would read the same with storage left unsettled).
    assert len({round(v, 6) for v in lhs}) == 4, f"per-period rents not distinct: {lhs}"
    assert min(abs(v) for v in lhs) > 1.0, f"a period cleared with no congestion at all: {lhs}"
    storage_gap = [abs(a - b) for a, b in zip(lhs, _rent_lhs_without_storage(result), strict=True)]
    assert max(storage_gap) > 1.0, (
        f"storage's settlement terms make no difference on this fixture: {storage_gap}"
    )


def test_horizon_totals_are_the_sum_of_the_per_period_settlements() -> None:
    scenario = _congested_scenario([10.0, 50.0, 30.0])
    result = solve_multiperiod(scenario)

    assert result.status == "Optimal"
    for field in (
        "total_load_payment",
        "total_generator_receipts",
        "total_storage_charge_payment",
        "total_storage_discharge_revenue",
        "congestion_rent",
    ):
        assert getattr(result, field) == pytest.approx(
            sum(getattr(p, field) for p in result.periods), abs=1e-9
        ), field


# --- extraction: period loads, ramp limits, and the rows every result must carry -----------------


def test_a_load_absent_from_a_period_falls_back_to_its_own_p_mw() -> None:
    """``Period.load_p_mw`` is an override, not a complete specification: a load the dict omits
    keeps its own ``Load.p_mw`` in that period."""
    net = Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack"), Bus(id="b2", base_kv=138.0, type="pq")],
        branches=[Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0)],
        generators=[_gen("g1", "b1", 0.0, 500.0, 10.0)],
        loads=[
            Load(id="lda", bus="b2", p_mw=30.0, q_mvar=0.0),
            Load(id="ldb", bus="b2", p_mw=70.0, q_mvar=0.0),
        ],
    )
    scenario = Scenario(
        network=net,
        periods=[Period(load_p_mw={"ldb": 10.0}), Period(load_p_mw={})],
    )
    result = solve_multiperiod(scenario)

    assert result.status == "Optimal"
    served = [{ld.id: ld.p_mw for ld in p.loads} for p in result.periods]
    assert served[0] == pytest.approx({"lda": 30.0, "ldb": 10.0})
    assert served[1] == pytest.approx({"lda": 30.0, "ldb": 70.0})
    dispatch = [p.generators[0].p_mw for p in result.periods]
    np.testing.assert_allclose(dispatch, [40.0, 100.0], atol=1e-7)


def test_a_period_override_moves_a_bid_loads_quantity_too() -> None:
    """A ``Period.load_p_mw`` override on a **bid-carrying** load must move that load's served
    quantity, exactly as it does for a load with no bid.

    ``Load.p_mw`` means two things at once: a fixed load's whole demand, and an elastic load's
    *maximum served quantity* (``Load.bid``'s own field description -- the bid "covers this
    Load's entire p_mw"). ``Period.load_p_mw`` overrides ``p_mw``, so it has to move both. The
    failure this pins is a silent one: the period value is subtracted from the fixed-load total
    while the elastic column's bound stays at the network's base ``p_mw``, and the two cancel
    exactly, leaving the bid load flat across the whole horizon while its non-bidding neighbour
    tracks the profile.

    Both loads sit at b2 behind an unrated branch, so nothing but the profile can move them:

      g1: c1 = 10, [0, 500]        LMP is 10 $/MWh in every period
      ld_bid:   p_mw = 100, flat linear bid at 80 $/MWh -- 80 > 10, so it is a price taker and
                clears at its own upper bound in every period, whatever that bound is
      ld_fixed: p_mw = 50, no bid  -- must-serve at whatever the period says
      profile:  x0.8 then x1.2 on both

    so served demand is [80, 120] and [40, 60], and g1 covers the sum: [120, 180].
    """
    net = Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack"), Bus(id="b2", base_kv=138.0, type="pq")],
        branches=[Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0)],
        generators=[_gen("g1", "b1", 0.0, 500.0, 10.0)],
        loads=[
            Load(
                id="ld_bid",
                bus="b2",
                p_mw=100.0,
                q_mvar=0.0,
                bid=PolynomialBid(coefficients=[0.0, 80.0, 0.0]),
            ),
            Load(id="ld_fixed", bus="b2", p_mw=50.0, q_mvar=0.0),
        ],
    )
    scenario = Scenario(
        network=net,
        periods=[
            Period(load_p_mw={"ld_bid": 80.0, "ld_fixed": 40.0}),
            Period(load_p_mw={"ld_bid": 120.0, "ld_fixed": 60.0}),
        ],
    )

    result = solve_multiperiod(scenario)

    assert result.status == "Optimal"
    served = [{ld.id: ld.p_mw for ld in p.loads} for p in result.periods]
    assert served[0] == pytest.approx({"ld_bid": 80.0, "ld_fixed": 40.0}, abs=1e-7)
    assert served[1] == pytest.approx({"ld_bid": 120.0, "ld_fixed": 60.0}, abs=1e-7)
    # the bid load must not simply sit at its own base p_mw in both periods (the bug's signature)
    assert served[0]["ld_bid"] != pytest.approx(100.0, abs=1e-3)
    assert served[1]["ld_bid"] != pytest.approx(100.0, abs=1e-3)
    np.testing.assert_allclose(
        [p.generators[0].p_mw for p in result.periods], [120.0, 180.0], atol=1e-7
    )


def test_generator_ramp_limits_are_read_off_the_model() -> None:
    """AC-2's hand-derived optimum, reached through the *market* layer: the ramp fields S2 put
    on ``Generator`` are what reach the builder, and the binding period's dual is reported.

    ``gcheap`` c1=10 [0,100] ramp +/-20; ``gexp`` c1=50 [0,100] unconstrained; load [50, 100].
    Hand derivation (record/m5-s4-report.md §4.1): dispatch [[50, 0], [70, 30]], the ramp-up row
    binds at t=1 with dual -40, and LMP_0 = -30 (the ramp-induced negative price).
    """
    net = _two_bus(
        [
            _gen("gcheap", "b1", 0.0, 100.0, 10.0, ramp_up_mw=20.0, ramp_down_mw=20.0),
            _gen("gexp", "b1", 0.0, 100.0, 50.0),
        ],
        load_mw=50.0,
    )
    result = solve_multiperiod(Scenario(network=net, periods=_profile("ld2", [50.0, 100.0])))

    assert result.status == "Optimal"
    dispatch = [[g.p_mw for g in p.generators] for p in result.periods]
    np.testing.assert_allclose(dispatch, [[50.0, 0.0], [70.0, 30.0]], atol=1e-7)
    np.testing.assert_allclose([p.buses[0].lmp for p in result.periods], [-30.0, 50.0], atol=1e-7)
    ramp_duals = [{g.id: g.ramp_dual for g in p.generators} for p in result.periods]
    assert ramp_duals[0] == {"gcheap": 0.0, "gexp": 0.0}  # no row couples into period 0
    assert ramp_duals[1]["gcheap"] == pytest.approx(-40.0, abs=1e-7)
    assert ramp_duals[1]["gexp"] == 0.0


def test_ramp_up_and_ramp_down_are_not_interchangeable() -> None:
    """The extraction must not transpose the two ramp fields, and the test above cannot tell:
    its generator has ``ramp_up_mw == ramp_down_mw``, so swapping them there is a literal no-op.
    This fixture separates them.

    ``gcheap`` c1=10 [0,100], ramp_up 60 (slack), ramp_down **20** (binding); ``gexp`` c1=50
    [0,100] unconstrained; load [100, 50]. Hand derivation, before running:

    * ``t=1`` balance pins total at 50 and ``gexp >= 0``, so ``gcheap[1] <= 50``.
    * The ramp-*down* row ``gcheap[0] - gcheap[1] <= 20`` therefore caps ``gcheap[0]`` at 70,
      and ``gexp[0]`` covers the remaining 30 MW.  Cost ``10*70 + 50*30 + 10*50 = 2700``.
    * Duals: ``gexp[0]`` interior -> ``lambda_0 = 50``; ``gcheap[0]`` interior ->
      ``10 - (lambda_0 - y_ramp) = 0`` -> ``y_ramp = +40`` (positive: the ramp-down side binds,
      the mirror of the ramp-up case's -40); ``gcheap[1]`` interior ->
      ``10 - (lambda_1 + y_ramp) = 0`` -> ``lambda_1 = -30``.

    Transposing the two fields (up 20, down 60) would leave ``gcheap = [100, 50]`` and a cost of
    **1500** instead -- a visibly different answer, which is the point.
    """
    net = _two_bus(
        [
            _gen("gcheap", "b1", 0.0, 100.0, 10.0, ramp_up_mw=60.0, ramp_down_mw=20.0),
            _gen("gexp", "b1", 0.0, 100.0, 50.0),
        ],
        load_mw=100.0,
    )
    result = solve_multiperiod(Scenario(network=net, periods=_profile("ld2", [100.0, 50.0])))

    assert result.status == "Optimal"
    dispatch = [[g.p_mw for g in p.generators] for p in result.periods]
    np.testing.assert_allclose(dispatch, [[70.0, 30.0], [50.0, 0.0]], atol=1e-7)
    assert result.objective_cost == pytest.approx(2700.0, abs=1e-7)
    np.testing.assert_allclose([p.buses[0].lmp for p in result.periods], [50.0, -30.0], atol=1e-7)
    ramp_duals = [{g.id: g.ramp_dual for g in p.generators} for p in result.periods]
    assert ramp_duals[1]["gcheap"] == pytest.approx(40.0, abs=1e-7)


def test_dropping_the_ramp_limits_changes_the_answer() -> None:
    """Absence readback for the ramp *extraction*: the same scenario with the model's ramp
    fields cleared reaches the unconstrained optimum instead."""
    net = _two_bus(
        [_gen("gcheap", "b1", 0.0, 100.0, 10.0), _gen("gexp", "b1", 0.0, 100.0, 50.0)],
        load_mw=50.0,
    )
    result = solve_multiperiod(Scenario(network=net, periods=_profile("ld2", [50.0, 100.0])))

    assert result.status == "Optimal"
    dispatch = [[g.p_mw for g in p.generators] for p in result.periods]
    np.testing.assert_allclose(dispatch, [[50.0, 0.0], [100.0, 0.0]], atol=1e-7)
    assert result.objective_cost == pytest.approx(1500.0, abs=1e-7)


def test_every_load_and_storage_unit_gets_a_row_in_every_period() -> None:
    scenario = _congested_scenario([10.0, 50.0, 30.0])
    result = solve_multiperiod(scenario)

    assert result.status == "Optimal"
    for t, period in enumerate(result.periods):
        assert period.period == t
        assert [ld.id for ld in period.loads] == ["ld2"]
        assert [s.id for s in period.storage] == ["st2"]
        assert [s.bus for s in period.storage] == ["b2"]
        assert [b.id for b in period.buses] == ["b1", "b2"]


def test_an_infeasible_horizon_is_reported_not_raised() -> None:
    """Never-raise convention, mirroring ``solve_nodal``: an infeasible horizon comes back
    through ``status``/``message`` with the row lists left empty."""
    net = _two_bus([_gen("g1", "b1", 0.0, 30.0, 10.0)], load_mw=10.0)
    result = solve_multiperiod(Scenario(network=net, periods=_profile("ld2", [10.0, 500.0])))

    assert result.status != "Optimal"
    assert result.periods == []
    assert result.congestion_rent == 0.0
    assert result.provenance.kind == "market.multiperiod"


def test_options_model_is_accepted_and_recorded_in_provenance() -> None:
    result = solve_multiperiod(_arbitrage_scenario(), MarketMultiperiodOptions())
    assert result.provenance.kind == "market.multiperiod"
    assert result.provenance.options == {}
    assert result.provenance.engine == "mambo-power"
