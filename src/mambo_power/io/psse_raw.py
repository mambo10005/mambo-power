"""PSS/E RAW version 33 importer (wave M8, W4).

A record parser for the v33 layout only (``REV`` must be 33). It reads the case identification
(``SBASE``), bus, load, fixed shunt, generator, non-transformer branch, two-winding transformer,
area and zone sections and ignores every other record — three-winding transformers, switched
shunts, owners, DC lines, FACTS, ... — with **one report entry per ignored record**. Fields are
comma-separated; single-quoted strings may contain commas and slashes; ``/`` outside quotes
starts a comment; blank lines are skipped; each section ends with a line whose first field is
``0``; ``Q`` (or the end of the text) after the zone section ends the file. Field order and
units follow grg-pssedata's ``struct.py`` and the conversions follow MATPOWER's
``psse_convert.m`` / ``psse_convert_xfmr.m`` (both BSD-3; ``record/m8-research.md`` §3).

Ids: ``bus-<I>``; ``load-<I>-<ID>``, ``shunt-<I>-<ID>``, ``gen-<I>-<ID>`` (``ID`` stripped);
branches and transformers ``branch-<I>-<J>-<CKT>``; folded shunts ``shunt-branch-<I>-<J>-<CKT>-i``
/ ``-j`` and ``shunt-xfmr-<I>-<J>-<CKT>``. Every transformer record yields a
:class:`~mambo_power.model.Branch` with ``kind="transformer"`` (set from the record type, not
inferred from the tap); branch records yield ``kind="line"``.

Conversions (MATPOWER's rules):

* load ``P = PL + IP·VM + YP·VM²`` (same for Q) at the bus's ``VM`` when any of ``IP IQ YP YQ``
  is non-zero — reported ``RAW_LOAD_ZIP_FOLDED``;
* branch end shunts ``GI BI`` / ``GJ BJ`` (pu on ``SBASE``) become :class:`~mambo_power.model.Shunt`
  entries — reported ``RAW_BRANCH_END_SHUNT_FOLDED``;
* transformer impedance per ``CZ``: 1 = pu on ``SBASE`` as is; 2 = pu on ``SBASE1-2`` and
  ``NOMV1`` (0 = the from bus's base kV), scaled by ``(NOMV1/BASKV_I)² · SBASE/SBASE1-2``; 3 =
  load loss in W and ``|Z|`` pu on the winding base, ``R = R/(1e6·SBASE1-2)``,
  ``X = sqrt(|Z|² − R²)``, then scaled as for 2;
* tap per ``CW``: ``tap = t1/t2`` with ``t = WINDV`` (1, pu of bus base), ``WINDV/BASKV`` (2, kV)
  or ``WINDV·NOMV/BASKV`` (3, pu of nominal); ``shift = ANG1``; ``rating = RATA1``; ``b = 0``;
* magnetising admittance per ``CM`` becomes a shunt at the from bus: 1 = ``MAG1 + j·MAG2`` pu on
  ``SBASE``; 2 = ``MAG1`` no-load loss in W and ``MAG2`` exciting current pu on the winding base,
  ``G = MAG1/(1e6·SBASE1-2)``, ``B = −sqrt(MAG2² − G²)``, both scaled to the system base —
  reported ``RAW_XFMR_MAGNETISING_FOLDED``.

RAW carries no economic data at all (no cost section exists in the format), so every generator
imports with ``cost=None`` and the report says so once (``RAW_NO_COSTS``; spec A3). ``BASKV <= 0``
is repaired to 1.0 (``BASE_KV_REPLACED``) and islands are switched off before validation
(``ISLAND_DEACTIVATED``), exactly as :mod:`mambo_power.io.matpower` does. Defects in the *file*
raise :class:`RawImportError`; defects in the *network* are left to
:class:`~mambo_power.model.Network` validation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Literal

from mambo_power.io.report import ImportReport
from mambo_power.model import (
    Branch,
    Bus,
    BusType,
    Generator,
    ImportIssue,
    Load,
    Network,
    Shunt,
    Zone,
    repair_islands_entities,
)

__all__ = [
    "CODES",
    "ImportReport",
    "RawImportCode",
    "RawImportError",
    "load",
    "load_with_report",
    "loads",
    "loads_with_report",
]

CODES: tuple[str, ...] = (
    "BASE_KV_REPLACED",
    "ISLAND_DEACTIVATED",
    "RAW_NO_COSTS",
    "RAW_LOAD_ZIP_FOLDED",
    "RAW_BRANCH_END_SHUNT_FOLDED",
    "RAW_XFMR_MAGNETISING_FOLDED",
    "RAW_THREE_WINDING_IGNORED",
    "RAW_SWITCHED_SHUNT_IGNORED",
    "RAW_SECTION_IGNORED",
)
"""Every report code this importer can emit (its documented limitations)."""

RawImportCode = Literal[
    "BAD_HEADER",
    "UNSUPPORTED_VERSION",
    "BAD_NUMBER",
    "BAD_RECORD",
    "UNTERMINATED_SECTION",
    "UNKNOWN_BUS",
]
"""The closed set of importer error codes."""

DEFAULT_BASE_KV = 1.0
"""Substituted for ``BASKV <= 0`` (the ``io.matpower`` convention); each substitution is warned."""

_BUS_TYPES: dict[int, tuple[BusType, bool]] = {
    3: ("slack", True),
    2: ("pv", True),
    1: ("pq", True),
    4: ("pq", False),
}

# v33 section order after the three case-identification lines (grg-pssedata ``io.py``).
_SECTIONS = (
    "bus",
    "load",
    "fixed shunt",
    "generator",
    "branch",
    "transformer",
    "area",
    "two-terminal dc",
    "vsc dc",
    "impedance correction",
    "multi-terminal dc",
    "multi-section line",
    "zone",
    "inter-area transfer",
    "owner",
    "facts",
    "switched shunt",
    "gne",
    "induction machine",
)
_REQUIRED_THROUGH = "zone"
# Lines per record in the sections that are ignored (multi-terminal DC is computed per record).
_IGNORED_RECORD_LINES = {
    "two-terminal dc": 3,
    "vsc dc": 3,
    "impedance correction": 1,
    "multi-section line": 1,
    "inter-area transfer": 1,
    "owner": 1,
    "facts": 1,
    "switched shunt": 1,
    "gne": 1,
    "induction machine": 1,
}


class RawImportError(Exception):
    """A defect in the RAW *file*; ``code`` is stable, ``line`` is 1-based when known."""

    code: RawImportCode
    line: int | None

    def __init__(self, code: RawImportCode, message: str, line: int | None = None) -> None:
        self.code = code
        self.line = line
        super().__init__(message)

    def __str__(self) -> str:
        text = f"{self.code}: {super().__str__()}"
        return f"{text} (line {self.line})" if self.line is not None else text


# --- public API -------------------------------------------------------------------------------


def load(source: str | PathLike[str]) -> Network:
    """Parse the RAW v33 file at ``source``; the report is discarded."""
    return load_with_report(source)[0]


def loads(text: str) -> Network:
    """Parse RAW v33 text; the report is discarded."""
    return loads_with_report(text)[0]


def load_with_report(source: str | PathLike[str]) -> tuple[Network, ImportReport]:
    """Parse the file at ``source`` and return ``(network, report)``."""
    text = Path(source).read_text(encoding="utf-8-sig", errors="replace")
    return loads_with_report(text)


def loads_with_report(text: str) -> tuple[Network, ImportReport]:
    """Parse RAW v33 text and return ``(network, report)``; see the module docstring."""
    case = _scan(text.lstrip(chr(0xFEFF)))
    net, warnings = _build(case)
    return net, ImportReport(warnings=warnings)


# --- scanning: text -> records per section --------------------------------------------------------


@dataclass(frozen=True)
class _Record:
    line: int
    fields: list[str]
    extra: list[list[str]]
    """Continuation lines (transformer records: lines 2..4 or 2..5)."""


@dataclass
class _Case:
    base_mva: float
    sections: dict[str, list[_Record]]


def _split(line: str) -> list[str]:
    """Fields of one line: comma-separated, quotes respected, ``/`` comment stripped."""
    fields: list[str] = []
    current: list[str] = []
    quoted = False
    for char in line:
        if char == "'":
            quoted = not quoted
        elif char == "/" and not quoted:
            break
        elif char == "," and not quoted:
            fields.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail or fields:
        fields.append(tail)
    return fields


def _scan(text: str) -> _Case:
    lines = text.splitlines()
    if len(lines) < 3:
        raise RawImportError("BAD_HEADER", "a RAW file starts with three case-identification lines")
    header = _split(lines[0])
    if len(header) < 3:
        raise RawImportError("BAD_HEADER", "case identification needs IC, SBASE, REV", 1)
    ic = _integer(_number(header[0], "IC", 1), "IC", 1)
    if ic != 0:
        raise RawImportError("BAD_HEADER", f"IC must be 0 (full case), got {ic}", 1)
    base_mva = _number(header[1], "SBASE", 1)
    rev = _integer(_number(header[2], "REV", 1), "REV", 1)
    if rev != 33:
        raise RawImportError("UNSUPPORTED_VERSION", f"only RAW version 33 is read, got {rev}", 1)

    sections: dict[str, list[_Record]] = {name: [] for name in _SECTIONS}
    index = 3  # 0-based index into ``lines``; lines 2 and 3 are the free-text titles
    for section in _SECTIONS:
        records = sections[section]
        while True:
            if index >= len(lines) or lines[index].strip().upper() == "Q":
                if _SECTIONS.index(section) <= _SECTIONS.index(_REQUIRED_THROUGH) or records:
                    raise RawImportError(
                        "UNTERMINATED_SECTION",
                        f"{section} section is not terminated by a '0' line",
                        index + 1,
                    )
                break
            fields = _split(lines[index])
            index += 1
            if not fields:
                continue
            if fields[0] == "0":
                break
            span = _record_lines(section, fields, index)
            extra = [_split(lines[k]) for k in range(index, min(index + span - 1, len(lines)))]
            if len(extra) != span - 1:
                raise RawImportError(
                    "BAD_RECORD", f"{section} record spans {span} lines; file ends first", index
                )
            records.append(_Record(index, fields, extra))
            index += span - 1
        if index >= len(lines) or lines[index].strip().upper() == "Q":
            if _SECTIONS.index(section) >= _SECTIONS.index(_REQUIRED_THROUGH):
                break
    return _Case(base_mva=base_mva, sections=sections)


def _record_lines(section: str, fields: list[str], line: int) -> int:
    """How many lines the record starting with ``fields`` occupies."""
    if section == "transformer":
        _require(fields, 3, section, line)
        k = _integer(_number(fields[2], "transformer K", line), "transformer K", line)
        return 4 if k == 0 else 5
    if section == "multi-terminal dc":
        _require(fields, 4, section, line)
        counts = (
            _integer(_number(fields[i], f"{section} count", line), section, line) for i in (1, 2, 3)
        )
        return 1 + sum(counts)
    return _IGNORED_RECORD_LINES.get(section, 1)


# --- typing ------------------------------------------------------------------------------------


def _number(token: str, what: str, line: int) -> float:
    try:
        value = float(token)
    except ValueError:
        raise RawImportError("BAD_NUMBER", f"{what}: {token!r} is not a number", line) from None
    if not math.isfinite(value):
        raise RawImportError("BAD_NUMBER", f"{what}: {token!r} is not finite", line)
    return value


def _integer(value: float, what: str, line: int) -> int:
    if value != int(value):
        raise RawImportError("BAD_NUMBER", f"{what}: {value!r} is not an integer", line)
    return int(value)


def _require(fields: list[str], minimum: int, what: str, line: int) -> None:
    if len(fields) < minimum:
        raise RawImportError(
            "BAD_RECORD", f"{what} record has {len(fields)} fields, expected >= {minimum}", line
        )


def _floats(fields: list[str], what: str, line: int) -> list[float]:
    return [_number(f, what, line) for f in fields]


def _rating(value: float) -> float | None:
    return value if value > 0 else None


# --- building ----------------------------------------------------------------------------------


@dataclass
class _BusInfo:
    id: str
    base_kv: float
    vm: float


class _Builder:
    def __init__(self, case: _Case) -> None:
        self.case = case
        self.base_mva = case.base_mva
        self.warnings: list[ImportIssue] = []
        self.buses: list[Bus] = []
        self.loads: list[Load] = []
        self.shunts: list[Shunt] = []
        self.generators: list[Generator] = []
        self.branches: list[Branch] = []
        self.zones: dict[str, Zone] = {}
        self.info: dict[int, _BusInfo] = {}

    def warn(self, code: str, message: str, **ids: list[str]) -> None:
        self.warnings.append(ImportIssue(code=code, message=message, **ids))  # type: ignore[arg-type]

    def bus_ref(self, token: str, what: str, line: int) -> _BusInfo:
        number = abs(_integer(_number(token, what, line), what, line))
        try:
            return self.info[number]
        except KeyError:
            raise RawImportError(
                "UNKNOWN_BUS", f"{what}: bus {number} is not in the bus section", line
            ) from None

    # -- sections ------------------------------------------------------------------------------

    def read_buses(self) -> None:
        for rec in self.case.sections["bus"]:
            f, line = rec.fields, rec.line
            _require(f, 9, "bus", line)
            number = _integer(_number(f[0], "bus I", line), "bus I", line)
            bus_id = f"bus-{number}"
            base_kv = _number(f[2], "bus BASKV", line)
            if not base_kv > 0:
                self.warn(
                    "BASE_KV_REPLACED",
                    f"{bus_id}: BASKV is {base_kv:g}; base_kv set to {DEFAULT_BASE_KV} "
                    f"(line {line})",
                    bus_ids=[bus_id],
                )
                base_kv = DEFAULT_BASE_KV
            ide = _integer(_number(f[3], "bus IDE", line), "bus IDE", line)
            if ide not in _BUS_TYPES:
                raise RawImportError("BAD_NUMBER", f"bus IDE must be 1, 2, 3 or 4, got {ide}", line)
            bus_type, in_service = _BUS_TYPES[ide]
            area = _label(f[4], "bus AREA", line)
            zone = _label(f[5], "bus ZONE", line)
            self.zones.setdefault(zone, Zone(id=zone))
            vm, va = _number(f[7], "bus VM", line), _number(f[8], "bus VA", line)
            v_max = v_min = None
            if len(f) >= 11:
                v_max, v_min = _number(f[9], "bus NVHI", line), _number(f[10], "bus NVLO", line)
            self.buses.append(
                Bus(
                    id=bus_id,
                    base_kv=base_kv,
                    type=bus_type,
                    in_service=in_service,
                    vm_pu=vm,
                    va_deg=va,
                    v_min_pu=v_min,
                    v_max_pu=v_max,
                    area=area,
                    zone=zone,
                )
            )
            self.info[number] = _BusInfo(bus_id, base_kv, vm)

    def read_loads(self) -> None:
        for rec in self.case.sections["load"]:
            f, line = rec.fields, rec.line
            _require(f, 11, "load", line)
            bus = self.bus_ref(f[0], "load I", line)
            load_id = f"load-{f[0].strip()}-{f[1].strip()}"
            status = _integer(_number(f[2], "load STATUS", line), "load STATUS", line)
            pl, ql, ip, iq, yp, yq = _floats(f[5:11], "load", line)
            p, q = pl, ql
            if any(v != 0 for v in (ip, iq, yp, yq)):
                vm = bus.vm
                p = pl + ip * vm + yp * vm * vm
                q = ql + iq * vm + yq * vm * vm
                self.warn(
                    "RAW_LOAD_ZIP_FOLDED",
                    f"{load_id}: IP/IQ/YP/YQ ({ip:g}/{iq:g}/{yp:g}/{yq:g}) folded into p_mw/q_mvar "
                    f"at VM = {vm:g} of {bus.id} (line {line})",
                    element_ids=[load_id],
                    bus_ids=[bus.id],
                )
            self.loads.append(Load(id=load_id, bus=bus.id, p_mw=p, q_mvar=q, in_service=status > 0))

    def read_fixed_shunts(self) -> None:
        for rec in self.case.sections["fixed shunt"]:
            f, line = rec.fields, rec.line
            _require(f, 5, "fixed shunt", line)
            bus = self.bus_ref(f[0], "fixed shunt I", line)
            status = _integer(_number(f[2], "fixed shunt STATUS", line), "fixed shunt STATUS", line)
            gl, bl = _floats(f[3:5], "fixed shunt", line)
            self.shunts.append(
                Shunt(
                    id=f"shunt-{f[0].strip()}-{f[1].strip()}",
                    bus=bus.id,
                    g_mw=gl,
                    b_mvar=bl,
                    in_service=status > 0,
                )
            )

    def read_generators(self) -> None:
        for rec in self.case.sections["generator"]:
            f, line = rec.fields, rec.line
            _require(f, 18, "generator", line)
            bus = self.bus_ref(f[0], "generator I", line)
            pg, qg, qt, qb, vs = _floats(f[2:7], "generator", line)
            stat = _integer(_number(f[14], "generator STAT", line), "generator STAT", line)
            pt, pb = _floats(f[16:18], "generator", line)
            self.generators.append(
                Generator(
                    id=f"gen-{f[0].strip()}-{f[1].strip()}",
                    bus=bus.id,
                    p_mw=pg,
                    q_mvar=qg,
                    p_min_mw=pb,
                    p_max_mw=pt,
                    q_min_mvar=qb,
                    q_max_mvar=qt,
                    v_set_pu=vs,
                    in_service=stat > 0,
                    cost=None,
                )
            )
        if self.generators:
            self.warn(
                "RAW_NO_COSTS",
                f"RAW carries no cost data; all {len(self.generators)} generators imported "
                "with cost=None",
                element_ids=[g.id for g in self.generators],
            )

    def read_branches(self) -> None:
        for rec in self.case.sections["branch"]:
            f, line = rec.fields, rec.line
            _require(f, 14, "branch", line)
            i, j = self.bus_ref(f[0], "branch I", line), self.bus_ref(f[1], "branch J", line)
            key = f"{i.id[4:]}-{j.id[4:]}-{f[2].strip()}"
            r, x, b, rate_a = _floats(f[3:7], "branch", line)
            gi, bi, gj, bj = _floats(f[9:13], "branch", line)
            st = _integer(_number(f[13], "branch ST", line), "branch ST", line)
            self.branches.append(
                Branch(
                    id=f"branch-{key}",
                    from_bus=i.id,
                    to_bus=j.id,
                    r=r,
                    x=x,
                    b=b,
                    rating_mva=_rating(rate_a),
                    in_service=st > 0,
                    kind="line",
                )
            )
            for end, bus, g, bb in (("i", i, gi, bi), ("j", j, gj, bj)):
                if g == 0 and bb == 0:
                    continue
                shunt_id = f"shunt-branch-{key}-{end}"
                self.shunts.append(
                    Shunt(
                        id=shunt_id,
                        bus=bus.id,
                        g_mw=g * self.base_mva,
                        b_mvar=bb * self.base_mva,
                        in_service=st > 0,
                    )
                )
                self.warn(
                    "RAW_BRANCH_END_SHUNT_FOLDED",
                    f"branch-{key}: end shunt G{end.upper()}/B{end.upper()} = {g:g}/{bb:g} pu "
                    f"became "
                    f"{shunt_id} at {bus.id} (line {line})",
                    element_ids=[f"branch-{key}", shunt_id],
                    bus_ids=[bus.id],
                )

    def read_transformers(self) -> None:
        for rec in self.case.sections["transformer"]:
            f, line = rec.fields, rec.line
            _require(f, 12, "transformer", line)
            i, j = (
                self.bus_ref(f[0], "transformer I", line),
                self.bus_ref(f[1], "transformer J", line),
            )
            k = _integer(_number(f[2], "transformer K", line), "transformer K", line)
            ckt = f[3].strip()
            key = f"{i.id[4:]}-{j.id[4:]}-{ckt}"
            if k != 0:
                third = self.bus_ref(f[2], "transformer K", line)
                self.warn(
                    "RAW_THREE_WINDING_IGNORED",
                    f"transformer record {i.id[4:]}-{j.id[4:]}-{third.id[4:]}-{ckt} "
                    f"({f[10].strip()!r}) is "
                    f"three-winding; ignored (line {line})",
                    bus_ids=[i.id, j.id, third.id],
                )
                continue
            cw, cz, cm = (
                _integer(_number(f[n], "transformer CW/CZ/CM", line), "CW/CZ/CM", line)
                for n in (4, 5, 6)
            )
            mag1, mag2 = _floats(f[7:9], "transformer MAG", line)
            stat = _integer(_number(f[11], "transformer STAT", line), "transformer STAT", line)
            l2, l3, l4 = rec.extra
            _require(l2, 3, "transformer line 2", line + 1)
            _require(l3, 4, "transformer line 3", line + 2)
            _require(l4, 1, "transformer line 4", line + 3)
            r12, x12, sbase12 = _floats(l2[:3], "transformer line 2", line + 1)
            windv1, nomv1, ang1, rata1 = _floats(l3[:4], "transformer line 3", line + 2)
            windv2 = _number(l4[0], "transformer WINDV2", line + 3)
            nomv2 = _number(l4[1], "transformer NOMV2", line + 3) if len(l4) > 1 else 0.0
            nomv1 = nomv1 if nomv1 > 0 else i.base_kv
            nomv2 = nomv2 if nomv2 > 0 else j.base_kv

            if cz in (2, 3) and not sbase12 > 0:
                raise RawImportError(
                    "BAD_NUMBER", f"transformer {key}: CZ={cz} needs SBASE1-2 > 0", line + 1
                )
            factor = (nomv1 / i.base_kv) ** 2 * self.base_mva / sbase12 if cz in (2, 3) else 1.0
            if cz == 1:
                r, x = r12, x12
            elif cz == 2:
                r, x = r12 * factor, x12 * factor
            elif cz == 3:
                r_w = r12 / (1e6 * sbase12)
                if x12 * x12 < r_w * r_w:
                    raise RawImportError(
                        "BAD_NUMBER", f"transformer {key}: CZ=3 |Z| smaller than R", line + 1
                    )
                r, x = r_w * factor, math.sqrt(x12 * x12 - r_w * r_w) * factor
            else:
                raise RawImportError(
                    "BAD_NUMBER", f"transformer {key}: CZ must be 1, 2 or 3, got {cz}", line
                )

            if cw == 1:
                t1, t2 = windv1, windv2
            elif cw == 2:
                t1, t2 = windv1 / i.base_kv, windv2 / j.base_kv
            elif cw == 3:
                t1, t2 = windv1 * nomv1 / i.base_kv, windv2 * nomv2 / j.base_kv
            else:
                raise RawImportError(
                    "BAD_NUMBER", f"transformer {key}: CW must be 1, 2 or 3, got {cw}", line
                )
            if t2 == 0:
                raise RawImportError("BAD_NUMBER", f"transformer {key}: WINDV2 is 0", line + 3)

            self.branches.append(
                Branch(
                    id=f"branch-{key}",
                    from_bus=i.id,
                    to_bus=j.id,
                    r=r,
                    x=x,
                    b=0.0,
                    rating_mva=_rating(rata1),
                    tap_ratio=t1 / t2,
                    shift_deg=ang1 if ang1 != 0 else None,
                    in_service=stat > 0,
                    kind="transformer",
                )
            )
            if mag1 == 0 and mag2 == 0:
                continue
            if cm == 1:
                g_pu, b_pu = mag1, mag2
            elif cm == 2:
                g_w = mag1 / (1e6 * sbase12) if sbase12 > 0 else 0.0
                if mag2 * mag2 < g_w * g_w:
                    raise RawImportError(
                        "BAD_NUMBER",
                        f"transformer {key}: CM=2 MAG2 smaller than the loss current",
                        line,
                    )
                b_w = -math.sqrt(mag2 * mag2 - g_w * g_w)
                g_pu, b_pu = g_w / factor, b_w / factor
            else:
                raise RawImportError(
                    "BAD_NUMBER", f"transformer {key}: CM must be 1 or 2, got {cm}", line
                )
            shunt_id = f"shunt-xfmr-{key}"
            self.shunts.append(
                Shunt(
                    id=shunt_id,
                    bus=i.id,
                    g_mw=g_pu * self.base_mva,
                    b_mvar=b_pu * self.base_mva,
                    in_service=stat > 0,
                )
            )
            self.warn(
                "RAW_XFMR_MAGNETISING_FOLDED",
                f"branch-{key}: MAG1/MAG2 = {mag1:g}/{mag2:g} (CM={cm}) became {shunt_id} "
                f"at {i.id} "
                f"(line {line})",
                element_ids=[f"branch-{key}", shunt_id],
                bus_ids=[i.id],
            )

    def read_zones(self) -> None:
        for rec in self.case.sections["zone"]:
            f, line = rec.fields, rec.line
            _require(f, 2, "zone", line)
            zone_id = _label(f[0], "zone I", line)
            self.zones[zone_id] = Zone(id=zone_id, name=f[1].strip() or None)

    def read_ignored(self) -> None:
        for section in _SECTIONS:
            if section in (
                "bus",
                "load",
                "fixed shunt",
                "generator",
                "branch",
                "transformer",
                "area",
                "zone",
            ):
                continue
            for rec in self.case.sections[section]:
                f, line = rec.fields, rec.line
                if section == "switched shunt":
                    bus = self.bus_ref(f[0], "switched shunt I", line)
                    binit = f[9] if len(f) > 9 else "?"
                    self.warn(
                        "RAW_SWITCHED_SHUNT_IGNORED",
                        f"switched shunt at {bus.id} ignored; BINIT = {binit} MVAr not folded "
                        f"(line {line})",
                        bus_ids=[bus.id],
                    )
                    continue
                key = ", ".join(x.strip() for x in f[:2])
                self.warn(
                    "RAW_SECTION_IGNORED",
                    f"{section} section is not read; record ({key}) ignored (line {line})",
                )

    # -- assembly ------------------------------------------------------------------------------

    def build(self) -> tuple[Network, list[ImportIssue]]:
        self.read_buses()
        self.read_loads()
        self.read_fixed_shunts()
        self.read_generators()
        self.read_branches()
        self.read_transformers()
        self.read_zones()
        self.read_ignored()
        buses, branches, generators, loads, shunts, storage, island_warnings = (
            repair_islands_entities(
                self.buses, self.branches, self.generators, self.loads, self.shunts, []
            )
        )
        self.warnings.extend(island_warnings)
        net = Network(
            base_mva=self.base_mva,
            buses=buses,
            branches=branches,
            generators=generators,
            loads=loads,
            shunts=shunts,
            storage=storage,
            zones=list(self.zones.values()),
        )
        return net, self.warnings


def _build(case: _Case) -> tuple[Network, list[ImportIssue]]:
    return _Builder(case).build()


def _label(token: str, what: str, line: int) -> str:
    """Integer-valued fields (AREA, ZONE) as compact strings: ``1`` / ``1.0`` -> ``"1"``."""
    value = _number(token, what, line)
    return str(int(value)) if value == int(value) else repr(value)
