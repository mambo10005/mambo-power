"""AC-2, AC-3: ``opf.multiperiod.multiperiod_dc_opf`` — ramp coupling and storage SoC dynamics.

Every expected number in this module was **hand-derived before the builder existed** and is
written out in the derivation comment above the test that asserts it (the discipline M3's
hand-KKT case and M4's AC-1 established). Nothing here reads a number back off the solver and
calls it an oracle.

Four hand-built networks, each isolating one thing:

* :func:`_ramp_network` (**AC-2**) — a generator ramp limit that genuinely binds, with a
  negative period-0 energy price falling out of the KKT conditions.
* :func:`_arbitrage_network` (**AC-3** canonical) — ``record/m5-research.md`` §7's closed-form
  storage-arbitrage optimum, re-expressed so the two period prices are formed endogenously by
  the builder's own balance rows rather than assumed.
* :func:`_overlap_network` (**AC-3** paired positive) — research §3.2's constructed case where
  simultaneous charge *and* discharge is required for feasibility, so the
  ``min(charge, discharge) ~= 0`` readback the canonical fixtures rely on is shown to be
  capable of returning a large non-zero value on the same code path.
* :func:`_congested_storage_network` — storage in the PTDF flow rows: a rating that only a
  local discharge can respect.
"""

from __future__ import annotations

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.model import Branch, Bus, Generator, Load, Network, Storage
from mambo_power.numerics import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.dc_opf import OpfDcOptions, dc_opf
from mambo_power.opf.multiperiod import multiperiod_dc_opf
from tests._fixtures import FIXTURES_DIR

# --- shared network-building helpers ----------------------------------------------------------


def _gen(
    gid: str,
    bus: str,
    p_min_mw: float,
    p_max_mw: float,
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
    )


def _two_bus(
    generators: list[Generator],
    load_mw: float,
    storage: list[Storage] | None = None,
    rating_mva: float | None = None,
) -> Network:
    """b1 (slack) — br12 — b2; every generator at b1, the single load (and any storage) at b2."""
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
        ],
        branches=[
            Branch(
                id="br12",
                from_bus="b1",
                to_bus="b2",
                r=0.0,
                x=0.1,
                b=0.0,
                rating_mva=rating_mva,
            )
        ],
        generators=generators,
        loads=[Load(id="ld2", bus="b2", p_mw=load_mw, q_mvar=0.0)],
        storage=storage or [],
    )


def _linear_costs(c1: list[float]) -> np.ndarray:
    """``[c2, c1, c0]`` rows — every generator in this module has a purely linear cost."""
    return np.array([[0.0, c, 0.0] for c in c1], dtype=np.float64)


def _ramp_arrays(values: list[float | None], n_gen: int) -> np.ndarray:
    """``(n_gen,)`` ramp array, ``inf`` marking an unconstrained generator."""
    assert len(values) == n_gen
    return np.array([np.inf if v is None else v for v in values], dtype=np.float64)


# --- AC-2: a binding generator ramp limit -----------------------------------------------------
#
# Two generators at the slack bus, one load at b2 whose demand doubles between the two periods.
#
#   gcheap: c1 = 10, [0, 100], ramp_up = ramp_down = 20
#   gexp:   c1 = 50, [0, 100], unconstrained
#   ld2:    50 MW at t=0, 100 MW at t=1
#   br12:   unrated, so no flow row can ever bind
#
# Hand derivation (written down before the builder was run):
#
#   Period 0's balance row pins total generation at 50 MW, and gexp >= 0, so gcheap[0] <= 50;
#   the objective wants gcheap as high as possible, so gcheap[0] = 50 exactly.  The ramp-up row
#   gcheap[1] - gcheap[0] <= 20 then caps gcheap[1] at 70, and gexp[1] covers the rest:
#
#       dispatch = [[50, 0], [70, 30]]        objective = 10*50 + 10*70 + 50*30 = 2700
#
#   Duals, from HiGHS's own convention  reduced_cost_j = c_j - sum_r y_r * a_rj:
#
#     gexp[1]   interior  ->  50 - lambda_1 = 0                  ->  lambda_1 = 50
#     gcheap[1] interior  ->  10 - (lambda_1 + y_ramp) = 0       ->  y_ramp   = -40
#     gcheap[0] interior  ->  10 - (lambda_0 - y_ramp) = 0       ->  lambda_0 = -30
#     gexp[0]   at p_min  ->  reduced cost = 50 - lambda_0       ->  80
#
#   lambda_0 = -30 is not an artefact: one more MW of load at t=0 lets gcheap rise 1 MW at t=0,
#   which relaxes the ramp row so gcheap can also rise 1 MW at t=1 and displace gexp there.
#   Net system cost change = +10 - (50 - 10) = -30.  The classic ramp-induced negative price.


def _ramp_network() -> Network:
    return _two_bus(
        [
            _gen("gcheap", "b1", 0.0, 100.0, ramp_up_mw=20.0, ramp_down_mw=20.0),
            _gen("gexp", "b1", 0.0, 100.0),
        ],
        load_mw=50.0,
    )


@pytest.fixture
def ramp_arrays() -> NetworkArrays:
    return NetworkArrays.from_network(_ramp_network())


def _solve_ramp(arr: NetworkArrays, ramp_up: float | None = 20.0):  # type: ignore[no-untyped-def]
    return multiperiod_dc_opf(
        arr,
        _linear_costs([10.0, 50.0]),
        2,
        period_load_mw=np.array([[50.0], [100.0]]),
        ramp_up_mw=_ramp_arrays([ramp_up, None], len(arr.gen_ids)),
        ramp_down_mw=_ramp_arrays([20.0, None], len(arr.gen_ids)),
    )


def test_ramp_limit_binds_and_reproduces_the_hand_derived_dispatch(
    ramp_arrays: NetworkArrays,
) -> None:
    """AC-2 — the hand-derived optimum, exactly."""
    sol = _solve_ramp(ramp_arrays)

    assert sol.status == "Optimal"
    gcheap, gexp = (ramp_arrays.gen_ids.index(i) for i in ("gcheap", "gexp"))
    assert (gcheap, gexp) == (0, 1)
    np.testing.assert_allclose(sol.dispatch_mw, [[50.0, 0.0], [70.0, 30.0]], atol=1e-7)
    assert sol.objective_cost == pytest.approx(2700.0, abs=1e-7)


