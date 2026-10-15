"""MATPOWER case-file (``.m``) exporter (ADR-032): the writer :mod:`mambo_power.io.matpower`
reads back.

Writes a caseformat v2 ``mpc`` with ``baseMVA``, ``bus``, ``gen``, ``branch`` and — when any
generator carries a cost — ``gencost``, in exactly the column layout the importer reads, so that
a network the importer produced round-trips **losslessly**: ``loads(dumps(load(path)))`` equals
``load(path)`` on every bundled case, derived ids included (``bus-<I>``, ``gen-<row>``,
``branch-<row>``, ``load-<I>``, ``shunt-<I>``). Numbers are written with Python's shortest
round-trip ``repr``, which MATLAB and Octave read.

What the format cannot hold is dropped or merged and **named in the report** (D1: an empty
:class:`~mambo_power.io.report.ExportReport` means the file reads back as the same network):

* ``MATPOWER_ID_RENUMBERED`` — a bus id that is not ``bus-<I>`` (or ``<I>`` not unique) is
  numbered by position; a generator or branch id that is not its ``gen-<row>`` /
  ``branch-<row>`` comes back renamed; an area or zone label that is not an integer is
  numbered.
* ``ELEMENT_MERGED`` — several in-service loads (or shunts) at one bus become the bus row's
  one ``PD``/``QD`` (``GS``/``BS``); a single one whose id is not ``load-<I>`` / ``shunt-<I>``
  comes back renamed (reported under this code, since the row is the bus's, not the load's).
* ``ELEMENT_DROPPED`` — storage, an out-of-service load or shunt (MATPOWER loads and shunts
  carry no status), and a zone no bus names.
* ``FIELD_DROPPED`` — generator ramps, minimum up/down times, start-up tiers, reserve caps and
  initial state; ``Zone.name``; a ``rating_emergency_mva`` equal to ``rating_mva`` (the
  importer reads ``RATE_C`` only where it exceeds ``RATE_A``); an angle limit of exactly ±360
  (the importer's "no limit" spelling); the ``pv`` type of an out-of-service bus (``BUS_TYPE
  4`` reads back ``pq``); ``kind = "transformer"`` on a branch at nominal tap and shift
  (MATPOWER tells a transformer by its ``TAP``).
* ``FIELD_DEFAULTED`` — a bus with no stored ``vm_pu``/``va_deg`` is written at ``1.0`` / ``0``,
  one without voltage limits at ``VMAX 1.1`` / ``VMIN 0.9``; both read back as values.
* ``COST_DEFAULTED`` — ``gencost`` needs one row per generator: when some generators carry a
  cost and others none, the latter get a zero polynomial (``2 0 0 2 0 0``) that reads back as
  a cost. With no costs at all the section is omitted and every cost reads back ``None``.
* ``BID_DROPPED`` — load bids; MATPOWER has no demand-side costs.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from os import PathLike
from pathlib import Path
from typing import TypeVar

from mambo_power.io.report import ExportReport
from mambo_power.model import Bus, ImportIssue, Load, Network, PiecewiseCost, Shunt

__all__ = ["EXPORT_CODES", "dump", "dump_with_report", "dumps", "dumps_with_report"]

EXPORT_CODES: tuple[str, ...] = (
    "MATPOWER_ID_RENUMBERED",
    "ELEMENT_MERGED",
    "ELEMENT_DROPPED",
    "FIELD_DROPPED",
    "FIELD_DEFAULTED",
    "COST_DEFAULTED",
    "BID_DROPPED",
)
"""Every report code this exporter can emit."""

_BUS_ID = re.compile(r"^bus-(\d+)$")
_BUS_TYPE = {"pq": 1, "pv": 2, "slack": 3}
_GEN_FIELDS = (
    "ramp_up_mw",
    "ramp_down_mw",
    "min_up_periods",
    "min_down_periods",
    "initial_state_periods",
    "reserve_max_mw",
    "startup_hot_cost",
    "startup_hot_periods",
    "startup_warm_cost",
    "startup_warm_periods",
)
_QUANTITIES = {"load": ("p_mw", "q_mvar"), "shunt": ("g_mw", "b_mvar")}
_Warn = Callable[..., None]
_T = TypeVar("_T", Load, Shunt)


def dumps(net: Network) -> str:
    """MATPOWER ``.m`` text for ``net`` (module docstring); the report is discarded."""
    return dumps_with_report(net)[0]


def dump(net: Network, target: str | PathLike[str]) -> None:
    """Write ``net`` to *target* as a MATPOWER ``.m`` case."""
    dump_with_report(net, target)


def dump_with_report(net: Network, target: str | PathLike[str]) -> ExportReport:
    """Write ``net`` to *target* and return the :class:`ExportReport` of what was dropped."""
    text, report = dumps_with_report(net)
    Path(target).write_text(text, encoding="utf-8")
    return report


def dumps_with_report(net: Network) -> tuple[str, ExportReport]:
    """MATPOWER ``.m`` text for ``net`` and the :class:`ExportReport` of every drop, merge and
    default (module docstring)."""
    return _Writer(net).write()


def _f(value: float) -> str:
    """Shortest text that reads back as exactly *value*; integral values without ``.0``."""
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return repr(float(value))


class _Writer:
    def __init__(self, net: Network) -> None:
        self.net = net
        self.warnings: list[ImportIssue] = []
        self.number = _bus_numbers(net.buses, self.warn)
        self.area = _labels("area", [b.area for b in net.buses if b.area is not None], self.warn)
        self.zone = _labels("zone", [b.zone for b in net.buses if b.zone is not None], self.warn)

    def warn(self, code: str, message: str, **ids: list[str]) -> None:
        self.warnings.append(ImportIssue(code=code, message=message, **ids))  # type: ignore[arg-type]

    def write(self) -> tuple[str, ExportReport]:
        net = self.net
        lines = [
            "function mpc = mambo_power_case",
            "% MATPOWER case written by mambo-power (caseformat v2)",
            "mpc.version = '2';",
            "",
            "%% system MVA base",
            f"mpc.baseMVA = {_f(net.base_mva)};",
            "",
            "%% bus data",
            "%\tbus_i\ttype\tPd\tQd\tGs\tBs\tarea\tVm\tVa\tbaseKV\tzone\tVmax\tVmin",
            "mpc.bus = [",
            *self._buses(),
            "];",
            "",
            "%% generator data",
            "%\tbus\tPg\tQg\tQmax\tQmin\tVg\tmBase\tstatus\tPmax\tPmin\tPc1\tPc2\tQc1min\tQc1max"
            "\tQc2min\tQc2max\tramp_agc\tramp_10\tramp_30\tramp_q\tapf",
            "mpc.gen = [",
            *self._generators(),
            "];",
            "",
            "%% branch data",
            "%\tfbus\ttbus\tr\tx\tb\trateA\trateB\trateC\tratio\tangle\tstatus\tangmin\tangmax",
            "mpc.branch = [",
            *self._branches(),
            "];",
        ]
        gencost = self._gencost()
        if gencost is not None:
            lines += [
                "",
                "%% generator cost data",
                "%\t1\tstartup\tshutdown\tn\tx1\ty1\t...\txn\tyn",
                "%\t2\tstartup\tshutdown\tn\tc(n-1)\t...\tc0",
                "mpc.gencost = [",
                *gencost,
                "];",
            ]
        self._others()
        report = ExportReport(warnings=list(self.warnings))
        return "\n".join(lines) + "\n", report

    # -- sections --------------------------------------------------------------------------------

    def _buses(self) -> list[str]:
        net = self.net
        loads_at = _attached("load", net.loads, self.number, self.warn)
        shunts_at = _attached("shunt", net.shunts, self.number, self.warn)
        defaulted_state: list[str] = []
        defaulted_limits: list[str] = []
        pv_off: list[str] = []
        rows = []
        for bus in net.buses:
            bus_type = _BUS_TYPE[bus.type]
            if not bus.in_service:
                if bus.type == "pv":
                    pv_off.append(bus.id)
                bus_type = 4
            if bus.vm_pu is None or bus.va_deg is None:
                defaulted_state.append(bus.id)
            if bus.v_min_pu is None or bus.v_max_pu is None:
                defaulted_limits.append(bus.id)
            pd = sum(ld.p_mw for ld in loads_at.get(bus.id, []))
            qd = sum(ld.q_mvar for ld in loads_at.get(bus.id, []))
            gs = sum(sh.g_mw for sh in shunts_at.get(bus.id, []))
            bs = sum(sh.b_mvar for sh in shunts_at.get(bus.id, []))
            area = self.area[bus.area] if bus.area is not None else 1
            zone = self.zone[bus.zone] if bus.zone is not None else 1
            rows.append(
                "\t"
                + "\t".join(
                    _f(v)
                    for v in (
                        self.number[bus.id],
                        bus_type,
                        pd,
                        qd,
                        gs,
                        bs,
                        area,
                        1.0 if bus.vm_pu is None else bus.vm_pu,
                        0.0 if bus.va_deg is None else bus.va_deg,
                        bus.base_kv,
                        zone,
                        1.1 if bus.v_max_pu is None else bus.v_max_pu,
                        0.9 if bus.v_min_pu is None else bus.v_min_pu,
                    )
                )
                + ";"
            )
        if defaulted_state:
            self.warn(
                "FIELD_DEFAULTED",
                f"{len(defaulted_state)} bus(es) with no stored vm_pu / va_deg written at "
                "VM = 1, VA = 0, which read back as values",
                bus_ids=defaulted_state,
            )
        if defaulted_limits:
            self.warn(
                "FIELD_DEFAULTED",
                f"{len(defaulted_limits)} bus(es) with no v_min_pu / v_max_pu written at "
                "VMIN = 0.9, VMAX = 1.1, which read back as limits",
                bus_ids=defaulted_limits,
            )
        if pv_off:
            self.warn(
                "FIELD_DROPPED",
                f"{len(pv_off)} out-of-service pv bus(es) written as BUS_TYPE 4, which reads "
                "back as pq",
                bus_ids=pv_off,
            )
        return rows

    def _generators(self) -> list[str]:
        net = self.net
        renamed: list[str] = []
        fields: list[str] = []
        rows = []
        for k, gen in enumerate(net.generators, start=1):
            if gen.id != f"gen-{k}":
                renamed.append(gen.id)
            dropped = [name for name in _GEN_FIELDS if getattr(gen, name) is not None]
            if dropped:
                fields.append(f"{gen.id}: {', '.join(dropped)}")
            rows.append(
                "\t"
                + "\t".join(
                    _f(v)
                    for v in (
                        self.number[gen.bus],
                        gen.p_mw,
                        gen.q_mvar,
                        gen.q_max_mvar,
                        gen.q_min_mvar,
                        gen.v_set_pu,
                        net.base_mva,
                        int(gen.in_service),
                        gen.p_max_mw,
                        gen.p_min_mw,
                    )
                )
                + "\t0" * 11
                + ";"
            )
        if renamed:
            self.warn(
                "MATPOWER_ID_RENUMBERED",
                f"{len(renamed)} generator id(s) are not gen-<row>: the file reads back with "
                "ids by position",
                element_ids=renamed,
            )
        if fields:
            self.warn(
                "FIELD_DROPPED",
                "generator fields with no MATPOWER column dropped: " + "; ".join(fields),
                element_ids=[f.split(":")[0] for f in fields],
            )
        return rows

    def _branches(self) -> list[str]:
        renamed: list[str] = []
        emergency_equal: list[str] = []
        angle_edge: list[str] = []
        kind_only: list[str] = []
        rows = []
        for k, br in enumerate(self.net.branches, start=1):
            if br.id != f"branch-{k}":
                renamed.append(br.id)
            if br.kind == "transformer" and br.tap_ratio in (None, 1.0) and not br.shift_deg:
                kind_only.append(br.id)
            rate_a = br.rating_mva or 0.0
            rate_c = br.rating_emergency_mva or 0.0
            if br.rating_emergency_mva is not None and rate_c <= rate_a:
                emergency_equal.append(br.id)
            if br.angle_min_deg in (-360.0, 360.0) or br.angle_max_deg in (-360.0, 360.0):
                angle_edge.append(br.id)
            rows.append(
                "\t"
                + "\t".join(
                    _f(v)
                    for v in (
                        self.number[br.from_bus],
                        self.number[br.to_bus],
                        br.r,
                        br.x,
                        br.b,
                        rate_a,
                        0.0,
                        rate_c,
                        0.0 if br.tap_ratio is None else br.tap_ratio,  # TAP 0: no tap
                        0.0 if br.shift_deg is None else br.shift_deg,
                        int(br.in_service),
                        -360.0 if br.angle_min_deg is None else br.angle_min_deg,
                        360.0 if br.angle_max_deg is None else br.angle_max_deg,
                    )
                )
                + ";"
            )
        if renamed:
            self.warn(
                "MATPOWER_ID_RENUMBERED",
                f"{len(renamed)} branch id(s) are not branch-<row>: the file reads back with "
                "ids by position",
                element_ids=renamed,
            )
        if emergency_equal:
            self.warn(
                "FIELD_DROPPED",
                f"{len(emergency_equal)} branch(es) with rating_emergency_mva equal to "
                "rating_mva: RATE_C reads back only where it exceeds RATE_A",
                element_ids=emergency_equal,
            )
        if angle_edge:
            self.warn(
                "FIELD_DROPPED",
                f"{len(angle_edge)} branch(es) with an angle limit of exactly ±360, "
                "MATPOWER's 'no limit' spelling: it reads back as None",
                element_ids=angle_edge,
            )
        if kind_only:
            self.warn(
                "FIELD_DROPPED",
                f"{len(kind_only)} transformer(s) at nominal tap and shift: MATPOWER tells a "
                "transformer by its TAP, so they read back as lines",
                element_ids=kind_only,
            )
        return rows

    def _gencost(self) -> list[str] | None:
        gens = self.net.generators
        if not gens or all(g.cost is None for g in gens):
            return None
        defaulted = [g.id for g in gens if g.cost is None]
        numeric: list[list[float]] = []
        for gen in gens:
            cost = gen.cost
            if cost is None:
                numeric.append([2, 0, 0, 2, 0, 0])
                continue
            startup, shutdown = cost.startup, cost.shutdown
            if isinstance(cost, PiecewiseCost):
                values = [v for p in cost.points for v in p]
                numeric.append([1, startup, shutdown, len(cost.points), *values])
            else:
                values = list(cost.coefficients)
                numeric.append([2, startup, shutdown, len(values), *values])
        # one width for the matrix, zero-padded as MATPOWER itself does: NCOST governs
        width = max(len(row) for row in numeric)
        rows = [
            "\t" + "\t".join(_f(v) for v in (*row, *[0.0] * (width - len(row)))) + ";"
            for row in numeric
        ]
        if defaulted:
            self.warn(
                "COST_DEFAULTED",
                f"{len(defaulted)} generator(s) without a cost written as a zero polynomial: "
                "gencost needs one row per generator, and it reads back as a cost",
                element_ids=defaulted,
            )
        return rows

    def _others(self) -> None:
        net = self.net
        bids = [ld.id for ld in net.loads if ld.bid is not None]
        if bids:
            self.warn(
                "BID_DROPPED",
                f"{len(bids)} load bid(s) dropped: MATPOWER carries no demand-side costs",
                element_ids=bids,
            )
        if net.storage:
            self.warn(
                "ELEMENT_DROPPED",
                f"{len(net.storage)} storage unit(s) dropped: MATPOWER has no storage table",
                element_ids=[s.id for s in net.storage],
            )
        named = [z.id for z in net.zones if z.name is not None]
        if named:
            self.warn(
                "FIELD_DROPPED",
                f"{len(named)} zone name(s) dropped: a MATPOWER zone is a number",
                element_ids=named,
            )
        used = {b.zone for b in net.buses if b.zone is not None}
        unused = [z.id for z in net.zones if z.id not in used]
        if unused:
            self.warn(
                "ELEMENT_DROPPED",
                f"{len(unused)} zone(s) no bus names dropped: zones exist only on bus rows",
                element_ids=unused,
            )


# -- helpers -----------------------------------------------------------------------------------


def _bus_numbers(buses: Sequence[Bus], warn: _Warn) -> dict[str, int]:
    numbers: dict[str, int] = {}
    for bus in buses:
        match = _BUS_ID.match(bus.id)
        if match is not None and int(match.group(1)) > 0:
            numbers[bus.id] = int(match.group(1))
    if len(set(numbers.values())) == len(buses):
        return numbers
    renumbered = [bus.id for bus in buses if bus.id not in numbers] or [b.id for b in buses]
    warn(
        "MATPOWER_ID_RENUMBERED",
        f"{len(buses)} bus id(s) do not carry a unique bus number (bus-<I>); numbered by "
        "position from 1",
        bus_ids=renumbered,
    )
    return {bus.id: k for k, bus in enumerate(buses, start=1)}


def _labels(what: str, labels: Sequence[str], warn: _Warn) -> dict[str, int]:
    """MATPOWER ``AREA`` / ``ZONE`` numbers for the labels: the label itself where every one is
    a positive integer, else numbered by first appearance."""
    distinct = list(dict.fromkeys(labels))
    if all(label.isdigit() and int(label) > 0 for label in distinct):
        return {label: int(label) for label in distinct}
    warn(
        "MATPOWER_ID_RENUMBERED",
        f"{what} labels are not all positive integers ({', '.join(distinct)}); numbered by "
        "first appearance from 1",
    )
    return {label: k for k, label in enumerate(distinct, start=1)}


def _attached(
    what: str, elements: Sequence[_T], number: dict[str, int], warn: _Warn
) -> dict[str, list[_T]]:
    """In-service loads (shunts) by bus; the out-of-service ones dropped, and the ones the bus
    row's single ``PD``/``QD`` (``GS``/``BS``) cannot give back one by one reported."""
    by_bus: dict[str, list[_T]] = {}
    dropped: list[str] = []
    merged: list[str] = []
    zero: list[str] = []
    for element in elements:
        if not element.in_service:
            dropped.append(element.id)
            continue
        if not any(getattr(element, name) for name in _QUANTITIES[what]):
            zero.append(element.id)  # an all-zero row is not read back as an element
            continue
        by_bus.setdefault(element.bus, []).append(element)
    for bus_id, group in by_bus.items():
        if len(group) > 1 or group[0].id != f"{what}-{number[bus_id]}":
            merged.extend(e.id for e in group)
    if dropped:
        warn(
            "ELEMENT_DROPPED",
            f"{len(dropped)} out-of-service {what}(s) dropped: MATPOWER {what}s carry no status",
            element_ids=dropped,
        )
    if zero:
        warn(
            "ELEMENT_DROPPED",
            f"{len(zero)} all-zero {what}(s) dropped: the importer reads a zero row as none",
            element_ids=zero,
        )
    if merged:
        warn(
            "ELEMENT_MERGED",
            f"{len(merged)} {what}(s) become their bus row's single entry and read back as "
            f"{what}-<bus number>",
            element_ids=merged,
        )
    return by_bus
