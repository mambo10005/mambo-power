"""AC-6: ``market.multiperiod`` matches a PyPSA multi-period oracle -- ramp limits and lossy
storage both active -- on a 24-period, rated-branch case14 horizon where congestion binds in some
periods and not others.

**The fixture, and why it binds and un-binds.** ``tests/_periods.py``'s single-curve diurnal
profile (peak 1.2x / trough 0.7x of case14's own committed load, module docstring on why a single
curve rather than two locationally-diverse archetypes) drives total system load from 181 MW to
311 MW over the day. ``tests/_rated.py``'s unmodified ``rated_network`` derives every
branch's rating from that same network's own *base-case* flow (20% headroom). At low hours the
dispatch sits well under every rating; from hour 13 through hour 22 one or more branches sit
exactly at their own rating (measured below, not assumed) -- the precondition this module's own
docstring requires before any PyPSA comparison means anything (AC-6 fixture-fidelity note).
:func:`tests._storage.storage_for_network` places a lossy (0.92/0.88 asymmetric-efficiency) unit
at bus-14, and ``gen-1`` carries an asymmetric ramp limit (10 MW/h up, 14.5 MW/h down) -- both
genuinely engaged, not decorative (measured below).

**The oracle-construction gotcha this fixture surfaces, beyond the already-documented ``p_set``
trap** (``tests/parity/test_opf_vs_pypsa.py``'s own module docstring): case14 has three
tap-ratio transformers (raw branch rows 8, 9, 10 -- ``bus4-bus7``, ``bus4-bus9``, ``bus5-bus6``,
imported by PyPSA as ``Transformer`` components ``T0``/``T1``/``T2``, not ``Line``s). Setting
``tests/_rated.py``'s own derived rating as ``s_nom`` on **both** the 17 ``Line`` and the 3
``Transformer`` components simultaneously makes PyPSA's constrained QP genuinely infeasible on
this fixture -- reproduced from a bare single-snapshot base-case solve (no ramp, no storage,
multiplier 1.0, i.e. the exact dispatch the ratings were derived from) up through a 3x uniform
slack on every rating, so it is not a numerical near-miss. Root cause not fully diagnosed
(candidate: PyPSA's linear power flow references a transformer's ``s_nom`` against a different
per-unit base than the one this repository's own PTDF-based flow uses, `unverified` beyond "the
combination reproducibly fails, well past any tie-breaking-scale slack"). This module routes
around it by rating **only the 17 lines** in PyPSA's oracle (transformers left at
``overwrite_zero_s_nom``, effectively unconstrained there) while ``mambo_power``'s own engine
rates all 20 branches, exactly as ``tests/_rated.py`` derives them, unchanged. This is safe for
*this* fixture's own claim, not a general fix: every branch that binds in
``mambo_power``'s own dispatch across the horizon (measured below) is one of the 17 lines, so the
comparison is never asked to agree on a constraint PyPSA's oracle does not itself enforce.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import pytest

from mambo_power.io import matpower
from mambo_power.market.multiperiod import _period_load_mw, _ramp_limits, solve_multiperiod
from mambo_power.model import Network, Period, Scenario, Storage
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.multiperiod import multiperiod_dc_opf
from mambo_power.results import MarketMultiperiodResult
from tests._fixtures import FIXTURES_DIR
from tests._periods import HOURS_PER_DAY, derive_periods
from tests._rated import rated_network
from tests._storage import storage_for_network
from tests.parity._mpc_reader import read_mpc_numpy

CASE = "case14"
STORAGE_BUS = "bus-14"
"""Sited explicitly rather than left to ``tests/_storage.py``'s own default (largest-aggregate-
load bus): measured (scratchpad probe, not committed) to be the case14 bus with the largest
LMP peak-to-trough spread under this profile, the only siting where the round-trip-lossy unit's
charge/discharge is genuinely profitable rather than a rounding-scale no-op."""
GEN1_RAMP_UP_MW = 10.0
GEN1_RAMP_DOWN_MW = 14.5
"""Deliberately asymmetric (module docstring pattern, ``tests/_storage.py``'s own efficiency
asymmetry rationale): an equal up/down limit is exactly the transposition-sabotage-proof shape
S4 and S5 both had to patch around after finding it by their own sabotage sweeps. Sized off the
fixture's own natural (unconstrained) hour-to-hour dispatch swing for gen-1 (measured up to
14.3 MW/h): ramp-up (10.0) sits below that swing so it genuinely binds on the rising slope;
ramp-down (14.5) sits just above it so the falling slope stays slack -- one-sided binding,
verified below."""

TIGHT_COST_REL_TOL = 1e-9
"""Margin over the measured worst-case relative objective residual, 4.35e-13."""
DISPATCH_ABS_TOL_MW = 1e-2
"""Margin over the measured worst-case per-generator, per-period dispatch residual, 3.01e-4 MW."""
STORAGE_ABS_TOL_MW = 1e-2
"""Margin over the measured worst-case net storage-power (discharge - charge) residual,
1.10e-4 MW."""
SOC_ABS_TOL_MWH = 1e-2
"""Margin over the measured worst-case state-of-charge residual, 1.25e-4 MWh.

