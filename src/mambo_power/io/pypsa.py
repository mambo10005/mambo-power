"""PyPSA export (wave M8, W3): ``Network`` → :class:`pypsa.Network`, plus what was dropped.

PyPSA is imported lazily, inside :func:`to_network`, so the core package keeps its
zero-optional-dependency import (design item R9; ``pypsa`` is a dev extra).

**Field map** (``m8-research.md`` §2; verified against ``opf.solve_dc_opf`` by
``tests/parity/test_pypsa_export_vs_pypsa.py``):

* ``Bus`` → ``Bus``: ``v_nom = base_kv``, ``v_mag_pu_min/max``, ``control`` from ``type``
  (``Slack``/``PV``/``PQ``), ``x/y`` from ``geo`` (lon, lat),
  ``v_mag_pu_set`` from the bus's generators' ``v_set_pu``; ``area``/``zone`` ride along as
  custom columns (PyPSA keeps unknown columns through CSV export/import). PyPSA buses have no
  ``active`` flag, so ``in_service`` is kept as a custom ``in_service`` column and every element
  at an out-of-service bus is exported ``active = False`` — what ``numerics.NetworkArrays`` does
  with such elements, so the solvers on both sides see the same network.
* ``Branch`` with ``is_transformer`` false (``kind == "line"`` at a nominal tap) → ``Line`` in
  physical units on the from-bus base:
  ``Zb = base_kv² / base_mva``; ``r, x`` in ohm (``× Zb``), ``b`` in siemens (``÷ Zb``).
* ``Branch`` with ``is_transformer`` (``kind == "transformer"`` or an off-nominal tap/shift,
  so a line mutated to carry a tap is not dropped) → ``Transformer(model="pi")`` with
  ``r, x, b`` per unit on the transformer's own ``s_nom`` (impedances ``r, x``
  ``× s_nom / base_mva``; the admittance ``b`` ``× base_mva / s_nom``), ``tap_ratio``,
  ``tap_side=0`` (mambo's tap is on the from side) and ``phase_shift`` in degrees.
* ``rating_mva`` → ``s_nom``; an unrated branch gets :data:`UNRATED_S_NOM_MVA` because PyPSA's
  optimiser reads ``s_nom == 0`` as "carries nothing", not "unlimited" -- an approximation, so
  the report names each such branch (``PYPSA_UNRATED_S_NOM_DEFAULTED``, M8 walk surprise 4).
* ``Generator`` → ``Generator``: ``p_nom = max(|p_min_mw|, |p_max_mw|)``, ``p_min_pu``/``p_max_pu``
  as fractions of it (so ``p_nom == p_max_mw`` in the ordinary case and a negative-only range
  survives too), ``marginal_cost = c1``, ``marginal_cost_quadratic = c2``, the constant ``c0`` in
  the custom :data:`COST_CONSTANT_COLUMN` column (``n.objective`` excludes constants),
  ``ramp_limit_up/down`` as fractions of ``p_nom``, ``start_up_cost``/``shut_down_cost``,
  ``control``, ``active``. **``p_set`` is never written**: a non-NaN ``p_set`` pins the dispatch
  in ``optimize()`` (``tests/parity/test_opf_vs_pypsa.py``'s root cause).
* ``phase_shift`` is carried faithfully and honoured by PyPSA's linear power flow (``n.lpf()``
  agrees with ``pf.solve_dc`` on a shifted loop, sign included), but PyPSA 1.2.4's ``optimize()``
  never reads it (``pypsa/optimization`` has no reference to ``phase_shift``; measured in
  ``tests/parity/test_pypsa_export_vs_pypsa.py``). The AC-3 parity claim is therefore for
  shift-free networks; a phase shifter is exported, not dropped, so it is not reported.
* ``Load`` → ``Load(p_set, q_set)``; ``Shunt`` → ``ShuntImpedance(g, b)`` in siemens
  (``MW / kV²``); ``Storage`` → ``StorageUnit(p_nom, max_hours, state_of_charge_initial,
  efficiency_store, efficiency_dispatch)``; ``base_mva`` → ``n.meta["base_mva"]``.

**Dropped and reported** (design item D1 — never approximated; each entry names the element id
and the field): piecewise costs, polynomial costs of effective degree > 2, load bids, zones,
generator reactive limits, a ramp on a zero-capacity generator, and disagreeing voltage
setpoints at one bus (PyPSA has one ``v_mag_pu_set`` per bus). :data:`CODES` lists the codes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mambo_power.io.report import ConversionIssue, ExportReport
from mambo_power.model import Generator, Network, PiecewiseCost, PolynomialCost

if TYPE_CHECKING:
    import pypsa

CODES: tuple[str, ...] = (
    "PYPSA_PWL_COST_DROPPED",
    "PYPSA_COST_DEGREE_DROPPED",
    "PYPSA_LOAD_BID_DROPPED",
    "PYPSA_ZONE_DROPPED",
    "PYPSA_GEN_Q_LIMITS_DROPPED",
    "PYPSA_GEN_RAMP_DROPPED",
    "PYPSA_GEN_VSET_CONFLICT",
    "PYPSA_UNRATED_S_NOM_DEFAULTED",
)
"""Every report code this exporter can emit (its documented limitations)."""

UNRATED_S_NOM_MVA = 1e5
"""``s_nom`` written for a branch with ``rating_mva = None``. PyPSA's optimiser bounds every
branch flow by ``s_nom``, so 0 would mean "no flow", not "no limit"; this sentinel is far above
any flow on the fixtures (case300's whole dispatch is 2.4e4 MW) and small enough not to hurt the
LP's scaling."""

COST_CONSTANT_COLUMN = "marginal_cost_constant"
"""Custom generator column holding the polynomial cost's constant term ``c0`` (cost per hour at
any dispatch). PyPSA has no attribute for it and ``n.objective`` excludes constants; a caller
comparing objectives adds ``n.generators[COST_CONSTANT_COLUMN].sum()``."""

_CONTROL = {"slack": "Slack", "pv": "PV", "pq": "PQ"}


def to_network(net: Network) -> pypsa.Network:
    """Export ``net`` as a :class:`pypsa.Network`, discarding the report.

    See :func:`to_network_with_report` for what may be dropped; this form is for callers who
    already know their network is within what PyPSA can express.
    """
    return to_network_with_report(net)[0]


def to_network_with_report(net: Network) -> tuple[pypsa.Network, ExportReport]:
    """Export ``net`` as a :class:`pypsa.Network` and report every field PyPSA cannot carry.

    An empty report means the export was lossless. The report only ever carries warnings — every
    unsupported field is dropped, never refused (D1) — so ``raise_on_error`` is a no-op.
    """
    import pypsa

    report = ExportReport()
    warn = report.warnings.append
    n = pypsa.Network()
    n.meta["base_mva"] = net.base_mva

    base_kv = {bus.id: bus.base_kv for bus in net.buses}
    live = {bus.id for bus in net.buses if bus.in_service}
    _add_buses(n, net, warn)
    _add_branches(n, net, base_kv, live, warn)
    _add_generators(n, net, live, warn)
    _add_loads(n, net, live, warn)
    _add_shunts(n, net, base_kv, live)
    _add_storage(n, net, live)
    if net.zones:
        warn(
            ConversionIssue(
                code="PYPSA_ZONE_DROPPED",
                message=f"PyPSA has no zone component; dropped zones {[z.id for z in net.zones]} "
                "(bus.zone labels are kept as a custom 'zone' column on buses)",
                element_ids=[z.id for z in net.zones],
            )
        )
    return n, report


def _add_buses(n: pypsa.Network, net: Network, warn: Any) -> None:
    v_set: dict[str, float] = {}
    gens_at: dict[str, list[Generator]] = {}
    for g in net.generators:
        gens_at.setdefault(g.bus, []).append(g)
    for bus_id, gens in gens_at.items():
        v_set[bus_id] = gens[0].v_set_pu
        if len({g.v_set_pu for g in gens}) > 1:
            warn(
                ConversionIssue(
                    code="PYPSA_GEN_VSET_CONFLICT",
                    message=f"bus {bus_id!r}: generators {[g.id for g in gens]} disagree on "
                    f"v_set_pu {[g.v_set_pu for g in gens]}; PyPSA has one v_mag_pu_set per bus, "
                    f"kept {gens[0].id!r}'s {gens[0].v_set_pu}",
                    bus_ids=[bus_id],
                    element_ids=[g.id for g in gens],
                )
            )
    n.add(
        "Bus",
        [b.id for b in net.buses],
        v_nom=[b.base_kv for b in net.buses],
        control=[_CONTROL[b.type] for b in net.buses],
        in_service=[b.in_service for b in net.buses],
        v_mag_pu_min=[b.v_min_pu if b.v_min_pu is not None else 0.0 for b in net.buses],
        v_mag_pu_max=[b.v_max_pu if b.v_max_pu is not None else float("inf") for b in net.buses],
        v_mag_pu_set=[v_set.get(b.id, 1.0) for b in net.buses],
        x=[b.geo.lon if b.geo is not None else 0.0 for b in net.buses],
        y=[b.geo.lat if b.geo is not None else 0.0 for b in net.buses],
        area=[b.area if b.area is not None else "" for b in net.buses],
        zone=[b.zone if b.zone is not None else "" for b in net.buses],
    )


def _add_branches(
    n: pypsa.Network, net: Network, base_kv: dict[str, float], live: set[str], warn: Any
) -> None:
    lines = [br for br in net.branches if not br.is_transformer]
    trafos = [br for br in net.branches if br.is_transformer]
    for br in net.branches:
        if br.rating_mva is None:
            warn(
                ConversionIssue(
                    code="PYPSA_UNRATED_S_NOM_DEFAULTED",
                    message=f"branch {br.id!r}: rating_mva is None; wrote s_nom = "
                    f"{UNRATED_S_NOM_MVA} (pypsa.UNRATED_S_NOM_MVA) because PyPSA's optimiser "
                    f"reads s_nom == 0 as 'carries nothing', not 'unlimited'",
                    element_ids=[br.id],
                )
            )
    if lines:
        zb = [base_kv[br.from_bus] ** 2 / net.base_mva for br in lines]
        n.add(
            "Line",
            [br.id for br in lines],
            bus0=[br.from_bus for br in lines],
            bus1=[br.to_bus for br in lines],
            r=[br.r * z for br, z in zip(lines, zb, strict=True)],
            x=[br.x * z for br, z in zip(lines, zb, strict=True)],
            b=[br.b / z for br, z in zip(lines, zb, strict=True)],
            s_nom=[_s_nom(br.rating_mva) for br in lines],
            active=[br.in_service and br.from_bus in live and br.to_bus in live for br in lines],
        )
    if trafos:
        s_nom = [_s_nom(br.rating_mva) for br in trafos]
        scale = [s / net.base_mva for s in s_nom]
        n.add(
            "Transformer",
            [br.id for br in trafos],
            bus0=[br.from_bus for br in trafos],
            bus1=[br.to_bus for br in trafos],
            model="pi",
            r=[br.r * k for br, k in zip(trafos, scale, strict=True)],
            x=[br.x * k for br, k in zip(trafos, scale, strict=True)],
            b=[br.b / k for br, k in zip(trafos, scale, strict=True)],  # admittance: / scale
            s_nom=s_nom,
            tap_ratio=[br.tap_ratio if br.tap_ratio is not None else 1.0 for br in trafos],
            tap_side=0,
            phase_shift=[br.shift_deg if br.shift_deg is not None else 0.0 for br in trafos],
            active=[br.in_service and br.from_bus in live and br.to_bus in live for br in trafos],
        )


def _s_nom(rating_mva: float | None) -> float:
    return rating_mva if rating_mva is not None else UNRATED_S_NOM_MVA


def _add_generators(n: pypsa.Network, net: Network, live: set[str], warn: Any) -> None:
    if not net.generators:
        return
    bus_type = {b.id: b.type for b in net.buses}
    p_nom, p_min_pu, p_max_pu, ramp_up, ramp_down = [], [], [], [], []
    c2, c1, c0, startup, shutdown = [], [], [], [], []
    for g in net.generators:
        nom = max(abs(g.p_min_mw), abs(g.p_max_mw))
        p_nom.append(nom)
        p_min_pu.append(g.p_min_mw / nom if nom else 0.0)
        p_max_pu.append(g.p_max_mw / nom if nom else 0.0)
        ramp_up.append(_ramp_pu(g, "ramp_up_mw", g.ramp_up_mw, nom, warn))
        ramp_down.append(_ramp_pu(g, "ramp_down_mw", g.ramp_down_mw, nom, warn))
        q2, q1, q0 = _cost_terms(g, warn)
        c2.append(q2)
        c1.append(q1)
        c0.append(q0)
        startup.append(g.cost.startup if g.cost is not None else 0.0)
        shutdown.append(g.cost.shutdown if g.cost is not None else 0.0)
        if g.q_min_mvar != 0.0 or g.q_max_mvar != 0.0:
            warn(
                ConversionIssue(
                    code="PYPSA_GEN_Q_LIMITS_DROPPED",
                    message=f"generator {g.id!r}: PyPSA generators carry no reactive limits; "
                    f"dropped q_min_mvar={g.q_min_mvar}, q_max_mvar={g.q_max_mvar}",
                    element_ids=[g.id],
                )
            )
    n.add(
        "Generator",
        [g.id for g in net.generators],
        bus=[g.bus for g in net.generators],
        control=[_CONTROL[bus_type[g.bus]] for g in net.generators],
        active=[g.in_service and g.bus in live for g in net.generators],
        p_nom=p_nom,
        p_min_pu=p_min_pu,
        p_max_pu=p_max_pu,
        marginal_cost=c1,
        marginal_cost_quadratic=c2,
        start_up_cost=startup,
        shut_down_cost=shutdown,
        ramp_limit_up=ramp_up,
        ramp_limit_down=ramp_down,
    )
    # a custom column (PyPSA keeps it through CSV export/import); assigned after add() because
    # add()'s typed signature does not admit unknown keyword attributes
    n.generators[COST_CONSTANT_COLUMN] = c0


def _ramp_pu(g: Generator, field: str, ramp_mw: float | None, nom: float, warn: Any) -> float:
    if ramp_mw is None:
        return float("nan")
    if nom == 0.0:
        warn(
            ConversionIssue(
                code="PYPSA_GEN_RAMP_DROPPED",
                message=f"generator {g.id!r}: {field}={ramp_mw} cannot be expressed as a "
                "fraction of p_nom = 0 (p_min_mw = p_max_mw = 0); dropped",
                element_ids=[g.id],
            )
        )
        return float("nan")
    return ramp_mw / nom


def _cost_terms(g: Generator, warn: Any) -> tuple[float, float, float]:
    """``(c2, c1, c0)`` PyPSA can carry, or zeros plus a report entry for what it cannot."""
    cost = g.cost
    if cost is None:
        return 0.0, 0.0, 0.0
    if isinstance(cost, PiecewiseCost):
        warn(
            ConversionIssue(
                code="PYPSA_PWL_COST_DROPPED",
                message=f"generator {g.id!r}: PyPSA has no piecewise-linear cost; dropped the "
                f"{len(cost.points)}-point cost, exported with marginal_cost 0",
                element_ids=[g.id],
            )
        )
        return 0.0, 0.0, 0.0
    assert isinstance(cost, PolynomialCost)
    coeffs = list(cost.coefficients)
    while len(coeffs) > 1 and coeffs[0] == 0.0:
        coeffs.pop(0)
    if len(coeffs) > 3:
        warn(
            ConversionIssue(
                code="PYPSA_COST_DEGREE_DROPPED",
                message=f"generator {g.id!r}: PyPSA carries polynomial costs up to degree 2; "
                f"dropped the degree {len(coeffs) - 1} cost, exported with marginal_cost 0",
                element_ids=[g.id],
            )
        )
        return 0.0, 0.0, 0.0
    padded = [0.0] * (3 - len(coeffs)) + coeffs
    return padded[0], padded[1], padded[2]


def _add_loads(n: pypsa.Network, net: Network, live: set[str], warn: Any) -> None:
    for ld in net.loads:
        if ld.bid is not None:
            warn(
                ConversionIssue(
                    code="PYPSA_LOAD_BID_DROPPED",
                    message=f"load {ld.id!r}: PyPSA has no elastic-demand bid; dropped the "
                    f"{ld.bid.kind} bid, exported as a fixed p_set of {ld.p_mw} MW",
                    element_ids=[ld.id],
                )
            )
    if net.loads:
        n.add(
            "Load",
            [ld.id for ld in net.loads],
            bus=[ld.bus for ld in net.loads],
            p_set=[ld.p_mw for ld in net.loads],
            q_set=[ld.q_mvar for ld in net.loads],
            active=[ld.in_service and ld.bus in live for ld in net.loads],
        )


def _add_shunts(n: pypsa.Network, net: Network, base_kv: dict[str, float], live: set[str]) -> None:
    if net.shunts:
        n.add(
            "ShuntImpedance",
            [sh.id for sh in net.shunts],
            bus=[sh.bus for sh in net.shunts],
            g=[sh.g_mw / base_kv[sh.bus] ** 2 for sh in net.shunts],
            b=[sh.b_mvar / base_kv[sh.bus] ** 2 for sh in net.shunts],
            active=[sh.in_service and sh.bus in live for sh in net.shunts],
        )


def _add_storage(n: pypsa.Network, net: Network, live: set[str]) -> None:
    if net.storage:
        n.add(
            "StorageUnit",
            [st.id for st in net.storage],
            bus=[st.bus for st in net.storage],
            p_nom=[st.p_max_mw for st in net.storage],
            max_hours=[st.energy_mwh / st.p_max_mw if st.p_max_mw else 0.0 for st in net.storage],
            state_of_charge_initial=[st.soc_initial * st.energy_mwh for st in net.storage],
            efficiency_store=[st.efficiency_charge for st in net.storage],
            efficiency_dispatch=[st.efficiency_discharge for st in net.storage],
            active=[st.in_service and st.bus in live for st in net.storage],
        )
