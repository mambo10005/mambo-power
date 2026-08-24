"""AC-1 (PyPSA secondary-oracle half): ``opf.solve_dc_opf`` agrees with PyPSA ``optimize`` on
every OPF fixture: case14, case_ieee30, case57, case118, case300 — within a tight band on 4/5
fixtures, and within a separately, honestly wider band on case300.

Promotes ``.bionic/tmp/m3-pypsa-diag-result.md``'s bounded diagnostic to a committed, repeatable
test — this file did not exist when the Step-5 audit refuted AC-1's status ("implemented and
proven") purely for lacking committed PyPSA evidence (``m3-audit.md`` §3/§5); everything below is
the diagnostic's own proven recipe, unchanged, now wired into pytest and re-measured fresh rather
than assumed from the diagnostic's own numbers.

**Root cause and fix (m3-pypsa-diag-result.md).** ``pypsa.Network.import_from_pypower_ppc``
populates ``n.generators.p_set`` from MATPOWER's raw base-case ``gen[:, PG]`` column, and
PyPSA's optimizer treats a non-null ``p_set`` as a *fixed-dispatch* constraint (pins the
decision variable exactly to that value) — not an initial guess. Since MATPOWER's raw base-case
dispatch does not itself balance (e.g. case14: ``sum(PG) = 272.4`` MW vs ``sum(load) = 259.0``
MW), every generator's degrees of freedom vanish and the nodal balance becomes infeasible. The
fix, confirmed on all 5 fixtures by the diagnostic and reproduced fresh here: clear the pin
(``n.generators["p_set"] = float("nan")``) before calling ``n.optimize()``.

**Cost bridge.** PyPSA's linear-cost import path does not read MATPOWER's ``gencost`` at all
(``import_from_pypower_ppc`` does not populate ``marginal_cost``/``marginal_cost_quadratic`` from
it); the diagnostic's own bridge is mirrored verbatim: ``gencost``'s columns 4/5 (``c2``/``c1``,
the same 0-indexed ``MODEL STARTUP SHUTDOWN NCOST c2 c1 c0`` layout ``dc_opf`` itself reads) go
straight into ``n.generators["marginal_cost_quadratic"]``/``n.generators["marginal_cost"]``.
Column 6 (``c0``, the constant term) is added to PyPSA's reported ``n.objective`` (which excludes
constants) for comparison against ``opf.dc_opf``'s ``objective_cost`` (which includes it,
``dc_opf.py``'s own ``+ np.sum(c0)`` — see ``test_opf_vs_pandapower.py``'s identical convention);
in practice every one of the 5 OPF fixtures' ``gencost`` has ``c0 == 0`` on every generator
(checked directly, not assumed), so this term is a no-op here but kept for correctness and to
match the diagnostic's own approach rather than silently dropping it.

**Branch ratings.** ``overwrite_zero_s_nom=9999.0`` (the diagnostic's own value) makes every
branch's PyPSA thermal limit effectively unconstrained — matching ``test_opf_vs_pandapower.py``'s
own confirmed fact that no OPF fixture rates a branch (``record/m3-research.md`` §6), so neither
oracle's flow-limit rows can be the source of any dispatch difference here.

**Tolerance policy.** Measured fresh against this exact test (not assumed from the diagnostic's
own printed numbers, though they land in the same range): case14/case_ieee30/case57/case118's
worst relative cost residual is ``1.27e-12`` (case118) and worst absolute dispatch residual is
``1.87e-03`` MW (case118) — ``TIGHT_COST_REL_TOL``/``TIGHT_DISPATCH_ABS_TOL_MW`` below are pinned
with margin above both. case300 does not fit that band — its residual is a real, separate
``7.37e-05`` relative cost gap (~0.0074%) and ``0.082`` MW worst dispatch gap.

**case300's root cause, closed (m3-critic.md Issue 1, re-verified here).** case300 is the only
one of the 5 OPF fixtures with nonzero MATPOWER bus ``GS`` (shunt conductance): 17 buses summing
to exactly 1.3 MW (checked directly against the fixture's raw ``bus`` matrix, column 5). This
module's own balance row correctly includes it (``Σ p_g == Σ p_load + Σ g_shunt``,
``opf/dc_opf.py``'s own derivation) — ``solve_dc_opf``'s total case300 dispatch, 23527.15 MW,
matches the fixture's true load-plus-shunt total exactly. PyPSA's ``import_from_pypower_ppc``/
DC-LOPF silently drops bus shunt conductance from its own power balance: its total case300
dispatch, 23525.85 MW, equals only the raw ``PD`` (load) column with zero ``GS`` contribution
(``n.loads["p_set"].sum() == raw bus PD sum``, checked directly). The gap between the two totals
is exactly 1.3 MW, redistributed thinly across 68 of case300's 69 generators by the QP's
marginal-cost weighting — not a bus-numbering/index-alignment artifact, which would produce a
handful of large, lumpy per-generator discrepancies without changing either dispatch total.
``dc_opf`` is provably *more* complete than this oracle on this one point, not less; nothing in
``dc_opf`` needs to change. ``WIDE_COST_REL_TOL``/``WIDE_DISPATCH_ABS_TOL_MW`` cover case300
alone, pinned with margin above what is actually measured, so a case300-specific regression would
still be caught. A future PyPSA-oracle fixture with nonzero bus shunts will need this same
accounting, not a wider tolerance band.
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

OVERWRITE_ZERO_S_NOM = 9999.0

TIGHT_CASES = ["case14", "case_ieee30", "case57", "case118"]
WIDE_CASES = ["case300"]
CASES = TIGHT_CASES + WIDE_CASES

TIGHT_COST_REL_TOL = 1e-9
"""Margin over the measured worst tight-band relative cost residual, 1.27e-12 (case118)."""
TIGHT_DISPATCH_ABS_TOL_MW = 0.01
"""Margin over the measured worst tight-band absolute per-generator dispatch residual, 1.87e-03
MW (case118)."""

WIDE_COST_REL_TOL = 2e-4
"""case300 only — margin over the measured 7.37e-05 (~0.0074%) relative cost residual, matching
the diagnostic's own ~0.007% finding; named, not chased further."""
WIDE_DISPATCH_ABS_TOL_MW = 0.5
"""case300 only — margin over the measured worst absolute per-generator dispatch residual,
0.082 MW; the QP re-optimizes around the cost gap above, so individual generators can
redistribute more than the cost gap alone would suggest."""


