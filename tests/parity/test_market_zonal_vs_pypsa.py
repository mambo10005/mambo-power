"""AC-6: the zonal clearing stage matches a PyPSA oracle built as **one bus per zone joined by
``Link``s carrying the corridor caps** -- spec ``## Design`` A1, the wave's one at-risk assumption,
settled here as an *exact* LP equivalence rather than a tolerance-band agreement.

**What A1 was at risk about.** ``record/m6-research.md`` §5 probed a different oracle shape: the
full nodal network with every *intra-zone* line's ``s_nom`` set effectively unconstrained and only
the tie lines rated. That probe answers "can PyPSA express something zonal-ish at all", and it is
not the LP :func:`~mambo_power.opf.zonal.zonal_dc_opf` builds. Two differences, both structural:

* that shape keeps PyPSA's **linearised power flow** over the whole network, so inter-zone transfer
  still splits across the tie lines by reactance (KVL) and each tie line is capped
  *individually*; the engine's corridor is one free variable capped by the **sum** of its cut-set's
  ratings (``tests/_zones.py``'s :func:`~tests._zones.corridors`), which no reactance-constrained
  model can reproduce;
* that shape keeps every intra-zone bus as a real balance row, so intra-zone topology still shapes
  the answer; the engine's zone is a copper plate with exactly one row.

So the probe's form could not have settled A1 either way. This module builds the form A1 actually
names, and the reason it works is worth stating as algebra rather than as a measurement.

**Why ``Link`` and not ``Line`` -- the exact-equivalence argument.** A PyPSA ``Line`` carries a
reactance and enters the linearised-power-flow (KVL) constraints; on a 3-zone network with 3
corridors that closes a loop, and the loop equation would pin the flow split by reactance -- a
constraint the engine's LP has no counterpart for, and one no choice of "unit reactance" removes
(a unit reactance is still *a* reactance). A ``Link`` is instead a *controllable transport*
element: PyPSA constrains it only by ``p_min_pu * p_nom <= p0 <= p_max_pu * p_nom`` and enters
``p0`` in ``bus0``'s nodal balance with ``-1`` and ``p1 = -efficiency * p0`` in ``bus1``'s. With
``p_nom = cap``, ``p_min_pu = -1``, ``p_max_pu = +1`` and ``efficiency = 1`` that is, column for
column, the engine's own corridor variable: bounds ``[-cap, +cap]``, coefficient ``-1`` in ``z1``'s
balance row and ``+1`` in ``z2``'s (``opf/zonal.py``, "Corridor sign convention"). The two LPs are
therefore *the same LP*, and the agreement below is exact to solver round-off -- the objective is
bit-identical on both fixed-load cases -- not a band that had to be argued for.

**Why the oracle is hand-built rather than imported.** ``import_from_pypower_ppc`` (the bridge
``tests/parity/test_opf_vs_pypsa.py`` and ``test_market_multiperiod_vs_pypsa.py`` both use) imports
a MATPOWER case as a nodal network; the zone-aggregated network has no MATPOWER counterpart -- 3
or 4 buses and no branches at all. Building it directly from the raw matrices also removes that
importer's own known gap: it silently drops the bus shunt-conductance column ``GS`` from its power
balance, which is the entire root cause of ``test_opf_vs_pypsa.py``'s separate, wider case300 band
(1.3 MW spread thinly over 68 generators). Here the per-zone fixed load is ``sum(PD) + sum(GS)``
over that zone's own buses -- exactly what the engine's balance row uses -- so **case300 lands in
the same tight band as case30** instead of needing a band of its own. The gencost bridge (columns
4/5 into ``marginal_cost_quadratic``/``marginal_cost``, column 6's ``c0`` added back to
``n.objective``, which excludes constants) is ``test_opf_vs_pypsa.py``'s own, unchanged. The
``p_set`` fix that module root-caused does not arise: nothing here is imported, so no generator is
ever pinned in the first place.

**The partition and the caps are handed to PyPSA independently of the engine** (AC-6's own wording,
and ``continuation-m5.md``'s A34 lesson). Both come from ``tests/_zones.py`` --
:func:`~tests._zones.zone_of_bus` and :func:`~tests._zones.corridors`, over a
``tests/_rated.py``-rated, ``promote_areas_to_zones``-promoted network -- and are passed to the two
sides *separately*; nothing this module reads from :class:`~mambo_power.opf.zonal.ZonalSolution`
feeds the oracle. That makes an engine-side fault (a flipped corridor sign, a dropped bound, a
relabelled zone) visible, and it deliberately does **not** make a fault in the shared derivation
visible -- which is a property, not a gap, and
:func:`test_transposing_the_shared_caps_is_not_a_sabotage` commits the demonstration.

**What is compared, and against what.** ``market.zonal``'s *zonal stage* is
:func:`~mambo_power.opf.zonal.zonal_dc_opf` itself -- ``market.solve_zonal`` chains it with
redispatch and a nodal reference, neither of which this comparison is about, and the corridor flows
and capacity prices AC-6 names live on ``ZonalSolution``. Comparing at the array level also puts
the comparison directly on the rows and columns an engine-side sabotage would corrupt.

PyPSA declines to write back the shadow prices of a ``Link``'s own ``p`` bounds (it says so:
"the shadow-prices of the constraints Link-fix-p-lower, Link-fix-p-upper were not assigned"), so
``mu_upper``/``mu_lower`` come back empty. The oracle-side corridor capacity price is therefore
taken as ``|price(z1) - price(z2)|`` from PyPSA's **own** bus marginal prices, which is that price
by construction rather than by assumption: a costless link's reduced cost is exactly the negated
price difference across it (``opf/zonal.py``'s :func:`~mambo_power.opf.zonal._corridor_cap_price`
derives the same identity from the other side), so a binding corridor's capacity is worth precisely
the spread it sustains. It is still oracle-side data -- PyPSA's duals, not the engine's.

**Tolerances: measured first, then pinned with margin** (the M5 discipline). Worst residual over
all four fixture/bid combinations, measured against this module's own oracle:

===========================  ==============  ===============  ==========
quantity                     worst measured  pinned           margin
===========================  ==============  ===============  ==========
objective (relative)         1.67e-15        1e-9             ~6e5x
generator dispatch           1.59e-12 MW     1e-6 MW          ~6e5x
elastic demand dispatch      2.27e-13 MW     1e-6 MW          ~4e6x
zone price                   7.11e-15 $/MWh  1e-6 $/MWh       ~1e8x
corridor flow                2.64e-12 MW     1e-6 MW          ~4e5x
corridor capacity price      1.31e-05 $/MWh  1e-3 $/MWh       ~76x
===========================  ==============  ===============  ==========

Every band except the last sits at machine precision because the two LPs are identical; they are
pinned four orders *tighter* than this repository's usual parity bands (``1e-2`` MW) precisely
because there is no modelling gap left to absorb, while still holding five-plus orders of margin
against the platform drift wave M5 met on macOS CI (spec A3). The corridor capacity price is the
one genuinely looser band, and its looseness is the solver's dual precision, not a model
difference: HiGHS reports a primal-dual objective error around ``1e-6`` on these QPs, and both
sides read duals off it. 1e-3 keeps ~76x over what is measured and stays two orders below the
smallest real signal any sabotage produces here (0.12 $/MWh).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from mambo_power.io import matpower
from mambo_power.market.nodal import load_bid_coeffs
from mambo_power.model import Network
from mambo_power.numerics.arrays import NetworkArrays
from mambo_power.opf import gen_cost_coeffs
from mambo_power.opf.zonal import ZonalSolution, ZoneKey, zonal_dc_opf
from tests._bids import with_bids
from tests._fixtures import FIXTURES_DIR
from tests._rated import rated_network
from tests._zones import corridors, promote_areas_to_zones, zone_of_bus
from tests.parity._mpc_reader import read_mpc_numpy

OBJ_REL_TOL = 1e-9
"""Margin over the measured worst relative objective residual, 1.67e-15 (case30, elastic)."""
GEN_DISPATCH_ABS_TOL_MW = 1e-6
"""Margin over the measured worst per-generator dispatch residual, 1.59e-12 MW (case300)."""
DEMAND_DISPATCH_ABS_TOL_MW = 1e-6
"""Margin over the measured worst per-elastic-load dispatch residual, 2.27e-13 MW (case300)."""
ZONE_PRICE_ABS_TOL = 1e-6
"""Margin over the measured worst per-zone price residual, 7.11e-15 $/MWh (case300)."""
CORRIDOR_FLOW_ABS_TOL_MW = 1e-6
"""Margin over the measured worst per-corridor flow residual, 2.64e-12 MW (case300)."""
CORRIDOR_PRICE_ABS_TOL = 1e-3
"""Margin over the measured worst per-corridor capacity-price residual, 1.31e-05 $/MWh (case300).

