"""Packaging metadata: the installed distribution and the import surface agree (AC-8 support).

Runs against whatever install pytest sees — the editable install in the normal suite — and
guards the metadata the wheel/sdist smoke job relies on: a PEP 440 version string and a
``py.typed`` marker inside the package.
"""

import re
from importlib import metadata, resources

import mambo_power

# Canonical PEP 440 version pattern (Appendix B of the spec), kept inline so the test does not
# depend on the ``packaging`` distribution, which is not a declared dependency of this project.
_PEP440 = re.compile(
    r"""
    ^v?
    (?:(?:(?P<epoch>[0-9]+)!)?
    (?P<release>[0-9]+(?:\.[0-9]+)*)
    (?P<pre>[-_\.]?(?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview))[-_\.]?(?P<pre_n>[0-9]+)?)?
    (?P<post>(?:-(?P<post_n1>[0-9]+))|(?:[-_\.]?(?P<post_l>post|rev|r)[-_\.]?(?P<post_n2>[0-9]+)?))?
    (?P<dev>[-_\.]?(?P<dev_l>dev)[-_\.]?(?P<dev_n>[0-9]+)?)?)
    (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)


def test_distribution_version_is_pep440() -> None:
    installed = metadata.version("mambo-power")
    assert _PEP440.match(installed), f"not a PEP 440 version: {installed!r}"


def test_dunder_version_matches_distribution_metadata() -> None:
    assert mambo_power.__version__ == metadata.version("mambo-power")


def test_py_typed_marker_ships_inside_the_package() -> None:
    assert resources.files("mambo_power").joinpath("py.typed").is_file()
