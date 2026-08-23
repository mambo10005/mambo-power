"""Load a MATPOWER case, read the import report, and see validation fail with every issue.

What this shows:

* ``io.matpower.load_with_report`` returns the ``Network`` **and** an ``ImportReport`` whose
  typed ``ImportIssue`` entries name every repair the importer made (here: case14 stores
  ``BASE_KV = 0`` on every bus, which becomes 1.0 kV with one issue per bus).
* A network can be built by hand from the entity classes; the model validates on construction.
* Validation reports **all** issues at once: one ``NetworkValidationError`` carrying a
  ``ValidationIssue`` (code, path, message) per problem, never just the first one.
* ``validate_network`` re-checks a mutated network and returns the issues instead of raising.

Run from the repository root: ``uv run python examples/01_load_and_validate.py``.
"""

from __future__ import annotations

from mambo_power.io import matpower
from mambo_power.model import (
    Branch,
    Bus,
    Generator,
    Load,
    Network,
    NetworkValidationError,
    validate_network,
)

# --- 1. Load a case with its import report -------------------------------------------------
net, report = matpower.load_with_report("fixtures/matpower/case14.m")
print("case14:", len(net.buses), "buses,", len(net.branches), "branches,", end=" ")
print(len(net.generators), "generators,", len(net.loads), "loads,", len(net.shunts), "shunts")
print("base_mva:", net.base_mva, "| slack:", [b.id for b in net.buses if b.type == "slack"])
print("import report:", len(report.warnings), "issue(s), codes", sorted(report.codes))
first = report.warnings[0]
print("first issue:", first.code, "| buses", first.bus_ids, "|", first.message)
print("legacy string form:", report.as_strings()[0])

# --- 2. Build a tiny network by hand ------------------------------------------------------
mini = Network(
    base_mva=100,
    buses=[
        Bus(id="b1", base_kv=110, type="slack"),
        Bus(id="b2", base_kv=110, type="pv"),
        Bus(id="b3", base_kv=110, type="pq"),
    ],
    branches=[
        Branch(id="l12", from_bus="b1", to_bus="b2", r=0.01, x=0.10, b=0.02),
        Branch(id="l13", from_bus="b1", to_bus="b3", r=0.02, x=0.20, b=0.02),
        Branch(id="l23", from_bus="b2", to_bus="b3", r=0.01, x=0.10, b=0.02),
    ],
    generators=[
        Generator(
            id="g1",
            bus="b1",
            p_mw=0,
            q_mvar=0,
            p_min_mw=0,
            p_max_mw=300,
            q_min_mvar=-100,
            q_max_mvar=100,
            v_set_pu=1.02,
        ),
        Generator(
            id="g2",
            bus="b2",
            p_mw=60,
            q_mvar=0,
            p_min_mw=0,
            p_max_mw=100,
            q_min_mvar=-40,
            q_max_mvar=40,
            v_set_pu=1.01,
        ),
    ],
    loads=[Load(id="d3", bus="b3", p_mw=120, q_mvar=40)],
)
print("hand-built network is valid:", validate_network(mini) == [])

# --- 3. Trigger a validation error and print every issue ----------------------------------
broken = {
    "base_mva": 100,
    "buses": [
        {"id": "a", "base_kv": 110, "type": "pq"},
        {"id": "a", "base_kv": 0, "type": "pq"},
    ],
    "branches": [{"id": "x", "from_bus": "a", "to_bus": "zz", "r": 0.0, "x": 0.0, "b": 0.0}],
    "generators": [
        {
            "id": "g",
            "bus": "a",
            "p_mw": 10,
            "q_mvar": 0,
            "p_min_mw": 50,
            "p_max_mw": 20,
            "q_min_mvar": 0,
            "q_max_mvar": 0,
            "v_set_pu": 1.0,
        }
    ],
}
try:
    Network.model_validate(broken)
except NetworkValidationError as err:
    print(f"NetworkValidationError with {len(err.issues)} issue(s); codes {sorted(err.codes)}")
    for issue in err.issues:
        print(f"  {issue.code:16s} {issue.path:22s} {issue.message}")

# --- 4. Mutation does not re-validate; validate_network does -----------------------------
mini.buses[2].base_kv = -1.0
issues = validate_network(mini)
print("after mutation:", [(i.code, i.path) for i in issues])