The one band not at machine precision, and deliberately so (module docstring): it carries the
solver's own dual precision on a QP whose primal-dual objective error is itself ~1e-6, not a
difference between the two models. Still two orders below the smallest signal any sabotage in the
S6 sweep produced (0.12 $/MWh)."""

BINDING_RATIO = 1.0 - 1e-9
"""``|flow| / cap`` above which a corridor counts as at its bound
(:func:`test_case30_corridor_structure_binds_two_of_three`). Measured on case30: the two binding
corridors sit at exactly 1.0 and the slack one at 0.9265, so nothing lands near this threshold."""
DISTINCT_PRICE_MIN = 1e-3
"""Two zone prices count as distinct when they differ by more than this. Measured on case30:
zones 1 and 3 agree to 1.5e-6 $/MWh (tied by a slack corridor) while zone 2 stands 0.121 $/MWh
apart -- two orders clear on either side of this threshold
(:func:`test_case30_prices_separate_into_exactly_two_levels`)."""

CASES = ["case30", "case300"]
"""``case30`` carries the AREA-promoted 3-zone partition (11/10/9 buses) whose corridors actually
bind; ``case300`` carries four importer-real zones (122/80/63/35) and solves in well under a
second, so both are in rather than case30 alone."""


# --- fixture construction: partition and caps from tests/_zones.py, once, for both sides ---------


@dataclass(frozen=True)
class ZonalFixture:
    """Everything both sides are handed, derived only from committed fixture data plus
    ``tests/_rated.py`` and ``tests/_zones.py`` -- never from a solve."""

    case: str
    net: Network
    zone_of: dict[str, str]
    caps: dict[ZoneKey, float]
    elastic_ids: list[str]


def _largest_load_per_zone(net: Network, zone_of: dict[str, str]) -> list[str]:
    """One load id per zone -- that zone's largest. Chosen so every zone has an elastic column,
    which is what makes a zone price a *marginal-value* price there rather than a pure
    supply-side one."""
    best: dict[str, tuple[float, str]] = {}
    for load in net.loads:
        zone = zone_of[load.bus]
        if load.p_mw > best.get(zone, (0.0, ""))[0]:
            best[zone] = (load.p_mw, load.id)
    return sorted(load_id for _, load_id in best.values())


def build_fixture(case: str, *, elastic: bool) -> ZonalFixture:
    """Rated (``tests/_rated.py``) + zone-promoted (``tests/_zones.py``) ``case``, optionally with
    interior-clearing bids (``tests/_bids.py``) on the largest load of each zone.

    ``interior_bid_for_load`` rather than ``bid_for_load``: the latter's fleet-ceiling anchor is
    price-taking by construction, so every bid load would sit pinned at its own upper bound and the
    demand comparison could not distinguish a correct solve from a double-counted one (that
    module's own docstring, M4 critic Issue 1). :func:`test_elastic_loads_clear_strictly_inside`
    asserts the interior clearing actually happened rather than trusting the anchor rule.
    """
    net = promote_areas_to_zones(rated_network(matpower.load(FIXTURES_DIR / f"{case}.m")))
    zone_of = zone_of_bus(net)
    caps = corridors(net)
    elastic_ids: list[str] = []
    if elastic:
        elastic_ids = _largest_load_per_zone(net, zone_of)
        net = with_bids(net, elastic_ids, interior_load_ids=elastic_ids)
    return ZonalFixture(case, net, zone_of, caps, elastic_ids)


def run_engine(fix: ZonalFixture) -> tuple[NetworkArrays, ZonalSolution, list[int]]:
    """``opf.zonal.zonal_dc_opf`` on ``fix``, plus the elastic load-index order
    ``demand_dispatch_mw`` is in."""
    arr = NetworkArrays.from_network(fix.net)
    cost_coeffs, pwl_costs = gen_cost_coeffs(fix.net, arr)
    bid_coeffs, pwl_bids = load_bid_coeffs(fix.net, arr)
    sol = zonal_dc_opf(
        arr,
        cost_coeffs,
        fix.zone_of,
        fix.caps,
        pwl_costs=pwl_costs or None,
        demand_bid_coeffs=bid_coeffs or None,
        demand_pwl_bids=pwl_bids or None,
    )
    return arr, sol, sorted(set(bid_coeffs) | set(pwl_bids))


# --- the oracle: one Bus per zone, one Link per corridor ----------------------------------------


def run_pypsa_zonal_oracle(fix: ZonalFixture) -> tuple[Any, str, str, float]:
    """One PyPSA ``Bus`` per zone, every generator and load attached to its own zone's bus, one
    bidirectional ``Link`` per corridor at ``p_nom = cap`` (module docstring on why ``Link``).

    Reads the raw MATPOWER matrices for generator bounds and costs and for the ``GS`` column, and
    ``fix.net``'s own ``Load``/``Load.bid`` rows for the demand side -- all fixture data. The
    partition and the caps come in through ``fix``, i.e. from ``tests/_zones.py``, never from a
    :class:`~mambo_power.opf.zonal.ZonalSolution`.
    """
    import pypsa

    raw = read_mpc_numpy(FIXTURES_DIR / f"{fix.case}.m")
    bus, gen, gencost = raw["bus"], raw["gen"], raw["gencost"]
    zone_ids = sorted(set(fix.zone_of.values()))

    n = pypsa.Network()
    for zone in zone_ids:
        n.add("Bus", zone)

    # Fixed load per zone: every non-elastic load's own p_mw, plus the bus shunt conductance the
    # engine's balance row carries and import_from_pypower_ppc would have dropped (module
    # docstring). test_zone_fixed_load_totals_the_raw_matpower_columns checks this aggregation
    # against the raw matrices independently.
    elastic = set(fix.elastic_ids)
    fixed_mw = dict.fromkeys(zone_ids, 0.0)
    for load in fix.net.loads:
        if load.in_service and load.id not in elastic:
            fixed_mw[fix.zone_of[load.bus]] += load.p_mw
    for row in range(bus.shape[0]):
        fixed_mw[fix.zone_of[f"bus-{int(bus[row, 0])}"]] += float(bus[row, 4])
    for zone in zone_ids:
        n.add("Load", f"load-{zone}", bus=zone, p_set=fixed_mw[zone])

    for k in range(gen.shape[0]):
        if gen[k, 7] <= 0:  # MATPOWER GEN_STATUS
            continue
        p_max = float(gen[k, 8])
        n.add(
            "Generator",
            f"G{k}",
            bus=fix.zone_of[f"bus-{int(gen[k, 0])}"],
            p_nom=p_max,
            p_min_pu=(float(gen[k, 9]) / p_max) if p_max else 0.0,
            p_max_pu=1.0,
            marginal_cost=float(gencost[k, 5]),
            marginal_cost_quadratic=float(gencost[k, 4]),
        )

    # Elastic demand as PyPSA's negative-generator pattern: a Generator with sign=-1 withdraws its
    # own p from the bus, so a marginal_cost of -v1 and marginal_cost_quadratic of -v2 reproduce
    # the engine's own demand column exactly (dc_opf minimises sum cost_g - sum value_d, putting
    # -v1 on the column and -2*v2 on the Hessian diagonal).
    loads_by_id = {load.id: load for load in fix.net.loads}
    for load_id in fix.elastic_ids:
        load = loads_by_id[load_id]
        assert load.bid is not None and load.bid.kind == "polynomial", load_id
        v2, v1, _v0 = (float(c) for c in load.bid.coefficients)
        n.add(
            "Generator",
            f"D-{load_id}",
            bus=fix.zone_of[load.bus],
            p_nom=load.p_mw,
            p_min_pu=0.0,
            p_max_pu=1.0,
            sign=-1.0,
            marginal_cost=-v1,
            marginal_cost_quadratic=-v2,
        )

    for z1, z2 in sorted(fix.caps):
        n.add(
            "Link",
            f"{z1}->{z2}",
            bus0=z1,
            bus1=z2,
            p_nom=float(fix.caps[(z1, z2)]),
            p_min_pu=-1.0,
            p_max_pu=1.0,
            efficiency=1.0,
            marginal_cost=0.0,
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        status, cond = n.optimize(solver_name="highs")
    # gencost column 6 is c0, which PyPSA has no concept of and n.objective excludes
    # (test_opf_vs_pypsa.py's own convention). Inert on every fixture here -- c0 == 0 throughout --
    # but kept so a future c0-bearing fixture is not silently mis-compared.
    c0_sum = float(np.sum(gencost[gen[:, 7] > 0, 6]))
    return n, status, cond, c0_sum


# --- the case under comparison -------------------------------------------------------------------


@dataclass
class Case:
    fix: ZonalFixture
    arr: NetworkArrays
    ours: ZonalSolution
    elastic_idxs: list[int]
    pypsa: Any
    pypsa_status: str
    pypsa_cond: str
    pypsa_obj: float

    @property
    def is_elastic(self) -> bool:
        return bool(self.fix.elastic_ids)

    def welfare_objective(self) -> float:
        """The engine's own objective in the oracle's units: ``ZonalSolution.objective_cost`` is
        generation cost only (deliberately, mirroring ``OpfSolution``), while PyPSA's
        ``n.objective`` nets the demand value out. Subtracting the bid value at the engine's *own*
        cleared quantities puts the two on the same footing without either side borrowing the
        other's primal solution. With no bids the subtraction is empty and this is
        ``objective_cost`` unchanged."""
        total = self.ours.objective_cost
        loads_by_id = {load.id: load for load in self.fix.net.loads}
        for j, i in enumerate(self.elastic_idxs):
            bid = loads_by_id[self.arr.load_ids[i]].bid
            assert bid is not None
            v2, v1, v0 = (float(c) for c in bid.coefficients)
            d = float(self.ours.demand_dispatch_mw[j])
            total -= v2 * d**2 + v1 * d + v0
        return total


PARAMS = [(case, elastic) for case in CASES for elastic in (False, True)]
IDS = [f"{case}-{'bids' if elastic else 'fixed'}" for case, elastic in PARAMS]


@pytest.fixture(scope="module", params=PARAMS, ids=IDS)
def case(request: pytest.FixtureRequest) -> Case:
    name, elastic = request.param
    fix = build_fixture(name, elastic=elastic)
    arr, ours, elastic_idxs = run_engine(fix)
    n, status, cond, c0_sum = run_pypsa_zonal_oracle(fix)
    obj = float(n.objective) + c0_sum if status == "ok" else float("nan")
    return Case(fix, arr, ours, elastic_idxs, n, status, cond, obj)


def _pypsa_gen_names(case: Case) -> list[tuple[str, int]]:
    """``(PyPSA generator name, engine generator index)`` for every in-service MATPOWER gen row.

    The name bridge is ``test_opf_vs_pypsa.py``'s own: PyPSA generators are positional in gen-row
    order, and this repository's ids are ``gen-{row+1}`` in the same order. A row the engine
    dropped and the oracle kept (or vice versa) raises here rather than being skipped.
    """
    gen = read_mpc_numpy(FIXTURES_DIR / f"{case.fix.case}.m")["gen"]
    index = {gid: i for i, gid in enumerate(case.arr.gen_ids)}
    pairs = [(f"G{k}", index[f"gen-{k + 1}"]) for k in range(gen.shape[0]) if gen[k, 7] > 0]
    assert len(pairs) == len(case.arr.gen_ids), (len(pairs), len(case.arr.gen_ids))
    return pairs


# --- both solvers must actually have solved ------------------------------------------------------


def test_zonal_dc_opf_converges_optimal(case: Case) -> None:
    assert case.ours.status == "Optimal", (case.fix.case, case.ours.message)


def test_pypsa_itself_converges_optimal(case: Case) -> None:
    """Sanity check on the oracle: an unsolved PyPSA network would make every comparison below
    vacuously agree on ``nan``."""
    assert (case.pypsa_status, case.pypsa_cond) == ("ok", "optimal"), (
        case.fix.case,
        case.pypsa_status,
        case.pypsa_cond,
    )


# --- the oracle's own inputs are what they claim to be -------------------------------------------


def test_zone_fixed_load_totals_the_raw_matpower_columns(case: Case) -> None:
    """The oracle's per-zone aggregation is checked against the raw ``PD``/``GS`` columns, summed
    a second way: every zone's fixed load plus every elastic load's own upper bound must total the
    fixture's whole ``sum(PD) + sum(GS)``. A partition that dropped or double-counted a bus would
    show up here before it could show up as a dispatch difference the tolerances might absorb."""
    raw = read_mpc_numpy(FIXTURES_DIR / f"{case.fix.case}.m")
    raw_total = float(raw["bus"][:, 2].sum() + raw["bus"][:, 4].sum())
    oracle_fixed = float(case.pypsa.loads["p_set"].sum())
    elastic_bound = sum(
        load.p_mw for load in case.fix.net.loads if load.id in set(case.fix.elastic_ids)
    )
    assert oracle_fixed + elastic_bound == pytest.approx(raw_total, abs=1e-9), (
        oracle_fixed,
        elastic_bound,
        raw_total,
    )


def test_every_bus_and_corridor_reaches_the_oracle(case: Case) -> None:
    """The oracle carries one bus per zone and one link per corridor, and the engine agrees on
    both axes -- so no corridor is silently missing from one side of the comparison."""
    assert sorted(case.pypsa.buses.index) == sorted(case.ours.zone_ids)
    assert sorted(case.pypsa.links.index) == sorted(
        f"{z1}->{z2}" for z1, z2 in case.ours.corridor_ids
    )
    assert set(case.ours.corridor_ids) == set(case.fix.caps)


# --- AC-6: agreement within the pinned, measured tolerances --------------------------------------


def test_objective_matches_pypsa(case: Case) -> None:
    ours = case.welfare_objective()
    rel = abs(ours - case.pypsa_obj) / abs(case.pypsa_obj)
    assert rel <= OBJ_REL_TOL, (case.fix.case, ours, case.pypsa_obj, rel)


def test_generator_dispatch_matches_pypsa(case: Case) -> None:
    pypsa_p = case.pypsa.generators_t.p.iloc[0]
    diffs = np.array(
        [
            abs(float(case.ours.dispatch_mw[i]) - float(pypsa_p[name]))
            for name, i in _pypsa_gen_names(case)
        ]
    )
    worst = int(np.argmax(diffs))
    assert diffs[worst] <= GEN_DISPATCH_ABS_TOL_MW, (case.fix.case, worst, diffs[worst])


def test_demand_dispatch_matches_pypsa(case: Case) -> None:
    """The elastic half. Skipped on the fixed-load parameters, where there is no demand column at
    all on either side -- asserted rather than assumed, so a fixture that quietly lost its bids
    would fail here instead of passing an empty comparison."""
    if not case.is_elastic:
        assert case.ours.demand_dispatch_mw.size == 0
        pytest.skip("fixed-load parameter: no elastic demand column on either side")
    pypsa_p = case.pypsa.generators_t.p.iloc[0]
    diffs = np.array(
        [
            abs(
                float(case.ours.demand_dispatch_mw[j]) - float(pypsa_p[f"D-{case.arr.load_ids[i]}"])
            )
            for j, i in enumerate(case.elastic_idxs)
        ]
    )
    assert diffs.size == len(case.fix.elastic_ids)
    worst = int(np.argmax(diffs))
    assert diffs[worst] <= DEMAND_DISPATCH_ABS_TOL_MW, (case.fix.case, worst, diffs[worst])


def test_zone_prices_match_pypsa(case: Case) -> None:
    """The engine's zone price is its zone's balance-row dual; PyPSA's is that bus's marginal
    price. AC-6's "zone prices (PyPSA's bus marginal prices)"."""
    prices = case.pypsa.buses_t.marginal_price.iloc[0]
    diffs = np.array(
        [
            abs(float(case.ours.duals.zone_price[i]) - float(prices[z]))
            for i, z in enumerate(case.ours.zone_ids)
        ]
    )
    worst = int(np.argmax(diffs))
    assert diffs[worst] <= ZONE_PRICE_ABS_TOL, (
        case.fix.case,
        case.ours.zone_ids[worst],
        diffs[worst],
    )


