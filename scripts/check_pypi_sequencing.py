#!/usr/bin/env python3
"""AC-3 (wave M9, W5): ``docs/getting-started.md`` may not claim PyPI availability before a
matching ``v0.1.0``\\+ git tag exists.

The page's install section is meant to read "not on PyPI yet ... install from source" up to
and including Step 8's merge, and switch to real ``pip install mambo-power`` / ``uv add
mambo-power`` instructions only in the same action as the ``v0.1.0`` tag push (Step 9). This
script is the guard that keeps that sequencing from silently drifting in a later wave: it reads
the page, detects an *unqualified* PyPI install instruction (one not accompanied by "not on
PyPI yet" / "wave M9" pre-release framing in the same paragraph), and — only when it finds
one — asserts a ``v0.1.0``\\+ tag is reachable from ``HEAD``. When no such instruction is
present, the check passes trivially: that is the correct pre-release state.

Run directly: ``python3 scripts/check_pypi_sequencing.py`` (no project deps needed — stdlib
only). Wired into CI as its own lean job (``.github/workflows/ci.yml``, job
``pypi-sequencing``).
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GETTING_STARTED = REPO_ROOT / "docs" / "getting-started.md"

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

# A real install invocation naming this package: `pip install mambo-power`, `uv add
# mambo-power`, with `-` or `_` in the name and an optional version pin/extra
# (`mambo-power==0.1.0`, `mambo_power[docs]`). Deliberately anchored on the *command*, not on
# any mention of "PyPI" as a word, so prose like "mambo-power is not on PyPI yet" never
# matches on its own.
PYPI_INSTALL_PATTERN = re.compile(
    r"\b(?:pip install|uv add)\s+([\"']?)mambo[-_]power\1(?:\[[^\]]*\])?(?:[=<>!~][^\s`\"']*)?",
    re.IGNORECASE,
)

# Phrases that mark a paragraph as explicit pre-release framing, so a paragraph carrying one
# of these does not count as a live PyPI claim even if it also happens to name the install
# command (e.g. describing what *will* be run once released). Matches this page's actual
# current wording ("not on PyPI yet ... wave M9") without pinning to that exact sentence.
NOT_YET_PATTERN = re.compile(
    r"not\s+(?:yet\s+)?on\s+pypi|\bnot\s+yet\b|\bwave\s+m9\b", re.IGNORECASE
)


def _blocks(content: str) -> list[str]:
    """Split markdown into paragraph/code-fence blocks (separated by a blank line)."""
    return re.split(r"\n\s*\n", content)


def has_unqualified_pypi_install_text(content: str) -> bool:
    """True if `content` contains a PyPI install command not qualified as pre-release.

    A block matching :data:`PYPI_INSTALL_PATTERN` counts as an unqualified claim unless that
    block, or the block immediately preceding it (the usual place for an introductory
    sentence ahead of a fenced command), matches :data:`NOT_YET_PATTERN`.
    """
    blocks = _blocks(content)
    for i, block in enumerate(blocks):
        if not PYPI_INSTALL_PATTERN.search(block):
            continue
        context = block if i == 0 else blocks[i - 1] + "\n\n" + block
        if not NOT_YET_PATTERN.search(context):
            return True
    return False


def _is_release_tag(tag: str) -> bool:
    """True if `tag` is a `v<major>.<minor>.<patch>` tag at or above v0.1.0."""
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)(?:[-+].*)?", tag.strip())
    if not match:
        return False
    version = tuple(int(part) for part in match.groups())
    return version >= (0, 1, 0)


def matching_tag_exists(repo_root: Path, *, runner: Runner = subprocess.run) -> bool:
    """True if a `v0.1.0`+ tag is reachable (merged) from HEAD in `repo_root`."""
    result = runner(
        ["git", "tag", "--list", "v*", "--merged", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    tags = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return any(_is_release_tag(tag) for tag in tags)


def check(
    content: str,
    repo_root: Path = REPO_ROOT,
    *,
    runner: Runner = subprocess.run,
) -> tuple[bool, str]:
    """Evaluate the AC-3 rule against `content`. Returns (ok, message)."""
    if not has_unqualified_pypi_install_text(content):
        return True, "OK: no unqualified PyPI install text found (pre-release state)."
    if matching_tag_exists(repo_root, runner=runner):
        return True, "OK: PyPI install text present and a v0.1.0+ tag is reachable from HEAD."
    return False, (
        "FAIL: docs/getting-started.md contains an unqualified PyPI install instruction "
        "(a `pip install`/`uv add mambo-power` line not framed as pre-release) but no "
        "v0.1.0+ git tag is reachable from HEAD. Per wave M9 spec W5/AC-3, PyPI install "
        "instructions may only be added in the same action as the v0.1.0 tag push — either "
        "restore the pre-release framing or cut the matching tag."
    )


def main(
    argv: list[str] | None = None,
    *,
    getting_started_path: Path = GETTING_STARTED,
    repo_root: Path = REPO_ROOT,
    runner: Runner = subprocess.run,
) -> int:
    del argv  # no CLI options; present for a conventional main() signature
    content = getting_started_path.read_text(encoding="utf-8")
    ok, message = check(content, repo_root, runner=runner)
    print(message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
