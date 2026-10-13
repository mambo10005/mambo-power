"""Bundled test cases: the MATPOWER and PSS/E RAW files shipped inside the package.

The files live under ``mambo_power/cases/data/`` and ship in the wheel, so a bare
``pip install mambo-power`` can load them without a repository clone::

    from mambo_power import cases, pf

    result = pf.solve_dc(cases.load("case14"))

Names are relative POSIX paths under that directory — ``"case14.m"``,
``"derived/case14_roles.m"``, ``"case14_v33.raw"``. The six top-level ``.m`` files are verbatim
MATPOWER distribution bytes; ``derived/`` holds synthetic case14 variants (among them
``case14_rated``, the one bundled case with a binding thermal rating on every branch, for N-1
and OPF flow limits) and the ``.raw`` file is a hand transcription of case14. Their provenance
records (``PROVENANCE.md``, ``SOURCES.md``, ``derived/PROVENANCE.md``, ``PROVENANCE-raw.md``)
ship alongside them but are not listed as cases.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from mambo_power.io import matpower
from mambo_power.model import Network

__all__ = ["available", "load", "path"]

_CASE_SUFFIXES = (".m", ".raw")


def _data_dir() -> Path:
    # The package is installed unzipped, so the resource root is a real directory and
    # ``as_file`` would only add a context manager around the same path.
    return Path(str(files(__name__) / "data"))


def available() -> list[str]:
    """List every bundled case file.

    :returns: The sorted relative POSIX names of the ``.m`` and ``.raw`` files, e.g.
        ``"case14.m"``, ``"derived/case14_roles.m"`` and ``"case14_v33.raw"``. Provenance
        markdown is not included.
    """
    root = _data_dir()
    return sorted(
        file.relative_to(root).as_posix()
        for file in root.rglob("*")
        if file.is_file() and file.suffix in _CASE_SUFFIXES
    )


def path(name: str) -> Path:
    """Return the on-disk path of a bundled case file.

    :param name: A name from :func:`available`, including its suffix (``"case14.m"``).
    :returns: The absolute path of the file.
    :raises ValueError: If ``name`` is not one of :func:`available`; the message lists them.
    """
    names = available()
    if name not in names:
        raise ValueError(f"unknown bundled case {name!r}; available cases: {', '.join(names)}")
    return _data_dir().joinpath(*name.split("/"))


def load(name: str) -> Network:
    """Load a bundled MATPOWER case with :func:`mambo_power.io.matpower.load`.

    :param name: A ``.m`` name from :func:`available`, with or without the suffix —
        ``"case14"``, ``"case14.m"`` and ``"derived/case14_pwl"`` all work.
    :returns: The imported network; repair warnings are discarded as in
        :func:`mambo_power.io.matpower.load`.
    :raises ValueError: If ``name`` is not a bundled MATPOWER case. A ``.raw`` name is rejected
        too: read it with :func:`mambo_power.io.psse_raw.load` on :func:`path`.
    """
    if name.endswith(".raw"):
        raise ValueError(
            f"{name!r} is a PSS/E RAW case; load it with "
            f"mambo_power.io.psse_raw.load(cases.path({name!r}))"
        )
    filename = name if name.endswith(".m") else f"{name}.m"
    return matpower.load(path(filename))
