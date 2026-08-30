"""AC-7 (docs half): every report code a format module registers in ``io.report.LIMITATIONS``
is documented in ``docs/manual/formats.md``, and the registry names real modules with real
codes. S2–S5 register their modules there; this test grows with them for free."""

import importlib
from pathlib import Path
from typing import get_args

import pytest

from mambo_power.io import report
from mambo_power.model import ImportIssueCode

FORMATS_MD = Path(__file__).parents[2] / "docs" / "manual" / "formats.md"


def test_registry_is_non_empty_and_names_importable_modules() -> None:
    assert report.LIMITATIONS
    for module_name, codes in report.LIMITATIONS.items():
        assert module_name.startswith("io."), module_name
        importlib.import_module(f"mambo_power.{module_name}")
        assert codes, f"{module_name} registers no codes"


@pytest.mark.parametrize(
    ("module_name", "code"),
    [(m, c) for m, codes in report.LIMITATIONS.items() for c in codes],
)
def test_every_registered_code_is_documented(module_name: str, code: str) -> None:
    text = FORMATS_MD.read_text(encoding="utf-8")
    assert f"`{code}`" in text, (
        f"{module_name} emits {code} but docs/manual/formats.md never names it"
    )


@pytest.mark.parametrize(
    ("module_name", "code"),
    [(m, c) for m, codes in report.LIMITATIONS.items() for c in codes],
)
def test_every_registered_code_is_a_known_issue_code(module_name: str, code: str) -> None:
    assert code in get_args(ImportIssueCode), f"{module_name} registers unknown code {code}"


def test_matpower_registers_exactly_the_codes_it_emits() -> None:
    src = (Path(report.__file__).parent / "matpower.py").read_text(encoding="utf-8")
    emitted = {c for c in get_args(ImportIssueCode) if f'code="{c}"' in src}
    emitted.add("ISLAND_DEACTIVATED")  # emitted through model.repair_islands, which matpower calls
    assert set(report.LIMITATIONS["io.matpower"]) == emitted