def test_ramp_dual_is_recovered_on_the_identified_binding_period(
    ramp_arrays: NetworkArrays,
) -> None:
    """AC-2 — the binding period is t=1 and its ramp dual matches the hand derivation."""
    sol = _solve_ramp(ramp_arrays)
    assert sol.duals is not None
    gcheap, gexp = 0, 1

    # one ramp row per adjacent pair: T-1 == 1 row here, the t=1 row.
    assert sol.duals.ramp.shape == (1, 2)
    assert sol.duals.ramp[0, gcheap] == pytest.approx(-40.0, abs=1e-7)
    assert sol.duals.ramp[0, gexp] == 0.0  # no ramp row exists for an unconstrained generator

    np.testing.assert_allclose(sol.duals.balance, [-30.0, 50.0], atol=1e-7)
    np.testing.assert_allclose(sol.duals.gen_bound, [[0.0, 80.0], [0.0, 0.0]], atol=1e-7)
    # br12 is unrated: its row can never bind in either period.
    np.testing.assert_allclose(sol.duals.flow_limit, np.zeros((2, 1)), atol=1e-12)


def test_the_ramp_row_is_what_moves_the_answer(ramp_arrays: NetworkArrays) -> None:
    """Absence readback for the ramp family: relax the limit and the constrained optimum goes
    away entirely (gcheap serves the whole of both periods, cost 1500)."""
    sol = _solve_ramp(ramp_arrays, ramp_up=None)
    assert sol.status == "Optimal"
    np.testing.assert_allclose(sol.dispatch_mw, [[50.0, 0.0], [100.0, 0.0]], atol=1e-7)
    assert sol.objective_cost == pytest.approx(1500.0, abs=1e-7)
    assert sol.duals is not None
    np.testing.assert_allclose(sol.duals.ramp, np.zeros((1, 2)), atol=1e-12)


def test_ramp_down_binds_on_a_falling_profile(ramp_arrays: NetworkArrays) -> None:
    """The mirror direction of the same two-sided row: with the profile reversed the ramp-*down*
    side binds, so gcheap must stay at 70 MW in the cheap period and gexp is not needed.

    Derivation: load = [100, 50]; gcheap[0] <= 100 by its own bound, and gcheap[0] - gcheap[1]
    <= 20 with gcheap[1] <= 50 (balance, gexp >= 0) gives gcheap[0] <= 70, so gexp[0] = 30 and
    gcheap = [70, 50].  Cost = 10*70 + 50*30 + 10*50 = 2700 — the mirror image of the AC-2 case.
    """
    sol = multiperiod_dc_opf(
        ramp_arrays,
        _linear_costs([10.0, 50.0]),
        2,
        period_load_mw=np.array([[100.0], [50.0]]),
        ramp_up_mw=_ramp_arrays([20.0, None], 2),
        ramp_down_mw=_ramp_arrays([20.0, None], 2),
    )
    assert sol.status == "Optimal"
    np.testing.assert_allclose(sol.dispatch_mw, [[70.0, 30.0], [50.0, 0.0]], atol=1e-7)
    assert sol.objective_cost == pytest.approx(2700.0, abs=1e-7)
    assert sol.duals is not None
    assert sol.duals.ramp[0, 0] != 0.0


# --- AC-3 canonical: research §7's analytic arbitrage optimum ----------------------------------
#
#   b1 (slack): gcheap c1=10 [0, 40];  gexp c1=50 [0, 200]
#   b2:         ld2 profile [20, 100];  st2 p_max=20 MW, energy=15 MWh, soc_initial=0,
#               eta_c = eta_d = 0.9
#   br12 unrated.
#
# The two period prices are *formed by the builder*, not assumed: at t=0 gcheap is interior
# (36.67 of its 40 MW), so lambda_0 = 10; at t=1 gcheap is at its cap and gexp is interior, so
# lambda_1 = 50.  That reproduces research §7.1's price-taker setup without hard-coding a price.
#
# Research §7.2's closed form, with c_L=10, c_H=50, eta_c=eta_d=0.9, P_max=20, E_max=15:
#
#     c_H * eta_c * eta_d = 50 * 0.81 = 40.5 > 10 = c_L        -> arbitrage is on
#     charge*    = min(P_max, E_max/eta_c) = min(20, 16.6667) = 16.6667   (the energy cap binds)
#     discharge* = eta_c * eta_d * charge* = 0.81 * 16.6667 = 13.5
#     profit*    = charge* * (c_H*eta_c*eta_d - c_L) = 16.6667 * 30.5 = 508.3333
#
# so soc[0] = 0.9 * 16.6667 = 15.0 = E_max exactly, and soc[1] = 15 - 13.5/0.9 = 0 == soc_initial
# (the cyclic condition is *consistent* with the free-ending-SoC derivation here, not an extra
# restriction: using all stored energy is what the closed form already does).
#
#     gcheap = [36.6667, 40],  gexp = [0, 46.5],  objective = 3091.6667
#     no-storage cost = 10*20 + (10*40 + 50*60) = 200 + 3400 = 3600
#     saving = 3600 - 3091.6667 = 508.3333 == profit*     <- the end-to-end check


def _arbitrage_network() -> Network:
    return _two_bus(
        [_gen("gcheap", "b1", 0.0, 40.0), _gen("gexp", "b1", 0.0, 200.0)],
        load_mw=20.0,
        storage=[
            Storage(
                id="st2",
                bus="b2",
                p_max_mw=20.0,
                energy_mwh=15.0,
                soc_initial=0.0,
                efficiency_charge=0.9,
                efficiency_discharge=0.9,
            )
        ],
    )


@pytest.fixture
def arbitrage_arrays() -> NetworkArrays:
    return NetworkArrays.from_network(_arbitrage_network())


def _solve_arbitrage(arr: NetworkArrays):  # type: ignore[no-untyped-def]
    return multiperiod_dc_opf(
        arr,
        _linear_costs([10.0, 50.0]),
        2,
        period_load_mw=np.array([[20.0], [100.0]]),
    )


def test_analytic_storage_arbitrage_optimum(arbitrage_arrays: NetworkArrays) -> None:
    """The closed form of research §7.2/§7.3, reproduced by the builder."""
    sol = _solve_arbitrage(arbitrage_arrays)

    assert sol.status == "Optimal"
    np.testing.assert_allclose(sol.storage_charge_mw, [[50.0 / 3.0], [0.0]], atol=1e-7)
    np.testing.assert_allclose(sol.storage_discharge_mw, [[0.0], [13.5]], atol=1e-7)
    np.testing.assert_allclose(sol.storage_soc_mwh, [[15.0], [0.0]], atol=1e-7)
    np.testing.assert_allclose(sol.dispatch_mw, [[110.0 / 3.0, 0.0], [40.0, 46.5]], atol=1e-7)
    assert sol.objective_cost == pytest.approx(3091.6666667, abs=1e-6)

    assert sol.duals is not None
    np.testing.assert_allclose(sol.duals.balance, [10.0, 50.0], atol=1e-7)


