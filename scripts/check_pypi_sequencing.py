#!/usr/bin/env python3
"""AC-3 (wave M9, W5): ``docs/getting-started.md``'s PyPI-availability claim must always agree
with whether a matching ``v0.1.0``\\+ git tag exists — in **both** directions.

The page's install section is meant to read "not on PyPI yet ... install from source" up to
and including Step 8's merge, and switch to real ``pip install mambo-power`` / ``uv add
mambo-power`` instructions only in the same action as the ``v0.1.0`` tag push (Step 9). This
script is the guard that keeps that sequencing from silently drifting in a later wave. It checks
both halves of the agreement:

- an *unqualified* PyPI install instruction (one not accompanied by "not on PyPI yet" / "wave
  M9" pre-release framing in the same paragraph) present with **no** matching tag — the
  original direction, claiming release before it happened;
- a matching tag reachable from ``HEAD`` with **no** unqualified install instruction present —
  the reverse: released, but the page still reads pre-release. (Step-6 critic finding C5: the
  first cut of this guard only checked the first direction, so it would print "OK ...
  (pre-release state)" and exit 0 forever after a real release, on an unmodified page.)

Only when neither half of the disagreement holds does the check pass.

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
    """True if `tag` is a real, final `v<major>.<minor>.<patch>` tag at or above v0.1.0.

    A prerelease or build-metadata suffix (`-rc1`, `+build.5`) is rejected outright, not just
    stripped: by semver a prerelease sorts *below* its release and is not "released" in the
    plain sense AC-3 means. This matters beyond naming, per Step-6 reviewer finding R3 — this
    predicate now also gates the *reverse* direction of `check()` (a matching tag REQUIRES live
    PyPI install text). Treating an rc tag as a match would make cutting a release candidate —
    the ordinary way to smoke-test a first trusted-publish run — fail CI until someone writes an
    install instruction that is still false.
    """
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag.strip())
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
    """Evaluate the AC-3 rule against `content`. Returns (ok, message).

    Bidirectional (critic finding C5): a tag must always be checked, even when `content` has
    no unqualified install text, because that combination — tag exists, page still reads
    pre-release — is itself the failure a post-release drift would produce.
    """
    unqualified = has_unqualified_pypi_install_text(content)
    tag_exists = matching_tag_exists(repo_root, runner=runner)
    if unqualified and not tag_exists:
        return False, (
            "FAIL: docs/getting-started.md contains an unqualified PyPI install instruction "
            "(a `pip install`/`uv add mambo-power` line not framed as pre-release) but no "
            "v0.1.0+ git tag is reachable from HEAD. Per wave M9 spec W5/AC-3, PyPI install "
            "instructions may only be added in the same action as the v0.1.0 tag push — either "
            "restore the pre-release framing or cut the matching tag."
        )
    if tag_exists and not unqualified:
        return False, (
            "FAIL: a v0.1.0+ git tag is reachable from HEAD, but docs/getting-started.md "
            "carries no unqualified PyPI install instruction — it still reads as pre-release. "
            "Per wave M9 spec W5/AC-3, the page must switch to real `pip install`/`uv add "
            "mambo-power` instructions in the same action as the tag push."
        )
    if unqualified and tag_exists:
        return True, "OK: PyPI install text present and a v0.1.0+ tag is reachable from HEAD."
    return True, "OK: no unqualified PyPI install text found (pre-release state)."


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