def test_corridor_flows_match_pypsa(case: Case) -> None:
    """Sign conventions agree as well as magnitudes: the engine's positive corridor flow is
    ``z1 -> z2`` for the sorted key, and PyPSA's ``links_t.p0`` is power *into* ``bus0``, i.e.
    likewise ``z1 -> z2`` for a link built ``bus0=z1, bus1=z2``. Comparing signed values rather
    than magnitudes is what makes a flipped sign convention in the engine a failure here."""
    p0 = case.pypsa.links_t.p0.iloc[0]
    diffs = np.array(
        [
            abs(float(case.ours.corridor_flow_mw[c]) - float(p0[f"{z1}->{z2}"]))
            for c, (z1, z2) in enumerate(case.ours.corridor_ids)
        ]
    )
    worst = int(np.argmax(diffs))
    assert diffs[worst] <= CORRIDOR_FLOW_ABS_TOL_MW, (
        case.fix.case,
        case.ours.corridor_ids[worst],
        diffs[worst],
        case.ours.corridor_flow_mw[worst],
    )


def test_corridor_capacity_prices_match_pypsa(case: Case) -> None:
    """``ZonalDuals.corridor_cap`` against the price spread PyPSA's own bus duals sustain across
    that link (module docstring on why the spread, not ``links_t.mu_upper``)."""
    prices = case.pypsa.buses_t.marginal_price.iloc[0]
    diffs = np.array(
        [
            abs(float(case.ours.duals.corridor_cap[c]) - abs(float(prices[z1]) - float(prices[z2])))
            for c, (z1, z2) in enumerate(case.ours.corridor_ids)
        ]
    )
    worst = int(np.argmax(diffs))
    assert diffs[worst] <= CORRIDOR_PRICE_ABS_TOL, (
        case.fix.case,
        case.ours.corridor_ids[worst],
        diffs[worst],
    )


