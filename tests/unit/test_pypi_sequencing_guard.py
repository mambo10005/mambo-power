"""AC-3: the guard in ``scripts/check_pypi_sequencing.py`` itself.

These tests exercise the guard's *logic* against fabricated content and a mocked git-tag
check — never against this repo's real ``docs/getting-started.md`` or real tag state, which
will legitimately change over time (Step 9 cuts ``v0.1.0`` and rewrites that page in the same
action). ``test_guard_passes_against_real_getting_started`` is the one exception: it runs the
guard against the actual current page to confirm today's pre-release state passes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.check_pypi_sequencing import (
    GETTING_STARTED,
    REPO_ROOT,
    check,
    has_unqualified_pypi_install_text,
    main,
    matching_tag_exists,
)

NOT_YET_CONTENT = """\
# Getting started

## Install

mambo-power is not on PyPI yet (that is wave M9, version 0.1.0). Until then, install from
source with uv:

```bash
git clone https://github.com/mambo10005/mambo-power.git
cd mambo-power
uv sync
```
"""

PYPI_CONTENT = """\
# Getting started

## Install

Install the latest release from PyPI:

```bash
pip install mambo-power
```
"""

PYPI_CONTENT_UV_ADD = """\
# Getting started

## Install

```bash
uv add mambo-power
```
"""

PYPI_CONTENT_QUALIFIED_ELSEWHERE = """\
# Getting started

mambo-power is not on PyPI yet (that is wave M9, version 0.1.0).

## Once released

Once released, run:

```bash
pip install mambo-power
```
"""


def _runner(stdout: str) -> object:
    def run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    return run


# --- has_unqualified_pypi_install_text -----------------------------------------------------


def test_not_yet_framing_is_not_a_pypi_claim() -> None:
    assert has_unqualified_pypi_install_text(NOT_YET_CONTENT) is False


def test_bare_pip_install_is_a_pypi_claim() -> None:
    assert has_unqualified_pypi_install_text(PYPI_CONTENT) is True


def test_bare_uv_add_is_a_pypi_claim() -> None:
    assert has_unqualified_pypi_install_text(PYPI_CONTENT_UV_ADD) is True


def test_source_install_line_is_not_a_pypi_claim() -> None:
    # `pip install -e .` / `pip install .` never name the package -- must not match.
    content = "## Install\n\n```bash\npip install -e .        # or: pip install .\n```\n"
    assert has_unqualified_pypi_install_text(content) is False


def test_qualifier_in_a_distant_paragraph_does_not_excuse_a_later_claim() -> None:
    # "not on PyPI yet" earlier in the doc doesn't retroactively qualify an unrelated,
    # later, unqualified install block -- only the block itself or its immediate
    # predecessor counts.
    assert has_unqualified_pypi_install_text(PYPI_CONTENT_QUALIFIED_ELSEWHERE) is True


# --- matching_tag_exists --------------------------------------------------------------------


def test_matching_tag_exists_true_for_v0_1_0() -> None:
    assert matching_tag_exists(Path("."), runner=_runner("v0.1.0\n")) is True


def test_matching_tag_exists_true_for_later_version() -> None:
    assert matching_tag_exists(Path("."), runner=_runner("v0.1.0\nv0.2.3\n")) is True


def test_matching_tag_exists_false_when_no_tags() -> None:
    assert matching_tag_exists(Path("."), runner=_runner("")) is False


def test_matching_tag_exists_false_below_0_1_0() -> None:
    # A pre-0.1.0 tag (e.g. an accidental v0.0.9) must not satisfy the check.
    assert matching_tag_exists(Path("."), runner=_runner("v0.0.9\n")) is False


def test_matching_tag_exists_ignores_non_release_shaped_tags() -> None:
    assert matching_tag_exists(Path("."), runner=_runner("vNEXT\nsomething-else\n")) is False


# --- check / main: the three end-to-end scenarios the report requires ----------------------


def test_scenario_no_pypi_text_passes_trivially(tmp_path: Path) -> None:
    ok, message = check(NOT_YET_CONTENT, tmp_path, runner=_runner("should not be called"))
    assert ok is True
    assert "no unqualified" in message.lower()


def test_scenario_pypi_text_present_no_tag_fails() -> None:
    ok, message = check(PYPI_CONTENT, Path("."), runner=_runner(""))
    assert ok is False
    assert "FAIL" in message
    assert "v0.1.0" in message


def test_scenario_pypi_text_present_tag_exists_passes() -> None:
    ok, message = check(PYPI_CONTENT, Path("."), runner=_runner("v0.1.0\n"))
    assert ok is True
    assert "OK" in message


def test_main_returns_0_for_no_pypi_text(tmp_path: Path) -> None:
    page = tmp_path / "getting-started.md"
    page.write_text(NOT_YET_CONTENT, encoding="utf-8")
    assert main(getting_started_path=page, runner=_runner("should not be called")) == 0


def test_main_returns_1_for_pypi_text_without_tag(tmp_path: Path) -> None:
    page = tmp_path / "getting-started.md"
    page.write_text(PYPI_CONTENT, encoding="utf-8")
    assert main(getting_started_path=page, runner=_runner("")) == 1


def test_main_returns_0_for_pypi_text_with_tag(tmp_path: Path) -> None:
    page = tmp_path / "getting-started.md"
    page.write_text(PYPI_CONTENT, encoding="utf-8")
    assert main(getting_started_path=page, runner=_runner("v0.1.0\n")) == 0


# --- the real page: today's pre-release state must pass ------------------------------------


def test_guard_passes_against_real_getting_started() -> None:
    assert GETTING_STARTED.exists(), GETTING_STARTED
    content = GETTING_STARTED.read_text(encoding="utf-8")
    # Real git-tag check too: today's wave head legitimately has no v* tag yet, but the
    # doc has no unqualified PyPI claim either, so the guard must pass without even needing
    # to shell out -- exercised via the real matching_tag_exists as an extra confidence check.
    ok, message = check(content, REPO_ROOT)
    assert ok is True, message


@pytest.mark.parametrize("tag", ["v1.0.0", "v0.1.0-rc1", "v10.20.30"])
def test_is_release_tag_shapes_accepted(tag: str) -> None:
    assert matching_tag_exists(Path("."), runner=_runner(tag + "\n")) is True
