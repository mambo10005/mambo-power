"""AC-5: the CSV bundle round-trips every fixture bit-exactly, and malformed bundles fail with a
named :class:`~mambo_power.io.report.ImportReport` error (wave M8, W5 / T6)."""

from __future__ import annotations

import csv
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import get_args

import numpy as np
import pytest

from mambo_power.io import csv_bundle, matpower
from mambo_power.io.report import ImportReport, ReportError
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    ImportIssueCode,
    Load,
    Network,
    PiecewiseBid,
    PolynomialBid,
    PolynomialCost,
    Storage,
    Zone,
)
from mambo_power.numerics import NetworkArrays
from tests import _agents
from tests._bids import with_bids
from tests._fixtures import FIXTURES, FIXTURES_DIR
from tests._storage import with_storage
from tests._zones import promote_areas_to_zones
from tests.unit.test_model_roundtrip import full_network


def _matpower(name: str) -> Callable[[], Network]:
    return lambda: matpower.load(FIXTURES_DIR / f"{name}.m")


def _piecewise_bid_network() -> Network:
    """A hand-built network that exercises every column the bundle can carry at once: a
    piecewise bid, a polynomial bid, ids that look numeric (``"01"``, ``"1"``), an empty-string
    id, and floats whose ``.12g`` rendering differs from ``repr`` (``0.1 + 0.2``, ``1 / 3``)."""
    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="01", base_kv=110.0, type="slack", area="1", zone="1"),
            Bus(id="1", base_kv=110.0, type="pq", vm_pu=0.1 + 0.2),
            Bus(id="", base_kv=110.0, type="pq"),
        ],
        branches=[
            Branch(id="01", from_bus="01", to_bus="1", r=0.01, x=0.1, b=0.0),
            Branch(id="1", from_bus="1", to_bus="", r=0.0, x=0.1, b=0.0, kind="transformer"),
        ],
        generators=[
            Generator(
                id="1",
                bus="01",
                p_mw=0.1 + 0.2,
                q_mvar=0.0,
                p_min_mw=0.0,
                p_max_mw=1e300,
                q_min_mvar=-1.0,
                q_max_mvar=1.0,
                v_set_pu=1.0,
                cost=PolynomialCost(coefficients=[1 / 3, 2.0, 5e-324]),
            )
        ],
        loads=[
            Load(id="1", bus="1", p_mw=10.0, q_mvar=1.0, bid=PolynomialBid(coefficients=[-1.0])),
            Load(
                id="2",
                bus="",
                p_mw=10.0,
                q_mvar=1.0,
                bid=PiecewiseBid(points=[(0.0, 0.0), (1 / 3, 7.0), (10.0, 0.1 + 0.2)]),
            ),
        ],
        storage=[
            Storage(
                id="1",
                bus="1",
                p_max_mw=1.0,
                energy_mwh=4.0,
                soc_initial=0.5,
                efficiency_charge=0.9,
                efficiency_discharge=0.8,
                in_service=False,
            )
        ],
        zones=[Zone(id="1", name="one"), Zone(id="2")],
    )


NETWORKS: dict[str, Callable[[], Network]] = {
    **{name: _matpower(name) for name in FIXTURES},
    "agents_smooth_pivotal": _agents.smooth_pivotal_network,
    "agents_non_pivotal_control": _agents.non_pivotal_control_network,
    "agents_duopoly": _agents.duopoly_network,
    "schema_full_network": full_network,
    "schema_case30_storage": lambda: with_storage(_matpower("case30")()),
    "schema_case30_zones": lambda: promote_areas_to_zones(_matpower("case30")()),
    "schema_case14_bids": lambda: with_bids(_matpower("case14")()),
    "schema_piecewise_bid_numeric_ids": _piecewise_bid_network,
}


@pytest.mark.parametrize("name", list(NETWORKS))
def test_load_dump_is_identity_on_the_model(name: str, tmp_path: Path) -> None:
    net = NETWORKS[name]()
    csv_bundle.dump(net, tmp_path)
    assert csv_bundle.load(tmp_path) == net