def test_storage_saving_equals_the_closed_form_arbitrage_profit(
    arbitrage_arrays: NetworkArrays,
) -> None:
    """End-to-end: the cost the storage unit removes from the system is exactly research
    §7.2's ``profit* = charge* * (c_H*eta_c*eta_d - c_L)`` = 508.3333."""
    with_storage = _solve_arbitrage(arbitrage_arrays)
    no_storage = multiperiod_dc_opf(
        NetworkArrays.from_network(
            _two_bus(
                [_gen("gcheap", "b1", 0.0, 40.0), _gen("gexp", "b1", 0.0, 200.0)],
                load_mw=20.0,
            )
        ),
        _linear_costs([10.0, 50.0]),
        2,
        period_load_mw=np.array([[20.0], [100.0]]),
    )

    assert no_storage.status == "Optimal"
    assert no_storage.objective_cost == pytest.approx(3600.0, abs=1e-7)
    saving = no_storage.objective_cost - with_storage.objective_cost
    assert saving == pytest.approx(508.3333333, abs=1e-6)


# --- AC-3: SoC balance, cyclic condition, and the overlap readback -----------------------------


def _overlap_network(p_max_mw: float = 100.0) -> Network:
    """Research §3.2's construction: a must-run generator forces a fixed 15 MW/period surplus
    into a storage unit whose energy cap (5 MWh) cannot canonically absorb it.

    Balance leaves no dispatch freedom at all — ``charge[t] - discharge[t] == 15`` every period
    — so the LP's only remaining freedom is *how much overlap* to use.  With
    ``eta_c = eta_d = 0.8``: ``soc[t] - soc[t-1] = 0.8c - (c-15)/0.8 = -0.45c + 18.75``, and the
    cyclic condition ``soc[1] == 0`` forces ``c0 + c1 == 83.3333``, while ``0 <= soc[0] <= 5``
    forces each ``c`` into ``[30.5556, 41.6667]``.  Every feasible point therefore has
    ``min(charge, discharge) = c - 15 >= 15.5556``, strictly positive by a wide margin.

    At ``p_max_mw = 60`` the shared ``charge + discharge <= p_max`` row caps ``c`` at 37.5, so
    ``c0 + c1 <= 75 < 83.3333`` and the whole problem is infeasible — which is what makes that
    row demonstrably load-bearing rather than decorative.
    """
    return _two_bus(
        [_gen("gmust", "b1", 65.0, 65.0)],
        load_mw=50.0,
        storage=[
            Storage(
                id="st2",
                bus="b2",
                p_max_mw=p_max_mw,
                energy_mwh=5.0,
                soc_initial=0.0,
                efficiency_charge=0.8,
                efficiency_discharge=0.8,
            )
        ],
    )


def _solve_overlap(p_max_mw: float = 100.0):  # type: ignore[no-untyped-def]
    return multiperiod_dc_opf(
        NetworkArrays.from_network(_overlap_network(p_max_mw)),
        _linear_costs([0.0]),
        2,
        period_load_mw=np.array([[50.0], [50.0]]),
    )


def test_overlap_is_used_when_feasibility_requires_it() -> None:
    """AC-3's **paired positive case**: the same ``min(charge, discharge)`` readback that the
    canonical fixtures return ~0 on returns a large non-zero value here.

    Without this pairing the invariant test below cannot discharge: a near-zero reading looks
    identical whether the storage columns are correct or were never built at all.
    """
    sol = _solve_overlap()

    assert sol.status == "Optimal"
    net = sol.storage_discharge_mw - sol.storage_charge_mw
    np.testing.assert_allclose(net, [[-15.0], [-15.0]], atol=1e-7)

    overlap = np.minimum(sol.storage_charge_mw, sol.storage_discharge_mw)
    assert overlap.shape == (2, 1)
    assert overlap.min() > 15.0, f"paired positive case produced no overlap: {overlap!r}"
    # the whole feasible set has c in [30.5556, 41.6667], hence min = c - 15 in [15.5556, 26.6667]
    assert overlap.max() <= 26.6666667 + 1e-7


def test_the_shared_power_limit_row_is_live() -> None:
    """Absence readback for the ``charge + discharge <= p_max`` row: shrink ``p_max`` to 60 MW
    and the overlap network becomes infeasible (derivation in :func:`_overlap_network`)."""
    assert _solve_overlap(p_max_mw=60.0).status == "Infeasible"


# --- storage participates in the PTDF flow rows ------------------------------------------------
#
#   b1 (slack): g1 c1=10 [0, 200];  b2: ld2 profile [10, 50], st2 p_max=50, energy=20,
#   soc_initial=0, eta_c = eta_d = 0.9;  br12 rated 40 MVA.
#
# At t=1 the 50 MW load at b2 can only draw 40 MW across br12, so at least 10 MW must be
# injected locally: discharge[1] >= 10.  Round-trip loss makes any more strictly worse (an extra
# delta of discharge costs delta/0.81 of charging), so discharge[1] = 10 exactly, and the cyclic
# condition forces soc[0] = 10/0.9 = 11.1111, i.e. charge[0] = 11.1111/0.9 = 12.345679.
#
#     g1 = [10 + 12.345679, 50 - 10] = [22.345679, 40]      objective = 623.45679
#
# If the storage columns were missing from the flow rows, the t=1 row would read 50 MW against a
# 40 MW rating with nothing able to relieve it and the solve would be Infeasible.