def test_elastic_loads_clear_strictly_inside(case: Case) -> None:
    """Fixture power for :func:`test_demand_dispatch_matches_pypsa`: every bid load clears
    *strictly between* its bounds, so the demand comparison is reading a solved quantity rather
    than a bound both sides would hit regardless (``tests/_bids.py``'s own
    ``interior_bid_for_load`` rationale, M4 critic Issue 1). A load pinned at its upper bound would
    make that comparison agree even under a demand-column fault."""
    if not case.is_elastic:
        pytest.skip("fixed-load parameter: nothing to clear")
    for j, i in enumerate(case.elastic_idxs):
        upper = float(case.arr.load_p_max_pu[i] * case.arr.base_mva)
        d = float(case.ours.demand_dispatch_mw[j])
        assert 1e-3 < d < upper - 1e-3, (case.fix.case, case.arr.load_ids[i], d, upper)


# --- the fixture's own binding structure, committed as a test ------------------------------------


@pytest.fixture(scope="module")
def case30_fixed() -> Case:
    """The rated case30 fixed-load solve on its own, so the two structure tests below do not
    depend on which parameter of :func:`case` happens to be current."""
    fix = build_fixture("case30", elastic=False)
    arr, ours, elastic_idxs = run_engine(fix)
    n, status, cond, c0_sum = run_pypsa_zonal_oracle(fix)
    obj = float(n.objective) + c0_sum if status == "ok" else float("nan")
    return Case(fix, arr, ours, elastic_idxs, n, status, cond, obj)


