"""AC-6: ``market.nodal.solve_nodal`` agrees with pandapower's ``sgen``-framed elastic-demand
``rundcopp`` oracle, on case14 with every load's bid derived by ``tests/_bids.py``.

**The ``sgen`` oracle-construction convention (spec Design item 7; wave M4 W6), permanent from
this wave on** -- one more entry in the "oracle-construction discipline" this repo's parity
tests already maintain, alongside ``BASE_KV<=0 -> 1.0`` and ``trafo_model="pi"``
(``tests/parity/test_opf_vs_pandapower.py``): a flexible load is modelled as a **negative-sign,
negative-bound** ``sgen`` (not as a ``controllable=True`` ``load`` row with its own
``poly_cost``), with a **sign-flip transformation** applied to the bid curve --
``cost_sgen(p) = -value(-p)``. For our quadratic bid ``value(d) = v1*d + v2*d**2`` this expands
to ``cost_sgen(p) = v1*p - v2*p**2``, so ``pp.create_poly_cost``'s ``cp1_eur_per_mw = v1`` and
``cp2_eur_per_mw2 = -v2`` (``v2 <= 0`` for a concave bid, so ``-v2 >= 0`` -- a convex sgen cost,
as ``poly_cost``'s own QP Hessian requires). The load's own aggregate row in ``net.load`` is
dropped entirely (not zeroed) before the matching ``sgen`` is added, so pandapower's own balance
equation carries exactly one representation of that bus's demand, the same "no double-counting"
contract ``opf.dc_opf``'s own module docstring documents for our side of this parity.

**Why ``sgen``, not the more "natural"-looking ``load`` row (spec Assumption b)**: pandapower's
``create_poly_cost`` genuinely accepts ``"load"`` as an element type, and a **linear**-only load
cost converges correctly via that path -- but a **quadratic** (concave-value, the economically
interesting case; a flat/linear bid is really just a step function) ``load``-row cost
reproducibly fails to converge in ``rundcopp`` (``pandapower.auxiliary.OPFNotConverged``,
reproduced twice independently in this wave's research with two different network shapes --
record/m4-research.md §3.1), even though the economically identical ``sgen`` framing converges
instantly to the same answer a hand KKT solve gives. Root cause not diagnosed (candidate:
pandapower's internal ``dcopf`` may assume ``cp2 >= 0`` represents a *convex generation* cost and
mis-handle the sign when the element is internally a negative-generation "load" row -- research
§3.1, ``unverified`` beyond "it reproducibly fails"). This is a real, reproduced pandapower
limitation worth naming here precisely, per spec Assumption (b), so a future pandapower upgrade
or a curious reader doesn't have to rediscover it via ``git log -S``; this wave routes around it
via ``sgen`` rather than root-causing it (spec "Not Doing").

**Fixture and tolerance**: case14 (module docstring "at least one real multi-bus fixture"),
every one of its 11 loads bid via ``tests/_bids.with_bids`` (VOLL=10,000 $/MWh, linear marginal
value descending to the fleet's own max marginal cost -- ``tests/_bids.py``'s own module
docstring). By that anchor rule's own mathematical consequence (documented there), every load on
this fixture ends up fully price-taking (dispatched at its own committed ``p_mw``) -- this test
still proves genuine oracle parity on the *quadratic* elastic-demand QP path (``dc_opf``'s
Hessian sign-flip for a nonzero ``v2``), a code path AC-5's own price-taker test does not
exercise (its bid is purely linear, ``v2=0``, an LP not a QP). Tolerances below are measured
directly (worst case across all 11 loads, ``<scratchpad>/probe_bid_oracle_all.py``: dispatch
7.14e-10 MW, LMP 1.94e-5 $/MWh) and pinned a comfortable margin above, per this wave's own AC-6
and the repo's established parity-tolerance discipline (measure and record, don't assume a round
number).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.market.nodal import MarketNodalOptions, solve_nodal
from mambo_power.model import Scenario
from mambo_power.results import MarketNodalResult
from tests._bids import with_bids
from tests._fixtures import FIXTURES_DIR
from tests.parity._mpc_reader import read_mpc_numpy
from tests.parity.test_matpower_vs_pandapower import pandapower_from_raw

DISPATCH_ABS_TOL_MW = 1e-6
"""Margin over the measured worst absolute per-load dispatch residual, 7.14e-10 MW."""
LMP_ABS_TOL = 1e-3
"""Margin over the measured worst absolute per-bus LMP residual, 1.94e-5 $/MWh."""

CASE = "case14"


@dataclass
class Case:
    ours: MarketNodalResult
    pp: Any
    sgen_bus: dict[str, int]
    """load id -> the sgen's pandapower bus index, for looking up ``res_bus.lam_p``."""
    sgen_idx: dict[str, int]
    """load id -> the sgen's pandapower row index, for looking up ``res_sgen.p_mw``."""