def _congested_storage_network() -> Network:
    return _two_bus(
        [_gen("g1", "b1", 0.0, 200.0)],
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


# --- asymmetric charge/discharge efficiency ----------------------------------------------------
#
# Every other storage fixture here has eta_c == eta_d, which makes the two efficiencies
# indistinguishable: swapping them in the SoC row changes nothing, so no test could catch it.
# This one separates them (eta_c = 0.95, eta_d = 0.80) on the otherwise identical arbitrage shape.
#
#   activation (research §7.2):  c_H*eta_c*eta_d = 50*0.76 = 38 > 10 = c_L
#   charge*    = min(P_max, E_max/eta_c) = min(20, 15/0.95) = 300/19 = 15.789474
#   discharge* = eta_c*eta_d*charge*     = 0.76 * 300/19    = 12.0 exactly
#   soc        = [15.0, 0.0]              gcheap = [20 + 300/19, 40]     gexp = [0, 48]
#   objective  = 10*35.789474 + 10*40 + 50*48 = 3157.894737
#   saving vs the storage-free 3600 = 8400/19 = 442.105263 = charge* * (38 - 10) = profit*
#
# Swapping the two efficiencies would give charge* = 15/0.8 = 18.75 and discharge* = 14.25 —
# a visibly different answer.


def _asymmetric_efficiency_network() -> Network:
    return _two_bus(
        [_gen("gcheap", "b1", 0.0, 40.0), _gen("gexp", "b1", 0.0, 200.0)],
        load_mw=20.0,
        storage=[
            Storage(
                id="st2",
                bus="b2",
                p_max_mw=20.0,
                energy_mwh=15.0,
                soc_initial=0.0,
                efficiency_charge=0.95,
                efficiency_discharge=0.80,
            )
        ],
    )


def test_charge_and_discharge_efficiencies_enter_the_soc_row_the_right_way_round() -> None:
    """The two efficiencies are not interchangeable, and this fixture is what proves it."""
    arr = NetworkArrays.from_network(_asymmetric_efficiency_network())
    sol = multiperiod_dc_opf(
        arr, _linear_costs([10.0, 50.0]), 2, period_load_mw=np.array([[20.0], [100.0]])
    )

    assert sol.status == "Optimal"
    np.testing.assert_allclose(sol.storage_charge_mw, [[300.0 / 19.0], [0.0]], atol=1e-7)
    np.testing.assert_allclose(sol.storage_discharge_mw, [[0.0], [12.0]], atol=1e-7)
    np.testing.assert_allclose(sol.storage_soc_mwh, [[15.0], [0.0]], atol=1e-7)
    np.testing.assert_allclose(
        sol.dispatch_mw, [[20.0 + 300.0 / 19.0, 0.0], [40.0, 48.0]], atol=1e-7
    )
    assert sol.objective_cost == pytest.approx(3157.8947368, abs=1e-6)

    assert sol.duals is not None
    np.testing.assert_allclose(sol.duals.balance, [10.0, 50.0], atol=1e-7)
    # y_soc0 = -lambda_0/eta_c, y_soc1 = -eta_d*lambda_1 — each efficiency appears in exactly one
    np.testing.assert_allclose(sol.duals.soc_balance, [[-10.0 / 0.95], [-40.0]], atol=1e-7)


# --- the cyclic end-of-horizon row, where it genuinely binds ------------------------------------
#
# Same 2-period price structure (lambda = [10, 50]), but the unit starts *half full*: 15 MWh of a
# 30 MWh unit, p_max = 20 MW, eta_c = eta_d = 0.9.
#
#   With the cyclic row: headroom caps charging at 15 + 0.9*c0 <= 30 -> c0 = 50/3 = 16.6667, so
#   soc[0] = 30 (the cap), d1 = 0.81*c0 = 13.5, and soc[1] = 30 - 13.5/0.9 = 15 == soc_initial.
#   gcheap = [36.6667, 40], gexp = [0, 46.5], objective = 3091.6667.
#
#   Cyclic dual, derived two ways and agreeing: relaxing the row's RHS by 1 MWh frees 0.9 MW of
#   extra discharge at lambda_1 = 50, so d(cost)/d(rhs) = +45; and soc[1] is interior, so
#   0 - (y_soc1 + y_cyclic) = 0 with y_soc1 = -eta_d*lambda_1 = -45 gives y_cyclic = +45.
#
#   *Without* the row the LP would also drain the 15 MWh it started with: discharge would hit its
#   own 20 MW power cap and soc[1] would land at 30 - 20/0.9 = 7.7778.  That is what makes the
#   cyclic assertion on this fixture a real measurement instead of a tautology.


def _cyclic_binding_network() -> Network:
    return _two_bus(
        [_gen("gcheap", "b1", 0.0, 40.0), _gen("gexp", "b1", 0.0, 200.0)],
        load_mw=20.0,
        storage=[
            Storage(
                id="st2",
                bus="b2",
                p_max_mw=20.0,
                energy_mwh=30.0,
                soc_initial=0.5,
                efficiency_charge=0.9,
                efficiency_discharge=0.9,
            )
        ],
    )


def test_cyclic_row_forces_the_unit_back_to_its_starting_energy() -> None:
    """AC-3's cyclic half, on the one fixture where the row changes the answer."""
    arr = NetworkArrays.from_network(_cyclic_binding_network())
    sol = multiperiod_dc_opf(
        arr, _linear_costs([10.0, 50.0]), 2, period_load_mw=np.array([[20.0], [100.0]])
    )

    assert sol.status == "Optimal"
    np.testing.assert_allclose(sol.storage_charge_mw, [[50.0 / 3.0], [0.0]], atol=1e-7)
    np.testing.assert_allclose(sol.storage_discharge_mw, [[0.0], [13.5]], atol=1e-7)
    np.testing.assert_allclose(sol.storage_soc_mwh, [[30.0], [15.0]], atol=1e-7)
    assert sol.objective_cost == pytest.approx(3091.6666667, abs=1e-6)

    assert sol.duals is not None
    np.testing.assert_allclose(sol.duals.cyclic, [45.0], atol=1e-7)


def _storage_case(case: str) -> tuple[Network, list[float], np.ndarray]:
    """The storage-bearing networks this module ships, keyed by name, each with the linear cost
    vector and 2-period load profile it is solved with — the fixture set AC-3's invariants sweep.
    """
    cases: dict[str, tuple[Network, list[float], np.ndarray]] = {
        "arbitrage": (_arbitrage_network(), [10.0, 50.0], np.array([[20.0], [100.0]])),
        "overlap-required": (_overlap_network(), [0.0], np.array([[50.0], [50.0]])),
        "congested": (_congested_storage_network(), [10.0], np.array([[10.0], [50.0]])),
        "asymmetric-efficiency": (
            _asymmetric_efficiency_network(),
            [10.0, 50.0],
            np.array([[20.0], [100.0]]),
        ),
        "cyclic-binding": (
            _cyclic_binding_network(),
            [10.0, 50.0],
            np.array([[20.0], [100.0]]),
        ),
    }
    return cases[case]


STORAGE_CASES = (
    "arbitrage",
    "asymmetric-efficiency",
    "congested",
    "cyclic-binding",
    "overlap-required",
)
"""Every storage-bearing network in this module (AC-3 sweeps all of them)."""


@pytest.mark.parametrize("case", STORAGE_CASES)
def test_soc_balance_identity_holds_every_period(case: str) -> None:
    """AC-3 — ``soc[t] == soc[t-1] + eta_c*charge[t] - discharge[t]/eta_d`` every period, with
    ``soc[-1] == soc_initial * energy_mwh``, on every storage-bearing network this module ships.

    Recomputed from the *entity* efficiencies, not from anything the builder returns.
    """
    net, c1, profile = _storage_case(case)
    arr = NetworkArrays.from_network(net)
    sol = multiperiod_dc_opf(arr, _linear_costs(c1), 2, period_load_mw=profile)
    assert sol.status == "Optimal"

    eta_c = np.array([s.efficiency_charge for s in net.storage])
    eta_d = np.array([s.efficiency_discharge for s in net.storage])
    soc_initial = np.array([s.soc_initial * s.energy_mwh for s in net.storage])

    previous = soc_initial
    for t in range(2):
        expected = previous + eta_c * sol.storage_charge_mw[t] - sol.storage_discharge_mw[t] / eta_d
        np.testing.assert_allclose(sol.storage_soc_mwh[t], expected, atol=1e-7)
        previous = sol.storage_soc_mwh[t]


@pytest.mark.parametrize("case", STORAGE_CASES)
def test_cyclic_end_of_horizon_soc_is_met_exactly(case: str) -> None:
    """AC-3 — ``SoC_T == soc_initial``, to the LP's own equality-row tolerance."""
    net, c1, profile = _storage_case(case)
    arr = NetworkArrays.from_network(net)
    sol = multiperiod_dc_opf(arr, _linear_costs(c1), 2, period_load_mw=profile)
    assert sol.status == "Optimal"

    soc_initial = np.array([s.soc_initial * s.energy_mwh for s in net.storage])
    np.testing.assert_allclose(sol.storage_soc_mwh[-1], soc_initial, atol=1e-9)


@pytest.mark.parametrize(
    "case", ["arbitrage", "asymmetric-efficiency", "congested", "cyclic-binding"]
)
def test_no_simultaneous_charge_and_discharge_on_the_canonical_fixtures(case: str) -> None:
    """AC-3 — ``min(charge, discharge) ~= 0``.

    This assertion is only meaningful because
    :func:`test_overlap_is_used_when_feasibility_requires_it` shows the identical readback
    returning >15 MW on the same code path.
    """
    net, c1, profile = _storage_case(case)
    arr = NetworkArrays.from_network(net)
    sol = multiperiod_dc_opf(arr, _linear_costs(c1), 2, period_load_mw=profile)
    assert sol.status == "Optimal"

    overlap = np.minimum(sol.storage_charge_mw, sol.storage_discharge_mw)
    assert overlap.max() < 1e-7, f"{case}: simultaneous charge/discharge {overlap!r}"


def test_storage_soc_duals_match_the_hand_derived_kkt_conditions(
    arbitrage_arrays: NetworkArrays,
) -> None:
    """The SoC row duals of the arbitrage case, derived from the same KKT relation as the ramp
    dual above (``reduced_cost_j = c_j - sum_r y_r * a_rj``, every storage column costless):

        charge[0]    interior -> 0 - (lambda_0*(-1) + y_soc0*(-eta_c)) = 0
                              -> y_soc0 = -lambda_0/eta_c = -10/0.9 = -11.1111
        discharge[1] interior -> 0 - (lambda_1*(+1) + y_soc1*(1/eta_d)) = 0
                              -> y_soc1 = -eta_d*lambda_1 = -0.9*50 = -45
        soc[0] at E_max       -> reduced cost = -(y_soc0*1 + y_soc1*(-1)) = -33.8889

    ``y_soc0 = -11.1111`` is exactly the ``mu_soc`` research §7.3's independent
    ``scipy.optimize.linprog`` probe reports for the same instance — a second, dual-side
    confirmation that this builder's SoC row carries the efficiencies the right way round.

    The cyclic row's own dual is 0 here: research §7.1 derives this optimum with a *free* ending
    SoC and gets the same answer, so pinning ``soc[1] = soc_initial`` costs nothing.
    """
    sol = _solve_arbitrage(arbitrage_arrays)
    assert sol.duals is not None
    assert sol.storage_soc_mwh.max() <= 15.0 + 1e-7

    np.testing.assert_allclose(sol.duals.soc_balance, [[-100.0 / 9.0], [-45.0]], atol=1e-7)
    np.testing.assert_allclose(sol.duals.cyclic, [0.0], atol=1e-9)
    assert sol.duals.storage_soc_bound[0, 0] == pytest.approx(-45.0 + 100.0 / 9.0, abs=1e-7)
    # the power-limit row is slack here (16.67 + 0 < 20), unlike in the overlap case
    np.testing.assert_allclose(sol.duals.storage_power_limit, np.zeros((2, 1)), atol=1e-9)


def test_storage_relieves_a_binding_flow_limit() -> None:
    """Storage appears in the per-period PTDF flow rows, not only in the balance row."""
    arr = NetworkArrays.from_network(_congested_storage_network())
    sol = multiperiod_dc_opf(
        arr, _linear_costs([10.0]), 2, period_load_mw=np.array([[10.0], [50.0]])
    )

    assert sol.status == "Optimal"
    np.testing.assert_allclose(sol.storage_discharge_mw, [[0.0], [10.0]], atol=1e-7)
    np.testing.assert_allclose(sol.storage_charge_mw, [[1000.0 / 81.0], [0.0]], atol=1e-7)
    np.testing.assert_allclose(sol.dispatch_mw, [[10.0 + 1000.0 / 81.0], [40.0]], atol=1e-7)
    assert sol.objective_cost == pytest.approx(10.0 * (20.0 + 1000.0 / 81.0 + 30.0), abs=1e-6)

    assert sol.duals is not None
    assert sol.duals.flow_limit[1, 0] != 0.0, "the t=1 flow row must bind"
    assert sol.duals.flow_limit[0, 0] == pytest.approx(0.0, abs=1e-9)


# --- T=1 reduces to dc_opf --------------------------------------------------------------------


def test_single_period_matches_dc_opf_on_a_hand_built_network(
    ramp_arrays: NetworkArrays,
) -> None:
    """With T=1, no storage and no ramp data the builder must produce ``dc_opf``'s own answer."""
    coeffs = _linear_costs([10.0, 50.0])
    single = multiperiod_dc_opf(ramp_arrays, coeffs, 1)
    reference = dc_opf(ramp_arrays, coeffs, OpfDcOptions())

    assert single.status == reference.status == "Optimal"
    assert single.duals is not None and reference.duals is not None
    np.testing.assert_array_equal(single.dispatch_mw[0], reference.dispatch_mw)
    np.testing.assert_array_equal(single.duals.balance[0], reference.duals.balance)
    np.testing.assert_array_equal(single.duals.flow_limit[0], reference.duals.flow_limit)
    np.testing.assert_array_equal(single.duals.gen_bound[0], reference.duals.gen_bound)
    assert single.objective_cost == reference.objective_cost


@pytest.mark.parametrize("case", ["case14", "case30"])
def test_single_period_matches_dc_opf_on_a_real_fixture(case: str) -> None:
    """The same reduction on real fixture data, including quadratic costs — exact equality, not
    ``allclose``: at T=1 with no coupling row the builder hands HiGHS the same LP."""
    net = matpower.load(FIXTURES_DIR / f"{case}.m")
    arr = NetworkArrays.from_network(net)
    coeffs, pwl = gen_cost_coeffs(net, arr)

    single = multiperiod_dc_opf(arr, coeffs, 1, pwl_costs=pwl)
    reference = dc_opf(arr, coeffs, OpfDcOptions(), pwl_costs=pwl)

    assert single.status == reference.status == "Optimal"
    assert single.duals is not None and reference.duals is not None
    np.testing.assert_array_equal(single.dispatch_mw[0], reference.dispatch_mw)
    np.testing.assert_array_equal(single.duals.balance[0], reference.duals.balance)
    np.testing.assert_array_equal(single.duals.flow_limit[0], reference.duals.flow_limit)
    np.testing.assert_array_equal(single.duals.gen_bound[0], reference.duals.gen_bound)
    assert single.objective_cost == reference.objective_cost


# --- period-varying elastic demand, and the PWL paths at T > 1 ---------------------------------
#
# Everything below exists because the T=1 reductions above cannot see it: at T=1 the second-tier
# column base is ``n_dispatch_total + 0 * per_period_free``, every ``gen_cols[t]`` is
# ``gen_cols[0]``, and every per-unit stride is a stride of one period, so a whole family of
# index arithmetic is exercised only from T >= 2.


def _scaled_loads(net: Network, factor: float) -> Network:
    """A copy of ``net`` with every ``Load.p_mw`` multiplied by ``factor``, nothing else touched.

    The reference path for an *uncoupled* horizon: with no storage and no ramp limit, period
    ``t`` of a ``T``-period solve is a standalone ``dc_opf`` on the network whose loads are that
    period's own, and ``dc_opf`` is a separate builder reached through a separate call.
    """
    out = net.model_copy(deep=True)
    for load in out.loads:
        load.p_mw = load.p_mw * factor
    return out


def _profile(net: Network, arr: NetworkArrays, factors: tuple[float, ...]) -> np.ndarray:
    """``(T, n_load)`` MW in ``NetworkArrays.load_ids`` order — ``factors[t]`` x the base load."""
    loads_by_id = {load.id: load for load in net.loads}
    base = np.array([loads_by_id[load_id].p_mw for load_id in arr.load_ids], dtype=np.float64)
    return np.array([factor * base for factor in factors], dtype=np.float64)


def _elastic_network(p_mw: float = 100.0, fixed_mw: float | None = 50.0) -> Network:
    """b1 (slack, one 10 $/MWh generator) — unrated br12 — b2 carrying the elastic load."""
    loads = [Load(id="elastic", bus="b2", p_mw=p_mw, q_mvar=0.0)]
    if fixed_mw is not None:
        loads.append(Load(id="fixed", bus="b2", p_mw=fixed_mw, q_mvar=0.0))
    return Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack"), Bus(id="b2", base_kv=138.0, type="pq")],
        branches=[Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0)],
        generators=[_gen("g1", "b1", 0.0, 500.0)],
        loads=loads,
    )


