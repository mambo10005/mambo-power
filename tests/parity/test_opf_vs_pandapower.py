"""AC-1 (parity half): ``opf.solve_dc_opf`` agrees with pandapower ``rundcopp`` on every OPF
fixture: case14, case_ieee30, case57, case118, case300.

Oracle path: the same construction ``tests/parity/test_dc_vs_pandapower.py`` already uses for
the DC power-flow oracle (independent ``.m`` read via ``_mpc_reader``, the ``BASE_KV<=0 -> 1.0``
patch, ``pandapower_from_raw`` with ``trafo_model="pi"``), run through ``pp.rundcopp`` instead
of ``pp.rundcpp``. ``pandapower_from_raw``/``_from_ppc_gencost`` map MATPOWER's raw ``gencost``
coefficients straight into pandapower's ``poly_cost`` table (``cp2_eur_per_mw2 = c2`` etc., the
same unscaled ``cost(p) = c2·p² + c1·p + c0`` convention MATPOWER's own gencost uses), so this is
a genuine cost-including OPF oracle, not merely a DC power flow relabelled.

**A real formulation difference, measured and found immaterial on these fixtures, not
assumed.** pandapower's OPF marks the slack-bus generator (``ext_grid``) ``controllable=False``:
its dispatch is the network's power-balance residual (a full nodal, theta-based DC-OPF — every
bus's balance is enforced individually, not just the system-wide sum), not a bounded decision
variable, even though its real cost coefficients are still charged against the reported total
cost. ``opf.dc_opf`` builds a different, PTDF-based formulation (design item 1): a single
system-wide balance row, every generator — including the one at the slack bus — a normal
decision variable bounded by its own ``[p_min, p_max]``. These two formulations are only
guaranteed to agree when (a) no branch is rated (so ``dc_opf``'s per-branch flow-limit rows
never bind — confirmed true of all 5 fixtures, ``record/m3-research.md`` §6) and (b) the
slack-bus generator's own bounds never happen to bind in the oracle's unconstrained-by-bound
dispatch. Measured directly against all 5 fixtures below (not assumed): both hold, and the two
solvers' independent LP/QP paths agree to within double-precision-adjacent tolerances (worst
measured: cost 1.6e-11 relative, dispatch 0.0142 MW absolute on case300's 69 generators). The
tolerances below are pinned a comfortable margin above what was actually measured, per the
wave's own AC-1 discipline (measure and record, don't assume a round number) — not proof the
two formulations are equivalent in general, only that they coincide on this exact fixture set.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.opf import solve_dc_opf
from mambo_power.results import OpfDcResult
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy
from tests.parity.test_matpower_vs_pandapower import pandapower_from_raw

COST_REL_TOL = 1e-7
"""Margin over the measured worst relative cost residual, 1.6e-11 (case_ieee30)."""
DISPATCH_ABS_TOL_MW = 0.05
"""Margin over the measured worst absolute per-generator dispatch residual, 0.0142 MW (case300)."""

CASES = ["case14", "case_ieee30", "case57", "case118", "case300"]


@dataclass
class Case:
    name: str
    pp: Any
    ours: OpfDcResult


def run_pandapower_dcopp(raw: dict[str, Any]) -> Any:
    """pandapower net from the raw matrices (BASE_KV <= 0 patched), solved with ``rundcopp``."""
    import pandapower as pp

    patched = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    patched["bus"][patched["bus"][:, 9] <= 0, 9] = 1.0
    net = pandapower_from_raw(patched)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pp.rundcopp(net, trafo_model="pi")
    return net


@pytest.fixture(scope="module", params=CASES)
def case(request: pytest.FixtureRequest) -> Case:
    path = FIXTURES_DIR / f"{request.param}.m"
    raw = read_mpc_numpy(path)
    pp_net = run_pandapower_dcopp(raw)
    net = matpower.load(path)
    ours = solve_dc_opf(net)
    return Case(request.param, pp_net, ours)


def _pp_dispatch_by_gen_lookup_order(pp_net: Any) -> np.ndarray:
    """pandapower dispatch, MATPOWER ``gen`` row order (``_from_ppc_lookups["gen"]``)."""
    lookup = pp_net._from_ppc_lookups["gen"]
    dispatch = np.zeros(len(lookup))
    for i, row in lookup.iterrows():
        table = pp_net.res_gen if row.element_type == "gen" else pp_net.res_ext_grid
        dispatch[i] = table.at[row.element, "p_mw"]
    return dispatch


def test_solve_dc_opf_converges_optimal(case: Case) -> None:
    assert case.ours.status == "Optimal", (case.name, case.ours.message)


def test_objective_cost_matches_rundcopp(case: Case) -> None:
    pp_cost = float(case.pp.res_cost)
    ours_cost = case.ours.objective_cost
    rel = abs(ours_cost - pp_cost) / abs(pp_cost)
    assert rel <= COST_REL_TOL, (case.name, ours_cost, pp_cost, rel)


def test_dispatch_matches_rundcopp(case: Case) -> None:
    theirs = _pp_dispatch_by_gen_lookup_order(case.pp)
    # our generator ids are "gen-{k+1}", 1-based positional in the .m file's gen block —
    # exactly the MATPOWER gen-row order _from_ppc_lookups["gen"] also preserves.
    ours = np.zeros(len(theirs))
    by_id = {g.id: g.p_mw for g in case.ours.generators}
    for k in range(len(theirs)):
        ours[k] = by_id[f"gen-{k + 1}"]
    diffs = np.abs(ours - theirs)
    worst = int(np.argmax(diffs))
    detail = (case.name, worst, diffs[worst], ours[worst], theirs[worst])
    assert diffs[worst] <= DISPATCH_ABS_TOL_MW, detail


def test_every_branch_is_unconstrained_so_no_flow_limit_dual_binds(case: Case) -> None:
    """Confirms the module docstring's load-bearing assumption (a): no fixture rates a branch,
    so opf.dc_opf's per-branch flow-limit rows can never be the source of any dispatch
    difference from the oracle's own (differently-shaped) formulation."""
    assert all(b.flow_limit_dual == 0.0 for b in case.ours.branches)
