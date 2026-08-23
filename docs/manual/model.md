# Network model

`mambo_power.model` defines the **`Network`** root and its entities as pydantic v2 models. The
JSON form of these models is the native file format; the JSON schema is generated from them
and snapshot-tested. This page is the class-by-class reference: fields, units, optionality and
the invariants that validation enforces. The [API reference](../api/model.md) lists the same
classes with their signatures.

## Conventions that apply everywhere

| Convention | Rule |
| --- | --- |
| Units | Physical: MW, MVAr, MVA, kV, MWh, degrees. Branch `r`, `x`, `b` are per-unit on `Network.base_mva`. Voltages `*_pu` are per-unit of the bus `base_kv`. Per-unit conversion of powers happens only in [`NetworkArrays`](numerics.md). |
| Field names | snake_case with a unit suffix: `p_mw`, `q_mvar`, `base_kv`, `v_set_pu`, `shift_deg`, `energy_mwh`. |
| Ids | Stable strings, unique within their collection. References (`Branch.from_bus`, `Generator.bus`, `Bus.zone`) are ids, never indices. |
| `in_service` | A boolean on every element; defaults to `True`. Out-of-service elements stay in the file and are dropped from the numerics. |
| Unknown fields | Rejected (`extra="forbid"`): a typo in a file is an error, not silently dropped data. |
| Non-finite numbers | Rejected (`allow_inf_nan=False`). A quantity that does not exist is `None`. |
| Optional fields | Default to `None` and are omitted from native JSON on write. |

## `Network`

The root document. Construction — `Network(...)`, `Network.model_validate(...)`,
`Network.model_validate_json(...)` — runs every cross-entity invariant in one pass and
raises `NetworkValidationError` listing every issue found.

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `schema_version` | `Literal[1]` | `1` | Format version stamp; bumps only on a breaking schema change. |
| `base_mva` | `float` | required | System MVA base for every per-unit quantity. Must be > 0 (`BAD_BASE`). |
| `buses` | `list[Bus]` | `[]` | At least one in-service slack is required (`NO_SLACK`). |
| `branches` | `list[Branch]` | `[]` | Lines and transformers. |
| `generators` | `list[Generator]` | `[]` | Dispatchable injections. |
| `loads` | `list[Load]` | `[]` | Fixed demand. |
| `shunts` | `list[Shunt]` | `[]` | Fixed shunt admittances. |
| `storage` | `list[Storage]` | `[]` | Energy storage; schema-present, no solver reads it yet. |
| `zones` | `list[Zone]` | `[]` | Named bus groupings. |

Methods:

