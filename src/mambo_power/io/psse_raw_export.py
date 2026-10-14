"""PSS/E RAW version 33 exporter (ADR-022): the writer :mod:`mambo_power.io.psse_raw` reads back.

Writes the v33 layout the importer accepts — the three case-identification lines, then the bus,
load, fixed shunt, generator, non-transformer branch, two-winding transformer, area and zone
sections with every other section present and empty, each ended by its ``0`` terminator and the
file by ``Q``. Field order follows grg-pssedata's ``struct.py``; the records are the inverse of
the importer's conversions, written in the one form the importer reads without any folding:
``CW = CZ = CM = 1`` (tap in pu of the bus base, impedance pu on ``SBASE``, no magnetising
admittance), loads as constant power (``IP = IQ = YP = YQ = 0``), no branch end shunts.

**Numbers and ids.** RAW addresses a bus by an integer and a load, shunt, generator or circuit by
a one- or two-character ``ID``. An id the importer produced — ``bus-<I>``, ``load-<I>-<ID>``,
``gen-<I>-<ID>``, ``shunt-<I>-<ID>``, ``branch-<I>-<J>-<CKT>`` — is taken apart again, so a
network read from RAW writes back with the numbers it came with. Any other id is numbered: buses
by position from 1, and loads, shunts, generators and circuits per bus (pair) from ``1``; the
report says so once per table (``RAW_ID_RENUMBERED``), naming every element, because a reader
of the file cannot recover the original ids from it.

**What the format cannot carry** is reported, never silently dropped: generator costs
(``COST_DROPPED``) and load bids (``BID_DROPPED``) — RAW has no economic section; storage
(``ELEMENT_DROPPED``); a transformer's line charging ``b`` (RAW transformers have none), bus
``geo``, generator ramps and minimum up/down times (``FIELD_DROPPED``). A bus without a stored
state is written at ``VM = 1, VA = 0`` and one without voltage limits at ``1.1 / 0.9``, the
format's own defaults (``FIELD_DEFAULTED``, one entry per bus table). ``rating_emergency_mva``
is written as ``RATEC`` on a branch record and ``RATC1`` on a transformer's (the importer reads
the former back). An area record is written for every distinct ``Bus.area`` (``ISW = 0``,
``PDES = 0``, ``PTOL = 999.99``) and a zone record for every zone, with its name.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from os import PathLike
from pathlib import Path
from typing import Protocol

from mambo_power.io.report import ExportReport
from mambo_power.model import Branch, Bus, ImportIssue, Network


class _Attached(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def bus(self) -> str: ...


_Warn = Callable[..., None]

__all__ = ["EXPORT_CODES", "dump", "dump_with_report", "dumps", "dumps_with_report"]

EXPORT_CODES: tuple[str, ...] = (
    "RAW_ID_RENUMBERED",
    "COST_DROPPED",
    "BID_DROPPED",
    "ELEMENT_DROPPED",
    "FIELD_DROPPED",
    "FIELD_DEFAULTED",
)
"""Every report code this exporter can emit."""

_BUS_ID = re.compile(r"^bus-(\d+)$")
_IDE = {"slack": 3, "pv": 2, "pq": 1}
_EMPTY_SECTIONS_AFTER_AREA = (
    "TWO-TERMINAL DC",
    "VSC DC LINE",
    "IMPEDANCE CORRECTION",
    "MULTI-TERMINAL DC",
    "MULTI-SECTION LINE",
)
_EMPTY_SECTIONS_AFTER_ZONE = (
    "INTER-AREA TRANSFER",
    "OWNER",
    "FACTS DEVICE",
    "SWITCHED SHUNT",
    "GNE",
    "INDUCTION MACHINE",
)


def dumps(net: Network) -> str:
    """RAW v33 text for ``net`` (module docstring); the report is discarded."""
    return dumps_with_report(net)[0]


def dump(net: Network, target: str | PathLike[str]) -> None:
    """Write ``net`` to *target* as RAW v33 text."""
    dump_with_report(net, target)


def dump_with_report(net: Network, target: str | PathLike[str]) -> ExportReport:
    """Write ``net`` to *target* and return the :class:`ExportReport` of what was dropped."""
    text, report = dumps_with_report(net)
    Path(target).write_text(text, encoding="utf-8")
    return report


def dumps_with_report(net: Network) -> tuple[str, ExportReport]:
    """RAW v33 text for ``net`` and the :class:`ExportReport` of every drop and default."""
    return _Writer(net).write()


class _Writer:
    def __init__(self, net: Network) -> None:
        self.net = net
        self.warnings: list[ImportIssue] = []
        self.number = _bus_numbers(net.buses, self.warn)
        self.area = _labels([b.area for b in net.buses if b.area is not None])
        self.zone = _labels([z.id for z in net.zones] + [b.zone for b in net.buses if b.zone])

    def warn(self, code: str, message: str, **ids: list[str]) -> None:
        self.warnings.append(ImportIssue(code=code, message=message, **ids))  # type: ignore[arg-type]

    # -- records -------------------------------------------------------------------------------

    def write(self) -> tuple[str, ExportReport]:
        net = self.net
        lines = [
            f"0, {net.base_mva:.2f}, 33, 0, 0, 60.00     / written by mambo-power",
            "mambo-power export, PSS/E RAW v33 layout",
            "no cost data exists in RAW: every generator cost was dropped (see the export report)",
        ]
        lines.extend(self._buses())
        lines.append("0 / END OF BUS DATA, BEGIN LOAD DATA")
        lines.extend(self._loads())
        lines.append("0 / END OF LOAD DATA, BEGIN FIXED SHUNT DATA")
        lines.extend(self._shunts())
        lines.append("0 / END OF FIXED SHUNT DATA, BEGIN GENERATOR DATA")
        lines.extend(self._generators())
        lines.append("0 / END OF GENERATOR DATA, BEGIN BRANCH DATA")
        branch_lines, transformer_lines = self._branches()
        lines.extend(branch_lines)
        lines.append("0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA")
        lines.extend(transformer_lines)
        lines.append("0 / END OF TRANSFORMER DATA, BEGIN AREA DATA")
        lines.extend(self._areas())
        previous = "AREA"
        for section in _EMPTY_SECTIONS_AFTER_AREA:
            lines.append(f"0 / END OF {previous} DATA, BEGIN {section} DATA")
            previous = section
        lines.append(f"0 / END OF {previous} DATA, BEGIN ZONE DATA")
        lines.extend(self._zones())
        previous = "ZONE"
        for section in _EMPTY_SECTIONS_AFTER_ZONE:
            lines.append(f"0 / END OF {previous} DATA, BEGIN {section} DATA")
            previous = section
        lines.append(f"0 / END OF {previous} DATA")
        lines.append("Q")
        self._storage()
        return "\n".join(lines) + "\n", ExportReport(warnings=self.warnings)

    def _buses(self) -> list[str]:
        out: list[str] = []
        defaulted_state: list[str] = []
        defaulted_limits: list[str] = []
        geo: list[str] = []
        for bus in self.net.buses:
            ide = _IDE[bus.type] if bus.in_service else 4
            if bus.vm_pu is None or bus.va_deg is None:
                defaulted_state.append(bus.id)
            if bus.v_min_pu is None or bus.v_max_pu is None:
                defaulted_limits.append(bus.id)
            if bus.geo is not None:
                geo.append(bus.id)
            vm = 1.0 if bus.vm_pu is None else bus.vm_pu
            va = 0.0 if bus.va_deg is None else bus.va_deg
            v_max = 1.1 if bus.v_max_pu is None else bus.v_max_pu
            v_min = 0.9 if bus.v_min_pu is None else bus.v_min_pu
            area = self.area[bus.area] if bus.area is not None else 1
            zone = self.zone[bus.zone] if bus.zone is not None else 1
            out.append(
                f"{self.number[bus.id]:6d},{_quoted(bus.id, 12)},{_f(bus.base_kv, 11)},{ide},"
                f"{area:4d},{zone:4d},   1,{_f(vm)},{_f(va, 10)},{_f(v_max)},{_f(v_min)},"
                f"{_f(v_max)},{_f(v_min)}"
            )
        if defaulted_state:
            self.warn(
                "FIELD_DEFAULTED",
                f"{len(defaulted_state)} bus(es) without a stored vm_pu/va_deg written at "
                "VM = 1, VA = 0",
                bus_ids=defaulted_state,
            )
        if defaulted_limits:
            self.warn(
                "FIELD_DEFAULTED",
                f"{len(defaulted_limits)} bus(es) without v_min_pu/v_max_pu written at "
                "NVLO/EVLO = 0.9, NVHI/EVHI = 1.1",
                bus_ids=defaulted_limits,
            )
        if geo:
            self.warn(
                "FIELD_DROPPED",
                f"{len(geo)} bus(es) with geo: RAW has no coordinates",
                bus_ids=geo,
            )
        return out

    def _loads(self) -> list[str]:
        out: list[str] = []
        ids = _element_ids("load", self.net.loads, self.number, self.warn)
        bids: list[str] = []
        for load in self.net.loads:
            if load.bid is not None:
                bids.append(load.id)
            bus = self._bus(load.bus)
            out.append(
                f"{self.number[load.bus]:6d},{_quoted(ids[load.id], 2)},{int(load.in_service)},"
                f"{self._area_of(bus):4d},{self._zone_of(bus):4d},{_f(load.p_mw, 10)},"
                f"{_f(load.q_mvar, 10)},     0.000,     0.000,     0.000,     0.000,   1,1,0"
            )
        if bids:
            self.warn(
                "BID_DROPPED",
                f"{len(bids)} load bid(s) dropped: RAW carries no economic data",
                element_ids=bids,
            )
        return out

    def _shunts(self) -> list[str]:
        ids = _element_ids("shunt", self.net.shunts, self.number, self.warn)
        return [
            f"{self.number[s.bus]:6d},{_quoted(ids[s.id], 2)},{int(s.in_service)},"
            f"{_f(s.g_mw, 10)},{_f(s.b_mvar, 10)}"
            for s in self.net.shunts
        ]

    def _generators(self) -> list[str]:
        out: list[str] = []
        ids = _element_ids("gen", self.net.generators, self.number, self.warn)
        costs: list[str] = []
        fields: list[str] = []
        for gen in self.net.generators:
            if gen.cost is not None:
                costs.append(gen.id)
            dropped = [
                name
                for name in (
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
                if getattr(gen, name) is not None
            ]
            if dropped:
                fields.append(f"{gen.id}: {', '.join(dropped)}")
            out.append(
                f"{self.number[gen.bus]:6d},{_quoted(ids[gen.id], 2)},{_f(gen.p_mw, 10)},"
                f"{_f(gen.q_mvar, 10)},{_f(gen.q_max_mvar, 10)},{_f(gen.q_min_mvar, 10)},"
                f"{_f(gen.v_set_pu)},    0,{self.net.base_mva:10.3f}, 0.00000, 1.00000, "
                f"0.00000, 0.00000,1.00000,{int(gen.in_service)},  100.0,{_f(gen.p_max_mw, 10)},"
                f"{_f(gen.p_min_mw, 10)},   1,1.0000,   0,1.0000,   0,1.0000,   0,1.0000,0,1.0000"
            )
        if costs:
            self.warn(
                "COST_DROPPED",
                f"{len(costs)} generator cost(s) dropped: RAW carries no economic data",
                element_ids=costs,
            )
        if fields:
            self.warn(
                "FIELD_DROPPED",
                "generator fields with no RAW counterpart dropped: " + "; ".join(fields),
                element_ids=[f.split(":")[0] for f in fields],
            )
        return out

    def _branches(self) -> tuple[list[str], list[str]]:
        branch_lines: list[str] = []
        transformer_lines: list[str] = []
        ckts = _circuit_ids(self.net.branches, self.number, self.warn)
        charging: list[str] = []
        for br in self.net.branches:
            i, j = self.number[br.from_bus], self.number[br.to_bus]
            ckt = _quoted(ckts[br.id], 2)
            rate_a = br.rating_mva or 0.0
            rate_c = br.rating_emergency_mva or 0.0
            if not br.is_transformer:
                branch_lines.append(
                    f"{i:6d},{j:6d},{ckt},{_f(br.r, 9)},{_f(br.x, 9)},{_f(br.b, 9)},"
                    f"{_f(rate_a, 7)},   0.00,{_f(rate_c, 7)}, 0.00000, 0.00000, 0.00000, 0.00000,"
                    f"{int(br.in_service)},1,   0.00,   1,1.0000,   0,1.0000,   0,1.0000,"
                    "   0,1.0000"
                )
                continue
            if br.b != 0.0:
                charging.append(br.id)
            tap = 1.0 if br.tap_ratio is None else br.tap_ratio
            shift = 0.0 if br.shift_deg is None else br.shift_deg
            transformer_lines.append(
                f"{i:6d},{j:6d},     0,{ckt},1,1,1,  0.00000,  0.00000,2,{_quoted('', 12)},"
                f"{int(br.in_service)},   1,1.0000,   0,1.0000,   0,1.0000,   0,1.0000,"
                f"{_quoted('', 12)}"
            )
            transformer_lines.append(f"{_f(br.r, 10)},{_f(br.x, 10)},{_f(self.net.base_mva, 9)}")
            transformer_lines.append(
                f"{_f(tap)},   0.000,{_f(shift, 8)},{_f(rate_a, 9)},     0.00,{_f(rate_c, 9)},0,"
                "     0, 1.10000, 0.90000, 1.10000, 0.90000, 33, 0, 0.00000, 0.00000, 0.000"
            )
            transformer_lines.append("1.00000,   0.000")
        if charging:
            self.warn(
                "FIELD_DROPPED",
                f"{len(charging)} transformer(s) with line charging b: a RAW transformer "
                "record carries none",
                element_ids=charging,
            )
        return branch_lines, transformer_lines

    def _areas(self) -> list[str]:
        return [
            f"{number:6d},     0,     0.000,   999.990,{_quoted(label, 12)}"
            for label, number in sorted(self.area.items(), key=lambda kv: kv[1])
        ]

    def _zones(self) -> list[str]:
        names = {z.id: z.name for z in self.net.zones}
        return [
            f"{number:6d},{_quoted(names.get(label) or label, 12)}"
            for label, number in sorted(self.zone.items(), key=lambda kv: kv[1])
        ]

    def _storage(self) -> None:
        if self.net.storage:
            self.warn(
                "ELEMENT_DROPPED",
                f"{len(self.net.storage)} storage unit(s) dropped: RAW has no storage record",
                element_ids=[s.id for s in self.net.storage],
            )

    # -- helpers -------------------------------------------------------------------------------

    def _bus(self, bus_id: str) -> Bus:
        return next(b for b in self.net.buses if b.id == bus_id)

    def _area_of(self, bus: Bus) -> int:
        return self.area[bus.area] if bus.area is not None else 1

    def _zone_of(self, bus: Bus) -> int:
        return self.zone[bus.zone] if bus.zone is not None else 1


def _f(value: float, width: int = 0) -> str:
    """A float at full precision (``.10g``), right-aligned to *width*."""
    return format(value, ".10g").rjust(width)


def _quoted(text: str, width: int) -> str:
    """A single-quoted RAW string field padded to *width* (and cut to it)."""
    return "'" + text[:width].ljust(width) + "'"


def _labels(values: list[str]) -> dict[str, int]:
    """Integer RAW numbers for area/zone labels: a label that is an integer keeps it, the rest
    are numbered after the largest, in first-seen order."""
    seen: list[str] = []
    for v in values:
        if v not in seen:
            seen.append(v)
    out: dict[str, int] = {}
    taken: set[int] = set()
    for label in seen:
        if label.isdigit() and int(label) > 0 and int(label) not in taken:
            out[label] = int(label)
            taken.add(int(label))
    next_number = max(taken, default=0) + 1
    for label in seen:
        if label not in out:
            out[label] = next_number
            taken.add(next_number)
            next_number += 1
    return out


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
        "RAW_ID_RENUMBERED",
        f"{len(buses)} bus id(s) do not carry a unique RAW bus number (bus-<I>); numbered by "
        "position from 1",
        bus_ids=renumbered,
    )
    return {bus.id: k for k, bus in enumerate(buses, start=1)}


def _element_ids(
    prefix: str, elements: Sequence[_Attached], number: dict[str, int], warn: _Warn
) -> dict[str, str]:
    """RAW ``ID`` per element: the one in ``<prefix>-<I>-<ID>`` when it names the element's own
    bus and is unique at it, else ``1``, ``2``, ... per bus."""
    out: dict[str, str] = {}
    used: dict[int, set[str]] = {}
    renumbered: list[str] = []
    pattern = re.compile(rf"^{prefix}-(\d+)-(.{{1,2}})$")
    for element in elements:
        bus_number = number[element.bus]
        match = pattern.match(element.id)
        taken = used.setdefault(bus_number, set())
        if match is not None and int(match.group(1)) == bus_number and match.group(2) not in taken:
            out[element.id] = match.group(2)
        else:
            candidate = 1
            while str(candidate) in taken:
                candidate += 1
            out[element.id] = str(candidate)
            renumbered.append(element.id)
        taken.add(out[element.id])
    if renumbered:
        warn(
            "RAW_ID_RENUMBERED",
            f"{len(renumbered)} {prefix} id(s) do not carry a RAW ID ({prefix}-<I>-<ID> at "
            "their own bus); given '1', '2', ... per bus",
            element_ids=renumbered,
        )
    return out


def _circuit_ids(branches: Sequence[Branch], number: dict[str, int], warn: _Warn) -> dict[str, str]:
    """RAW ``CKT`` per branch: the one in ``branch-<I>-<J>-<CKT>`` when it names the branch's
    own buses and is unique between them, else ``1``, ``2``, ... per bus pair."""
    out: dict[str, str] = {}
    used: dict[tuple[int, int], set[str]] = {}
    renumbered: list[str] = []
    pattern = re.compile(r"^branch-(\d+)-(\d+)-(.{1,2})$")
    for br in branches:
        pair = (number[br.from_bus], number[br.to_bus])
        taken = used.setdefault(pair, set())
        match = pattern.match(br.id)
        if (
            match is not None
            and (int(match.group(1)), int(match.group(2))) == pair
            and match.group(3) not in taken
        ):
            out[br.id] = match.group(3)
        else:
            candidate = 1
            while str(candidate) in taken:
                candidate += 1
            out[br.id] = str(candidate)
            renumbered.append(br.id)
        taken.add(out[br.id])
    if renumbered:
        warn(
            "RAW_ID_RENUMBERED",
            f"{len(renumbered)} branch id(s) do not carry a RAW circuit id "
            "(branch-<I>-<J>-<CKT> between their own buses); given '1', '2', ... per bus pair",
            element_ids=renumbered,
        )
    return out
