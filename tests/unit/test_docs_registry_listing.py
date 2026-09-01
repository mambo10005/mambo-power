"""The jobs manual's hand-written registry listing must match the real registry (wave M5 W8).

``docs/examples/index.md`` embeds its code with ``pymdownx.snippets``, so the scripts it shows
are the bytes CI ran (``tests/unit/test_examples_run.py``). ``docs/manual/jobs.md`` cannot do
that: its snippets are prose-length fragments, not runnable files, and their ``text`` output
blocks are pasted by hand. That is exactly how the page's kind list came to be **two waves out
of date** -- it still listed four kinds after M4 registered a fifth, and this wave's docs slice
found it still listing four after M5 registered a sixth.

This module pins the three places the page states the registry's contents, against the registry
itself. It does not try to execute the page; it asserts that the strings the running code
produces appear verbatim in it, which is the whole of what goes stale.
"""

from __future__ import annotations

from pathlib import Path

from mambo_power import jobs

JOBS_MANUAL = Path(__file__).parents[2] / "docs" / "manual" / "jobs.md"


def _page() -> str:
    return JOBS_MANUAL.read_text(encoding="utf-8")


def test_the_manual_prints_the_real_sorted_kind_list() -> None:
    """The ``print(jobs.kinds())`` output block."""
    page = _page()
    assert str(jobs.kinds()) in page, (
        f"docs/manual/jobs.md does not carry the current jobs.kinds() output: {jobs.kinds()}"
    )


def test_the_manual_capability_table_lists_every_registered_kind() -> None:
    """The ``for name, spec in jobs.KINDS.items()`` output block, one line per kind."""
    page = _page()
    missing = []
    for name, spec in jobs.KINDS.items():
        options = spec.options_model.__name__ if spec.options_model else None
        line = f"{name} {options} {spec.result_model.__name__}"
        if line not in page:
            missing.append(line)
    assert missing == [], f"capability lines missing from docs/manual/jobs.md: {missing}"


def test_the_manual_unknown_kind_message_lists_every_registered_kind() -> None:
    """The ``UNKNOWN_KIND`` failure block quotes ``run``'s own "registered kinds:" text."""
    page = _page()
    known = ", ".join(sorted(jobs.KINDS))
    assert f"registered kinds: {known}" in page, (
        f"docs/manual/jobs.md's UNKNOWN_KIND message is stale; current list: {known}"
    )


def test_the_registry_is_non_trivial() -> None:
    """Absence-readback guard: the three checks above are vacuous on an empty registry."""
    assert len(jobs.KINDS) >= 6, sorted(jobs.KINDS)
