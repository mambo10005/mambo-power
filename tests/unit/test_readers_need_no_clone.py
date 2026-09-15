"""Reader-facing executables load data through ``mambo_power.cases``, never a repository path.

The examples and tutorials are what a reader runs after ``pip install mambo-power``, where no
repository tree exists. The cases once lived in a top-level fixtures tree (ADR-014 moved them
into the package); a path into a tree like that works in a clone and fails everywhere else, so
the string is banned from both reader trees.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
READER_DIRS = (REPO_ROOT / "examples", REPO_ROOT / "docs" / "tutorials")
FORBIDDEN = "fixtures/"


def test_reader_directories_exist() -> None:
    missing = [str(directory) for directory in READER_DIRS if not directory.is_dir()]
    assert missing == [], missing


def test_no_reader_file_mentions_the_fixtures_tree() -> None:
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for directory in READER_DIRS
        for path in sorted(directory.rglob("*"))
        if path.is_file() and FORBIDDEN in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"{FORBIDDEN!r} appears in: {offenders}"
