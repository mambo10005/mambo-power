"""The bundled cases in :mod:`mambo_power.cases` resolve, load and reject unknown names."""

from __future__ import annotations

from pathlib import Path

import pytest

from mambo_power import cases
from mambo_power.model import Network, validate_network

TOP_LEVEL_BUS_COUNTS = {
    "case14": 14,
    "case30": 30,
    "case_ieee30": 30,
    "case57": 57,
    "case118": 118,
    "case300": 300,
}

EXPECTED_NAMES = [
    "case118.m",
    "case14.m",
    "case14_v33.raw",
    "case30.m",
    "case300.m",
    "case57.m",
    "case_ieee30.m",
    "derived/case14_island.m",
    "derived/case14_noslackgen.m",
    "derived/case14_pwl.m",
    "derived/case14_rated.m",
    "derived/case14_roles.m",
]

PROVENANCE_RECORDS = ["PROVENANCE.md", "SOURCES.md", "PROVENANCE-raw.md", "derived/PROVENANCE.md"]


def test_available_lists_exactly_the_case_files_sorted() -> None:
    names = cases.available()
    assert names == sorted(names)
    assert names == EXPECTED_NAMES
    assert "case14_v33.raw" in names
    assert "derived/case14_roles.m" in names
    assert not [name for name in names if name.endswith(".md")]


@pytest.mark.parametrize("name", cases.available())
def test_every_available_name_resolves_to_an_existing_file(name: str) -> None:
    resolved = cases.path(name)
    assert isinstance(resolved, Path)
    assert resolved.is_file()
    assert resolved.as_posix().endswith(name)


def test_provenance_records_ship_next_to_the_cases() -> None:
    root = cases.path("case14.m").parent
    for record in PROVENANCE_RECORDS:
        assert (root / record).is_file(), record


@pytest.mark.parametrize(("name", "buses"), TOP_LEVEL_BUS_COUNTS.items())
def test_load_returns_a_valid_network_for_every_top_level_case(name: str, buses: int) -> None:
    net = cases.load(name)
    assert isinstance(net, Network)
    assert len(net.buses) == buses
    assert validate_network(net) == []


def test_load_accepts_names_with_and_without_the_suffix() -> None:
    assert len(cases.load("case14.m").buses) == 14
    assert len(cases.load("case14").buses) == 14
    assert isinstance(cases.load("derived/case14_pwl"), Network)
    assert isinstance(cases.load("derived/case14_pwl.m"), Network)


@pytest.mark.parametrize("call", [cases.path, cases.load])
def test_unknown_name_raises_value_error_listing_the_cases(call: object) -> None:
    assert callable(call)
    with pytest.raises(ValueError) as excinfo:
        call("nope")
    message = str(excinfo.value)
    for name in cases.available():
        assert name in message


def test_load_rejects_the_raw_case_and_points_at_psse_raw() -> None:
    with pytest.raises(ValueError, match="psse_raw"):
        cases.load("case14_v33.raw")
