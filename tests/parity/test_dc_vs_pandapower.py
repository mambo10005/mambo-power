"""AC-3: ``pf.solve_dc`` agrees with pandapower ``rundcpp`` on every MATPOWER fixture.

Oracle path: the same ``.m`` bytes are read independently (:mod:`tests.parity._mpc_reader`),
pushed through pandapower's own ``from_ppc`` pipeline (the helper in
:mod:`tests.parity.test_matpower_vs_pandapower`), and solved with ``pandapower.rundcpp``. Ours
is ``mambo_power.io.matpower.load`` followed by ``mambo_power.pf.solve_dc``.

Alignment rules (each one is a documented convention difference, not a tolerance):

* **Base voltage.** case14 and case57 carry ``BASE_KV = 0`` on every bus. Our importer
  substitutes 1.0 kV with a warning; pandapower's trafo model divides by ``vn_kv`` and yields
  NaN. The oracle's raw copy gets the same substitution. DC results do not depend on the base
  voltage (``test_oracle_is_invariant_to_the_base_kv_substitution`` proves it on case14).
* **Transformer model.** MATPOWER's branch is a π equivalent; pandapower's default
  ``trafo_model="t"`` turns a transformer with magnetizing admittance (``BR_B != 0`` — four
  case300 transformers) into a T and converts the series impedance T→π (``_wye_delta``),
  changing ``x`` by up to 6e-4 relative and the case300 angles by 2.6e-3 deg. The oracle runs
  with ``trafo_model="pi"``, pandapower's exact MATPOWER-equivalent branch.
* **Slack angle.** pandapower starts the DC solve from the ext_grid's ``va_degree`` (the stored
  slack VA — 30° in case118) and every angle is shifted by it; ours fixes the slack at 0. The
  oracle's angles are compared after subtracting its slack angle.
* **Branch orientation.** pandapower lines and impedances keep MATPOWER's from/to; a trafo's
  ``hv_bus`` is the higher-voltage end, which is MATPOWER's ``T_BUS`` for 16 case300 branches.
  When ``hv_bus`` equals our ``to_bus`` the oracle's from-side flow is ``p_lv_mw``.
* **Slack generation.** pandapower reports the slack balance on ``res_ext_grid`` (the first
  generator at the slack bus); ours follows MATPOWER's rule (whole balance on the first
  in-service slack-bus generator). The comparison is at bus level — generation summed per bus
  — so it does not depend on the per-generator split (and asserts the two rules agree anyway
  on the fixtures, where every slack bus carries exactly one generator).

Tolerances: 1e-9 deg on angles, 1e-9 MW on flows and injections (AC-3 "within 1e-9").
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.pf import solve_dc
from mambo_power.results import DcPowerFlowResult
from tests._fixtures import FIXTURES, FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy
from tests.parity.test_matpower_vs_pandapower import pandapower_from_raw

TOL_DEG = 1e-9
TOL_MW = 1e-9
SUBSTITUTE_KV = 1.0  # mirrors mambo_power.io.matpower.DEFAULT_BASE_KV

_CASE300 = FIXTURES_DIR / "case300.m"
CASES: list[Any] = list(FIXTURES)
if "case300" not in FIXTURES:
    CASES.append(
        pytest.param(
            "case300",
            marks=pytest.mark.skipif(not _CASE300.exists(), reason="case300.m not present"),
        )
    )


@dataclass
class Case:
    name: str
    raw: dict[str, Any]
    pp: Any
    ours: DcPowerFlowResult
    slack_id: str


def run_pandapower_dc(raw: dict[str, Any], substitute_kv: float = SUBSTITUTE_KV) -> Any:
    """pandapower net from the raw matrices (BASE_KV <= 0 patched), solved with ``rundcpp``."""
    import pandapower as pp

    patched = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    patched["bus"][patched["bus"][:, 9] <= 0, 9] = substitute_kv
    net = pandapower_from_raw(patched)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pp.rundcpp(net, numba=False, trafo_model="pi")
    return net


@pytest.fixture(scope="module", params=CASES)
def case(request: pytest.FixtureRequest) -> Case:
    path = FIXTURES_DIR / f"{request.param}.m"
    raw = read_mpc_numpy(path)
    net = matpower.load(path)
    slack_id = next(b.id for b in net.buses if b.type == "slack")
    return Case(request.param, raw, run_pandapower_dc(raw), solve_dc(net), slack_id)


def _pp_bus(bus_id: str) -> int:
    """pandapower bus index for one of our ids (``_adjust_ppc_indices`` -> BUS_I - 1)."""
    return int(bus_id.removeprefix("bus-")) - 1


# --- angles ------------------------------------------------------------------------------------


def oracle_angles_aligned(case: Case) -> dict[str, float]:
    va = case.pp.res_bus.va_degree
    offset = float(va.loc[_pp_bus(case.slack_id)])
    return {b.id: float(va.loc[_pp_bus(b.id)]) - offset for b in case.ours.buses}


def test_angles_match_rundcpp(case: Case) -> None:
    theirs = oracle_angles_aligned(case)
    assert len(theirs) == len(case.ours.buses) == len(case.pp.bus)
    diffs = {b.id: abs(b.va_deg - theirs[b.id]) for b in case.ours.buses}
    worst = max(diffs, key=diffs.__getitem__)
    assert diffs[worst] <= TOL_DEG, (case.name, worst, diffs[worst])
    ours_slack = next(b for b in case.ours.buses if b.id == case.slack_id)
    assert ours_slack.va_deg == 0.0
    assert max(abs(b.va_deg) for b in case.ours.buses) > 0.1  # a real, non-flat solution


# --- branch flows ------------------------------------------------------------------------------


def oracle_from_flows(case: Case) -> dict[str, float]:
    """pandapower from-side flow per branch id after orientation alignment."""
    pp = case.pp
    lookup = pp._from_ppc_lookups["branch"]
    flows: dict[str, float] = {}
    # branch ids are positional in the .m file: branch-k is row k (1-based), all in service
    for k, br in enumerate(case.ours.branches):
        assert br.id == f"branch-{k + 1}"
        et, el = lookup.element_type.iloc[k], int(lookup.element.iloc[k])
        f, t = _pp_bus(br.from_bus), _pp_bus(br.to_bus)
        if et == "line":
            assert (int(pp.line.at[el, "from_bus"]), int(pp.line.at[el, "to_bus"])) == (f, t)
            flows[br.id] = float(pp.res_line.at[el, "p_from_mw"])
        elif et == "impedance":
            row = pp.impedance.loc[el]
            assert (int(row.from_bus), int(row.to_bus)) == (f, t)
            flows[br.id] = float(pp.res_impedance.at[el, "p_from_mw"])
        else:
            hv, lv = int(pp.trafo.at[el, "hv_bus"]), int(pp.trafo.at[el, "lv_bus"])
            if (hv, lv) == (f, t):
                flows[br.id] = float(pp.res_trafo.at[el, "p_hv_mw"])
            else:
                assert (hv, lv) == (t, f)
                flows[br.id] = float(pp.res_trafo.at[el, "p_lv_mw"])
    return flows


def test_branch_flows_match_rundcpp(case: Case) -> None:
    theirs = oracle_from_flows(case)
    assert len(theirs) == len(case.ours.branches) == len(case.raw["branch"])
    diffs = {b.id: abs(b.p_from_mw - theirs[b.id]) for b in case.ours.branches}
    worst = max(diffs, key=diffs.__getitem__)
    assert diffs[worst] <= TOL_MW, (case.name, worst, diffs[worst])
    assert all(b.p_to_mw == -b.p_from_mw for b in case.ours.branches)


# --- bus injections and the slack balance --------------------------------------------------------


def oracle_bus_injection(case: Case) -> dict[str, float]:
    """Net MW injection per bus from pandapower's result tables (gens − loads − shunt GS)."""
    pp = case.pp
    inj: dict[int, float] = {int(i): 0.0 for i in pp.bus.index}
    for table, sign in (
        (pp.res_ext_grid.assign(bus=pp.ext_grid.bus), 1.0),
        (pp.res_gen.assign(bus=pp.gen.bus), 1.0),
        (pp.res_sgen.assign(bus=pp.sgen.bus), 1.0),
        (pp.res_load.assign(bus=pp.load.bus), -1.0),
        (pp.shunt, -1.0),  # DC uses GS at 1.0 pu: the input p_mw, not res_shunt (vm-scaled)
    ):
        for row in table.itertuples():
            inj[int(row.bus)] += sign * float(row.p_mw)
    return {b.id: float(inj[_pp_bus(b.id)]) for b in case.ours.buses}


