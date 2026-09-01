"""The MATPOWER fixture list, declared once for every tier.

Importable as ``tests._fixtures`` because ``pyproject.toml`` puts the repository root on
``pythonpath`` (``tests`` is a PEP 420 namespace package under ``--import-mode=importlib``).
Adding a fixture here is the only edit needed for the round-trip, parity and dense tiers to
pick it up.
"""

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "matpower"
FIXTURES = ["case14", "case30", "case_ieee30", "case57", "case118", "case300"]
