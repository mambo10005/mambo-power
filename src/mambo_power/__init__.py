"""mambo-power: power system analysis and electricity market modelling."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mambo-power")
except PackageNotFoundError:  # pragma: no cover - only when the package is not installed
    __version__ = "0.0.0"

__all__ = ["__version__"]
