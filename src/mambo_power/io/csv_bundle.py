"""CSV bundle: one directory, ``manifest.json`` plus one CSV per entity table (wave M8, W5).

The bundle is a machine-facing, bit-exact spelling of the native schema (spec A5). It exists so
a :class:`~mambo_power.model.Network` can be inspected and edited with spreadsheet tooling and
read back **identically**: ``load(dump(net)) == net`` and every
:class:`~mambo_power.numerics.NetworkArrays` matrix is ``array_equal`` (AC-5).

Layout
------

``manifest.json`` carries what is not tabular: ``{"format": "mambo-power-csv",
"schema_version": 1, "base_mva": ..., "tables": {file: row count, ...}}``. ``schema_version``
is :attr:`Network.schema_version`, the native format's own version — the bundle has no version
of its own because it is a re-spelling of that schema, not a second one.

One CSV per entity list, headed by the model's field names **verbatim and in field order**
(:data:`TABLES` lists them): ``buses.csv``, ``branches.csv``, ``generators.csv``, ``loads.csv``,
``shunts.csv``, ``storage.csv``, ``zones.csv``. The three nested fields are flattened in place:

- ``Bus.geo`` → ``geo_lat, geo_lon`` (both empty ⇔ ``None``);
- ``Generator.cost`` → ``cost_kind, cost_startup, cost_shutdown`` (all empty ⇔ ``None``) plus
  the long-format side table ``generator_costs.csv`` (``generator_id, index, p_mw, value``):
  one row per polynomial coefficient (``p_mw`` empty, ``value`` = coefficient, highest order
  first) or per piecewise breakpoint (``p_mw``, ``value`` = cost), ``index`` = 0-based position;
- ``Load.bid`` → ``bid_kind`` plus ``load_bids.csv`` (``load_id, index, p_mw, value``), the same
  shape.

Long format was chosen over a JSON cell because it is the spreadsheet-friendly one (research
§4): a coefficient is a cell, not a substring, and a breakpoint is a row.

Cell rules
----------

- Empty cell ⇔ ``None``. Consequently an *optional* string field (``area``, ``zone``,
  ``Zone.name``) cannot carry ``""``; :func:`dump` raises :class:`ValueError` rather than write
  a bundle that would read back differently. Required string fields (ids, bus references)
  round-trip ``""`` fine — an empty cell there is the empty string.
- Ids and every other string are written and read as text; nothing is ever passed to
  ``int()``, so ``"01"`` and ``"1"`` stay distinct.
- Floats are written with :func:`repr` (shortest round-trip form) and read with
  :func:`float`; ``nan``/``inf`` are rejected on read, as the model rejects them.
- Booleans are written ``true``/``false``; ``true/false/1/0`` are accepted on read in any
  case.
- Empty tables are written header-only, so the manifest's table set never varies.
- Row order is list order and is preserved. A fully blank row is not a row (an editor's
  trailing newline does not change the count the manifest states), and a table is read as
  ``utf-8-sig`` so a UTF-8 BOM (Excel's "CSV UTF-8") does not become part of the first header;
  the writer emits plain UTF-8 with no BOM and no blank rows.

Reading
-------

:func:`load_with_report` validates the whole bundle and collects every problem before giving up:
each is an :class:`~mambo_power.model.ImportIssue` with one of the :data:`CODES` (all errors — a
bundle is either exact or refused; there is nothing to repair). Errors are raised as
:class:`~mambo_power.io.report.ReportError`, whose ``.report`` carries them. Cross-entity
invariants (dangling references, slack count, connectivity) are the model's own and surface as
:class:`~mambo_power.model.NetworkValidationError` exactly as for the native format.
"""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
import stat
import tempfile
import types
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Literal, NoReturn, get_args, get_origin

from pydantic import BaseModel, ValidationError

from mambo_power.io.report import ImportReport, ReportError
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    ImportIssue,
    ImportIssueCode,
    Load,
    Network,
    Shunt,
    Storage,
    Zone,
)

__all__ = [
    "CODES",
    "FORMAT",
    "SCHEMA_VERSION",
    "TABLES",
    "dump",
    "load",
    "load_with_report",
]

FORMAT = "mambo-power-csv"
"""The ``format`` string in ``manifest.json``."""

