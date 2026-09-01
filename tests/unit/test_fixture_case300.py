"""W7 / AC-7 (fixture): ``fixtures/matpower/case300.m`` is the verbatim MATPOWER file.

The bytes are pinned by sha256 so "verbatim" is checkable, not asserted: the digest recorded
in ``fixtures/matpower/PROVENANCE.md`` (and in ``record/m2-research.md`` §4) is the one
computed over MATPOWER's ``data/case300.m`` at git blob ``004203b8``. The counts below were
taken from the file itself (``awk`` over the three matrices); the importer must reproduce
them and the native round-trip must be identity, as for the five M1 fixtures.
"""

from __future__ import annotations

import hashlib

from mambo_power.io import matpower, native
from tests._fixtures import FIXTURES_DIR

CASE300 = FIXTURES_DIR / "case300.m"
SHA256 = "69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5"
SIZE = 66034
N_BUS, N_GEN, N_BRANCH = 300, 69, 411


def test_bytes_are_the_recorded_upstream_blob() -> None:
    data = CASE300.read_bytes()
    assert len(data) == SIZE
    assert hashlib.sha256(data).hexdigest() == SHA256
    assert b"\r\n" not in data  # served with LF; `.gitattributes` keeps *.m untouched


def test_importer_reproduces_the_file_counts() -> None:
    net, warnings = matpower.load_with_warnings(CASE300)
    assert (len(net.buses), len(net.generators), len(net.branches)) == (N_BUS, N_GEN, N_BRANCH)
    assert warnings == []  # no BASE_KV <= 0, no duplicated gencost half
    slack = [b for b in net.buses if b.type == "slack"]
    assert [b.id for b in slack] == ["bus-7049"]
    assert all(b.in_service for b in net.buses)  # no type-4 rows
    assert sum(g.cost is not None for g in net.generators) == N_GEN


def test_native_round_trip_is_identity() -> None:
    net = matpower.load(CASE300)
    assert native.loads(native.dumps(net)) == net


def test_provenance_case300_entry_carries_the_licence_exclusion_and_no_bsd_claim() -> None:
    """AC-11: the case300 entry in PROVENANCE.md quotes MATPOWER's own carve-out for its case
    files (not covered by the BSD license) and never claims the fixture itself is BSD-licensed
    (audit m2-audit.md §1, "Uncovered list": W7 had no criterion for this clause)."""
    text = (FIXTURES_DIR / "PROVENANCE.md").read_text(encoding="utf-8")
    start = text.index("### case300.m")
    end = text.index("\n## ", start)
    entry = text[start:end]
    assert "not covered by MATPOWER's BSD licence" in entry
    assert SHA256 in entry
    # no sentence in the entry affirmatively claims the fixture is BSD-licensed
    for phrase in ("is BSD", "under the BSD", "BSD-licensed", "BSD licensed"):
        assert phrase not in entry, phrase
