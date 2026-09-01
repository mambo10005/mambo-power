"""Native JSON format: the serialised :class:`~mambo_power.model.Network` itself.

``loads(dumps(net)) == net`` for every valid network. Fields that are ``None`` are omitted on
write and default back to ``None`` on read, so files stay short and round-trip exactly.
"""

from os import PathLike
from pathlib import Path

from mambo_power.model import Network

__all__ = ["dumps", "load", "loads", "save"]


def dumps(net: Network) -> str:
    """Serialise to indented JSON without null fields."""
    return net.model_dump_json(indent=2, exclude_none=True)


def loads(text: str | bytes) -> Network:
    """Parse JSON text into a validated :class:`Network`."""
    return Network.model_validate_json(text)


def save(net: Network, path: str | PathLike[str]) -> None:
    """Write :func:`dumps` output to ``path`` as UTF-8 with a trailing newline."""
    Path(path).write_text(dumps(net) + "\n", encoding="utf-8", newline="\n")


def load(path: str | PathLike[str]) -> Network:
    """Read a native JSON file into a validated :class:`Network`."""
    return loads(Path(path).read_text(encoding="utf-8"))