SCHEMA_VERSION: int = Network.model_fields["schema_version"].default
"""The schema version the bundle spells: :attr:`Network.schema_version`."""

TABLES: tuple[str, ...] = (
    "buses.csv",
    "branches.csv",
    "generators.csv",
    "generator_costs.csv",
    "loads.csv",
    "load_bids.csv",
    "shunts.csv",
    "storage.csv",
    "zones.csv",
)
"""Every file a bundle carries besides ``manifest.json``, in manifest order."""

CODES: tuple[str, ...] = (
    "CSV_MANIFEST_INVALID",
    "CSV_SCHEMA_VERSION",
    "CSV_MISSING_TABLE",
    "CSV_UNKNOWN_COLUMN",
    "CSV_MISSING_COLUMN",
    "CSV_DUPLICATE_ID",
    "CSV_BAD_VALUE",
    "CSV_ORPHAN_ROW",
)
"""Every report code this module can emit (all as errors; see the module docstring)."""

_MANIFEST = "manifest.json"
_TRUE = frozenset({"true", "1"})
_FALSE = frozenset({"false", "0"})

_Kind = Literal["str", "float", "bool"]


@dataclass(frozen=True)
class _Column:
    name: str
    kind: _Kind
    optional: bool


def _blank_line(row: list[str]) -> bool:
    """A line with nothing on it -- not a row of empty cells (``,,,``), which is a bad row."""
    return not row or (len(row) == 1 and not row[0].strip())


class _BundleError(Exception):
    """A cell or row that cannot be read; caught per table and turned into an issue."""

    def __init__(self, code: ImportIssueCode, message: str) -> None:
        self.code = code
        super().__init__(message)


# --- column specs, derived from the models ------------------------------------------------


def _scalar_kind(annotation: Any) -> tuple[_Kind, bool]:
    """Classify a scalar field annotation as (kind, optional)."""
    optional = False
    if get_origin(annotation) is types.UnionType:
        members = [a for a in get_args(annotation) if a is not type(None)]
        if len(members) != 1:
            raise TypeError(f"not a scalar annotation: {annotation!r}")
        annotation = members[0]
        optional = True
    if get_origin(annotation) is Literal:
        return "str", optional
    if annotation is str:
        return "str", optional
    if annotation is float:
        return "float", optional
    if annotation is bool:
        return "bool", optional
    raise TypeError(f"not a scalar annotation: {annotation!r}")


def _columns(model: type[BaseModel], flattened: Mapping[str, list[_Column]]) -> list[_Column]:
    """The model's fields in order, each nested field replaced by its flattened columns."""
    out: list[_Column] = []
    for name, info in model.model_fields.items():
        if name in flattened:
            out.extend(flattened[name])
        else:
            kind, optional = _scalar_kind(info.annotation)
            out.append(_Column(name, kind, optional))
    return out


_GEO = [_Column("geo_lat", "float", True), _Column("geo_lon", "float", True)]
_COST = [
    _Column("cost_kind", "str", True),
    _Column("cost_startup", "float", True),
    _Column("cost_shutdown", "float", True),
]
_BID = [_Column("bid_kind", "str", True)]

_SIDE_COLUMNS = [
    _Column("index", "str", False),
    _Column("p_mw", "float", True),
    _Column("value", "float", False),
]


@dataclass(frozen=True)
class _Table:
    file: str
    attr: str
    model: type[BaseModel]
    columns: list[_Column]
    side: _Side | None = None


@dataclass(frozen=True)
class _Side:
    """A long-format side table keyed by the owner's id, and the owner's flattened ``kind``."""

    file: str
    owner_column: str
    kind_column: str
    nested: str
    scalars: tuple[str, ...] = field(default_factory=tuple)
    """The owner's flattened scalar columns beside ``kind`` (startup/shutdown for costs)."""

    @property
    def columns(self) -> list[_Column]:
        return [_Column(self.owner_column, "str", False), *_SIDE_COLUMNS]