def test_a_period_profile_moves_an_elastic_columns_upper_bound() -> None:
    """An elastic load's column bound is **that period's** demand, not the network's base
    ``Load.p_mw``.

    ``Load.p_mw`` is an elastic load's maximum served quantity, and ``period_load_mw`` overrides
    it, so it has to move that column's upper bound as well as the fixed-load total. The two
    cancel exactly if only the total moves, which makes the failure silent: the bidding load
    sits flat at its base ``p_mw`` across the whole horizon while the profile appears to work
    perfectly on every load that does *not* bid.

    Hand-derived: one 10 $/MWh generator at the slack, one elastic load at b2 bidding a flat
    80 $/MWh — 80 > 10, so it is a price taker and clears at whatever its own bound is — and one
    ordinary load beside it. Profile x0.8 then x1.2 on both, so the elastic load must serve 80
    then 120 MW and the fixed one 40 then 60.
    """
    net = _elastic_network()
    arr = NetworkArrays.from_network(net)
    elastic = arr.load_ids.index("elastic")

    sol = multiperiod_dc_opf(
        arr,
        _linear_costs([10.0]),
        2,
        period_load_mw=_profile(net, arr, (0.8, 1.2)),
        demand_bid_coeffs={elastic: (0.0, 80.0, 0.0)},
    )

    assert sol.status == "Optimal"
    np.testing.assert_allclose(sol.demand_dispatch_mw, [[80.0], [120.0]], atol=1e-7)
    np.testing.assert_allclose(sol.dispatch_mw, [[120.0], [180.0]], atol=1e-7)


