# File formats

`mambo_power.io` holds importers and exporters. Every format speaks only
[`mambo_power.model`](model.md): an importer produces a validated `Network`, an exporter
consumes one, and neither touches arrays or solvers. Two formats ship today — the **native
JSON** format and the **MATPOWER `.m`** importer. pandapower JSON, PyPSA, PSS/E RAW and a CSV
bundle are scheduled for wave M8.

## Native JSON

The native format is the `Network` model serialised by pydantic — there is no separate schema
to keep in sync. `mambo_power.io.native` wraps the four operations:

| Function | Does |
| --- | --- |
| `native.dumps(net) -> str` | Indented JSON, `None` fields omitted. |
| `native.loads(text) -> Network` | Parse and validate; raises `NetworkValidationError` or pydantic's `ValidationError`. |
| `native.save(net, path)` | Write `dumps` output as UTF-8 with a trailing newline. |
| `native.load(path) -> Network` | Read a file into a validated `Network`. |

`loads(dumps(net)) == net` holds for every valid network (tested on every fixture).

A minimal document — two buses, one line, one generator, one load:

```json
{
  "schema_version": 1,
  "base_mva": 100.0,
  "buses": [
    {"id": "b1", "base_kv": 110.0, "type": "slack", "in_service": true},
    {"id": "b2", "base_kv": 110.0, "type": "pq", "in_service": true}
  ],
  "branches": [
    {"id": "l12", "from_bus": "b1", "to_bus": "b2", "r": 0.01, "x": 0.1, "b": 0.02, "in_service": true}
  ],
  "generators": [
    {"id": "g1", "bus": "b1", "p_mw": 0.0, "q_mvar": 0.0,
     "p_min_mw": 0.0, "p_max_mw": 200.0, "q_min_mvar": -100.0, "q_max_mvar": 100.0,
     "v_set_pu": 1.0, "in_service": true}
  ],
  "loads": [
    {"id": "d2", "bus": "b2", "p_mw": 50.0, "q_mvar": 10.0, "in_service": true}
  ],
  "shunts": [],
  "storage": [],
  "zones": []
}
```

Rules worth knowing:

- `schema_version` is `1` and is the only accepted value; a future breaking change bumps it.
- Optional fields (`vm_pu`, `rating_mva`, `cost`, ...) may be omitted or written as `null`;
  on write they are omitted.