@dataclass
class Case:
    name: str
    pypsa_obj: float
    pypsa_dispatch: np.ndarray
    pypsa_status: str
    pypsa_cond: str
    ours: OpfDcResult


def run_pypsa_dcopf(raw: dict[str, Any]) -> Any:
    """PyPSA network from the raw matrices, solved with ``optimize`` (the diagnostic's recipe)."""
    import pypsa

    patched = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    patched["bus"][patched["bus"][:, 9] <= 0, 9] = 1.0
    ppc = {
        "version": "2",
        "baseMVA": patched["baseMVA"],
        "bus": patched["bus"],
        "gen": patched["gen"],
        "branch": patched["branch"],
    }
    n = pypsa.Network()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n.import_from_pypower_ppc(ppc, overwrite_zero_s_nom=OVERWRITE_ZERO_S_NOM)

    gencost = patched["gencost"]
    n.generators["marginal_cost_quadratic"] = gencost[:, 4]
    n.generators["marginal_cost"] = gencost[:, 5]
    c0_sum = float(np.sum(gencost[:, 6]))

    # the root-caused fix: import_from_pypower_ppc pins p_set to MATPOWER's unbalanced base-case
    # PG, which optimize() treats as a fixed-dispatch constraint, not a starting guess.
    n.generators["p_set"] = float("nan")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        status, cond = n.optimize(solver_name="highs")
    return n, status, cond, c0_sum


@pytest.fixture(scope="module", params=CASES)
def case(request: pytest.FixtureRequest) -> Case:
    path = FIXTURES_DIR / f"{request.param}.m"
    raw = read_mpc_numpy(path)
    n, status, cond, c0_sum = run_pypsa_dcopf(raw)
    obj = float(n.objective) + c0_sum if n.objective is not None else float("nan")
    dispatch = (
        n.generators_t.p.iloc[0].to_numpy()
        if status == "ok"
        else np.full(len(n.generators), np.nan)
    )

    net = matpower.load(path)
    ours = solve_dc_opf(net)
    return Case(request.param, obj, dispatch, status, cond, ours)


def test_solve_dc_opf_converges_optimal(case: Case) -> None:
    assert case.ours.status == "Optimal", (case.name, case.ours.message)


def test_pypsa_itself_converges_optimal(case: Case) -> None:
    """Sanity check on the oracle: the fix must actually make PyPSA solve, not just avoid a
    crash — a status other than ok/optimal would make every comparison below meaningless."""
    assert (case.pypsa_status, case.pypsa_cond) == ("ok", "optimal"), case.name


def _tolerances(name: str) -> tuple[float, float]:
    if name in WIDE_CASES:
        return WIDE_COST_REL_TOL, WIDE_DISPATCH_ABS_TOL_MW
    return TIGHT_COST_REL_TOL, TIGHT_DISPATCH_ABS_TOL_MW


def test_objective_cost_matches_pypsa(case: Case) -> None:
    cost_tol, _ = _tolerances(case.name)
    ours_cost = case.ours.objective_cost
    rel = abs(ours_cost - case.pypsa_obj) / abs(case.pypsa_obj)
    assert rel <= cost_tol, (case.name, ours_cost, case.pypsa_obj, rel)


def test_dispatch_matches_pypsa(case: Case) -> None:
    _, dispatch_tol = _tolerances(case.name)
    # PyPSA generator names ("G0", "G1", ...) are positional in MATPOWER gen-row order — the
    # same order our generator ids ("gen-{k+1}") preserve (test_opf_vs_pandapower.py's own
    # convention, reused verbatim here).
    ours = np.zeros(len(case.pypsa_dispatch))
    by_id = {g.id: g.p_mw for g in case.ours.generators}
    for k in range(len(case.pypsa_dispatch)):
        ours[k] = by_id[f"gen-{k + 1}"]
    diffs = np.abs(ours - case.pypsa_dispatch)
    worst = int(np.argmax(diffs))
    detail = (case.name, worst, diffs[worst], ours[worst], case.pypsa_dispatch[worst])
    assert diffs[worst] <= dispatch_tol, detail