def test_pwl_generator_costs_are_period_specific_at_t2() -> None:
    """``pwl_costs`` at T=2: each period gets its **own** epigraph rows over its **own**
    generator and ``cost_g`` columns.

    ``case14_pwl.m``'s piecewise generators reach ``multiperiod_dc_opf`` only at T=1 anywhere
    else in this suite, where ``t * per_period_free`` is 0 and every ``gen_cols[t]`` is
    ``gen_cols[0]`` — so the tier-2 column stride and the per-period epigraph wiring are both
    invisible there. Here they are not.

    Oracle: with no storage and no ramp limit the horizon is *uncoupled*, so it must equal two
    independent ``dc_opf`` solves on the networks carrying each period's own loads — a separate
    builder reached through a separate call, not a readback of this one. ``case14_pwl``'s own
    module docstring records a genuine LP tie between gen-2's and gen-3's 30 $/MWh segments, so
    the per-generator split is not unique; total cost, the price, and each period's total
    dispatch are, and those are what is asserted.
    """
    net = matpower.load(FIXTURES_DIR / "derived" / "case14_pwl.m")
    arr = NetworkArrays.from_network(net)
    coeffs, pwl = gen_cost_coeffs(net, arr)
    assert pwl, "case14_pwl must carry piecewise generator costs for this test to mean anything"
    factors = (0.9, 1.15)

    horizon = multiperiod_dc_opf(
        arr, coeffs, 2, period_load_mw=_profile(net, arr, factors), pwl_costs=pwl
    )
    assert horizon.status == "Optimal"
    assert horizon.duals is not None

    references = []
    for factor in factors:
        scaled = _scaled_loads(net, factor)
        scaled_arr = NetworkArrays.from_network(scaled)
        scaled_coeffs, scaled_pwl = gen_cost_coeffs(scaled, scaled_arr)
        reference = dc_opf(scaled_arr, scaled_coeffs, OpfDcOptions(), pwl_costs=scaled_pwl)
        assert reference.status == "Optimal"
        references.append(reference)

    assert horizon.objective_cost == pytest.approx(
        sum(r.objective_cost for r in references), abs=1e-6
    )
    for t, reference in enumerate(references):
        assert reference.duals is not None
        assert horizon.duals.balance[t] == pytest.approx(reference.duals.balance, abs=1e-7)
        assert horizon.dispatch_mw[t].sum() == pytest.approx(reference.dispatch_mw.sum(), abs=1e-6)
    # and the profile really did move the periods apart, so the equality above has content
    assert horizon.dispatch_mw[1].sum() > horizon.dispatch_mw[0].sum() + 1.0


