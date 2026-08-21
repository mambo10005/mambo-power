"""Root test configuration.

Tests are tiered by directory — ``tests/unit``, ``tests/parity``, ``tests/property`` — and
the matching marker is applied automatically so ``pytest -m parity`` (etc.) selects a tier
without every test repeating the decorator.
"""

from pathlib import Path

import pytest

TIERS = ("unit", "parity", "property")
TESTS_ROOT = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        try:
            relative = item.path.resolve().relative_to(TESTS_ROOT)
        except ValueError:
            continue
        tier = relative.parts[0] if relative.parts else None
        if tier in TIERS:
            item.add_marker(getattr(pytest.mark, tier))
