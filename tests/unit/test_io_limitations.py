"""AC-7 (docs half): every report code a format module registers in ``io.limitations.LIMITATIONS``
is documented in ``docs/manual/formats.md``, and the registry names real modules with real
codes. S2–S5 register their modules there; this test grows with them for free."""

import importlib
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest

from mambo_power.io import limitations
from mambo_power.model import ImportIssueCode

FORMATS_MD = Path(__file__).parents[2] / "docs" / "manual" / "formats.md"


def test_registry_is_non_empty_and_names_importable_modules() -> None:
    assert limitations.LIMITATIONS
    for module_name, codes in limitations.LIMITATIONS.items():
        assert module_name.startswith("io."), module_name
        importlib.import_module(f"mambo_power.{module_name}")
        assert codes, f"{module_name} registers no codes"


@pytest.mark.parametrize(
    ("module_name", "code"),
    [(m, c) for m, codes in limitations.LIMITATIONS.items() for c in codes],
)
def test_every_registered_code_is_documented(module_name: str, code: str) -> None:
    text = FORMATS_MD.read_text(encoding="utf-8")
    assert f"`{code}`" in text, (
        f"{module_name} emits {code} but docs/manual/formats.md never names it"
    )


@pytest.mark.parametrize(
    ("module_name", "code"),
    [(m, c) for m, codes in limitations.LIMITATIONS.items() for c in codes],
)
def test_every_registered_code_is_a_known_issue_code(module_name: str, code: str) -> None:
    assert code in get_args(ImportIssueCode), f"{module_name} registers unknown code {code}"


def test_matpower_registers_exactly_the_codes_it_emits() -> None:
    src = (Path(limitations.__file__).parent / "matpower.py").read_text(encoding="utf-8")
    emitted = {c for c in get_args(ImportIssueCode) if f'code="{c}"' in src}
    emitted.add("ISLAND_DEACTIVATED")  # emitted through model.repair_islands, which matpower calls
    assert set(limitations.LIMITATIONS["io.matpower"]) == emitted


IO_MODULES = [
    "csv_bundle",
    "limitations",
    "matpower",
    "native",
    "pandapower_json",
    "psse_raw",
    "pypsa",
    "report",
]


@pytest.mark.parametrize("first", IO_MODULES)
def test_io_imports_in_every_entry_order_without_the_optional_libraries(first: str) -> None:
    """M8 critic finding 9: the registry used to sit at the bottom of ``report.py`` — the leaf
    every format module imports — so ``mambo_power.io`` only imported because ``io/__init__``
    happened to import ``report`` first. Now ``report`` imports nothing from the formats, and
    whichever ``io`` module a caller imports first, in a fresh interpreter with ``pypsa``,
    ``pandapower`` and ``pandas`` blocked, the package imports and ``report`` carries no format
    module attribute."""
    code = f"""
import sys
for blocked in ("pypsa", "pandapower", "pandas"):
    sys.modules[blocked] = None
import mambo_power.io.{first}
import mambo_power.io as io_
from mambo_power.io import limitations, report
assert sorted(io_.__all__) == sorted({IO_MODULES!r}), io_.__all__
assert set(limitations.LIMITATIONS) == {{
    "io.matpower", "io.pandapower_json", "io.pypsa", "io.psse_raw", "io.csv_bundle"
}}
for name in ("pypsa", "pandapower_json", "psse_raw", "csv_bundle", "LIMITATIONS"):
    assert not hasattr(report, name), name
print("ok")
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