def test_bus_injections_match_rundcpp(case: Case) -> None:
    theirs = oracle_bus_injection(case)
    diffs = {b.id: abs(b.p_mw - theirs[b.id]) for b in case.ours.buses}
    worst = max(diffs, key=diffs.__getitem__)
    assert diffs[worst] <= TOL_MW, (case.name, worst, diffs[worst])


def test_slack_generation_matches_ext_grid_at_bus_level(case: Case) -> None:
    pp = case.pp
    slack_idx = _pp_bus(case.slack_id)
    theirs = float(pp.res_ext_grid.p_mw[pp.ext_grid.bus == slack_idx].sum())
    theirs += float(pp.res_gen.p_mw[pp.gen.bus == slack_idx].sum())
    theirs += float(pp.res_sgen.p_mw[pp.sgen.bus == slack_idx].sum())
    ours = sum(g.p_mw for g in case.ours.generators if g.bus == case.slack_id)
    assert abs(ours - theirs) <= TOL_MW, (case.name, ours, theirs)
    # non-slack generators keep their dispatch in both engines
    dispatch = {f"gen-{k + 1}": float(row[1]) for k, row in enumerate(case.raw["gen"])}
    for g in case.ours.generators:
        if g.bus != case.slack_id:
            assert g.p_mw == pytest.approx(dispatch[g.id], abs=TOL_MW)


# --- the base-kV substitution is inert ----------------------------------------------------------


def test_oracle_is_invariant_to_the_base_kv_substitution() -> None:
    raw = read_mpc_numpy(FIXTURES_DIR / "case14.m")
    assert (raw["bus"][:, 9] <= 0).all()
    one = run_pandapower_dc(raw, substitute_kv=1.0)
    hundred = run_pandapower_dc(raw, substitute_kv=100.0)
    np.testing.assert_allclose(
        one.res_bus.va_degree.to_numpy(), hundred.res_bus.va_degree.to_numpy(), rtol=0, atol=1e-9
    )
    np.testing.assert_allclose(
        one.res_line.p_from_mw.to_numpy(), hundred.res_line.p_from_mw.to_numpy(), rtol=0, atol=1e-9
    )
