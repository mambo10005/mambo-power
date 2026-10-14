"""``python -m mambo_power``: the :mod:`mambo_power.cli` command line."""

from __future__ import annotations

import sys

from mambo_power.cli import main

if __name__ == "__main__":  # pragma: no cover - the module exists to be run
    sys.exit(main())