def test_case30_corridor_structure_binds_two_of_three(case30_fixed: Case) -> None:
    """**The property that makes this fixture worth a parity test at all**: on rated case30 the
    corridor bounds genuinely matter. Two of the three corridors sit exactly at their own cap and
    the third is slack, so the comparison above is over a solve where a dropped or mis-signed
    corridor bound would change the answer -- not over a copper plate where the caps are inert.

    Measured (S3, re-measured here): ``('1','2')`` at its 1.5237 MVA cap; ``('2','3')`` at its
    19.4562 MVA cap, flowing ``3 -> 2`` (negative under the sorted-key convention); ``('1','3')``
    slack at 15.3588 of 16.5768. The cap on the tightest corridor is a *sum over its cut-set*
    (``tests/_zones.py``), and on this partition that cut-set is thin enough to bind hard.
    """
    sol = case30_fixed.ours
    caps = case30_fixed.fix.caps
    assert sol.corridor_ids == [("1", "2"), ("1", "3"), ("2", "3")]

    ratios = {
        key: abs(float(sol.corridor_flow_mw[c])) / caps[key]
        for c, key in enumerate(sol.corridor_ids)
    }
    binding = sorted(key for key, r in ratios.items() if r >= BINDING_RATIO)
    slack = sorted(key for key, r in ratios.items() if r < BINDING_RATIO)
    assert binding == [("1", "2"), ("2", "3")], ratios
    assert slack == [("1", "3")], ratios

    # the specific flows, with their signs -- the direction is part of the structure
    flow = dict(zip(sol.corridor_ids, sol.corridor_flow_mw, strict=True))
    assert float(flow[("1", "2")]) == pytest.approx(caps[("1", "2")], abs=1e-6)
    assert float(flow[("2", "3")]) == pytest.approx(-caps[("2", "3")], abs=1e-6)
    assert 0.0 < float(flow[("1", "3")]) < caps[("1", "3")]

    # a binding corridor prices its capacity; a slack one does not
    cap_price = dict(zip(sol.corridor_ids, sol.duals.corridor_cap, strict=True))
    assert float(cap_price[("1", "2")]) > DISTINCT_PRICE_MIN
    assert float(cap_price[("2", "3")]) > DISTINCT_PRICE_MIN
    assert float(cap_price[("1", "3")]) == pytest.approx(0.0, abs=CORRIDOR_PRICE_ABS_TOL)


