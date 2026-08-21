"""MATPOWER case-file (``.m``) importer.

A parser, not a MATLAB interpreter: it recognises ``mpc.<name> = <scalar>;``,
``mpc.<name> = [ rows ];`` and ``mpc.<name> = { ... };`` statements, tolerates ``%`` comments,
tabs, blank lines, CRLF, scientific notation, rows split by ``;`` or newlines, and ignores every
field it does not know (``mpc.version`` is not checked; the caseformat v2 column layout is
assumed). Read: ``baseMVA``, ``bus``, ``gen``, ``branch`` and the optional ``gencost``.
``bus_name`` is skipped because :class:`~mambo_power.model.Bus` carries no name field.

Column mapping follows the MATPOWER manual (wave M1 design items 3, 4 and 6; W1 extract §2).
Units stay physical — MW, MVAr, kV, degrees, branch impedances in pu on ``baseMVA`` — exactly
as the file stores them. Derived ids: ``bus-<BUS_I>``, ``gen-<row>``, ``branch-<row>``,
``load-<BUS_I>``, ``shunt-<BUS_I>``; loads and shunts are emitted only for non-zero rows.

Three conditions are repaired rather than rejected, and each repair is reported as an
:class:`~mambo_power.model.ImportWarning` — typed, in the
:class:`~mambo_power.io.report.ImportReport` returned by :func:`load_with_report` /
:func:`loads_with_report`, and as the ``CODE: message`` string in the legacy list returned by
:func:`load_with_warnings` / :func:`loads_with_warnings`:

* ``BASE_KV_REPLACED`` — ``BASE_KV <= 0`` becomes ``1.0`` (CDF-derived cases carry 0 for
  "unknown");
* ``GENCOST_REACTIVE_IGNORED`` — a ``gencost`` with ``2 * ngen`` rows (reactive costs
  appended) keeps the first ``ngen`` rows;
* ``ISLAND_DEACTIVATED`` — buses the slack cannot reach over in-service branches are switched
  off with their elements by :func:`mambo_power.model.repair_islands_entities` *before* the
  network is validated (W4, design item 4: the importer repairs, the model stays strict).

Everything else that is wrong with the *file* raises :class:`MatpowerImportError`; everything
that is wrong with the *network* (no slack, dangling bus, ...) is left to
:class:`~mambo_power.model.Network` validation, which raises
:class:`~mambo_power.model.NetworkValidationError`. :func:`load` / :func:`loads` discard the
warnings.
"""

from __future__ import annotations

import math
import re
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
    GeneratorCost,
    ImportWarning,
    Load,
    Network,
    PiecewiseCost,
    PolynomialCost,
    Shunt,
    Zone,
    repair_islands_entities,
)

__all__ = [
    "ImportReport",
    "MatpowerImportCode",
    "MatpowerImportError",
    "load",
    "load_with_report",
    "load_with_warnings",
    "loads",
    "loads_with_report",
    "loads_with_warnings",
]

MatpowerImportCode = Literal[
    "MISSING_BASE_MVA",
    "MISSING_SECTION",
    "UNTERMINATED_MATRIX",
    "BAD_NUMBER",
    "BAD_ROW",
]
"""The closed set of importer error codes (wave M1 design item 5, ported from W1)."""

DEFAULT_BASE_KV = 1.0
"""Substituted for ``BASE_KV <= 0`` (W1 convention); each substitution is warned."""

_MIN_COLUMNS = {"bus": 13, "gen": 10, "branch": 11, "gencost": 4}
_BUS_TYPES: dict[int, tuple[BusType, bool]] = {
    3: ("slack", True),
    2: ("pv", True),
    1: ("pq", True),
    4: ("pq", False),
}
_ASSIGNMENT = re.compile(r"^\s*mpc\.([A-Za-z_]\w*)\s*=\s*(.*)$")


class MatpowerImportError(Exception):
    """A defect in the case *file*; ``code`` is stable, ``line`` is 1-based when known."""

    code: MatpowerImportCode
    line: int | None

    def __init__(self, code: MatpowerImportCode, message: str, line: int | None = None) -> None:
        self.code = code
        self.line = line
        super().__init__(message)

    def __str__(self) -> str:
        text = f"{self.code}: {super().__str__()}"
        return f"{text} (line {self.line})" if self.line is not None else text