_ENTITY_TABLES: tuple[_Table, ...] = (
    _Table("buses.csv", "buses", Bus, _columns(Bus, {"geo": _GEO})),
    _Table("branches.csv", "branches", Branch, _columns(Branch, {})),
    _Table(
        "generators.csv",
        "generators",
        Generator,
        _columns(Generator, {"cost": _COST}),
        _Side(
            "generator_costs.csv",
            "generator_id",
            "cost_kind",
            "cost",
            ("cost_startup", "cost_shutdown"),
        ),
    ),
    _Table(
        "loads.csv",
        "loads",
        Load,
        _columns(Load, {"bid": _BID}),
        _Side("load_bids.csv", "load_id", "bid_kind", "bid"),
    ),
    _Table("shunts.csv", "shunts", Shunt, _columns(Shunt, {})),
    _Table("storage.csv", "storage", Storage, _columns(Storage, {})),
    _Table("zones.csv", "zones", Zone, _columns(Zone, {})),
)


# --- writing --------------------------------------------------------------------------------


def _cell(value: object, column: _Column, owner: str) -> str:
    if value is None:
        return ""
    if column.kind == "bool":
        return "true" if value else "false"
    if column.kind == "float":
        return repr(float(value))  # type: ignore[arg-type]
    text = str(value)
    if column.optional and text == "":
        raise ValueError(
            f'{owner}: optional string field "{column.name}" is "" — the empty cell means None,'
            " so an empty string cannot be written"
        )
    return text


def _flatten(entity: BaseModel, table: _Table) -> tuple[dict[str, object], list[list[object]]]:
    """The entity's flat cells, plus its side-table rows (``[index, p_mw, value]``)."""
    cells: dict[str, object] = {}
    side_rows: list[list[object]] = []
    for name in type(entity).model_fields:
        value = getattr(entity, name)
        if name == "geo":
            cells["geo_lat"] = None if value is None else value.lat
            cells["geo_lon"] = None if value is None else value.lon
        elif table.side is not None and name == table.side.nested:
            cells[table.side.kind_column] = None if value is None else value.kind
            for scalar in table.side.scalars:
                cells[scalar] = None if value is None else getattr(value, scalar.split("_", 1)[1])
            if value is not None:
                side_rows = _side_rows(value)
        else:
            cells[name] = value
    return cells, side_rows


def _side_rows(nested: BaseModel) -> list[list[object]]:
    if nested.kind == "polynomial":  # type: ignore[attr-defined]
        return [[i, None, c] for i, c in enumerate(nested.coefficients)]  # type: ignore[attr-defined]
    return [[i, p, v] for i, (p, v) in enumerate(nested.points)]  # type: ignore[attr-defined]


def _write_csv(path: Path, header: list[str], rows: Iterable[list[str]]) -> int:
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def dump(net: Network, directory: str | PathLike[str]) -> None:
    """Write ``net`` as a bundle into ``directory`` (created if absent; files overwritten).

    Raises :class:`ValueError` if an optional string field holds ``""`` (see the module
    docstring's cell rules); nothing else about a valid :class:`Network` can fail to serialise.

    All-or-nothing: every table is rendered before anything is written, the files go into a
    fresh temporary sibling directory (``.<name>.tmp-<random>``, so nothing pre-existing is
    ever removed), and when ``directory`` already holds a bundle the two are swapped *as
    directories* -- the old one is renamed aside, the new one renamed into place, the old one
    then removed (foreign files in it -- a README, a notebook -- are carried over first). So an
    exception anywhere -- the ``""`` refusal, a full disk, a table another program holds open
    (Windows refuses the first rename before anything has moved) -- leaves whatever bundle was
    there before byte-for-byte untouched, and nothing beside it (M8 critic findings 7, 20, 26).
    A ``directory`` that exists without a bundle in it (the working directory, say, which
    Windows cannot rename) is filled in place: there is nothing old to protect.

    Raises :class:`NotADirectoryError`, before anything is written, when ``directory`` names a
    file.
    """
    target = Path(directory).resolve()
    if target.exists() and not target.is_dir():
        raise NotADirectoryError(f"{directory!s} is a file, not a bundle directory")
    rendered = _render(net)
    manifest = {
        "format": FORMAT,
        "schema_version": net.schema_version,
        "base_mva": net.base_mva,
        "tables": {file: len(rendered[file][1]) for file in TABLES},
    }
    bundle_files = (*TABLES, _MANIFEST)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        for file, (header, rows) in rendered.items():
            _write_csv(staging / file, header, rows)
        (staging / _MANIFEST).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        if not target.is_dir() or not any((target / file).exists() for file in bundle_files):
            target.mkdir(exist_ok=True)
            for file in bundle_files:
                os.replace(staging / file, target / file)
            return
        old = staging.with_name(staging.name.replace(".tmp-", ".old-", 1))
        os.rename(target, old)  # fails whole on Windows if a file inside is open
        try:
            os.rename(staging, target)
        except BaseException:
            os.rename(old, target)
            raise
        for entry in old.iterdir():  # foreign files survive; bundle files are replaced
            if entry.name not in bundle_files:
                os.rename(entry, target / entry.name)
        _remove_tree(old)
    finally:
        if staging.exists():
            _remove_tree(staging)