**This is the tolerance that carries the efficiency-orientation proof, and loosening it would
cost the wave that proof.** Transposing ``eta_charge``/``eta_discharge`` in the engine's own SoC
row (``mambo_power.opf.multiperiod``, tier 3) leaves the objective, the generator dispatch, the
net storage power and the LMPs *all* comfortably inside their own tolerances here -- the
round-trip product is symmetric, so the grid-side charge/discharge schedule is invariant under
the transposition -- and moves the SoC trajectory alone, by a measured **5.088e-2 MWh** against
this 1e-2. That sabotage, run against this file unmodified, returns ``1 failed, 9 passed`` with
:func:`test_soc_matches_pypsa_every_period` the single failure.
:func:`test_the_fixture_can_tell_which_efficiency_is_which` pins the margin from the fixture's
own solved dispatch so that it cannot quietly evaporate."""
TRANSPOSITION_SIGNAL_MIN_MWH = 3e-2
"""Floor under the measured transposition signal, 5.10e-2 MWh
(:func:`test_the_fixture_can_tell_which_efficiency_is_which`), and itself 3x
:data:`SOC_ABS_TOL_MWH` -- so the fixture's detection power fails loudly, with a named number,
before the detection itself goes silent."""
LMP_ABS_TOL = 1e-3
"""Margin over the measured worst-case per-bus, per-period LMP residual, 4.24e-5 $/MWh."""
SIMULTANEITY_ABS_TOL_MW = 1e-6
"""Margin over the measured worst-case ``min(charge_mw, discharge_mw)`` on this fixture, 0.0 MW
exactly (AC-3). Not a physical tolerance: the overlap is *representable* in the formulation, so
this pins a measurement rather than an invariant the builder enforces."""


def _profile(net: Network) -> list[Period]:
    return derive_periods(net, n_periods=HOURS_PER_DAY)


def _fixture_network() -> tuple[Network, Storage]:
    """case14, rated (``tests/_rated.py``, unchanged), with a lossy storage unit
    (``tests/_storage.py``, unchanged) and gen-1's own asymmetric ramp limit (module docstring).
    Does not mutate any shared state -- fresh copies throughout, as every helper it calls
    guarantees."""
    net = rated_network(matpower.load(FIXTURES_DIR / f"{CASE}.m"))
    unit = storage_for_network(net, bus_id=STORAGE_BUS)
    net = net.model_copy(deep=True)
    net.storage.append(unit)
    for g in net.generators:
        if g.id == "gen-1":
            g.ramp_up_mw = GEN1_RAMP_UP_MW
            g.ramp_down_mw = GEN1_RAMP_DOWN_MW
    return net, unit


def _run_pypsa_oracle(
    net: Network, periods: list[Period], unit: Storage
) -> tuple[Any, str, str, float]:
    """PyPSA multi-period oracle: ``import_from_pypower_ppc`` + the already-committed ``p_set``
    fix (``tests/parity/test_opf_vs_pypsa.py``) + the gencost bridge, extended to 24 snapshots
    with ramp limits (MW -> PyPSA's per-unit-of-``p_nom`` convention, research §1.2), a
    ``StorageUnit`` (``efficiency_store``/``efficiency_dispatch``, and the cyclic condition
    matched via ``state_of_charge_initial`` + a ``state_of_charge_set`` pin at the last snapshot,
    since PyPSA's own ``cyclic_state_of_charge=True`` ignores ``state_of_charge_initial`` --
    module docstring on why that toggle is not used here), and **line-only** ``s_nom`` ratings
    (module docstring on why transformers are left unconstrained here).
    """
    raw = read_mpc_numpy(FIXTURES_DIR / f"{CASE}.m")
    patched = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    patched["bus"][patched["bus"][:, 9] <= 0, 9] = 1.0
    ppc = {
        "version": "2",
        "baseMVA": patched["baseMVA"],
        "bus": patched["bus"],
        "gen": patched["gen"],
        "branch": patched["branch"],
    }
    import pypsa

    n = pypsa.Network()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n.import_from_pypower_ppc(ppc, overwrite_zero_s_nom=9999.0)

    gencost = patched["gencost"]
    n.generators["marginal_cost_quadratic"] = gencost[:, 4]
    n.generators["marginal_cost"] = gencost[:, 5]
    c0_sum = float(np.sum(gencost[:, 6]))
    # the already-committed fix (test_opf_vs_pypsa.py): a non-null p_set is a fixed dispatch.
    n.generators["p_set"] = float("nan")

    # rate lines only (module docstring); transformers stay at overwrite_zero_s_nom.
    tap = patched["branch"][:, 8]
    line_i = 0
    rating_by_id = {b.id: b.rating_mva for b in net.branches}
    for row, is_xfmr in enumerate(tap != 0):
        bid = f"branch-{row + 1}"
        if not is_xfmr:
            n.lines.loc[f"L{line_i}", "s_nom"] = rating_by_id[bid]
            line_i += 1

    gens_by_id = {g.id: g for g in net.generators}
    for k, gid in enumerate([g.id for g in net.generators]):
        g = gens_by_id[gid]
        p_nom = float(n.generators.at[f"G{k}", "p_nom"])
        if g.ramp_up_mw is not None:
            n.generators.at[f"G{k}", "ramp_limit_up"] = g.ramp_up_mw / p_nom
        if g.ramp_down_mw is not None:
            n.generators.at[f"G{k}", "ramp_limit_down"] = g.ramp_down_mw / p_nom

    storage_bus_pypsa = str(int(unit.bus.split("-")[1]))
    n.add(
        "StorageUnit",
        unit.id,
        bus=storage_bus_pypsa,
        p_nom=unit.p_max_mw,
        max_hours=unit.energy_mwh / unit.p_max_mw,
        efficiency_store=unit.efficiency_charge,
        efficiency_dispatch=unit.efficiency_discharge,
        state_of_charge_initial=unit.soc_initial * unit.energy_mwh,
        cyclic_state_of_charge=False,
        marginal_cost=0.0,
    )

    n.set_snapshots(list(range(len(periods))))
    mambo_bus_to_load = {ld.bus: ld.id for ld in net.loads}
    pypsa_load_by_mambo_bus = {n.loads.at[name, "bus"]: name for name in n.loads.index}
    cols = list(n.loads.index)
    p_set = np.zeros((len(periods), len(cols)))
    for t, period in enumerate(periods):
        for mambo_bus, mambo_load_id in mambo_bus_to_load.items():
            bus_pp = str(int(mambo_bus.split("-")[1]))
            j = cols.index(pypsa_load_by_mambo_bus[bus_pp])
            p_set[t, j] = period.load_p_mw[mambo_load_id]
    n.loads_t.p_set = pd.DataFrame(p_set, index=n.snapshots, columns=cols)

    soc_set = pd.DataFrame(np.nan, index=n.snapshots, columns=[unit.id])
    soc_set.iloc[-1, 0] = unit.soc_initial * unit.energy_mwh
    n.storage_units_t.state_of_charge_set = soc_set

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        status, cond = n.optimize(solver_name="highs")
    # PyPSA has no constant-term concept at all (``marginal_cost`` and
    # ``marginal_cost_quadratic`` only), so our own convention -- gencost's ``c0`` is a cost per
    # *hour*, charged once in every period (``objective_cost``, verified directly at T in
    # {1, 2, 5, 24}) -- has to be added back here, ``len(periods)`` times and not once.
    # Currently inert either way: every gencost file in ``fixtures/`` carries ``c0 == 0.0``
    # exactly on all 5 OPF cases (measured), so this multiplication is what a future
    # ``c0``-bearing fixture needs rather than something this fixture exercises.
    obj = float(n.objective) + len(periods) * c0_sum if status == "ok" else float("nan")
    return n, status, cond, obj


@dataclass
class Case:
    net: Network
    unit: Storage
    periods: list[Period]
    ours: MarketMultiperiodResult
    pypsa: Any
    pypsa_status: str
    pypsa_cond: str
    pypsa_obj: float


@pytest.fixture(scope="module")
def case() -> Case:
    net, unit = _fixture_network()
    periods = _profile(net)
    ours = solve_multiperiod(Scenario(network=net, periods=periods))
    n, status, cond, obj = _run_pypsa_oracle(net, periods, unit)
    return Case(net, unit, periods, ours, n, status, cond, obj)


# --- the AC-6 precondition: congestion binds in some periods and not in others -----------------


def _per_period_flows(case: Case) -> tuple[NetworkArrays, np.ndarray]:
    """``(T, n_branch)`` MW flow, recomputed independently of ``solve_multiperiod`` -- a direct
    array-level call and the builder's own returned PTDF, mirroring
    ``tests/unit/test_market_multiperiod.py``'s own right-hand-side-independence discipline."""
    arr = NetworkArrays.from_network(case.net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(case.net, arr)
    period_load_mw = _period_load_mw(case.net, arr, case.periods)
    ramp_up, ramp_down = _ramp_limits(case.net, arr)
    sol = multiperiod_dc_opf(
        arr,
        cost_coeffs,
        len(case.periods),
        period_load_mw=period_load_mw,
        ramp_up_mw=ramp_up,
        ramp_down_mw=ramp_down,
        pwl_costs=pwl_costs or None,
    )
    assert sol.status == "Optimal"
    base = arr.base_mva
    ptdf = sol.ptdf
    flows = np.zeros((len(case.periods), arr.n_branch))
    for t in range(len(case.periods)):
        inj = np.zeros(len(arr.bus_ids))
        for i, b in enumerate(arr.gen_bus):
            inj[b] += sol.dispatch_mw[t, i] / base
        for s, b in enumerate(arr.storage_bus):
            inj[b] += (sol.storage_discharge_mw[t, s] - sol.storage_charge_mw[t, s]) / base
        for i, b in enumerate(arr.load_bus):
            inj[b] -= period_load_mw[t, i] / base
        flows[t] = (ptdf @ inj) * base
    return arr, flows


def test_solve_multiperiod_converges_optimal(case: Case) -> None:
    assert case.ours.status == "Optimal", case.ours.message


def test_congestion_binds_in_some_periods_and_not_others(case: Case) -> None:
    """The AC-6 fixture-fidelity precondition (module docstring, plan's AC-6 block): at least
    one period has a branch flow at its own rating, and at least one period has every branch
    comfortably clear of its rating. Both are asserted with the actual flow and rating, not
    merely a count."""
    arr, flows = _per_period_flows(case)
    ratings = {b.id: b.rating_mva for b in case.net.branches}
    rating_mw = np.array([ratings[bid] for bid in arr.branch_ids])

    binding_periods = [
        t for t in range(len(case.periods)) if np.any(np.abs(flows[t]) > 0.999 * rating_mw)
    ]
    slack_periods = [
        t for t in range(len(case.periods)) if np.all(np.abs(flows[t]) < 0.95 * rating_mw)
    ]

    assert binding_periods, "no period congests -- the fixture cannot test the flow-limit term"
    assert slack_periods, "every period congests -- the fixture cannot test the unconstrained case"

    # the binding evidence: the specific branch, flow and rating at the first binding period
    t0 = binding_periods[0]
    k0 = int(np.argmax(np.abs(flows[t0]) - rating_mw))
    assert abs(flows[t0, k0]) == pytest.approx(rating_mw[k0], abs=1e-2)

    # every branch that ever binds across the horizon must be one of the 17 PyPSA rates as a
    # Line -- the oracle-construction precondition the module docstring names.
    tap = read_mpc_numpy(FIXTURES_DIR / f"{CASE}.m")["branch"][:, 8]
    transformer_ids = {f"branch-{row + 1}" for row, is_xfmr in enumerate(tap != 0) if is_xfmr}
    for t in binding_periods:
        binding_ids = {
            arr.branch_ids[k]
            for k in range(arr.n_branch)
            if abs(flows[t, k]) > 0.999 * rating_mw[k]
        }
        assert binding_ids.isdisjoint(transformer_ids), (t, binding_ids & transformer_ids)


def test_no_simultaneous_charge_and_discharge(case: Case) -> None:
    """AC-3's ``min(charge, discharge) ~= 0`` reading, committed on the one fixture in this
    repository that is 24 periods long, rated and lossy at the same time --
    ``tests/unit/test_market_multiperiod.py`` pins it only on hand-built 2-period archetypes,
    and this is the horizon where a solver with room to arbitrage might actually take the
    overlap. Nothing in the formulation forbids it: charge and discharge are two independent
    nonnegative columns, capped only by their shared ``p_max_mw`` row (module docstring of
    ``mambo_power.opf.multiperiod`` on why banning it would need a binary). So this is a
    measurement, and it is asserted as one."""
    overlaps = np.array(
        [min(s.charge_mw, s.discharge_mw) for p in case.ours.periods for s in p.storage]
    )
    assert overlaps.size == HOURS_PER_DAY * len(case.net.storage)
    worst = int(np.argmax(overlaps))
    assert overlaps[worst] <= SIMULTANEITY_ABS_TOL_MW, (
        worst,
        overlaps[worst],
        case.ours.periods[worst].storage[0].charge_mw,
        case.ours.periods[worst].storage[0].discharge_mw,
    )


def test_ramp_and_storage_are_both_genuinely_engaged(case: Case) -> None:
    """Not decorative (module docstring): the ramp row actually binds at some hour, and the
    storage unit actually moves nonzero power at some hour."""
    ramp_binds = any(
        abs(g.ramp_dual) > 1e-6 for p in case.ours.periods for g in p.generators if g.id == "gen-1"
    )
    storage_moves = any(
        s.charge_mw > 1e-6 or s.discharge_mw > 1e-6 for p in case.ours.periods for s in p.storage
    )
    assert ramp_binds, "gen-1's ramp row never binds -- the fixture cannot test the ramp term"
    assert storage_moves, "storage never moves -- the fixture cannot test the storage term"


def test_the_fixture_can_tell_which_efficiency_is_which(case: Case) -> None:
    """The fixture-power precondition behind :data:`SOC_ABS_TOL_MWH`: this fixture distinguishes
    ``eta_charge`` from ``eta_discharge``, not merely their product.

    ``test_ramp_and_storage_are_both_genuinely_engaged`` only requires storage to move *at all*
    (> 1e-6 MW). That is far too weak to carry efficiency orientation, because the transposition
    is invisible to four of this module's five comparisons: ``eta_c * eta_d == eta_d * eta_c``, so
    a transposed engine converts grid-in to grid-out at exactly the same ratio and -- with no SoC
    bound and no energy cap binding on this fixture -- picks the *same* charge/discharge schedule.
    The objective, the dispatch, the net storage power and the LMPs therefore all agree. What
    moves is the SoC trajectory, and only the SoC trajectory.

    So the detectable signal is a closed form in the fixture's own solved schedule::

        soc_transposed[t] - soc_true[t]
            = sum_{tau <= t} [ (eta_d - eta_c) * charge[tau]
                               - (1/eta_c - 1/eta_d) * discharge[tau] ]

    Its worst-case magnitude is what has to clear :data:`SOC_ABS_TOL_MWH`, and it is proportional
    to the unit's *throughput*: the same 0.92/0.88 efficiencies on a horizon where the unit sat
    idle would leave the transposition genuinely undetectable. Measured here: **5.10e-2 MWh**
    predicted from the frozen schedule, against **5.088e-2 MWh** actually observed when the
    engine's tier-3 SoC row is transposed and this whole module re-run -- agreement to 0.3%, and
    5.1x over the tolerance that catches it.
    """
    unit = case.unit
    eta_c, eta_d = unit.efficiency_charge, unit.efficiency_discharge
    assert eta_c != eta_d, "equal efficiencies make the transposition a no-op by construction"

    charge = np.array([p.storage[0].charge_mw for p in case.ours.periods])
    discharge = np.array([p.storage[0].discharge_mw for p in case.ours.periods])
    soc0 = unit.soc_initial * unit.energy_mwh

    soc_true = soc0 + np.cumsum(eta_c * charge - discharge / eta_d)
    soc_transposed = soc0 + np.cumsum(eta_d * charge - discharge / eta_c)

    # the closed form must first be shown to be the engine's own SoC, or it proves nothing
    reported = np.array([p.storage[0].soc_mwh for p in case.ours.periods])
    assert np.abs(reported - soc_true).max() <= 1e-9, np.abs(reported - soc_true).max()

    signal = float(np.abs(soc_true - soc_transposed).max())
    assert signal >= TRANSPOSITION_SIGNAL_MIN_MWH, (signal, charge.sum(), discharge.sum())
    assert signal > SOC_ABS_TOL_MWH, (signal, SOC_ABS_TOL_MWH)


# --- the oracle itself must actually have solved ------------------------------------------------


def test_pypsa_itself_converges_optimal(case: Case) -> None:
    assert (case.pypsa_status, case.pypsa_cond) == ("ok", "optimal"), (
        case.pypsa_status,
        case.pypsa_cond,
    )


# --- AC-6: agreement within the pinned, measured tolerances -------------------------------------


def test_objective_cost_matches_pypsa(case: Case) -> None:
    rel = abs(case.ours.objective_cost - case.pypsa_obj) / abs(case.pypsa_obj)
    assert rel <= TIGHT_COST_REL_TOL, (case.ours.objective_cost, case.pypsa_obj, rel)


def test_dispatch_matches_pypsa_every_period(case: Case) -> None:
    ours = np.zeros((len(case.periods), len(case.net.generators)))
    for t, p in enumerate(case.ours.periods):
        by_id = {g.id: g.p_mw for g in p.generators}
        for k in range(len(case.net.generators)):
            ours[t, k] = by_id[f"gen-{k + 1}"]
    pypsa_gen = case.pypsa.generators_t.p[
        [f"G{k}" for k in range(len(case.net.generators))]
    ].to_numpy()
    diffs = np.abs(ours - pypsa_gen)
    worst = np.unravel_index(np.argmax(diffs), diffs.shape)
    assert diffs[worst] <= DISPATCH_ABS_TOL_MW, (worst, diffs[worst])


def test_storage_net_power_matches_pypsa_every_period(case: Case) -> None:
    ours_net = np.array(
        [p.storage[0].discharge_mw - p.storage[0].charge_mw for p in case.ours.periods]
    )
    pypsa_net = case.pypsa.storage_units_t.p[case.unit.id].to_numpy()
    diffs = np.abs(ours_net - pypsa_net)
    worst = int(np.argmax(diffs))
    assert diffs[worst] <= STORAGE_ABS_TOL_MW, (
        worst,
        diffs[worst],
        ours_net[worst],
        pypsa_net[worst],
    )


def test_soc_matches_pypsa_every_period(case: Case) -> None:
    ours_soc = np.array([p.storage[0].soc_mwh for p in case.ours.periods])
    pypsa_soc = case.pypsa.storage_units_t.state_of_charge[case.unit.id].to_numpy()
    diffs = np.abs(ours_soc - pypsa_soc)
    worst = int(np.argmax(diffs))
    assert diffs[worst] <= SOC_ABS_TOL_MWH, (worst, diffs[worst], ours_soc[worst], pypsa_soc[worst])


def test_lmp_matches_pypsa_every_period_and_bus(case: Case) -> None:
    ours_lmp = np.zeros((len(case.periods), len(case.net.buses)))
    for t, p in enumerate(case.ours.periods):
        by_id = {b.id: b.lmp for b in p.buses}
        for k, bus in enumerate(case.net.buses):
            ours_lmp[t, k] = by_id[bus.id]
    pypsa_lmp = case.pypsa.buses_t.marginal_price[
        [str(k + 1) for k in range(len(case.net.buses))]
    ].to_numpy()
    diffs = np.abs(ours_lmp - pypsa_lmp)
    worst = np.unravel_index(np.argmax(diffs), diffs.shape)
    assert diffs[worst] <= LMP_ABS_TOL, (worst, diffs[worst])