# --- public API -------------------------------------------------------------------------------


def load(source: str | PathLike[str]) -> Network:
    """Parse the MATPOWER case file at ``source``; repair warnings are discarded."""
    return load_with_warnings(source)[0]


def loads(text: str) -> Network:
    """Parse MATPOWER case text; repair warnings are discarded."""
    return loads_with_warnings(text)[0]


def load_with_warnings(source: str | PathLike[str]) -> tuple[Network, list[str]]:
    """Parse the file at ``source`` and return ``(network, warnings)`` with string warnings.

    Each string is ``str(warning)`` of the typed warning :func:`load_with_report` returns \u2014
    ``CODE: message`` \u2014 kept as ``list[str]`` for M1 callers.
    """
    net, report = load_with_report(source)
    return net, report.as_strings()


def loads_with_warnings(text: str) -> tuple[Network, list[str]]:
    """Parse case text and return ``(network, warnings)`` with string warnings."""
    net, report = loads_with_report(text)
    return net, report.as_strings()


def load_with_report(source: str | PathLike[str]) -> tuple[Network, ImportReport]:
    """Parse the file at ``source`` and return ``(network, report)`` with typed warnings."""
    text = Path(source).read_text(encoding="utf-8-sig", errors="replace")
    return loads_with_report(text)


def loads_with_report(text: str) -> tuple[Network, ImportReport]:
    """Parse case text and return ``(network, report)``; see the module docstring."""
    # A leading BOM is not whitespace and would hide an ``mpc.`` assignment on the first line.
    case = _scan(text.lstrip("\ufeff"))
    net, warnings = _build(case)
    return net, ImportReport(warnings=warnings)


# --- scanning: text -> matrices and scalars -----------------------------------------------------


@dataclass(frozen=True)
class _Row:
    line: int
    tokens: list[str]


@dataclass(frozen=True)
class _Matrix:
    rows: list[_Row]


@dataclass(frozen=True)
class _Scalar:
    line: int
    text: str


@dataclass
class _Case:
    scalars: dict[str, _Scalar]
    matrices: dict[str, _Matrix]


def _strip_comment(line: str) -> str:
    """Drop ``%`` to end of line unless the ``%`` sits inside a single-quoted string."""
    quoted = False
    for index, char in enumerate(line):
        if char == "'":
            quoted = not quoted
        elif char == "%" and not quoted:
            return line[:index]
    return line


def _scan(text: str) -> _Case:
    lines = [_strip_comment(line) for line in text.splitlines()]
    case = _Case(scalars={}, matrices={})
    index = 0
    while index < len(lines):
        match = _ASSIGNMENT.match(lines[index])
        if match is None:
            index += 1
            continue
        name, rest = match.group(1), match.group(2).strip()
        opener_line = index + 1
        if rest.startswith("["):
            rows, index = _collect_block(lines, index, rest[1:], "]", opener_line)
            case.matrices[name] = _Matrix(rows)
        elif rest.startswith("{"):
            _, index = _collect_block(lines, index, rest[1:], "}", opener_line)
        else:
            case.scalars[name] = _Scalar(opener_line, rest.split(";", 1)[0].strip())
            index += 1
    return case


def _collect_block(
    lines: list[str], index: int, first: str, closer: str, opener_line: int
) -> tuple[list[_Row], int]:
    """Gather rows from ``first`` (text after the opener) until ``closer``; return next index."""
    rows: list[_Row] = []
    text = first
    while True:
        end = text.find(closer)
        body = text if end < 0 else text[:end]
        for segment in body.split(";"):
            tokens = segment.replace(",", " ").split()
            if tokens:
                rows.append(_Row(index + 1, tokens))
        if end >= 0:
            return rows, index + 1
        index += 1
        if index >= len(lines):
            raise MatpowerImportError(
                "UNTERMINATED_MATRIX",
                f"matrix opened at line {opener_line} is never closed with '{closer}'",
                opener_line,
            )
        text = lines[index]


# --- typing: tokens -> numbers ------------------------------------------------------------------