def test_case30_prices_separate_into_exactly_two_levels(case30_fixed: Case) -> None:
    """The theorem-shaped half of the structure: three zones, three corridors, but exactly **two**
    distinct zone prices -- because the slack ``('1','3')`` corridor ties zones 1 and 3 into one
    price (``opf/zonal.py``: summing two balance rows joined by a non-binding exchange column
    cancels that column, collapsing them into the single system-wide row), while the two binding
    corridors let zone 2 stand apart by exactly their own capacity shadow price.

    Asserted through the oracle's prices, not the engine's, so it is a statement about the market
    and not about this builder's dual bookkeeping.
    """
    prices = case30_fixed.pypsa.buses_t.marginal_price.iloc[0]
    z1, z2, z3 = (float(prices[z]) for z in ("1", "2", "3"))

    assert abs(z1 - z3) < DISTINCT_PRICE_MIN, (z1, z3)
    assert abs(z2 - z1) > DISTINCT_PRICE_MIN, (z1, z2)

    # and the separation is exactly the binding corridors' capacity price, in both directions
    cap_price = dict(
        zip(case30_fixed.ours.corridor_ids, case30_fixed.ours.duals.corridor_cap, strict=True)
    )
    assert abs(z2 - z1) == pytest.approx(float(cap_price[("1", "2")]), abs=CORRIDOR_PRICE_ABS_TOL)
    assert abs(z2 - z3) == pytest.approx(float(cap_price[("2", "3")]), abs=CORRIDOR_PRICE_ABS_TOL)