@pytest.mark.parametrize("name", list(NETWORKS))
def test_load_dump_is_array_equal_on_every_matrix(name: str, tmp_path: Path) -> None:
    net = NETWORKS[name]()
    csv_bundle.dump(net, tmp_path)
    before = vars(NetworkArrays.from_network(net))
    after = vars(NetworkArrays.from_network(csv_bundle.load(tmp_path)))
    assert before.keys() == after.keys()
    for key, value in before.items():
        if isinstance(value, np.ndarray):
            assert np.array_equal(value, after[key]), key  # bit-exact: no tolerance
        else:
            assert value == after[key], key


def test_load_with_report_is_empty_on_a_clean_bundle(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    net, report = csv_bundle.load_with_report(tmp_path)
    assert isinstance(report, ImportReport)
    assert net == full_network()
    assert report.warnings == [] and report.errors == []


def test_trailing_blank_lines_are_not_rows(tmp_path: Path) -> None:
    """M8 walk, surprise 6: an editor that appends a blank line on save made the bundle
    unreadable (``manifest says 11 rows, file has 13``). A fully blank row is skipped."""
    csv_bundle.dump(full_network(), tmp_path)
    path = tmp_path / "loads.csv"
    path.write_bytes(path.read_bytes() + b"\n\n")
    net, report = csv_bundle.load_with_report(tmp_path)
    assert report.warnings == [] and report.errors == []
    assert net == full_network()
    # a row of empty cells is not a blank line: it is still a row, and the manifest disagrees
    path.write_bytes(path.read_bytes() + b",,,,,,,")
    with pytest.raises(ReportError, match="CSV_MANIFEST_INVALID"):
        csv_bundle.load(tmp_path)


def test_a_utf8_bom_on_a_table_is_ignored(tmp_path: Path) -> None:
    """M8 walk, surprise 7: Excel's "CSV UTF-8" prefixes a BOM, which made the first header
    ``\\ufeffid`` (``CSV_UNKNOWN_COLUMN`` + ``CSV_MISSING_COLUMN``). Read with ``utf-8-sig``;
    the writer still emits plain UTF-8 (no BOM)."""
    csv_bundle.dump(full_network(), tmp_path)
    path = tmp_path / "buses.csv"
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    net, report = csv_bundle.load_with_report(tmp_path)
    assert report.warnings == [] and report.errors == []
    assert net == full_network()


# --- bundle layout ---------------------------------------------------------------------------


def test_manifest_names_schema_version_base_mva_and_tables(tmp_path: Path) -> None:
    net = full_network()
    csv_bundle.dump(net, tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["format"] == csv_bundle.FORMAT
    assert manifest["schema_version"] == net.schema_version == csv_bundle.SCHEMA_VERSION
    assert manifest["base_mva"] == 100.0
    assert manifest["tables"] == {
        "buses.csv": 4,
        "branches.csv": 3,
        "generators.csv": 3,
        "generator_costs.csv": 6,
        "loads.csv": 1,
        "load_bids.csv": 0,
        "shunts.csv": 1,
        "storage.csv": 1,
        "zones.csv": 2,
    }
    assert list(csv_bundle.TABLES) == list(manifest["tables"])


def _header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def test_headers_are_the_model_field_names_in_field_order(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    assert _header(tmp_path / "buses.csv") == [
        *[f for f in Bus.model_fields if f != "geo"],
        "geo_lat",
        "geo_lon",
    ]
    assert _header(tmp_path / "branches.csv") == list(Branch.model_fields)
    gen_fields = list(Generator.model_fields)
    at = gen_fields.index("cost")
    assert _header(tmp_path / "generators.csv") == [
        *gen_fields[:at],
        "cost_kind",
        "cost_startup",
        "cost_shutdown",
        *gen_fields[at + 1 :],
    ]
    assert _header(tmp_path / "loads.csv") == [*list(Load.model_fields)[:-1], "bid_kind"]
    assert _header(tmp_path / "generator_costs.csv") == ["generator_id", "index", "p_mw", "value"]
    assert _header(tmp_path / "load_bids.csv") == ["load_id", "index", "p_mw", "value"]
    assert _header(tmp_path / "storage.csv") == list(Storage.model_fields)
    assert _header(tmp_path / "zones.csv") == list(Zone.model_fields)


def test_empty_tables_are_written_header_only(tmp_path: Path) -> None:
    csv_bundle.dump(_agents.smooth_pivotal_network(), tmp_path)
    for name in ("shunts.csv", "storage.csv", "zones.csv"):
        lines = (tmp_path / name).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1, name
    # the agents fixture's load carries a three-coefficient polynomial bid
    assert len((tmp_path / "load_bids.csv").read_text(encoding="utf-8").splitlines()) == 4


def test_cells_are_repr_floats_empty_none_and_lowercase_bools(tmp_path: Path) -> None:
    csv_bundle.dump(_piecewise_bid_network(), tmp_path)
    with (tmp_path / "buses.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[1]["vm_pu"] == repr(0.1 + 0.2) == "0.30000000000000004"
    assert rows[0]["vm_pu"] == ""  # None
    assert rows[0]["in_service"] == "true"
    assert rows[0]["id"] == "01" and rows[1]["id"] == "1" and rows[2]["id"] == ""
    with (tmp_path / "generator_costs.csv").open(newline="", encoding="utf-8") as handle:
        cost_rows = list(csv.DictReader(handle))
    assert [r["value"] for r in cost_rows] == ["0.3333333333333333", "2.0", "5e-324"]
    assert [r["p_mw"] for r in cost_rows] == ["", "", ""]
    assert [r["index"] for r in cost_rows] == ["0", "1", "2"]


def test_a_tap_assigned_after_construction_is_written_as_a_transformer_row(tmp_path: Path) -> None:
    """M8 critic nit 24: ``br.tap_ratio = 1.05`` on a line leaves ``kind == "line"`` in memory;
    the CSV row must not say ``line`` beside a tap -- ``dump`` writes ``is_transformer``'s
    answer, and the round trip equals the network built fresh with that tap."""
    net = full_network()
    line = next(b for b in net.branches if b.kind == "line")
    line.tap_ratio = 1.05
    csv_bundle.dump(net, tmp_path)
    with (tmp_path / "branches.csv").open(newline="", encoding="utf-8") as handle:
        row = next(r for r in csv.DictReader(handle) if r["id"] == line.id)
    assert row["kind"] == "transformer" and row["tap_ratio"] == "1.05"
    assert line.kind == "line"  # the object is not mutated by the dump
    back = csv_bundle.load(tmp_path)
    assert next(b for b in back.branches if b.id == line.id).kind == "transformer"
    assert back == Network.model_validate(net.model_dump())


def test_dump_rejects_an_empty_optional_string(tmp_path: Path) -> None:
    """``""`` and ``None`` share the empty cell; an optional string field cannot carry ``""``."""
    net = full_network()
    net.buses[0].area = ""
    with pytest.raises(ValueError, match="area"):
        csv_bundle.dump(net, tmp_path)


def test_dump_that_fails_midway_leaves_the_old_bundle_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M8 critic finding 7: ``dump`` used to write table by table into the target, so a failure
    after ``buses.csv`` left the old manifest beside a mix of new and old tables — a bundle
    that still *loaded*. Now every table is rendered first and written into a temporary sibling
    directory that is swapped in only on success: the original bundle survives unchanged, no
    temporary directory is left behind, and the ``""`` refusal is all-or-nothing."""
    original = full_network()
    csv_bundle.dump(original, tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    changed = full_network()
    changed.buses[0].base_kv = 999.0
    real_write = csv_bundle._write_csv

    def failing_write(path: Path, header: list[str], rows: object) -> int:
        if path.name == "loads.csv":
            raise OSError("disk full")
        return real_write(path, header, rows)  # type: ignore[arg-type]

    monkeypatch.setattr(csv_bundle, "_write_csv", failing_write)
    with pytest.raises(OSError, match="disk full"):
        csv_bundle.dump(changed, tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert csv_bundle.load(tmp_path) == original
    assert _leftovers(tmp_path) == []

    # the rendering-time refusal is all-or-nothing too
    monkeypatch.setattr(csv_bundle, "_write_csv", real_write)
    changed.zones.append(Zone(id="empty-name", name=""))
    with pytest.raises(ValueError, match="name"):
        csv_bundle.dump(changed, tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def _leftovers(target: Path) -> list[str]:
    """Temporary or old-bundle directories left beside ``target``."""
    return sorted(p.name for p in target.parent.iterdir() if ".tmp-" in p.name or ".old-" in p.name)


def _changed_network() -> Network:
    net = full_network()
    net.buses[0].base_kv = 999.0
    net.generators[0].p_max_mw = 12345.0
    return net


def test_dump_that_fails_in_the_swap_leaves_the_old_bundle_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M8 critic finding 20: the move phase was a per-table ``os.replace`` loop, so a failure on
    the second table (a read-only file, a spreadsheet holding it open) left ``buses.csv`` new,
    the rest old, and an orphan staging directory -- a mixed bundle that loads. The bundle is
    now swapped in at the directory level; a failure at either rename leaves the old bundle
    byte-identical and nothing beside it."""
    original = full_network()
    target = tmp_path / "bundle"
    csv_bundle.dump(original, target)
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    real_rename = os.rename

    def failing_rename(src: str | Path, dst: str | Path, *args: object, **kw: object) -> None:
        if ".tmp-" in Path(src).name:  # the second rename: staging -> target
            raise PermissionError("held open")
        real_rename(src, dst, *args, **kw)

    monkeypatch.setattr(csv_bundle.os, "rename", failing_rename)
    with pytest.raises(PermissionError, match="held open"):
        csv_bundle.dump(_changed_network(), target)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == before
    assert csv_bundle.load(target) == original
    assert _leftovers(target) == []

    def failing_first_rename(src: str | Path, dst: str | Path, *a: object, **kw: object) -> None:
        if Path(src) == target:  # the first rename: target -> old
            raise PermissionError("in use")
        real_rename(src, dst, *a, **kw)

    monkeypatch.setattr(csv_bundle.os, "rename", failing_first_rename)
    with pytest.raises(PermissionError, match="in use"):
        csv_bundle.dump(_changed_network(), target)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == before
    assert _leftovers(target) == []


def test_dump_over_a_bundle_with_a_file_held_open_is_all_or_nothing(tmp_path: Path) -> None:
    """The critic's x3b: ``generators.csv`` open in another handle while a new bundle is
    dumped. Windows refuses to rename a directory with an open file inside -- before anything
    moves -- so the dump fails whole; POSIX allows it, so the dump succeeds whole. Either way
    the directory is exactly one of the two bundles, and nothing is left beside it."""
    original, changed = full_network(), _changed_network()
    target = tmp_path / "bundle"
    csv_bundle.dump(original, target)
    with (target / "generators.csv").open(encoding="utf-8") as held:
        try:
            csv_bundle.dump(changed, target)
        except PermissionError:
            assert sys.platform == "win32"
            assert csv_bundle.load(target) == original
        else:
            assert csv_bundle.load(target) == changed
        held.read()
    assert _leftovers(target) == []


def test_dump_over_a_bundle_with_a_read_only_table_succeeds(tmp_path: Path) -> None:
    """A read-only ``generators.csv`` (the critic's x3 case 2) used to fail the per-file
    replace on Windows mid-loop. The directory swap moves it aside whole, and removing the old
    bundle clears the read-only bit rather than leaving a ``.old-`` directory behind."""
    target = tmp_path / "bundle"
    csv_bundle.dump(full_network(), target)
    (target / "generators.csv").chmod(0o444)
    changed = _changed_network()
    csv_bundle.dump(changed, target)
    assert csv_bundle.load(target) == changed
    assert _leftovers(target) == []


def test_dump_keeps_foreign_files_in_the_target_directory(tmp_path: Path) -> None:
    """A README or a notebook beside the bundle survives the directory swap; a stale extra
    CSV is not a bundle file either and survives too (``load`` ignores it)."""
    target = tmp_path / "bundle"
    csv_bundle.dump(full_network(), target)
    (target / "README.md").write_text("mine", encoding="utf-8")
    (target / "notes").mkdir()
    (target / "notes" / "a.txt").write_text("a", encoding="utf-8")
    changed = _changed_network()
    csv_bundle.dump(changed, target)
    assert csv_bundle.load(target) == changed
    assert (target / "README.md").read_text(encoding="utf-8") == "mine"
    assert (target / "notes" / "a.txt").read_text(encoding="utf-8") == "a"
    assert _leftovers(target) == []


def test_dump_into_the_working_directory_and_onto_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``dump(net, ".")`` must keep working (Windows cannot rename the process's cwd, so a
    bundle-free target is filled in place rather than swapped), and a target that is a file
    is refused before anything is written -- no staging directory, the file untouched."""
    monkeypatch.chdir(tmp_path)
    csv_bundle.dump(full_network(), ".")
    assert csv_bundle.load(".") == full_network()
    assert _leftovers(tmp_path / "x") == []
    clash = tmp_path / "file.txt"
    clash.write_text("keep", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="file.txt"):
        csv_bundle.dump(full_network(), clash)
    assert clash.read_text(encoding="utf-8") == "keep"
    assert _leftovers(clash) == []


# --- malformed bundles -----------------------------------------------------------------------

Rows = list[list[str]]


def _rewrite(path: Path, edit: Callable[[Rows], Rows]) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, lineterminator="\n").writerows(edit(rows))


def _set_cell(path: Path, row: int, column: str, cell: str) -> None:
    col = _header(path).index(column)

    def edit(rows: Rows) -> Rows:
        rows[row][col] = cell
        return rows

    _rewrite(path, edit)


def _set_count(directory: Path, file: str, delta: int) -> None:
    """Keep the manifest honest after a row edit, so only the edit under test is reported."""
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["tables"][file] += delta
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _errors(directory: Path) -> list[str]:
    with pytest.raises(ReportError) as info:
        csv_bundle.load(directory)
    report = info.value.report
    assert report.has_errors
    for issue in report.errors:
        assert issue.code in get_args(ImportIssueCode)
        assert issue.code in csv_bundle.CODES
    return [e.code for e in report.errors]


def test_unknown_column_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _rewrite(
        tmp_path / "buses.csv",
        lambda rows: [[*r, "colour" if i == 0 else "red"] for i, r in enumerate(rows)],
    )
    assert _errors(tmp_path) == ["CSV_UNKNOWN_COLUMN"]


def test_missing_column_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _rewrite(tmp_path / "shunts.csv", lambda rows: [r[:-1] for r in rows])  # drop in_service
    assert _errors(tmp_path) == ["CSV_MISSING_COLUMN"]


def test_missing_table_named_in_the_manifest_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    (tmp_path / "storage.csv").unlink()
    assert _errors(tmp_path) == ["CSV_MISSING_TABLE"]


def test_duplicated_id_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _rewrite(tmp_path / "zones.csv", lambda rows: [*rows, rows[1]])
    _set_count(tmp_path, "zones.csv", +1)
    with pytest.raises(ReportError) as info:
        csv_bundle.load(tmp_path)
    (issue,) = info.value.report.errors
    assert issue.code == "CSV_DUPLICATE_ID"
    assert issue.element_ids == ["z1"]


def test_duplicated_bus_id_names_the_bus(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _rewrite(tmp_path / "buses.csv", lambda rows: [*rows, rows[2]])
    _set_count(tmp_path, "buses.csv", +1)
    with pytest.raises(ReportError) as info:
        csv_bundle.load(tmp_path)
    (issue,) = info.value.report.errors
    assert issue.code == "CSV_DUPLICATE_ID"
    assert issue.bus_ids == ["b2"] and issue.element_ids == []


def test_schema_version_mismatch_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    manifest["schema_version"] = 99
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert _errors(tmp_path) == ["CSV_SCHEMA_VERSION"]


def test_broken_manifest_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")
    assert _errors(tmp_path) == ["CSV_MANIFEST_INVALID"]
    (tmp_path / "manifest.json").unlink()
    assert _errors(tmp_path) == ["CSV_MANIFEST_INVALID"]


def test_manifest_row_count_disagreeing_with_the_table_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    manifest["tables"]["zones.csv"] = 7
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert _errors(tmp_path) == ["CSV_MANIFEST_INVALID"]


@pytest.mark.parametrize("cell", ["nan", "inf", "-inf", "abc", "1,5", ""])
def test_non_finite_missing_or_unparsable_float_is_a_named_error(tmp_path: Path, cell: str) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _set_cell(tmp_path / "buses.csv", 1, "base_kv", cell)
    assert _errors(tmp_path) == ["CSV_BAD_VALUE"]


def test_bad_bool_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _set_cell(tmp_path / "buses.csv", 1, "in_service", "yes")
    assert _errors(tmp_path) == ["CSV_BAD_VALUE"]


def test_bad_literal_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _set_cell(tmp_path / "buses.csv", 1, "type", "swing")
    assert _errors(tmp_path) == ["CSV_BAD_VALUE"]


def test_bool_cells_accept_the_documented_spellings(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    path = tmp_path / "buses.csv"
    for row, cell in ((1, "True"), (2, "1"), (3, "TRUE"), (4, "0")):
        _set_cell(path, row, "in_service", cell)
    assert [b.in_service for b in csv_bundle.load(tmp_path).buses] == [True, True, True, False]


def test_orphan_side_table_row_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _rewrite(tmp_path / "load_bids.csv", lambda rows: [*rows, ["nobody", "0", "", "1.0"]])
    _set_count(tmp_path, "load_bids.csv", +1)
    assert _errors(tmp_path) == ["CSV_ORPHAN_ROW"]
    csv_bundle.dump(full_network(), tmp_path)
    # a row for a generator whose cost_kind is empty is an orphan too
    _rewrite(tmp_path / "generator_costs.csv", lambda rows: [*rows, ["g3", "0", "", "1.0"]])
    _set_count(tmp_path, "generator_costs.csv", +1)
    assert _errors(tmp_path) == ["CSV_ORPHAN_ROW"]


def test_side_table_index_out_of_sequence_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _rewrite(tmp_path / "generator_costs.csv", lambda rows: [rows[0], *rows[2:], rows[1]])
    assert _errors(tmp_path) == ["CSV_BAD_VALUE"]


def test_kind_without_side_rows_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _rewrite(tmp_path / "generator_costs.csv", lambda rows: [rows[0]])
    _set_count(tmp_path, "generator_costs.csv", -6)
    assert _errors(tmp_path) == ["CSV_BAD_VALUE", "CSV_BAD_VALUE"]  # g1 and g2 both lost theirs


def test_half_geo_is_a_named_error(tmp_path: Path) -> None:
    csv_bundle.dump(full_network(), tmp_path)
    _set_cell(tmp_path / "buses.csv", 1, "geo_lon", "")
    assert _errors(tmp_path) == ["CSV_BAD_VALUE"]


def test_every_code_is_registered_on_the_closed_set() -> None:
    assert csv_bundle.CODES
    assert set(csv_bundle.CODES) <= set(get_args(ImportIssueCode))
    assert all(code.startswith("CSV_") for code in csv_bundle.CODES)


def test_a_cell_over_the_csv_field_limit_is_a_report_error(tmp_path: Path) -> None:
    """M8 critic finding 14: ``csv.field_size_limit()`` (131 072 chars) used to surface as an
    uncaught ``_csv.Error``; the report is the only channel."""
    csv_bundle.dump(full_network(), tmp_path)
    (tmp_path / "zones.csv").write_text("id,name\n" + "x" * 200_000 + ",\n", encoding="utf-8")
    with pytest.raises(ReportError) as info:
        csv_bundle.load(tmp_path)
    codes = [(e.code, e.message.split(":")[0]) for e in info.value.report.errors]
    assert ("CSV_BAD_VALUE", "zones.csv") in codes
