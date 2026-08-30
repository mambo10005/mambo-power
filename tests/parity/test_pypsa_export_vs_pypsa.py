"""AC-3 (wave M8, W3): PyPSA ``optimize()`` on ``io.pypsa.to_network(net)`` agrees with
``opf.solve_dc_opf(net)`` on case14 / case30 / case118 — objective within ``1e-8`` relative,
dispatch within ``1e-4`` MW — and a piecewise-cost network exports with those generators at
``marginal_cost`` 0, each named in the ``ExportReport``.

Unlike ``test_opf_vs_pypsa.py`` (M3), which builds the oracle from raw MATPOWER matrices via
``import_from_pypower_ppc`` and then patches costs and clears the ``p_set`` pin, this file goes
through the exporter alone: transformers are real PyPSA ``Transformer`` rows (case14 has three),
costs come from ``Generator.cost``, and no generator carries ``p_set``. The one term the exporter
cannot hand PyPSA's objective is the constant ``c0`` (``n.objective`` excludes constants); it is
kept per generator in the :data:`io.pypsa.COST_CONSTANT_COLUMN` column and added back here, as
the M3 file adds ``gencost`` column 6.

**Tolerances.** Objective: ``1e-8`` relative on all three (measured worst ``1.3e-12``,
case118). Dispatch: ``1e-4`` MW on case14 and case30; case118 sits at a measured ``1.87e-3`` MW on
``gen-5`` — the *same* residual ``test_opf_vs_pypsa.py`` measured on its ppc-built oracle, and
not the mapping's doing: both dispatches balance the same 4242.0 MW, every case118 cost is
strictly convex, and evaluating the exact polynomial at both points puts ``solve_dc_opf``'s
dispatch ``1.6e-7`` $/h *below* PyPSA's. HiGHS's QP (the oracle side) simply stops there —
its own log reports a ``1.1e-6`` primal-dual objective error, and tightening
``primal/dual_feasibility_tolerance`` (``1e-8``, ``1e-9``) or switching ``solver`` to
``ipm``/``simplex`` leaves the residual at ``1.87e-3`` to the last digit, while ``1e-10`` makes
HiGHS refuse the solve. ``CASE118_DISPATCH_ABS_TOL_MW`` is pinned just above the measurement so a
mapping regression on case118 still fails; AC-3's ``1e-4`` holds where the oracle can deliver it.

**Phase shift.** None of the three fixtures has a phase shifter, so a hand-built three-bus loop
is the witness for ``phase_shift``'s sign: PyPSA's linear power flow (``n.lpf()``) agrees with
``pf.solve_dc`` on angles and flows for ``±5°``. The same loop shows that PyPSA 1.2.4's
``optimize()`` ignores ``phase_shift`` entirely (``pypsa/optimization`` never reads it), so the
DC-OPF parity above is a claim about shift-free networks — the exporter carries the shift, the
oracle's optimiser does not.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from mambo_power import pf
from mambo_power.io import matpower
from mambo_power.io import pypsa as io_pypsa
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    PiecewiseCost,
    PolynomialCost,
)
from mambo_power.opf import solve_dc_opf
from mambo_power.results import OpfDcResult
from tests._fixtures import FIXTURES_DIR

pytest.importorskip("pypsa")

CASES = ["case14", "case30", "case118"]
COST_REL_TOL = 1e-8
DISPATCH_ABS_TOL_MW = 1e-4
CASE118_DISPATCH_ABS_TOL_MW = 2e-3
"""Margin over the measured 1.87e-3 MW HiGHS-QP residual on case118's gen-5 (module docstring)."""


@dataclass
class Case:
    name: str
    pypsa_obj: float
    pypsa_dispatch: dict[str, float]
    pypsa_status: tuple[str, str]
    ours: OpfDcResult


def optimize(net: Network) -> tuple[Any, float, dict[str, float], tuple[str, str]]:
    n = io_pypsa.to_network(net)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        status, cond = n.optimize(solver_name="highs")
    c0 = float(n.generators[io_pypsa.COST_CONSTANT_COLUMN].sum())
    obj = float(n.objective) + c0 if n.objective is not None else float("nan")
    dispatch = (
        {str(k): float(v) for k, v in n.generators_t.p.iloc[0].items()} if status == "ok" else {}
    )
    return n, obj, dispatch, (status, cond)


