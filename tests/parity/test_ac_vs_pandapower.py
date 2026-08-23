"""AC-1 / AC-2: ``pf.solve_ac`` agrees with pandapower ``runpp`` (Newton-Raphson) per fixture.

Oracle path: the ``.m`` bytes are read independently (:mod:`tests.parity._mpc_reader`), pushed
through pandapower's own ``from_ppc`` pipeline (:func:`pandapower_from_raw`) and solved with
``pp.runpp(init="flat", tolerance_mva=1e-8, enforce_q_lims=<matched>, trafo_model="pi",
max_iteration=50)``. Ours is ``mambo_power.io.matpower.load`` → ``solve_ac(AcOptions(init="flat",
q_limits=<matched>))``. Q-limits are on for case14, case_ieee30, case57 and case118 and off for
the spec's case300 row; a sixth row runs case300 with limits on, which the aligned oracle
converges (see ``CASES``).

Alignment rules, each a documented convention difference (S3's list, record/m2-s3-report.md):

* ``BASE_KV = 0`` (case14, case57) → 1.0 kV on the oracle's copy, as the importer does;
* ``trafo_model="pi"`` — pandapower's default T model alters transformers with ``BR_B != 0``;
* angles compared after subtracting the oracle's slack angle (case118 stores 30°);
* transformer orientation — ``from_ppc`` taps the ``hv_bus`` it picks by base voltage, so the
  oracle copy reverses every transformer whose T_BUS is the higher-voltage end with MATPOWER's
  exact swap identity (:func:`hv_side_first`); the oracle's from-side flow for those is then
  its ``lv`` side;
* ``res_bus.p_mw``/``q_mvar`` are consumption-positive; our ``BusResult`` is the net injection,
  so the oracle injection is the negative.

Pinned buses (AC-2) are read from ``net._ppc["internal"]["pq"]`` — the PQ row list of the
**last** Newton solve, i.e. after the Q-limit loop converted the violators (rows mapped from
pandapower bus indices through ``net._pd2ppc_lookups["bus"]``). (``_ppc["bus"]``
BUS_TYPE is not usable: ``_run_ac_pf_with_qlims_enforced`` sets only the *last round's* changed
buses back to PV for reporting, ``run_newton_raphson_pf.py:244``.) The limit side is read from
``res_gen.q_mvar`` against ``gen.min_q_mvar``/``max_q_mvar``.

Tolerances (AC-1): 1e-6 pu on ``vm``, 1e-4 deg on ``va``, 1e-4 MVA on branch flows and bus
injections.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.pf import AcOptions, solve_ac
from mambo_power.results import AcPowerFlowResult
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy
from tests.parity.test_matpower_vs_pandapower import pandapower_from_raw

TOL_VM = 1e-6
TOL_VA_DEG = 1e-4
TOL_MVA = 1e-4
SUBSTITUTE_KV = 1.0  # mirrors mambo_power.io.matpower.DEFAULT_BASE_KV

CASES: list[tuple[str, bool]] = [
    ("case14", True),
    ("case_ieee30", True),
    ("case57", True),
    ("case118", True),
    ("case300", False),  # the spec's contracted case300 row
    # Beyond the spec: on the hv-first oracle pandapower *does* converge case300 with limits
    # (2 iterations, 10 pins). Its reported failure (record/m2-research.md §4.3) was a
    # consequence of from_ppc's tap-side defect, not of the data — recorded in the S4 report.
    ("case300", True),
]
PV = 2


@dataclass
class Case:
    name: str
    raw: dict[str, Any]
    pp: Any
    ours: AcPowerFlowResult
    slack_id: str
    q_limits: bool


def hv_side_first(raw: dict[str, Any]) -> dict[str, Any]:
    """Copy of the raw matrices with every transformer's F_BUS at the higher base voltage.

    ``from_ppc`` puts the tap on ``hv_bus`` and picks ``hv_bus`` by base voltage, so for a
    MATPOWER transformer whose T_BUS is the higher-voltage end (16 branches in case300) the tap
    would move to the wrong winding — inert in DC, where only ``1/(x·tap)`` enters, but a real
    network change in AC (164 MVA on branch 396, bus 7062, before this alignment). Those rows
    are rewritten with MATPOWER's own exact swap identity: with the tap on the from side,
    ``Yff = (y + jb/2)/τ², Ytt = y + jb/2, Yft = −y/conj(a), Ytf = −y/a``; reversing the
    branch with ``τ' = 1/τ, y' = y/τ² (r' = rτ², x' = xτ²), b' = b/τ², shift' = −shift``
    reproduces the same four entries. Applied to the oracle's copy only.
    """
    patched = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    bus, branch = patched["bus"], patched["branch"]
    kv = {int(row[0]): float(row[9]) for row in bus}
    for row in branch:
        tau = float(row[8])
        if tau in (0.0, 1.0) or kv[int(row[1])] <= kv[int(row[0])]:
            continue
        row[0], row[1] = row[1], row[0]
        row[2] *= tau * tau
        row[3] *= tau * tau
        row[4] /= tau * tau
        row[8] = 1.0 / tau
        row[9] = -row[9]
    return patched


def run_pandapower_ac(raw: dict[str, Any], *, q_limits: bool) -> Any:
    """pandapower net from the raw matrices (BASE_KV <= 0 patched, transformers hv-first),
    solved with ``runpp``."""
    import pandapower as pp

    patched = hv_side_first(raw)
    patched["bus"][patched["bus"][:, 9] <= 0, 9] = SUBSTITUTE_KV
    net = pandapower_from_raw(patched)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pp.runpp(
            net,
            init="flat",
            tolerance_mva=1e-8,
            enforce_q_lims=q_limits,
            trafo_model="pi",
            max_iteration=50,
            calculate_voltage_angles=True,
            numba=False,
        )
    assert net.converged
    return net


@pytest.fixture(
    scope="module",
    params=CASES,
    ids=[f"{name}-qlim-{'on' if q else 'off'}" for name, q in CASES],
)
def case(request: pytest.FixtureRequest) -> Case:
    name, q_limits = request.param
    path = FIXTURES_DIR / f"{name}.m"
    raw = read_mpc_numpy(path)
    net = matpower.load(path)
    slack_id = next(b.id for b in net.buses if b.type == "slack")
    ours = solve_ac(net, options=AcOptions(init="flat", q_limits=q_limits))
    assert ours.converged, (name, ours.iterations, ours.max_mismatch_mva)
    return Case(name, raw, run_pandapower_ac(raw, q_limits=q_limits), ours, slack_id, q_limits)


def _pp_bus(bus_id: str) -> int:
    """pandapower bus index for one of our ids (``_adjust_ppc_indices`` -> BUS_I - 1)."""
    return int(bus_id.removeprefix("bus-")) - 1


def _worst(diffs: dict[str, float]) -> tuple[str, float]:
    worst = max(diffs, key=diffs.__getitem__)
    return worst, diffs[worst]


# --- voltages ------------------------------------------------------------------------------------


def test_voltage_magnitudes_match_runpp(case: Case) -> None:
    vm = case.pp.res_bus.vm_pu
    assert len(case.ours.buses) == len(case.pp.bus)
    diffs = {b.id: abs(b.vm_pu - float(vm.loc[_pp_bus(b.id)])) for b in case.ours.buses}
    worst, value = _worst(diffs)
    assert value <= TOL_VM, (case.name, worst, value)


def test_voltage_angles_match_runpp(case: Case) -> None:
    va = case.pp.res_bus.va_degree
    offset = float(va.loc[_pp_bus(case.slack_id)])
    diffs = {b.id: abs(b.va_deg - (float(va.loc[_pp_bus(b.id)]) - offset)) for b in case.ours.buses}
    worst, value = _worst(diffs)
    assert value <= TOL_VA_DEG, (case.name, worst, value)
    assert next(b for b in case.ours.buses if b.id == case.slack_id).va_deg == 0.0


# --- branch flows --------------------------------------------------------------------------------


def oracle_flows(case: Case) -> dict[str, tuple[float, float, float, float]]:
    """pandapower ``(p_from, q_from, p_to, q_to)`` per branch id after orientation alignment."""
    pp = case.pp
    lookup = pp._from_ppc_lookups["branch"]
    flows: dict[str, tuple[float, float, float, float]] = {}
    for k, br in enumerate(case.ours.branches):
        assert br.id == f"branch-{k + 1}"
        et, el = lookup.element_type.iloc[k], int(lookup.element.iloc[k])
        f, t = _pp_bus(br.from_bus), _pp_bus(br.to_bus)
        if et in ("line", "impedance"):
            table, res = (
                (pp.line, pp.res_line) if et == "line" else (pp.impedance, pp.res_impedance)
            )
            assert (int(table.at[el, "from_bus"]), int(table.at[el, "to_bus"])) == (f, t)
            row = res.loc[el]
            flows[br.id] = (
                float(row.p_from_mw),
                float(row.q_from_mvar),
                float(row.p_to_mw),
                float(row.q_to_mvar),
            )
        else:
            hv, lv = int(pp.trafo.at[el, "hv_bus"]), int(pp.trafo.at[el, "lv_bus"])
            row = pp.res_trafo.loc[el]
            if (hv, lv) == (f, t):
                flows[br.id] = (
                    float(row.p_hv_mw),
                    float(row.q_hv_mvar),
                    float(row.p_lv_mw),
                    float(row.q_lv_mvar),
                )
            else:
                assert (hv, lv) == (t, f)
                flows[br.id] = (
                    float(row.p_lv_mw),
                    float(row.q_lv_mvar),
                    float(row.p_hv_mw),
                    float(row.q_hv_mvar),
                )
    return flows


def test_branch_flows_match_runpp(case: Case) -> None:
    theirs = oracle_flows(case)
    assert len(theirs) == len(case.ours.branches) == len(case.raw["branch"])
    diffs: dict[str, float] = {}
    for br in case.ours.branches:
        pf, qf, pt, qt = theirs[br.id]
        diffs[br.id] = max(
            abs(br.p_from_mw - pf),
            abs(br.q_from_mvar - qf),
            abs(br.p_to_mw - pt),
            abs(br.q_to_mvar - qt),
        )
    worst, value = _worst(diffs)
    assert value <= TOL_MVA, (case.name, worst, value)


# --- bus injections -------------------------------------------------------------------------------


def test_bus_injections_match_runpp(case: Case) -> None:
    res = case.pp.res_bus
    diffs = {
        b.id: max(
            abs(b.p_mw + float(res.p_mw.loc[_pp_bus(b.id)])),
            abs(b.q_mvar + float(res.q_mvar.loc[_pp_bus(b.id)])),
        )
        for b in case.ours.buses
    }
    worst, value = _worst(diffs)
    assert value <= TOL_MVA, (case.name, worst, value)


def test_slack_generation_matches_ext_grid_at_bus_level(case: Case) -> None:
    pp = case.pp
    slack_idx = _pp_bus(case.slack_id)
    for column in ("p_mw", "q_mvar"):
        theirs = float(pp.res_ext_grid[column][pp.ext_grid.bus == slack_idx].sum())
        theirs += float(pp.res_gen[column][pp.gen.bus == slack_idx].sum())
        theirs += float(pp.res_sgen[column][pp.sgen.bus == slack_idx].sum())
        ours = sum(getattr(g, column) for g in case.ours.generators if g.bus == case.slack_id)
        assert abs(ours - theirs) <= TOL_MVA, (case.name, column, ours, theirs)


# --- AC-2: the pinned set -------------------------------------------------------------------------


def oracle_pinned(case: Case) -> dict[str, str]:
    """``{bus_id: "max" | "min"}`` for every declared-PV bus pandapower converted to PQ."""
    pp = case.pp
    # internal["pq"] indexes ppci rows; every fixture bus is in service, so ppci == ppc rows
    # and pandapower's bus index (BUS_I - 1, non-consecutive in case300) maps to a row via
    # _pd2ppc_lookups["bus"]
    assert len(pp._ppc["bus"]) == len(pp.bus)
    row_of = pp._pd2ppc_lookups["bus"]
    internal_pq = {int(i) for i in pp._ppc["internal"]["pq"]}
    pinned: dict[str, str] = {}
    for bus_row in case.raw["bus"]:
        if int(bus_row[1]) != PV:
            continue
        b = int(bus_row[0]) - 1
        if int(row_of[b]) not in internal_pq:
            continue
        rows = pp.gen.index[pp.gen.bus == b]
        assert len(rows) >= 1
        q = float(pp.res_gen.q_mvar[rows].sum())
        q_max = float(pp.gen.max_q_mvar[rows].sum())
        q_min = float(pp.gen.min_q_mvar[rows].sum())
        if abs(q - q_max) <= 1e-9:
            pinned[f"bus-{b + 1}"] = "max"
        else:
            assert abs(q - q_min) <= 1e-9, (b + 1, q, q_min, q_max)
            pinned[f"bus-{b + 1}"] = "min"
    return pinned


def test_pinned_buses_match_runpp(case: Case) -> None:
    ours: dict[str, str] = {}
    for g in case.ours.generators:
        if g.q_limited != "none":
            assert ours.setdefault(g.bus, g.q_limited) == g.q_limited
    theirs = oracle_pinned(case) if case.q_limits else {}
    assert ours == theirs, (case.name, ours, theirs)
    roles = {b.id: b.role_effective for b in case.ours.buses}
    for bus_id in ours:
        assert roles[bus_id] == "pq"
    if not case.q_limits:
        assert case.ours.q_limit_rounds == 0


def test_at_least_one_fixture_pins() -> None:
    """The AC-2 comparison is not vacuous: case118 binds limits (record/m2-research.md §1.2)."""
    path = FIXTURES_DIR / "case118.m"
    ours = solve_ac(matpower.load(path), options=AcOptions(init="flat"))
    assert ours.q_limit_rounds >= 1
    assert any(g.q_limited != "none" for g in ours.generators)