BID_POINTS = [(0.0, 0.0), (40.0, 3200.0), (100.0, 3500.0)]
"""A 2-segment concave bid: marginal value 80 $/MWh on [0, 40], then 5 $/MWh on [40, 100]."""


def test_pwl_demand_bids_are_period_specific_at_t2() -> None:
    """``demand_pwl_bids`` at T=2 — the argument nothing else in this repository passes to this
    builder at all, so its per-period hypograph rows and its ``val_d`` column stride are
    otherwise unexercised.

    Hand-derived on the same two-bus network (one 10 $/MWh generator, unrated branch, so the
    price is 10 $/MWh in both periods). The bid's first segment is worth 80 $/MWh and its second
    only 5, so the load wants exactly ``min(bound, 40)`` MW:

      * period 0, bound 30 MW -> its own bound binds -> 30 MW served
      * period 1, bound 90 MW -> the *bid* binds     -> 40 MW served

    Both regimes on one horizon, and the two periods' answers are formed by different rows —
    which is exactly what a hypograph row pinned to period 0 cannot reproduce.
    """
    net = _elastic_network(fixed_mw=None)
    arr = NetworkArrays.from_network(net)
    bids = {arr.load_ids.index("elastic"): BID_POINTS}

    sol = multiperiod_dc_opf(
        arr,
        _linear_costs([10.0]),
        2,
        period_load_mw=np.array([[30.0], [90.0]]),
        demand_pwl_bids=bids,
    )

    assert sol.status == "Optimal"
    np.testing.assert_allclose(sol.demand_dispatch_mw, [[30.0], [40.0]], atol=1e-7)
    np.testing.assert_allclose(sol.dispatch_mw, [[30.0], [40.0]], atol=1e-7)
    assert sol.objective_cost == pytest.approx(10.0 * 70.0, abs=1e-7)

    # the same uncoupled-horizon oracle as the generator-side test: period t must equal a
    # standalone dc_opf on the network carrying that period's own load.
    for t, p_mw in enumerate((30.0, 90.0)):
        scaled_arr = NetworkArrays.from_network(_scaled_loads(net, p_mw / 100.0))
        reference = dc_opf(scaled_arr, _linear_costs([10.0]), OpfDcOptions(), demand_pwl_bids=bids)
        assert reference.status == "Optimal"
        np.testing.assert_allclose(
            sol.demand_dispatch_mw[t], reference.demand_dispatch_mw, atol=1e-7
        )


# --- heterogeneous units: the per-unit strides every other fixture in this module hides --------
#
# Every other storage-bearing network here has exactly one storage unit, and every ramped network
# exactly one ramped generator, so ``np.tile(x, T)`` and ``np.repeat(x, T)`` are the *same array*
# and a per-unit/per-period transposition in the tier-4 or tier-6 bounds cannot be observed at
# all. The two networks below carry two genuinely different units of each kind.


def _hetero_storage_network() -> Network:
    """Two storage units differing in power, energy **and** efficiency, both at b2.

    b1 (slack): gcheap c1=10 [0, 60]; gexp c1=50 [0, 200]. br12 unrated.
    b2: ld2 (profile [20, 100, 20]); st_small P=10 E=10 eta=0.8/0.8; st_big P=30 E=30 eta=1/1.
    """
    return Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack"), Bus(id="b2", base_kv=138.0, type="pq")],
        branches=[Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0)],
        generators=[_gen("gcheap", "b1", 0.0, 60.0), _gen("gexp", "b1", 0.0, 200.0)],
        loads=[Load(id="ld2", bus="b2", p_mw=20.0, q_mvar=0.0)],
        storage=[
            Storage(
                id="st_small",
                bus="b2",
                p_max_mw=10.0,
                energy_mwh=10.0,
                soc_initial=0.0,
                efficiency_charge=0.8,
                efficiency_discharge=0.8,
            ),
            Storage(
                id="st_big",
                bus="b2",
                p_max_mw=30.0,
                energy_mwh=30.0,
                soc_initial=0.0,
                efficiency_charge=1.0,
                efficiency_discharge=1.0,
            ),
        ],
    )