@pytest.fixture(scope="module", params=CASES)
def case(request: pytest.FixtureRequest) -> Case:
    net = matpower.load(FIXTURES_DIR / f"{request.param}.m")
    _, obj, dispatch, status = optimize(net)
    return Case(request.param, obj, dispatch, status, solve_dc_opf(net))


def test_both_optimal(case: Case) -> None:
    assert case.ours.status == "Optimal", (case.name, case.ours.message)
    assert case.pypsa_status == ("ok", "optimal"), case.name


def test_objective_matches(case: Case) -> None:
    rel = abs(case.ours.objective_cost - case.pypsa_obj) / abs(case.pypsa_obj)
    assert rel <= COST_REL_TOL, (case.name, case.ours.objective_cost, case.pypsa_obj, rel)


def test_dispatch_matches(case: Case) -> None:
    tol = CASE118_DISPATCH_ABS_TOL_MW if case.name == "case118" else DISPATCH_ABS_TOL_MW
    diffs = {g.id: abs(g.p_mw - case.pypsa_dispatch[g.id]) for g in case.ours.generators}
    worst = max(diffs, key=lambda k: diffs[k])
    assert diffs[worst] <= tol, (case.name, worst, diffs[worst])


def _shifter_mesh(shift_deg: float, tap_ratio: float | None = None) -> Network:
    """Three-bus loop: cheap gen at b1, dear gen at b3, load at b2; the b1–b2 branch is a
    phase shifter with a 70 MVA rating, so under ``solve_dc_opf`` a −5° shift pushes flow onto
    it and forces the dear generator on (g1 ≈ 23 MW, g3 ≈ 77 MW) while +5° lets g1 carry the
    whole load — the shift moves the optimum, which is what makes the loop a witness."""

    def gen(gid: str, bus: str, c1: float) -> Generator:
        return Generator(
            id=gid,
            bus=bus,
            p_mw=0.0,
            q_mvar=0.0,
            p_min_mw=0.0,
            p_max_mw=200.0,
            q_min_mvar=0.0,
            q_max_mvar=0.0,
            v_set_pu=1.0,
            cost=PolynomialCost(coefficients=[c1, 0.0]),
        )

    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pv"),
        ],
        branches=[
            Branch(
                id="t12",
                from_bus="b1",
                to_bus="b2",
                r=0.0,
                x=0.1,
                b=0.0,
                shift_deg=shift_deg,
                tap_ratio=tap_ratio,
                rating_mva=70.0,
            ),
            Branch(id="l23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0),
            Branch(id="l13", from_bus="b1", to_bus="b3", r=0.0, x=0.1, b=0.0),
        ],
        generators=[gen("g1", "b1", 10.0), gen("g3", "b3", 30.0)],
        loads=[Load(id="d2", bus="b2", p_mw=100.0, q_mvar=0.0)],
    )


def test_rated_tap_transformer_loop_dispatch_matches() -> None:
    """The three fixtures rate no branch, so their dispatch is the merit order whatever the
    impedances are — a wrong transformer ``x`` cannot show there. This loop's 70 MVA transformer
    (tap 0.9, no shift) carries 66.7 MW of the 100 MW load unaided at nominal tap, so the split
    between the cheap and the dear generator depends on the transformer's reactance as PyPSA
    reads it back from ``x`` and ``s_nom``."""
    net = _shifter_mesh(0.0, tap_ratio=0.9)
    net.branches[0].rating_mva = 60.0
    ours = solve_dc_opf(net)
    assert ours.status == "Optimal", ours.message
    _, obj, dispatch, status = optimize(net)
    assert status == ("ok", "optimal")
    by_id = {g.id: g.p_mw for g in ours.generators}
    assert by_id["g3"] > 1.0  # the rating binds, so the dear generator is on
    assert abs(ours.objective_cost - obj) / obj <= COST_REL_TOL
    for gid, p in by_id.items():
        assert abs(p - dispatch[gid]) <= DISPATCH_ABS_TOL_MW, (gid, p, dispatch[gid])


