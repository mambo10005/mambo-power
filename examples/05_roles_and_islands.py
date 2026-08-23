"""Effective bus roles and the island policy on the derived case14 fixtures.

What this shows:

* ``numerics.effective_roles`` derives the roles a solver must use from the declared ones:
  a PV bus whose only generator is out of service solves as PQ; a bus with two in-service
  generators takes the **last** one's ``v_set_pu`` (MATPOWER's rule) and a
  ``SetpointConflictWarning`` names the bus when the setpoints differ.
* A slack bus without an in-service generator is a named error, ``NoSlackGeneratorError``.
* Islands: ``load_with_report`` deactivates the buses the slack cannot reach (and their
  elements) and reports an ``ISLAND_DEACTIVATED`` issue listing them; the solve then runs on
  the main island. The model itself stays strict: constructing the same ``Network`` with the
  island switched back on raises ``DISCONNECTED_BUS``.

Run from the repository root: ``uv run python examples/05_roles_and_islands.py``.
"""

from __future__ import annotations

import warnings

from mambo_power import pf
from mambo_power.io import matpower
from mambo_power.model import Network, NetworkValidationError
from mambo_power.numerics import (
    NetworkArrays,
    NoSlackGeneratorError,
    SetpointConflictWarning,
    effective_roles,
)

ROLE = {1: "pq", 2: "pv", 3: "slack"}

# --- 1. Effective roles on case14_roles ----------------------------------------------------
net = matpower.load("fixtures/matpower/derived/case14_roles.m")
arr = NetworkArrays.from_network(net)
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    roles = effective_roles(arr)
print("case14_roles: declared vs effective role where they differ")
for i, bus_id in enumerate(arr.bus_ids):
    if arr.bus_type[i] != roles.bus_type[i]:
        print(f"  {bus_id}: declared {ROLE[int(arr.bus_type[i])]}, effective", end=" ")
        print(f"{ROLE[int(roles.bus_type[i])]} (no in-service generator)")
print("demoted PV buses:", [arr.bus_ids[i] for i in roles.demoted_pv])
for bus_id, gen_ids, setpoints in roles.setpoint_conflicts:
    print(f"setpoint conflict at {bus_id}: {gen_ids} -> {setpoints}; last wins:", end=" ")
    print(roles.v_set[arr.bus_index[bus_id]])
print("warnings raised:", [type(w.message).__name__ for w in caught])
assert any(issubclass(w.category, SetpointConflictWarning) for w in caught)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", SetpointConflictWarning)
    result = pf.solve_ac(net, options=pf.AcOptions(init="flat"))
bus6 = next(b for b in result.buses if b.id == "bus-6")
bus2 = next(b for b in result.buses if b.id == "bus-2")
print(f"solved: bus-6 role_effective={bus6.role_effective} vm={bus6.vm_pu:.4f} pu;", end=" ")
print(f"bus-2 vm={bus2.vm_pu:.4f} pu (the last generator's setpoint)")

# --- 2. Slack without a generator --------------------------------------------------------
noslack = matpower.load("fixtures/matpower/derived/case14_noslackgen.m")
try:
    pf.solve_ac(noslack)
except NoSlackGeneratorError as err:
    print(f"\ncase14_noslackgen: NoSlackGeneratorError for {err.bus_id}: {err}")

# --- 3. Island repair by the importer ------------------------------------------------------
island, report = matpower.load_with_report("fixtures/matpower/derived/case14_island.m")
issue = next(w for w in report.warnings if w.code == "ISLAND_DEACTIVATED")
print("\ncase14_island:", issue.code, "| buses", issue.bus_ids, "| elements", issue.element_ids)
print("  message:", issue.message)
live_buses = sum(b.in_service for b in island.buses)
live_gens = sum(g.in_service for g in island.generators)
print(f"  in service: {live_buses} of {len(island.buses)} buses,", end=" ")
print(f"{live_gens} of {len(island.generators)} generators")
main = pf.solve_ac(island, options=pf.AcOptions(init="flat"))
print(f"  solve on the main island: converged={main.converged}, {len(main.buses)} bus rows")

# --- 4. The model stays strict --------------------------------------------------------------
raw = island.model_dump()
for bus in raw["buses"]:
    if bus["id"] in issue.bus_ids:
        bus["in_service"] = True
try:
    Network.model_validate(raw)
except NetworkValidationError as err:
    print("direct Network with the island re-enabled ->", sorted(err.codes), end=": ")
    print([i.path for i in err.issues])