- `Network.json_schema() -> dict` — the JSON schema of the native format (see
  [JSON schema](#json-schema)).
- The usual pydantic surface: `model_dump()`, `model_dump_json()`, `model_validate()`,
  `model_validate_json()`, `model_copy()`.

## `Bus`

An electrical node. `vm_pu` / `va_deg` hold an initial or last-solved state when present
(MATPOWER's VM/VA columns import here); solvers use them as a warm start when every in-service
bus carries both.

| Field | Type | Unit | Default | Notes |
| --- | --- | --- | --- | --- |
| `id` | `str` | — | required | Unique within `buses`. |
| `base_kv` | `float` | kV | required | Nominal voltage; must be > 0 (`BAD_BASE`). |
| `type` | `"slack" \| "pv" \| "pq"` | — | required | Declared power-flow role. Exactly one in-service slack per network. |
| `in_service` | `bool` | — | `True` | MATPOWER type 4 (isolated) imports as `in_service=False`. |
| `vm_pu` | `float \| None` | pu | `None` | Voltage magnitude (initial or solved). |
| `va_deg` | `float \| None` | degrees | `None` | Voltage angle (initial or solved). |
| `v_min_pu` | `float \| None` | pu | `None` | Lower voltage limit; must be ≤ `v_max_pu` when both given (`BAD_RANGE`). |
| `v_max_pu` | `float \| None` | pu | `None` | Upper voltage limit. |
| `area` | `str \| None` | — | `None` | Free-form area label (MATPOWER AREA). |
| `zone` | `str \| None` | — | `None` | Must resolve to a `Zone.id` (`DANGLING_REF`). |
| `geo` | `Geo \| None` | — | `None` | Position. |

`BusType` is the type alias `Literal["slack", "pv", "pq"]`. The *declared* type is not always
the role a solver uses: a PV bus without an in-service generator is solved as PQ (see
[Power flow › Effective bus roles](power-flow.md#effective-bus-roles)).

### `Geo`

| Field | Type | Unit | Notes |
| --- | --- | --- | --- |
| `lat` | `float` | decimal degrees | WGS 84 latitude. |
| `lon` | `float` | decimal degrees | WGS 84 longitude. |

## `Branch`

A line or a transformer between two buses. The tap is on the **from** side (MATPOWER's
π-model with the off-nominal tap at the from end).

| Field | Type | Unit | Default | Notes |
| --- | --- | --- | --- | --- |
| `id` | `str` | — | required | Unique within `branches`. |
| `from_bus` | `str` | — | required | Bus id of the from (tap) side; must exist (`DANGLING_REF`). |
| `to_bus` | `str` | — | required | Bus id of the to side; must exist and differ from `from_bus` (`BAD_RANGE`). |
| `r` | `float` | pu on `base_mva` | required | Series resistance. |
| `x` | `float` | pu on `base_mva` | required | Series reactance. `r` and `x` must not both be 0 (`BAD_RANGE`). |
| `b` | `float` | pu on `base_mva` | required | **Total** line-charging susceptance; builders apply `b/2` per end. |
| `rating_mva` | `float \| None` | MVA | `None` | Thermal rating; `None` means unrated. Must be > 0 when given (`BAD_RANGE`). |
| `tap_ratio` | `float \| None` | — | `None` | Off-nominal tap magnitude; `None` means 1.0. Must be > 0 when given (`BAD_RANGE`). |
| `shift_deg` | `float \| None` | degrees | `None` | Phase shift; `None` means 0. |
| `in_service` | `bool` | — | `True` | |

## `Generator`

A dispatchable injection. `cost` is present in the schema from M1 so that M3's optimal power
flow needs no schema bump; no power-flow solver reads it.

| Field | Type | Unit | Default | Notes |
| --- | --- | --- | --- | --- |
| `id` | `str` | — | required | Unique within `generators`. |
| `bus` | `str` | — | required | Bus id; must exist (`DANGLING_REF`). |
| `p_mw` | `float` | MW | required | Active setpoint (input) or dispatch. |
| `q_mvar` | `float` | MVAr | required | Reactive setpoint or dispatch. |
| `p_min_mw` | `float` | MW | required | Must be ≤ `p_max_mw` (`BAD_RANGE`). |
| `p_max_mw` | `float` | MW | required | |
| `q_min_mvar` | `float` | MVAr | required | Must be ≤ `q_max_mvar` (`BAD_RANGE`). |
| `q_max_mvar` | `float` | MVAr | required | |
| `v_set_pu` | `float` | pu | required | Voltage setpoint used when the bus is PV or slack. |
| `in_service` | `bool` | — | `True` | |
| `cost` | `PolynomialCost \| PiecewiseCost \| None` | — | `None` | Discriminated on `kind`. |

Several generators may sit on one bus. Their powers and limits are summed per bus in the
numerics; the voltage setpoint rule is described under
[effective roles](power-flow.md#effective-bus-roles).

### `PolynomialCost` (`kind = "polynomial"`)

MATPOWER gencost MODEL 2: \(\text{cost}(p) = \sum_k c_k\,p^k\), coefficients highest order
first, cost per hour.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `kind` | `"polynomial"` | `"polynomial"` | Discriminator. |
| `coefficients` | `list[float]` | required | At least one (`BAD_RANGE`), highest order first. |
| `startup` | `float` | `0.0` | Startup cost. |
| `shutdown` | `float` | `0.0` | Shutdown cost. |

### `PiecewiseCost` (`kind = "piecewise"`)

MATPOWER gencost MODEL 1: piecewise-linear breakpoints.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `kind` | `"piecewise"` | `"piecewise"` | Discriminator. |
| `points` | `list[tuple[float, float]]` | required | `(p_mw, cost)` pairs; at least two, `p_mw` strictly increasing (`BAD_RANGE`). |
| `startup` | `float` | `0.0` | |
| `shutdown` | `float` | `0.0` | |

`GeneratorCost` is the annotated union of the two, discriminated on `kind`.

## `Load`

| Field | Type | Unit | Default | Notes |
| --- | --- | --- | --- | --- |
| `id` | `str` | — | required | Unique within `loads`. |
| `bus` | `str` | — | required | Must exist (`DANGLING_REF`). |
| `p_mw` | `float` | MW | required | Active demand (positive consumes). |
| `q_mvar` | `float` | MVAr | required | Reactive demand. |
| `in_service` | `bool` | — | `True` | |

## `Shunt`

A fixed shunt specified by its power at 1.0 pu voltage, MATPOWER GS/BS sign convention.

| Field | Type | Unit | Default | Notes |
| --- | --- | --- | --- | --- |
| `id` | `str` | — | required | Unique within `shunts`. |
| `bus` | `str` | — | required | Must exist (`DANGLING_REF`). |
| `g_mw` | `float` | MW at 1.0 pu | required | Conductance; **positive consumes**. |
| `b_mvar` | `float` | MVAr at 1.0 pu | required | Susceptance; **positive injects** (a capacitor is positive). |
| `in_service` | `bool` | — | `True` | |

## `Storage`

Schema-present for the market waves; no M1/M2 solver reads it.

| Field | Type | Unit | Default | Notes |
| --- | --- | --- | --- | --- |
| `id` | `str` | — | required | Unique within `storage`. |
| `bus` | `str` | — | required | Must exist (`DANGLING_REF`). |
| `p_max_mw` | `float` | MW | required | Charge/discharge power limit. |
| `energy_mwh` | `float` | MWh | required | Energy capacity. |
| `soc_initial` | `float` | fraction | required | Initial state of charge in \([0, 1]\) (`BAD_RANGE`). |
| `efficiency_charge` | `float` | fraction | required | In \((0, 1]\) (`BAD_RANGE`). |
| `efficiency_discharge` | `float` | fraction | required | In \((0, 1]\) (`BAD_RANGE`). |
| `in_service` | `bool` | — | `True` | |

## `Zone`

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | `str` | required | Unique within `zones`; referenced by `Bus.zone`. |
| `name` | `str \| None` | `None` | Display name. |

## Validation

### The all-issues contract

Validation never stops at the first problem. `Network` construction runs every invariant and
raises **one** `NetworkValidationError` whose `.issues` lists every `ValidationIssue` found,
each with a stable `code`, a `path` into the document (`buses[3].base_kv`) and a message.
`.codes` is the set of distinct codes for quick membership checks; `str(err)` prints the
full list.

`NetworkValidationError` subclasses `Exception`, **not** `ValueError`. pydantic wraps any
`ValueError` raised inside a validator into its own `ValidationError` and would drop the issue
list; a plain `Exception` propagates unchanged through `Network(...)`, `model_validate` and
`model_validate_json`. Catch it by name:

```python
from mambo_power.model import Network, NetworkValidationError

text = '{"base_mva": 100, "buses": [{"id": "a", "base_kv": 110, "type": "pq"}]}'
try:
    net = Network.model_validate_json(text)
except NetworkValidationError as err:
    for issue in err.issues:
        print(issue.code, issue.path, issue.message)
```

```text
NO_SLACK buses no in-service slack bus defined
```

Field-level problems that pydantic itself detects — a missing required field, a string
where a number is expected, an unknown field, `NaN` — still raise pydantic's
`ValidationError` before the invariant pass runs.

### Validation codes

| Code | Triggered when |
| --- | --- |
| `NO_SLACK` | No bus has `type="slack"` **and** `in_service=True`. |
| `MULTIPLE_SLACK` | More than one in-service slack bus. |
| `DISCONNECTED_BUS` | An in-service bus cannot reach the slack over in-service branches whose end buses are both in service (one issue per unreachable bus). Importers repair this case by deactivating the island — see [islands](formats.md#islands); the model itself stays strict. |
| `DUPLICATE_ID` | Two elements in the same collection share an `id` (ids may repeat across collections). |
| `DANGLING_REF` | `Branch.from_bus` / `to_bus`, `Generator.bus`, `Load.bus`, `Shunt.bus`, `Storage.bus` names a bus that does not exist; `Bus.zone` names a zone that does not exist. |
| `BAD_BASE` | `base_mva <= 0`, or a bus with `base_kv <= 0`. |
| `BAD_RANGE` | `v_min_pu > v_max_pu`; `from_bus == to_bus`; `tap_ratio <= 0`; `r == x == 0`; `rating_mva <= 0`; `p_min_mw > p_max_mw`; `q_min_mvar > q_max_mvar`; an empty polynomial cost; a piecewise cost with fewer than two points or non-increasing `p_mw`; `soc_initial` outside \([0, 1]\); an efficiency outside \((0, 1]\). |

`ValidationCode` is the `Literal` of these seven strings.

### `validate_network`

Models are mutable and mutation never re-validates. `validate_network(net)` runs the same
invariant pass and **returns** the issue list (empty means valid) instead of raising:

```python
from mambo_power.io import matpower
from mambo_power.model import validate_network

net = matpower.load("fixtures/matpower/case14.m")
net.buses[0].base_kv = 0.0
issues = validate_network(net)
assert issues and issues[0].code == "BAD_BASE"
print(issues[0].path)
```

```text
buses[0].base_kv
```

Use it after editing a network in place and before handing it to a solver. Solvers do not
re-validate either; `NetworkArrays.from_network` only re-checks the slack count. (The
[jobs API](jobs.md) does re-validate, because it must not trust its input.)

## Import issues and island repair

A `ValidationIssue` is something the model **rejects**; an `ImportIssue` is something an
importer **repaired** and wants the caller to know about. Both are frozen pydantic records
with a closed code set, so callers can dispatch on `code` without parsing text.

| `ImportIssue` field | Type | Meaning |
| --- | --- | --- |
| `code` | `ImportIssueCode` | `"ISLAND_DEACTIVATED"`, `"BASE_KV_REPLACED"` or `"GENCOST_REACTIVE_IGNORED"`. |
| `message` | `str` | Human-readable description. |
| `bus_ids` | `list[str]` | Buses involved, if any. |
| `element_ids` | `list[str]` | Branches, generators, loads, shunts or storage involved, if any. |

`str(issue)` is the `CODE: message` line the legacy `list[str]` importer APIs return; the
typed form is returned by `load_with_report` inside an `ImportReport` (see
[File formats](formats.md#warnings-repairs)). The class was first shipped as
`ImportWarning` and renamed because that shadowed the built-in of the same name; it is a
record, not a `Warning`, and is never passed to `warnings.warn`.

### `repair_islands`

The model rejects an in-service bus that cannot reach the slack (`DISCONNECTED_BUS`). Real
files contain such islands, so every importer runs the **one shared repair** before
validation: `repair_islands(net) -> (Network, list[ImportIssue])` walks the in-service graph
from the in-service slack over in-service branches whose end buses are both in service, sets
`in_service=False` on every unreached bus and on every in-service branch, generator, load,
shunt and storage attached to it, and returns a new, validated `Network` plus one
`ISLAND_DEACTIVATED` issue **per island** listing the buses and the elements it switched off
(elements that were already out are not listed). The input is never mutated. With no
in-service slack nothing is changed — that is `NO_SLACK`'s job to report. The entity-level
form, `repair_islands_entities(buses, branches, generators, loads, shunts, storage)`, is what
importers call before they construct the `Network`.

```python
from mambo_power.io import matpower
from mambo_power.model import repair_islands

net = matpower.load("fixtures/matpower/case14.m")
net.branches[13].in_service = False  # branch-14 (7-8) is case14's only bridge: bus-8 islands
repaired, issues = repair_islands(net)
print([(i.code, i.bus_ids, i.element_ids) for i in issues])
print(sum(b.in_service for b in repaired.buses), "of", len(repaired.buses), "buses in service")
print(sum(b.in_service for b in net.buses), "in the untouched input")
```

```text
[('ISLAND_DEACTIVATED', ['bus-8'], ['gen-5'])]
13 of 14 buses in service
14 in the untouched input
```

The model itself stays strict: `Network.model_validate(...)` with the island switched back on
raises `DISCONNECTED_BUS`. [`05_roles_and_islands.py`](../examples/index.md#5-roles-and-islands)
shows both sides on the `case14_island` fixture.

## JSON schema

`Network.json_schema()` returns the JSON schema (draft 2020-12, as pydantic emits it) of the
native format. Entities appear under `$defs`; range bounds are documented in each field's
`description` rather than as `minimum`/`maximum` keywords, because the bounds are enforced in
the all-issues pass, not by pydantic field constraints.

```python
import json
from mambo_power.model import Network

schema = Network.json_schema()
print(sorted(schema["$defs"]))
with open("network.schema.json", "w", encoding="utf-8") as fh:
    json.dump(schema, fh, indent=2)
```

```text
['Branch', 'Bus', 'Generator', 'Geo', 'Load', 'PiecewiseCost', 'PolynomialCost', 'Shunt', 'Storage', 'Zone']
```

The committed snapshot under `tests/unit/snapshots/` is compared against this output in CI, so
any schema change is a visible diff.

## Mutability caveats

- Entities and the network are **not frozen**: `net.buses[0].base_kv = 220` works and does
  not re-validate. Run `validate_network` afterwards.
- Importers and solvers never mutate a network they are given. `solve_dc(net)` returns a
  separate result value; nothing is written back to `net.buses[i].vm_pu`.
- Lists are shared by reference in `model_copy()`; use `model_copy(deep=True)` before editing
  a copy.
- Because unknown fields are rejected, you cannot stash custom attributes on an entity; use
  a side table keyed by id.