def test_two_storage_units_keep_their_own_power_limits() -> None:
    """Hand derivation, written before this network was ever solved.

    Charging at t0 pays only while it displaces ``gexp`` at t1. ``gcheap`` has 40 MW of headroom
    at t0 (60 - 20), so 40 MW of charging is available at 10 $/MWh and the 41st MW would cost
    50 $/MWh to store *and* 50 $/MWh to replace — never worth it. 40 MW is exactly what the two
    units can take together: st_big at its 30 MW rating (which fills its 30 MWh in one period at
    eta=1) and st_small at its 10 MW rating (storing 8 MWh at eta_c=0.8). The split is not free:
    st_big is strictly the better unit and is already at both of its own caps, so st_small takes
    the remainder.

        t0  gcheap 60, gexp 0;   charge [10, 30];  soc [8, 30]
        t1  discharge [6.4, 30] = 36.4 MW;  gcheap 60;  gexp = 100 - 60 - 36.4 = 3.6
        t2  gcheap 20, gexp 0; both units are already empty, which is what the cyclic row wants
        objective = 10*(60 + 60 + 20) + 50*3.6 = 1580

    A tier-4 bound transposed across units (``np.tile`` -> ``np.repeat``) hands st_big
    st_small's 10 MW rating at t0, capping the charge that drives every number above.
    """
    net = _hetero_storage_network()
    arr = NetworkArrays.from_network(net)
    assert arr.storage_ids == ["st_small", "st_big"]

    sol = multiperiod_dc_opf(
        arr,
        _linear_costs([10.0, 50.0]),
        3,
        period_load_mw=np.array([[20.0], [100.0], [20.0]]),
    )

    assert sol.status == "Optimal"
    np.testing.assert_allclose(
        sol.storage_charge_mw, [[10.0, 30.0], [0.0, 0.0], [0.0, 0.0]], atol=1e-7
    )
    np.testing.assert_allclose(
        sol.storage_discharge_mw, [[0.0, 0.0], [6.4, 30.0], [0.0, 0.0]], atol=1e-7
    )
    np.testing.assert_allclose(
        sol.storage_soc_mwh, [[8.0, 30.0], [0.0, 0.0], [0.0, 0.0]], atol=1e-7
    )
    np.testing.assert_allclose(sol.dispatch_mw, [[60.0, 0.0], [60.0, 3.6], [20.0, 0.0]], atol=1e-7)
    assert sol.objective_cost == pytest.approx(1580.0, abs=1e-6)


def _hetero_ramp_network() -> Network:
    """Three generators at the slack bus, two of them ramp-limited and *differently* so.

    gA c1=10 [0, 100] up 20 / down 30; gB c1=20 [0, 100] up 5 / down 8; gC c1=99 [0, 500] with
    no ramp data at all (so it gets no ramp row, and is the filler that keeps every period
    feasible). One load at b2 behind an unrated branch, profile [0, 100, 200, 20].
    """
    return Network(
        base_mva=100.0,
        buses=[Bus(id="b1", base_kv=138.0, type="slack"), Bus(id="b2", base_kv=138.0, type="pq")],
        branches=[Branch(id="br12", from_bus="b1", to_bus="b2", r=0.0, x=0.1, b=0.0)],
        generators=[
            _gen("gA", "b1", 0.0, 100.0, ramp_up_mw=20.0, ramp_down_mw=30.0),
            _gen("gB", "b1", 0.0, 100.0, ramp_up_mw=5.0, ramp_down_mw=8.0),
            _gen("gC", "b1", 0.0, 500.0),
        ],
        loads=[Load(id="ld2", bus="b2", p_mw=20.0, q_mvar=0.0)],
    )


def test_two_ramped_generators_keep_their_own_ramp_limits() -> None:
    """Hand derivation, written before this network was ever solved, period by period.

        t0  load 0   -> every generator is at 0: generation is non-negative and must sum to 0.
        t1  load 100 -> gA <= 0 + 20 and gB <= 0 + 5, and both are cheaper than gC, so both go
                        to their own ramp ceiling: gA 20, gB 5, gC 75.
        t2  load 200 -> the same argument one period on: gA 40, gB 10, gC 150.
        t3  load 20  -> now the ramp-*down* rows bind: gA >= 40 - 30 = 10, gB >= 10 - 8 = 2. gC
                        is 89 $/MWh dearer than gA and 79 than gB, so the 20 MW goes to gA down
                        to gB's own floor: gA 18, gB 2, gC 0.

        objective = (10*20 + 20*5 + 99*75) + (10*40 + 20*10 + 99*150) + (10*18 + 20*2)
                  = 7725 + 15450 + 220 = 23395

    Holding t2's units at their ceilings is right despite t3's floors: dropping gB 1 MW at t2
    would save 10 $ at t3 (gA displacing gB) and cost 79 $ at t2 (gC displacing gB).

    A tier-6 bound transposed across generators (``np.tile`` -> ``np.repeat``) gives gB gA's
    20 MW ramp-up at t1 and gA gB's 5 MW at t2, moving every number above.
    """
    net = _hetero_ramp_network()
    arr = NetworkArrays.from_network(net)
    assert arr.gen_ids == ["gA", "gB", "gC"]

    sol = multiperiod_dc_opf(
        arr,
        _linear_costs([10.0, 20.0, 99.0]),
        4,
        period_load_mw=np.array([[0.0], [100.0], [200.0], [20.0]]),
        ramp_up_mw=_ramp_arrays([20.0, 5.0, None], 3),
        ramp_down_mw=_ramp_arrays([30.0, 8.0, None], 3),
    )

    assert sol.status == "Optimal"
    np.testing.assert_allclose(
        sol.dispatch_mw,
        [[0.0, 0.0, 0.0], [20.0, 5.0, 75.0], [40.0, 10.0, 150.0], [18.0, 2.0, 0.0]],
        atol=1e-7,
    )
    assert sol.objective_cost == pytest.approx(23395.0, abs=1e-6)


# --- input validation --------------------------------------------------------------------------


def test_rejects_a_non_positive_period_count(ramp_arrays: NetworkArrays) -> None:
    with pytest.raises(ValueError, match="n_periods"):
        multiperiod_dc_opf(ramp_arrays, _linear_costs([10.0, 50.0]), 0)


def test_rejects_a_mis_shaped_load_profile(ramp_arrays: NetworkArrays) -> None:
    with pytest.raises(ValueError, match="period_load_mw"):
        multiperiod_dc_opf(
            ramp_arrays,
            _linear_costs([10.0, 50.0]),
            2,
            period_load_mw=np.array([[50.0, 1.0], [100.0, 1.0]]),
        )


def test_rejects_a_mis_shaped_ramp_array(ramp_arrays: NetworkArrays) -> None:
    with pytest.raises(ValueError, match="ramp_up_mw"):
        multiperiod_dc_opf(ramp_arrays, _linear_costs([10.0, 50.0]), 2, ramp_up_mw=np.array([20.0]))


def test_rejects_a_non_positive_ramp_limit(ramp_arrays: NetworkArrays) -> None:
    """``0`` would mean "frozen" — the MATPOWER unpopulated-column trap (research §4.2)."""
    with pytest.raises(ValueError, match="strictly positive"):
        multiperiod_dc_opf(
            ramp_arrays,
            _linear_costs([10.0, 50.0]),
            2,
            ramp_up_mw=np.array([0.0, np.inf]),
        )