def _number(token: str, what: str, line: int) -> float:
    try:
        value = float(token)
    except ValueError:
        raise MatpowerImportError(
            "BAD_NUMBER", f"{what}: {token!r} is not a number", line
        ) from None
    if not math.isfinite(value):
        raise MatpowerImportError("BAD_NUMBER", f"{what}: {token!r} is not finite", line)
    return value


def _integer(value: float, what: str, line: int) -> int:
    if value != int(value):
        raise MatpowerImportError("BAD_NUMBER", f"{what}: {value!r} is not an integer", line)
    return int(value)


def _matrix(case: _Case, name: str, required: bool) -> list[tuple[int, list[float]]]:
    """Numeric rows of ``mpc.<name>`` with their line numbers; rectangular, wide enough."""
    block = case.matrices.get(name)
    if block is None:
        if required:
            raise MatpowerImportError("MISSING_SECTION", f"mpc.{name} = [ ... ]; not found")
        return []
    minimum = _MIN_COLUMNS[name]
    width: int | None = None
    rows: list[tuple[int, list[float]]] = []
    for row in block.rows:
        if len(row.tokens) < minimum:
            raise MatpowerImportError(
                "BAD_ROW",
                f"mpc.{name} row has {len(row.tokens)} columns, expected >= {minimum}",
                row.line,
            )
        if width is None:
            width = len(row.tokens)
        elif len(row.tokens) != width:
            raise MatpowerImportError(
                "BAD_ROW",
                f"mpc.{name} row has {len(row.tokens)} columns, earlier rows have {width}",
                row.line,
            )
        values = [_number(token, f"mpc.{name}", row.line) for token in row.tokens]
        rows.append((row.line, values))
    return rows


# --- building: matrices -> Network --------------------------------------------------------------


def _build(case: _Case) -> tuple[Network, list[ImportWarning]]:
    warnings: list[ImportWarning] = []
    base = case.scalars.get("baseMVA")
    if base is None:
        raise MatpowerImportError("MISSING_BASE_MVA", "mpc.baseMVA = ...; not found")
    base_mva = _number(base.text, "mpc.baseMVA", base.line)

    bus_rows = _matrix(case, "bus", required=True)
    gen_rows = _matrix(case, "gen", required=True)
    branch_rows = _matrix(case, "branch", required=True)
    gencost_rows = _matrix(case, "gencost", required=False)

    buses: list[Bus] = []
    loads: list[Load] = []
    shunts: list[Shunt] = []
    zones: dict[str, Zone] = {}
    for line, row in bus_rows:
        number = _integer(row[0], "mpc.bus BUS_I", line)
        bus_id = f"bus-{number}"
        type_code = _integer(row[1], "mpc.bus BUS_TYPE", line)
        if type_code not in _BUS_TYPES:
            raise MatpowerImportError(
                "BAD_NUMBER", f"mpc.bus BUS_TYPE must be 1, 2, 3 or 4, got {type_code}", line
            )
        bus_type, in_service = _BUS_TYPES[type_code]
        base_kv = row[9]
        if not base_kv > 0:
            warnings.append(
                ImportWarning(
                    code="BASE_KV_REPLACED",
                    message=(
                        f"{bus_id}: BASE_KV is {base_kv:g}; base_kv set to {DEFAULT_BASE_KV} "
                        f"(line {line})"
                    ),
                    bus_ids=[bus_id],
                )
            )
            base_kv = DEFAULT_BASE_KV
        zone = _label(row[10])
        zones.setdefault(zone, Zone(id=zone))
        buses.append(
            Bus(
                id=bus_id,
                base_kv=base_kv,
                type=bus_type,
                in_service=in_service,
                vm_pu=row[7],
                va_deg=row[8],
                v_min_pu=row[12],
                v_max_pu=row[11],
                area=_label(row[6]),
                zone=zone,
            )
        )
        if row[2] != 0 or row[3] != 0:
            loads.append(Load(id=f"load-{number}", bus=bus_id, p_mw=row[2], q_mvar=row[3]))
        if row[4] != 0 or row[5] != 0:
            shunts.append(Shunt(id=f"shunt-{number}", bus=bus_id, g_mw=row[4], b_mvar=row[5]))

    costs = _costs(gencost_rows, len(gen_rows), warnings)
    generators = [
        Generator(
            id=f"gen-{k}",
            bus=f"bus-{_integer(row[0], 'mpc.gen GEN_BUS', line)}",
            p_mw=row[1],
            q_mvar=row[2],
            p_min_mw=row[9],
            p_max_mw=row[8],
            q_min_mvar=row[4],
            q_max_mvar=row[3],
            v_set_pu=row[5],
            in_service=row[7] > 0,
            cost=cost,
        )
        for k, ((line, row), cost) in enumerate(zip(gen_rows, costs, strict=True), start=1)
    ]

    branches = [
        Branch(
            id=f"branch-{k}",
            from_bus=f"bus-{_integer(row[0], 'mpc.branch F_BUS', line)}",
            to_bus=f"bus-{_integer(row[1], 'mpc.branch T_BUS', line)}",
            r=row[2],
            x=row[3],
            b=row[4],
            rating_mva=row[5] if row[5] > 0 else None,
            tap_ratio=row[8] if row[8] != 0 else None,
            shift_deg=row[9] if row[9] != 0 else None,
            in_service=row[10] > 0,
        )
        for k, (line, row) in enumerate(branch_rows, start=1)
    ]

    # W4: switch off islands on the raw entities, before the model's strict validation.
    buses, branches, generators, loads, shunts, storage, island_warnings = repair_islands_entities(
        buses, branches, generators, loads, shunts, []
    )
    warnings.extend(island_warnings)

    net = Network(
        base_mva=base_mva,
        buses=buses,
        branches=branches,
        generators=generators,
        loads=loads,
        shunts=shunts,
        storage=storage,
        zones=list(zones.values()),
    )
    return net, warnings