def _build_sgen_oracle(
    raw: dict[str, Any], bid_net: Any
) -> tuple[Any, dict[str, int], dict[str, int]]:
    """A pandapower net from ``raw`` (``BASE_KV<=0`` patched) with every one of ``bid_net``'s
    bid loads replaced by a sign-flipped ``sgen`` (module docstring)."""
    import pandapower as pp

    patched = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in raw.items()}
    patched["bus"][patched["bus"][:, 9] <= 0, 9] = 1.0
    net_pp = pandapower_from_raw(patched)

    bid_loads = [ld for ld in bid_net.loads if ld.bid is not None]
    assert bid_loads, "test fixture must actually attach bids, or this parity test proves nothing"

    # every raw bus row's position equals its pandapower internal bus index (_adjust_ppc_indices
    # relabels bus numbers but preserves row order) -- match a load id ("load-<bus_i>", io.matpower
    # docstring) back to its row position via the raw matrix directly, not any pandapower-side id.
    sgen_bus: dict[str, int] = {}
    for ld in bid_loads:
        bus_i = int(ld.id.split("-")[1])
        sgen_bus[ld.id] = int(np.where(raw["bus"][:, 0] == bus_i)[0][0])

    net_pp.load = net_pp.load.drop(index=list(net_pp.load.index)).reset_index(drop=True)
    sgen_idx: dict[str, int] = {}
    for ld in bid_loads:
        assert ld.bid is not None
        v2, v1, _v0 = ld.bid.coefficients
        bus_pp = sgen_bus[ld.id]
        idx = pp.create_sgen(
            net_pp, bus_pp, p_mw=-ld.p_mw / 2, min_p_mw=-ld.p_mw, max_p_mw=0.0, controllable=True
        )
        pp.create_poly_cost(net_pp, idx, "sgen", cp1_eur_per_mw=v1, cp2_eur_per_mw2=-v2)
        sgen_idx[ld.id] = idx

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pp.rundcopp(net_pp, trafo_model="pi")
    return net_pp, sgen_bus, sgen_idx


@pytest.fixture(scope="module")
def case() -> Case:
    path = FIXTURES_DIR / f"{CASE}.m"
    raw = read_mpc_numpy(path)
    net = matpower.load(path)
    bid_net = with_bids(net)  # every load, tests/_bids.py's own module docstring
    ours = solve_nodal(Scenario(network=bid_net), MarketNodalOptions())
    pp_net, sgen_bus, sgen_idx = _build_sgen_oracle(raw, bid_net)
    return Case(ours=ours, pp=pp_net, sgen_bus=sgen_bus, sgen_idx=sgen_idx)


def test_solve_nodal_converges_optimal(case: Case) -> None:
    assert case.ours.status == "Optimal", case.ours.message


def test_dispatch_matches_the_sgen_oracle_on_every_bid_load(case: Case) -> None:
    ours_by_id = {ld.id: ld.p_mw for ld in case.ours.loads}
    worst = 0.0
    detail: tuple[str, float, float] | None = None
    for load_id, idx in case.sgen_idx.items():
        pp_p_mw = -float(case.pp.res_sgen.at[idx, "p_mw"])  # sign-flip back to a load quantity
        diff = abs(ours_by_id[load_id] - pp_p_mw)
        if diff >= worst:
            worst, detail = diff, (load_id, ours_by_id[load_id], pp_p_mw)
    assert worst <= DISPATCH_ABS_TOL_MW, detail


def test_lmp_matches_the_sgen_oracle_on_every_bid_load_s_bus(case: Case) -> None:
    lmp_by_bus = {b.id: b.lmp for b in case.ours.buses}
    by_load_id = {ld.id: ld.bus for ld in case.ours.loads}
    worst = 0.0
    detail: tuple[str, float, float] | None = None
    for load_id, bus_pp in case.sgen_bus.items():
        ours_lmp = lmp_by_bus[by_load_id[load_id]]
        pp_lmp = float(case.pp.res_bus.at[bus_pp, "lam_p"])
        diff = abs(ours_lmp - pp_lmp)
        if diff >= worst:
            worst, detail = diff, (load_id, ours_lmp, pp_lmp)
    assert worst <= LMP_ABS_TOL, detail


def test_every_bid_load_is_fully_price_taking_on_this_fixture(case: Case) -> None:
    """The mathematical consequence tests/_bids.py's own module docstring documents: this
    anchor rule's low end upper-bounds the achievable market price, so every derived bid is
    dispatched at its own full p_mw on this fixture -- confirmed against both engines, not just
    ours."""
    ours_by_id = {ld.id: ld.p_mw for ld in case.ours.loads if ld.id in case.sgen_idx}
    net = matpower.load(FIXTURES_DIR / f"{CASE}.m")
    p_mw_by_id = {ld.id: ld.p_mw for ld in net.loads}
    for load_id, p_mw in ours_by_id.items():
        assert p_mw == pytest.approx(p_mw_by_id[load_id], abs=1e-6)