def _remove_tree(path: Path) -> None:
    """``shutil.rmtree`` that also removes read-only files (Windows refuses them by default)."""
    for entry in path.rglob("*"):
        if entry.is_file():
            entry.chmod(stat.S_IWRITE | stat.S_IREAD)
    shutil.rmtree(path)


def _render(net: Network) -> dict[str, tuple[list[str], list[list[str]]]]:
    """Every table file → ``(header, rows)`` as text cells; every ``_cell`` call happens here."""
    out: dict[str, tuple[list[str], list[list[str]]]] = {}
    for table in _ENTITY_TABLES:
        rows: list[list[str]] = []
        side: list[list[str]] = []
        for entity in getattr(net, table.attr):
            owner = f"{table.attr} {entity.id!r}"
            cells, side_rows = _flatten(entity, table)
            rows.append([_cell(cells[c.name], c, owner) for c in table.columns])
            for index, p_mw, value in side_rows:
                side.append(
                    [
                        entity.id,
                        str(index),
                        _cell(p_mw, _SIDE_COLUMNS[1], owner),
                        _cell(value, _SIDE_COLUMNS[2], owner),
                    ]
                )
        out[table.file] = ([c.name for c in table.columns], rows)
        if table.side is not None:
            out[table.side.file] = ([c.name for c in table.side.columns], side)
    return out


# --- reading --------------------------------------------------------------------------------


def _parse(cell: str, column: _Column, where: str) -> object:
    if cell == "":
        if column.optional:
            return None
        if column.kind == "str":
            return ""
        raise _BundleError("CSV_BAD_VALUE", f'{where}: "{column.name}" is empty but required')
    if column.kind == "str":
        return cell
    if column.kind == "bool":
        lowered = cell.lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
        raise _BundleError(
            "CSV_BAD_VALUE", f'{where}: "{column.name}" = {cell!r} is not true/false/1/0'
        )
    try:
        value = float(cell)
    except ValueError:
        raise _BundleError(
            "CSV_BAD_VALUE", f'{where}: "{column.name}" = {cell!r} is not a float'
        ) from None
    if not math.isfinite(value):
        raise _BundleError("CSV_BAD_VALUE", f'{where}: "{column.name}" = {cell!r} is not finite')
    return value