- Unknown keys anywhere are an error. Non-finite numbers are an error.
- The JSON schema for validators and editors comes from `Network.json_schema()`
  (see [Network model › JSON schema](model.md#json-schema)).

## MATPOWER `.m` importer

`mambo_power.io.matpower` reads MATPOWER case files — the de-facto exchange format for
academic test systems. It is a **parser, not a MATLAB interpreter**: it recognises
`mpc.<name> = <scalar>;`, `mpc.<name> = [ rows ];` and `mpc.<name> = { ... };` statements,
tolerates `%` comments, tabs, blank lines, CRLF line endings, a UTF-8 BOM, scientific
notation, rows split by `;` or by newlines, and ignores every field it does not know.

| Function | Does |
| --- | --- |
| `matpower.load(path) -> Network` | Parse a file; repair warnings discarded. |
| `matpower.loads(text) -> Network` | Parse case text. |
| `matpower.load_with_report(path) -> (Network, ImportReport)` | Parse and return the repairs performed as typed [`ImportIssue`](model.md#import-issues-and-island-repair) entries (code, message, bus and element ids). |
| `matpower.loads_with_report(text) -> (Network, ImportReport)` | Same, from text. |
| `matpower.load_with_warnings(path) -> (Network, list[str])` | The legacy form: one `CODE: message` string per repair — exactly `report.as_strings()`. |
| `matpower.loads_with_warnings(text) -> (Network, list[str])` | Same, from text. |

The path/text split follows the `json` module precedent; the importer never sniffs whether a
string is a path or a document.

### Sections read

`mpc.baseMVA` (required), `mpc.bus`, `mpc.gen`, `mpc.branch` (required), `mpc.gencost`
(optional). `mpc.version` is not checked — the caseformat v2 column layout is assumed.
`mpc.bus_name`, `mpc.areas` and any user-defined fields are skipped.

### Derived ids

| Element | Id | Emitted |
| --- | --- | --- |
| Bus | `bus-<BUS_I>` | every row |
| Generator | `gen-<row>` (1-based row in `mpc.gen`) | every row |
| Branch | `branch-<row>` (1-based row in `mpc.branch`) | every row |
| Load | `load-<BUS_I>` | only when `PD != 0` or `QD != 0` |
| Shunt | `shunt-<BUS_I>` | only when `GS != 0` or `BS != 0` |
| Zone | `<ZONE>` as a compact string (`1.0` → `"1"`) | one per distinct `ZONE` value |

### Column map — `mpc.bus`

| Col | MATPOWER | Field | Notes |
| --- | --- | --- | --- |
| 1 | `BUS_I` | `id = "bus-<n>"` | must be integer-valued |
| 2 | `BUS_TYPE` | `type`, `in_service` | 1 → `pq`, 2 → `pv`, 3 → `slack`, **4 → `pq` with `in_service=False`**; anything else is `BAD_NUMBER` |
| 3 | `PD` | `Load.p_mw` | with col 4, emitted as `load-<n>` when non-zero |
| 4 | `QD` | `Load.q_mvar` | |
| 5 | `GS` | `Shunt.g_mw` | with col 6, emitted as `shunt-<n>` when non-zero |
| 6 | `BS` | `Shunt.b_mvar` | |
| 7 | `BUS_AREA` | `area` | compact string |
| 8 | `VM` | `vm_pu` | |
| 9 | `VA` | `va_deg` | |
| 10 | `BASE_KV` | `base_kv` | `<= 0` is replaced by `1.0` with a warning |
| 11 | `ZONE` | `zone` (+ a `Zone`) | compact string |
| 12 | `VMAX` | `v_max_pu` | |
| 13 | `VMIN` | `v_min_pu` | |
| 14–17 | `LAM_P`, `LAM_Q`, `MU_VMAX`, `MU_VMIN` | dropped | OPF result columns |

### Column map — `mpc.gen`

| Col | MATPOWER | Field | Notes |
| --- | --- | --- | --- |
| 1 | `GEN_BUS` | `bus = "bus-<n>"` | |
| 2 | `PG` | `p_mw` | |
| 3 | `QG` | `q_mvar` | |
| 4 | `QMAX` | `q_max_mvar` | |
| 5 | `QMIN` | `q_min_mvar` | |
| 6 | `VG` | `v_set_pu` | |
| 7 | `MBASE` | dropped | machine base; all quantities are on the system base |
| 8 | `GEN_STATUS` | `in_service` | `> 0` is in service |
| 9 | `PMAX` | `p_max_mw` | |
| 10 | `PMIN` | `p_min_mw` | |
| 11–21 | `PC1`…`APF` | dropped | capability-curve and AGC columns |
| 22–25 | `MU_*` | dropped | OPF result columns |

### Column map — `mpc.branch`

| Col | MATPOWER | Field | Notes |
| --- | --- | --- | --- |
| 1 | `F_BUS` | `from_bus` | |
| 2 | `T_BUS` | `to_bus` | |
| 3 | `BR_R` | `r` | pu |
| 4 | `BR_X` | `x` | pu |
| 5 | `BR_B` | `b` | pu, total charging |
| 6 | `RATE_A` | `rating_mva` | `0` means unrated → `None` |
| 7–8 | `RATE_B`, `RATE_C` | dropped | short-term / emergency ratings |
| 9 | `TAP` | `tap_ratio` | `0` means nominal → `None` |
| 10 | `SHIFT` | `shift_deg` | `0` → `None` |
| 11 | `BR_STATUS` | `in_service` | `> 0` is in service |
| 12–13 | `ANGMIN`, `ANGMAX` | dropped | angle-difference limits |
| 14–21 | `PF`…`MU_ANGMAX` | dropped | power-flow / OPF result columns |

### `mpc.gencost`

| Col | MATPOWER | Field |
| --- | --- | --- |
| 1 | `MODEL` | `2` → `PolynomialCost`, `1` → `PiecewiseCost`; anything else is `BAD_NUMBER` |
| 2 | `STARTUP` | `startup` |
| 3 | `SHUTDOWN` | `shutdown` |
| 4 | `NCOST` | number of coefficients (MODEL 2) or breakpoints (MODEL 1); must be ≥ 1 |
| 5… | `COST` | MODEL 2: `NCOST` coefficients highest order first → `coefficients`; MODEL 1: `NCOST` pairs `(p, cost)` → `points` |

Accepted shapes: exactly `ngen` rows (one per generator), or `2 * ngen` rows (reactive-power
costs appended) — the second half is ignored with a warning. Any other row count is `BAD_ROW`.
When `mpc.gencost` is absent every generator has `cost=None`.

### Warnings (repairs)

Conditions that are repaired rather than rejected are reported by `load_with_report` /
`loads_with_report` as an `ImportReport` whose `.warnings` are typed `ImportIssue` records
(`code`, `message`, `bus_ids`, `element_ids`; `.codes` is the set of distinct codes), and by
`load_with_warnings` / `loads_with_warnings` as the same entries rendered `CODE: message`:

| Code | Repair |
| --- | --- |
| `BASE_KV_REPLACED` | `BASE_KV <= 0` becomes `1.0` (CDF-derived cases store 0 for "unknown"); one issue per bus, naming the bus (`bus_ids`) and the line. |
| `GENCOST_REACTIVE_IGNORED` | `mpc.gencost` had `2 * ngen` rows; the second half (reactive costs) was dropped. |
| `ISLAND_DEACTIVATED` | Buses the slack cannot reach over in-service branches were switched off together with their generators, loads, shunts and storage; one issue per island, `bus_ids` and `element_ids` list what was switched off (decision D1). |

`load` / `loads` apply the same repairs and discard the report.

```python
from mambo_power.io import matpower

net, report = matpower.load_with_report("fixtures/matpower/derived/case14_island.m")
print(sorted(report.codes), len(report.warnings))
island = next(w for w in report.warnings if w.code == "ISLAND_DEACTIVATED")
print(island.bus_ids, island.element_ids)
print(str(island))
```

```text
['BASE_KV_REPLACED', 'ISLAND_DEACTIVATED'] 15
['bus-8'] ['gen-5']
ISLAND_DEACTIVATED: bus bus-8 cannot reach slack bus bus-1 over in-service branches; deactivated with attached elements [gen-5]
```

### Islands

The model rejects a network with an in-service bus that cannot reach the slack
(`DISCONNECTED_BUS`), because such a bus has no reference angle. Real files contain islands —
a branch out of service that splits off a sub-network. The importer therefore **repairs before
it validates**: every bus outside the slack's component is set `in_service=False`, so is
every element attached to those buses, and one `ISLAND_DEACTIVATED` warning lists them. The
resulting `Network` is valid and solves on the main island; the deactivated elements remain
in the file for inspection. Building the same `Network(...)` by hand still raises — the
importer repairs, the model stays strict. The shared implementation,
[`model.repair_islands`](model.md#import-issues-and-island-repair), is what every later
importer must call too. [`05_roles_and_islands.py`](../examples/index.md#5-roles-and-islands)
walks through the repaired fixture and the model's rejection of the same network.

### Errors

Anything wrong with the **file** raises `MatpowerImportError` with a stable `code` and a
1-based `line` when known:

| Code | Cause |
| --- | --- |
| `MISSING_BASE_MVA` | No `mpc.baseMVA = ...;` statement. |
| `MISSING_SECTION` | `mpc.bus`, `mpc.gen` or `mpc.branch` matrix not found. |
| `UNTERMINATED_MATRIX` | A `[` or `{` block never closed. |
| `BAD_NUMBER` | A token is not a finite number; a column that must be an integer is not; `BUS_TYPE` not in 1–4; gencost `MODEL` not 1 or 2; `NCOST < 1`. |
| `BAD_ROW` | A row narrower than the minimum for its matrix (bus 13, gen 10, branch 11, gencost 4), ragged rows, a gencost row too short for its `NCOST`, or a gencost row count that is neither `ngen` nor `2 * ngen`. |

Anything wrong with the **network** — no slack, a dangling bus reference, inverted limits —
is left to `Network` validation and raises `NetworkValidationError`
(see [validation codes](model.md#validation-codes)).

### Limitations

- Only the caseformat v2 column layout is supported; v1 files (no `mpc.` prefix, different
  branch columns) are not recognised.
- Dropped columns (listed above): `MBASE`, `PC1`–`APF`, `RATE_B`/`RATE_C`, `ANGMIN`/`ANGMAX`,
  every `MU_*` / `LAM_*` and stored-result column. Re-exporting a case is therefore lossy
  for those fields (an exporter is not shipped yet).
- `mpc.bus_name` is ignored because `Bus` carries no name field.
- No DC lines (`mpc.dcline`), no three-winding transformers, no three-phase data.
- The reactive half of a `2 * ngen` gencost is dropped, not stored.

### Example

```python
from mambo_power.io import matpower

net, warnings = matpower.load_with_warnings("fixtures/matpower/case14.m")
print(len(net.buses), len(warnings), warnings[0])
```

```text
14 14 BASE_KV_REPLACED: bus-1: BASE_KV is 0; base_kv set to 1.0 (line 25)
```

## Bundled fixtures

The repository ships MATPOWER cases under `fixtures/matpower/` with their provenance recorded
in `PROVENANCE.md` / `SOURCES.md`: `case14`, `case30`, `case_ieee30`, `case57`, `case118` and
`case300` (verbatim bytes with recorded sha256), plus derived variants under `derived/` that
exercise effective-role and island handling. These are public IEEE test data as distributed
by MATPOWER; see the provenance files for the exact wording.