def _costs(
    rows: list[tuple[int, list[float]]], n_gen: int, warnings: list[ImportWarning]
) -> list[GeneratorCost | None]:
    if not rows:
        return [None] * n_gen
    if len(rows) == 2 * n_gen and n_gen > 0:
        warnings.append(
            ImportWarning(
                code="GENCOST_REACTIVE_IGNORED",
                message=(
                    f"mpc.gencost has {len(rows)} rows for {n_gen} generators; the second half "
                    f"(reactive power costs) is ignored (line {rows[0][0]})"
                ),
            )
        )
        rows = rows[:n_gen]
    elif len(rows) != n_gen:
        raise MatpowerImportError(
            "BAD_ROW",
            f"mpc.gencost has {len(rows)} rows, expected {n_gen} or {2 * n_gen} (one per gen)",
            rows[0][0],
        )
    costs: list[GeneratorCost | None] = []
    for line, row in rows:
        model = _integer(row[0], "mpc.gencost MODEL", line)
        n_cost = _integer(row[3], "mpc.gencost NCOST", line)
        if n_cost < 1:
            raise MatpowerImportError(
                "BAD_NUMBER", f"mpc.gencost NCOST must be >= 1, got {n_cost}", line
            )
        startup, shutdown = row[1], row[2]
        values = row[4:]
        if model == 2:
            if len(values) < n_cost:
                raise MatpowerImportError(
                    "BAD_ROW",
                    f"mpc.gencost polynomial row needs {n_cost} coefficients, has {len(values)}",
                    line,
                )
            costs.append(
                PolynomialCost(coefficients=values[:n_cost], startup=startup, shutdown=shutdown)
            )
        elif model == 1:
            if len(values) < 2 * n_cost:
                raise MatpowerImportError(
                    "BAD_ROW",
                    f"mpc.gencost piecewise row needs {2 * n_cost} values, has {len(values)}",
                    line,
                )
            points = [(values[2 * i], values[2 * i + 1]) for i in range(n_cost)]
            costs.append(PiecewiseCost(points=points, startup=startup, shutdown=shutdown))
        else:
            raise MatpowerImportError(
                "BAD_NUMBER", f"mpc.gencost MODEL must be 1 or 2, got {model}", line
            )
    return costs


def _label(value: float) -> str:
    """Integer-valued columns (AREA, ZONE) as compact strings: ``1.0`` -> ``"1"``."""
    return str(int(value)) if value == int(value) else repr(value)