class _Reader:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.issues: list[ImportIssue] = []

    def error(
        self,
        code: ImportIssueCode,
        message: str,
        *,
        bus_ids: list[str] | None = None,
        element_ids: list[str] | None = None,
    ) -> None:
        self.issues.append(
            ImportIssue(
                code=code,
                message=message,
                bus_ids=bus_ids or [],
                element_ids=element_ids or [],
            )
        )

    # manifest

    def manifest(self) -> dict[str, Any] | None:
        path = self.directory / _MANIFEST
        if not path.is_file():
            self.error("CSV_MANIFEST_INVALID", f"{_MANIFEST} is missing")
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            self.error("CSV_MANIFEST_INVALID", f"{_MANIFEST} is not JSON: {exc}")
            return None
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            self.error(
                "CSV_MANIFEST_INVALID", f"{_MANIFEST} must be an object with format={FORMAT!r}"
            )
            return None
        version = data.get("schema_version")
        if version != SCHEMA_VERSION:
            self.error(
                "CSV_SCHEMA_VERSION",
                f"{_MANIFEST} schema_version {version!r}; this build reads {SCHEMA_VERSION}",
            )
            return None
        base = data.get("base_mva")
        if isinstance(base, bool) or not isinstance(base, int | float) or not math.isfinite(base):
            self.error(
                "CSV_MANIFEST_INVALID", f"{_MANIFEST} base_mva {base!r} is not a finite number"
            )
            return None
        tables = data.get("tables")
        if not isinstance(tables, dict) or set(tables) != set(TABLES):
            self.error(
                "CSV_MANIFEST_INVALID",
                f"{_MANIFEST} tables must name exactly {list(TABLES)}",
            )
            return None
        return data

    # tables

    def rows(
        self, file: str, columns: list[_Column], expected_rows: object
    ) -> list[dict[str, object]] | None:
        """The table's typed rows, or ``None`` when its header or shape is wrong."""
        path = self.directory / file
        if not path.is_file():
            self.error("CSV_MISSING_TABLE", f"{file} is missing")
            return None
        # utf-8-sig: Excel's "CSV UTF-8" prefixes a BOM that would otherwise become part of the
        # first header; a fully blank row (an editor's trailing newline) is not a row. Both from
        # the M8 walk (surprises 6 and 7). The writer stays plain UTF-8 with no blank rows.
        try:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                raw = [row for row in csv.reader(handle) if not _blank_line(row)]
        except csv.Error as exc:  # a cell over csv.field_size_limit() (131 072 chars), ...
            self.error("CSV_BAD_VALUE", f"{file}: {exc}")
            return None
        header = raw[0] if raw else []
        expected = [c.name for c in columns]
        ok = True
        for name in header:
            if name not in expected:
                self.error("CSV_UNKNOWN_COLUMN", f'{file}: unknown column "{name}"')
                ok = False
        for name in expected:
            if name not in header:
                self.error("CSV_MISSING_COLUMN", f'{file}: missing column "{name}"')
                ok = False
        if not ok:
            return None
        if expected_rows != len(raw) - 1:
            self.error(
                "CSV_MANIFEST_INVALID",
                f"{file}: manifest says {expected_rows!r} rows, file has {len(raw) - 1}",
            )
            return None
        by_name = {c.name: c for c in columns}
        typed: list[dict[str, object]] = []
        for number, row in enumerate(raw[1:], start=2):
            where = f"{file} line {number}"
            if len(row) != len(header):
                self.error("CSV_BAD_VALUE", f"{where}: {len(row)} cells for {len(header)} columns")
                continue
            try:
                typed.append(
                    {n: _parse(c, by_name[n], where) for n, c in zip(header, row, strict=True)}
                )
            except _BundleError as exc:
                self.error(exc.code, str(exc))
        return typed

    def entities(self, table: _Table, counts: Mapping[str, object]) -> list[BaseModel] | None:
        rows = self.rows(table.file, table.columns, counts.get(table.file))
        if rows is None:
            return None
        side_by_owner = self.side_rows(table, rows, counts) if table.side else {}
        if side_by_owner is None:
            return None
        seen: set[str] = set()
        out: list[BaseModel] = []
        for row in rows:
            entity_id = str(row["id"])
            if entity_id in seen:
                ids = {"bus_ids" if table.attr == "buses" else "element_ids": [entity_id]}
                self.error("CSV_DUPLICATE_ID", f'{table.file}: duplicate id "{entity_id}"', **ids)
                continue
            seen.add(entity_id)
            try:
                data = self.unflatten(table, row, side_by_owner.get(entity_id, []))
                out.append(table.model.model_validate(data))
            except _BundleError as exc:
                self.error(exc.code, str(exc))
            except ValidationError as exc:
                detail = "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
                )
                self.error("CSV_BAD_VALUE", f'{table.file} id "{entity_id}": {detail}')
        return out

    def side_rows(
        self, table: _Table, owners: list[dict[str, object]], counts: Mapping[str, object]
    ) -> dict[str, list[dict[str, object]]] | None:
        side = table.side
        assert side is not None
        rows = self.rows(side.file, side.columns, counts.get(side.file))
        if rows is None:
            return None
        kinds = {str(r["id"]): r[side.kind_column] for r in owners}
        grouped: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            owner = str(row[side.owner_column])
            if kinds.get(owner) is None:
                self.error(
                    "CSV_ORPHAN_ROW",
                    f'{side.file}: row for {side.owner_column} "{owner}" whose owner is absent '
                    f"or has no {side.kind_column}",
                    element_ids=[owner],
                )
                continue
            grouped.setdefault(owner, []).append(row)
        return grouped

    def unflatten(
        self, table: _Table, row: dict[str, object], side_rows: list[dict[str, object]]
    ) -> dict[str, object]:
        data = dict(row)
        where = f'{table.file} id "{row["id"]}"'
        if table.model is Bus:
            lat, lon = data.pop("geo_lat"), data.pop("geo_lon")
            if (lat is None) != (lon is None):
                raise _BundleError(
                    "CSV_BAD_VALUE", f"{where}: geo_lat and geo_lon must both be set or both empty"
                )
            data["geo"] = None if lat is None else {"lat": lat, "lon": lon}
        if table.side is not None:
            data[table.side.nested] = self.nested(table.side, data, side_rows, where)
        return data

    def nested(
        self,
        side: _Side,
        data: dict[str, object],
        side_rows: list[dict[str, object]],
        where: str,
    ) -> dict[str, object] | None:
        kind = data.pop(side.kind_column)
        scalars = {name: data.pop(name) for name in side.scalars}
        if kind is None:
            if any(v is not None for v in scalars.values()):
                raise _BundleError(
                    "CSV_BAD_VALUE",
                    f"{where}: {side.kind_column} is empty but {list(scalars)} are set",
                )
            return None
        if not side_rows:
            raise _BundleError(
                "CSV_BAD_VALUE",
                f'{where}: {side.kind_column}="{kind}" but {side.file} has no rows for it',
            )
        for position, srow in enumerate(side_rows):
            if srow["index"] != str(position):
                raise _BundleError(
                    "CSV_BAD_VALUE",
                    f"{where}: {side.file} row {position} has index {srow['index']!r}, "
                    f"expected {position}",
                )
        nested: dict[str, object] = {"kind": kind}
        if kind == "polynomial":
            if any(r["p_mw"] is not None for r in side_rows):
                raise _BundleError(
                    "CSV_BAD_VALUE", f"{where}: polynomial rows must leave p_mw empty"
                )
            nested["coefficients"] = [r["value"] for r in side_rows]
        elif kind == "piecewise":
            if any(r["p_mw"] is None for r in side_rows):
                raise _BundleError("CSV_BAD_VALUE", f"{where}: piecewise rows need p_mw")
            nested["points"] = [(r["p_mw"], r["value"]) for r in side_rows]
        else:
            raise _BundleError(
                "CSV_BAD_VALUE", f'{where}: {side.kind_column} "{kind}" is not polynomial/piecewise'
            )
        for name, value in scalars.items():
            if value is None:
                raise _BundleError(
                    "CSV_BAD_VALUE", f"{where}: {name} is required with a {side.kind_column}"
                )
            nested[name.split("_", 1)[1]] = value
        return nested


