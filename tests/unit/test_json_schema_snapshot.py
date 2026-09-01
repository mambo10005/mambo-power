"""AC-4 (schema half): the exported JSON schema matches the committed snapshot.

If this test fails because you changed the model on purpose, regenerate the snapshot with

    MAMBO_UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/test_json_schema_snapshot.py

then review the diff of tests/unit/snapshots/network.schema.json and commit it with the
model change. A schema change is a file-format change: say so in the commit message.
"""

import json
import os
from pathlib import Path

from mambo_power.model import Network

SNAPSHOT = Path(__file__).parent / "snapshots" / "network.schema.json"
REGENERATE_HINT = (
    "JSON schema of mambo_power.model.Network differs from the committed snapshot "
    f"{SNAPSHOT}. If the model change is intentional, regenerate with "
    "`MAMBO_UPDATE_SNAPSHOTS=1 uv run pytest tests/unit/test_json_schema_snapshot.py`, "
    "review the snapshot diff, and commit it together with the model change."
)


def test_json_schema_matches_snapshot() -> None:
    current = Network.json_schema()
    if os.environ.get("MAMBO_UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8", newline="\n")
    assert SNAPSHOT.exists(), REGENERATE_HINT
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current == committed, REGENERATE_HINT


def test_json_schema_is_the_pydantic_schema() -> None:
    assert Network.json_schema() == Network.model_json_schema()


def test_json_schema_names_every_entity() -> None:
    defs = Network.json_schema()["$defs"]
    expected = {
        "Bus",
        "Branch",
        "Generator",
        "Geo",
        "Load",
        "Shunt",
        "Storage",
        "Zone",
        "PolynomialCost",
        "PiecewiseCost",
    }
    assert expected <= set(defs), set(defs)