# --- the negative control: a shared-fixture transposition is NOT a sabotage -----------------------


def test_transposing_the_shared_caps_is_not_a_sabotage() -> None:
    """``continuation-m5.md``'s A34 lesson, made explicit and committed rather than left as prose:
    **a fault injected into shared fixture data cannot be caught by a parity test, by
    construction** -- and that is a property of what parity means, not a hole in this module.

    Here the transposition swaps the ``('1','3')`` and ``('2','3')`` caps in the dictionary
    ``tests/_zones.py`` returns, *before* it is handed to either side. Both the engine and the
    PyPSA oracle then solve the same, differently-capped market, so they still agree -- to the very
    same tolerances the true-cap comparison meets.

    This is only worth committing because the transposition is emphatically **not** a no-op: it
    moves the objective by 0.487 $/h, the worst generator's dispatch by 1.44 MW, the worst corridor
    flow by 2.88 MW and the worst zone price by 0.072 $/MWh -- each five or more orders of magnitude
    above the tolerance the corresponding comparison above pins. A one-sided fault of that size
    would fail every one of those tests loudly. Applied to both sides it is invisible. Which is
    exactly why the S6 sabotage sweep injects its faults into ``opf.zonal`` itself, holding this
    oracle's own construction fixed.
    """
    fix = build_fixture("case30", elastic=False)
    _arr_true, true_sol, _ = run_engine(fix)

    a, b = ("1", "3"), ("2", "3")
    swapped = dict(fix.caps)
    swapped[a], swapped[b] = fix.caps[b], fix.caps[a]
    shared = ZonalFixture(fix.case, fix.net, fix.zone_of, swapped, fix.elastic_ids)

    arr, ours, elastic_idxs = run_engine(shared)
    n, status, cond, c0_sum = run_pypsa_zonal_oracle(shared)
    assert (status, cond) == ("ok", "optimal")
    assert ours.status == "Optimal", ours.message
    swapped_case = Case(
        shared, arr, ours, elastic_idxs, n, status, cond, float(n.objective) + c0_sum
    )

    # 1. the transposition genuinely moved the market -- otherwise this proves nothing
    d_obj = abs(ours.objective_cost - true_sol.objective_cost)
    d_dispatch = float(np.abs(ours.dispatch_mw - true_sol.dispatch_mw).max())
    d_flow = float(np.abs(ours.corridor_flow_mw - true_sol.corridor_flow_mw).max())
    d_price = float(np.abs(ours.duals.zone_price - true_sol.duals.zone_price).max())
    assert d_obj > 1e-2, d_obj
    assert d_dispatch > 100 * GEN_DISPATCH_ABS_TOL_MW, d_dispatch
    assert d_flow > 100 * CORRIDOR_FLOW_ABS_TOL_MW, d_flow
    assert d_price > 100 * ZONE_PRICE_ABS_TOL, d_price

    # 2. ... and parity is nonetheless green, to the same tolerances, on every comparison above
    test_objective_matches_pypsa(swapped_case)
    test_generator_dispatch_matches_pypsa(swapped_case)
    test_zone_prices_match_pypsa(swapped_case)
    test_corridor_flows_match_pypsa(swapped_case)
    test_corridor_capacity_prices_match_pypsa(swapped_case)