def load_with_report(directory: str | PathLike[str]) -> tuple[Network, ImportReport]:
    """Read a bundle. The report is always empty on success (a bundle is exact or refused).

    Raises :class:`~mambo_power.io.report.ReportError` carrying every :data:`CODES` issue found
    when the bundle cannot be read; :class:`~mambo_power.model.NetworkValidationError` when the
    tables read cleanly but the network they describe breaks a cross-entity invariant.
    """
    reader = _Reader(Path(directory))
    manifest = reader.manifest()
    if manifest is None:
        _raise(reader.issues)
    counts = manifest["tables"]
    lists: dict[str, list[BaseModel] | None] = {
        table.attr: reader.entities(table, counts) for table in _ENTITY_TABLES
    }
    if reader.issues:
        _raise(reader.issues)
    net = Network(
        schema_version=manifest["schema_version"],
        base_mva=manifest["base_mva"],
        **{attr: entities for attr, entities in lists.items()},  # type: ignore[arg-type]
    )
    return net, ImportReport()


def load(directory: str | PathLike[str]) -> Network:
    """Read a bundle; :func:`load_with_report` without the (always empty) report."""
    return load_with_report(directory)[0]


def _raise(issues: list[ImportIssue]) -> NoReturn:
    raise ReportError(ImportReport(errors=list(issues)))