@pytest.mark.parametrize("shift_deg", [-5.0, 5.0])
def test_phase_shift_sign_matches_pypsa_lpf_on_a_loop(shift_deg: float) -> None:
    net = _shifter_mesh(shift_deg)
    net.generators[0].p_mw = 100.0  # the DC power flow needs a dispatch; g3 stays at 0
    n = io_pypsa.to_network(net)
    # lpf (not optimize) reads p_set, and this is the test's own pin, not the exporter's
    assert n.generators["p_set"].isna().all()
    n.generators.loc["g1", "p_set"] = 100.0
    n.generators.loc["g3", "p_set"] = 0.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n.lpf()
    ours = pf.solve_dc(net)
    assert ours.converged
    angles = n.buses_t.v_ang.iloc[0] * 180.0 / np.pi
    for bus in ours.buses:
        assert bus.va_deg == pytest.approx(float(angles[bus.id]), abs=1e-9), bus.id
    flows = {**n.lines_t.p0.iloc[0].to_dict(), **n.transformers_t.p0.iloc[0].to_dict()}
    for br in ours.branches:
        assert br.p_from_mw == pytest.approx(float(flows[br.id]), abs=1e-9), br.id
    # the shift is doing something: the shifter's flow differs from the unshifted loop's 66.7 MW
    shifter = next(br for br in ours.branches if br.id == "t12")
    assert abs(shifter.p_from_mw - 200.0 / 3.0) > 20.0


def test_pypsa_optimize_ignores_phase_shift_so_parity_is_for_shift_free_networks() -> None:
    """Documents the oracle's limit, not the exporter's: the shift is carried (test above) but
    PyPSA 1.2.4's optimiser returns the same dispatch for −5°, 0° and +5° — and at −5° that
    dispatch loads the 70 MVA shifter to 95.8 MW by PyPSA's own linear power flow, a rating an
    optimiser that read the shift could not have ignored. (Deliberately independent of
    ``solve_dc_opf``'s shifter path.)"""
    dispatches = []
    for shift in (-5.0, 0.0, 5.0):
        _, _, dispatch, status = optimize(_shifter_mesh(shift))
        assert status == ("ok", "optimal")
        dispatches.append(dispatch)
    assert dispatches[0] == pytest.approx(dispatches[1], abs=1e-6)
    assert dispatches[2] == pytest.approx(dispatches[1], abs=1e-6)
    assert dispatches[1] == pytest.approx({"g1": 100.0, "g3": 0.0}, abs=1e-6)
    net = _shifter_mesh(-5.0)
    net.generators[0].p_mw = 100.0
    flow = next(br for br in pf.solve_dc(net).branches if br.id == "t12")
    assert flow.p_from_mw > 70.0 + 20.0


def test_piecewise_costs_export_at_zero_and_are_named() -> None:
    net = matpower.load(FIXTURES_DIR / "derived" / "case14_pwl.m")
    pwl_ids = [g.id for g in net.generators if isinstance(g.cost, PiecewiseCost)]
    assert pwl_ids == ["gen-2", "gen-3"]
    n, report = io_pypsa.to_network_with_report(net)
    for gid in pwl_ids:
        assert n.generators.loc[gid, "marginal_cost"] == 0.0
        assert n.generators.loc[gid, "marginal_cost_quadratic"] == 0.0
    named = sorted(
        i for w in report.warnings if w.code == "PYPSA_PWL_COST_DROPPED" for i in w.element_ids
    )
    assert named == pwl_ids
    assert n.generators["p_set"].isna().all()
    # the polynomial generators still carry their costs, so the network stays solvable
    assert n.generators.loc["gen-1", "marginal_cost"] == 20.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert n.optimize(solver_name="highs") == ("ok", "optimal")
    # ... and the two free generators are, as expected, dispatched first: exactly the loss the
    # report names. This is a witness that the drop is not silent, not a parity claim.
    assert n.generators_t.p.iloc[0][pwl_ids].sum() > 0.0
    assert np.isfinite(n.objective)
