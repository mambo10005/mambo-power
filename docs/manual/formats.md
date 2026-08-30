# File formats

`mambo_power.io` holds importers and exporters. Every format speaks only
[`mambo_power.model`](model.md): an importer produces a validated `Network`, an exporter
consumes one, and neither touches arrays or solvers. Six formats ship: the **native JSON**
format, the **MATPOWER `.m`** importer, **pandapower JSON** both ways, **PyPSA** export, the
**PSS/E RAW v33** importer and the **CSV bundle**. Every importer returns an `ImportReport` and
every exporter an `ExportReport` (see [`io.report`](../api/io-report.md)) with one rule: an
empty report means the conversion was lossless; anything dropped, approximated or repaired is an
issue naming the element id and the field. [`io.limitations.LIMITATIONS`](../api/io-limitations.md)
maps each module to every code it can emit, and each code is documented on this page.

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

## pandapower JSON

`mambo_power.io.pandapower_json` reads and writes the JSON that pandapower's `pp.to_json` /
`pp.from_json` produce and consume — a `pandapowerNet` document with one table per element
type. pandapower itself is imported lazily, inside the functions that need it, so
`mambo_power` keeps its zero-optional-dependency import; both directions need pandapower
installed only when they run. Every conversion is **best effort + report**: anything the other
side cannot hold is dropped or repaired *and named in the report* with the element id and the
field; an empty report means the conversion was lossless. Nothing is logged or printed.

| Function | Does |
| --- | --- |
| `pandapower_json.load(path) -> Network` | Read a `pp.to_json` file; repair report discarded. |
| `pandapower_json.loads(text) -> Network` | Same, from text. |
| `pandapower_json.load_with_report(path) -> (Network, ImportReport)` | Read and return every drop and repair as typed [`ImportIssue`](model.md#import-issues-and-island-repair) entries. |
| `pandapower_json.loads_with_report(text) -> (Network, ImportReport)` | Same, from text. |
| `pandapower_json.dumps(net, *, f_hz=50.0) -> str` | Write a document `pp.from_json` loads; report discarded. |
| `pandapower_json.dump(net, path, *, f_hz=50.0)` | Same, to a file. |
| `pandapower_json.dumps_with_report(net, *, f_hz=50.0) -> (str, ExportReport)` | Write and return what pandapower could not carry. |

`f_hz` is pandapower's system frequency (its `create_empty_network` default is 50 Hz); it
enters only the `c_nf_per_km` conversion below, and the importer reads the document's own
`f_hz`.

### Tables read

`bus`, `ext_grid`, `gen`, `sgen`, `load`, `shunt`, `line`, `trafo` (two-winding), `poly_cost`,
`pwl_cost`. **Results tables (`res_bus`, `res_line`, ...) are neither read nor written** — the
wave's scope excludes pandapower results, and a solved `res_bus` in the file is a result, not
model data. The slack bus is the one bus with a state after import: its `vm_pu` / `va_deg` come
from the `ext_grid` row's `vm_pu` / `va_degree` (the setpoint the slack holds), and every other
bus has `None` — the warm-start rule in [the model page](model.md) (every in-service bus carries
both) does not apply to an imported file. On export the same holds in reverse: a stored state on
any other bus is not written and is named, once, in a `FIELD_DROPPED` issue whose `bus_ids` list
them.
Every other non-empty table — `trafo3w`, `switch`, `impedance`, `ward`, `xward`, `dcline`,
`storage`, `motor`, `asymmetric_*`, ... — is dropped **row by row** with `ELEMENT_DROPPED`, so
the report says exactly what was left behind.

### Derived ids

Import takes the row's `name` when it is present and not empty, else `<table>-<index>`
(`bus-3`, `trafo-0`, `ext_grid-0`). `pp.networks.case14()` names its buses `1`…`14` and leaves
its branches unnamed, so the imported ids are `"1"`, `line-0`, `trafo-0`. Export writes the
mambo id into `name`, so a network survives a round trip with its ids intact. Zones come from
`bus.zone` — one `Zone` per distinct value, id = the compact string form (`1.0` → `"1"`).

### Bus roles and the `ext_grid` rule

pandapower has no bus `type` column; roles come from what is connected. On import the **first
in-service `ext_grid`** is the slack (its bus is `slack`, the `ext_grid` row becomes the slack
generator with `v_set_pu = vm_pu` and limits from `min/max_p_mw`, `min/max_q_mvar`); every
further in-service `ext_grid` is **demoted to a PV generator** with `EXTRA_EXT_GRID_DEMOTED`,
because the model has exactly one slack. With **no in-service `ext_grid`** — none at all, or
every one switched off — the first in-service `gen` with `slack = True` (pandapower's own
ext_grid-less reference bus, which `runpp` solves) is the slack, reported `GEN_SLACK_PROMOTED`,
with `vm_pu` from `gen.vm_pu` and `va_deg = 0`; a `gen.slack = True` beside a live `ext_grid`
stays a PV generator and the flag is `COLUMN_DROPPED`. A file with neither a live `ext_grid`
nor a live slack `gen` has no reference bus, and the import ends in `NetworkValidationError`
(`NO_SLACK`) — the network is what the file says, and the model refuses it, as it refuses a
MATPOWER case with no type-3 bus. A bus with an in-service `gen` is `pv`; everything else is
`pq`. `sgen` rows become generators on their PQ bus (`v_set_pu = 1.0`, `p`/`q` scaled by
`scaling`). On export the rule runs backwards: the first in-service generator on the slack bus
becomes `ext_grid`, PV-bus generators become `gen`, PQ-bus generators become `sgen`.

### Unit conversions (measured on pandapower 3.3.0)

All impedances are per unit on `sn_mva` and the **from-bus** voltage; `Zb = vn_kv² / sn_mva`.

| pandapower | Field | Conversion |
| --- | --- | --- |
| `line.r_ohm_per_km`, `length_km`, `parallel` | `r` | `r_ohm_per_km · length / parallel / Zb` (same for `x`) |
| `line.c_nf_per_km` | `b` | `2π·f_hz · c_nf_per_km·1e-9 · length · parallel · Zb` |
| `line.max_i_ka`, `df` | `rating_mva` | `max_i_ka · df · parallel · √3 · vn_kv(from)` |
| `trafo.vk_percent`, `vkr_percent`, `sn_mva`, `vn_lv_kv` | `x`, `r` | `z = vk/100 · sn_mva/sn_trafo · (vn_lv_kv / vn(lv bus))² / parallel`, `r` likewise from `vkr`, `x = √(z² − r²)` — on the **system** base |
| `trafo.vn_hv_kv`, `vn_lv_kv`, `tap_*` | `tap_ratio`, `shift_deg` | `(vn_hv_kv/vn(hv bus)) / (vn_lv_kv/vn(lv bus))` after the tap changer has scaled the tapped winding, by pandapower 3.3's own rule (`build_branch._calc_tap_from_dataframe`): `tap_changer_type = None` applies **no** tap (the columns are inert in pandapower too; a non-neutral `tap_pos` is `COLUMN_DROPPED`); a pre-3.0 table with a `tap_phase_shifter` column and no `tap_changer_type` is read as pandapower 3.3's deprecation branch still does, `True` as `"Ideal"` and `False` as `"Ratio"`; `"Ratio"` / `"Symmetrical"` scale the winding by `1 + (tap_pos − tap_neutral)·tap_step_percent/100`, rotated by `tap_step_degree` when it is set (which also adds to `shift_deg`); `"Ideal"` adds `±(tap_pos − tap_neutral)·tap_step_degree` (or the arcsin-of-percent form) to `shift_deg` and leaves the ratio alone. `from_bus = hv_bus` (mambo's tap side) |
| `trafo.shift_degree`, `sn_mva` | `shift_deg`, `rating_mva` | as is |
| `shunt.p_mw`, `q_mvar`, `step`, `vn_kv` | `g_mw`, `b_mvar` | pandapower's values are *consumption*, mambo's `b_mvar` is *injection*: `b_mvar = −q_mvar · step · (vn(bus)/vn_kv)²`, `g_mw = p_mw · step · (vn(bus)/vn_kv)²` |
| `poly_cost.cp2/cp1/cp0` | `PolynomialCost.coefficients = [c2, c1, c0]` | both ways; the `cq*` columns are dropped |
| `pwl_cost.points = [[p0, p1, slope], ...]` | `PiecewiseCost.points` | breakpoints with the cost at `p0` taken as 0 — pandapower has no offset column |
| `bus.vn_kv`, `min/max_vm_pu`, `zone`, `geo`, `in_service` | `base_kv`, `v_min/max_pu`, `zone`, `geo`, `in_service` | `Bus.area` travels as an extra `bus.area` column (pandapower keeps unknown columns through `to_json`, measured) |

On export a nominal-tap transformer (`tap_ratio` `None` or `1.0`) is written with no tap
changer — `tap_side` `None`, `tap_neutral` / `tap_pos` / `tap_step_percent` `NaN`, the columns
pandapower itself leaves empty on such a transformer (its `networks.case14()` stores two that
way); an off-nominal one with `tap_side = "hv"`, `tap_neutral = 0`, `tap_pos = ±1` and
`tap_step_percent = |tap_ratio − 1|·100`, which is pandapower's own `from_ppc` encoding.
Both re-import to the same ratio. A transformer without `rating_mva` is
written with `sn_mva = base_mva` and `FIELD_DEFAULTED`, because pandapower needs a rated power
to compute its impedance — it re-imports as a rating.

### Warnings (repairs)

| Code | Direction | Repair |
| --- | --- | --- |
| `EXTRA_EXT_GRID_DEMOTED` | import | A second in-service `ext_grid`; imported as a PV generator (one slack). `bus_ids` names the bus. |
| `GEN_SLACK_PROMOTED` | import | No in-service `ext_grid`; the first in-service `gen` with `slack = True` became the slack generator (`bus_ids` names the bus, `element_ids` the generator). |
| `COLUMN_DROPPED` | import | A column the model has no place for held a non-inert value (`bus.type != "b"`, `gen.slack` beside a live `ext_grid`, `gen.slack_weight`, `line.g_us_per_km`, `trafo.pfe_kw` / `i0_percent`, a `trafo.tap_pos` off neutral under `tap_changer_type = None` (pandapower applies no tap either), a `trafo.tap_pos` whose `tap_neutral` is NaN — `create_transformer_from_parameters`'s own default — under a changer type (pandapower's step is NaN and counts as 0: no tap on either side), `load.const_z_*` / `const_i_*`, `*.max_loading_percent`, `*.controllable`, ...); the message names table, row, column and value. |
| `TAP_CHANGER_TYPE_UNSUPPORTED` | import | A `trafo` tap changer neither pandapower nor the model can express as a ratio and a shift: an unknown `tap_changer_type`, an `"Ideal"` shifter with both `tap_step_percent` and `tap_step_degree` set (`runpp` refuses it too), or a `tap_side` that is neither `hv` nor `lv`. Imported at the nominal tap; the message names the transformer. |
| `ELEMENT_DROPPED` | both | Import: a row of a table that is not read (`trafo3w`, `switch`, `storage`, ...) or a `poly_cost` / `pwl_cost` row that is not a generator's active-power cost. Export: a `Storage` unit (pandapower's `storage` has no efficiency columns). |
| `FIELD_DEFAULTED` | both | Import: a missing or `NaN` limit column (`min/max_p_mw`, `min/max_q_mvar` on `ext_grid` / `gen` / `sgen`) set to the element's setpoint, so the limits pin the setpoint rather than invent a range. Export: an unrated transformer's `sn_mva` set to `base_mva`. |
| `ISLAND_DEACTIVATED` | import | As for MATPOWER: buses that cannot reach the slack are switched off with their elements ([islands](#islands)). |
| `FIELD_DROPPED` | export | A model field with no pandapower column: `Zone.name`, a stored `Bus.vm_pu` / `va_deg` on any bus but the slack (results tables are not written; one issue, `bus_ids` names them), generator `ramp_up_mw` / `ramp_down_mw`, the slack generator's `p_mw` / `q_mvar` (`ext_grid` has no setpoint), a PV generator's `q_mvar`, an `sgen`'s `v_set_pu`, a transformer's `b` (no line charging on a trafo), `cost.startup` / `cost.shutdown`, and a piecewise cost's offset `points[0][1]`. |
| `COST_DROPPED` | export | A polynomial cost of degree > 2 (`poly_cost` holds `cp0..cp2`); dropped, never approximated. |
| `BID_DROPPED` | export | A load's demand bid (pandapower has no elastic demand); the load is written as a fixed `p_mw`. |

### Errors

A document that is not a `pandapowerNet` JSON, a table without its required columns, or a
reference to a missing bus raises pandapower's or pydantic's own exception; anything wrong
with the resulting **network** (no slack, inverted limits) raises `NetworkValidationError` as
for every format.

### Limitations

- Three-winding transformers, switches, impedances, wards, DC lines, motors and every
  asymmetric table are dropped (and reported), not modelled; a `switch` that opens a line is
  **not** applied to `in_service`.
- The tap changer is folded into `tap_ratio` / `shift_deg` exactly as pandapower 3.3 applies it
  (table above), so a `tap_pos` under `tap_changer_type = None` — pandapower's default from
  `create_transformer_from_parameters` — is inert on both sides; the changer's position itself
  (`tap_pos`, `tap_min`, `tap_max`) is not a model field and does not survive a round trip
  (the export writes a `±1` position encoding the ratio).
- A network with a non-zero `shift_deg` gets wrong or infeasible `opf` / `market` results
  until the phase-shifter fix lands (M8 finding F1, carried as A19): `opf.dc_opf`'s flow rows
  omit the shifter's PTDF term, so the flows are wrong when the LP solves and a generously
  rated loop with one shifter can come back `Infeasible` with no flows at all. `pf.solve_dc`
  is right, and pandapower's `rundcpp` agrees with it.
- **Round trip, measured (F2):** `pp.toolbox.nets_equal(from_json(dumps(loads(to_json(pn)))),
  pn)` holds for `poly_cost` and `pwl_cost` only. `bus`, `ext_grid`, `gen`, `sgen`, `load`,
  `shunt`, `line` and `trafo` fail strict equality on `name` (`None` in pandapower vs our ids),
  dtype (`bus.name` int vs str, `bus.zone` `1.0` vs `"1"`), the default-column sets `create_*`
  adds versus `from_ppc`, and 5e-13 float noise on `vk_percent` / `tap_step_percent` — never
  on a carried value: every value column the model holds survives at 1e-12
  (`tests/unit/test_io_pandapower_json.py::test_nets_equal_round_trip_measured` pins the set).
- pandapower's own solvers agree with mambo's on the exported document: `rundcpp` vs
  `pf.solve_dc` to 1.3e-13° and `runpp` vs `pf.solve_ac` to 2.4e-15 pu on case14 / case30 /
  case57 (`tests/parity/test_pandapower_json_vs_pandapower.py`).

### Example

```python
import pandapower as pp
import pandapower.networks as pn

from mambo_power.io import pandapower_json

net, report = pandapower_json.loads_with_report(pp.to_json(pn.case14()))
print(len(net.buses), len(net.branches), [b.id for b in net.branches if b.kind == "transformer"])
print(sorted(report.codes), len(report.warnings))
```

```text
14 20 ['trafo-0', 'trafo-1', 'trafo-2', 'trafo-3', 'trafo-4']
[] 0
```

## PyPSA export

`mambo_power.io.pypsa` turns a `Network` into a `pypsa.Network` — export only; PyPSA is
imported lazily inside the two functions. The field map was verified against
`opf.solve_dc_opf`: PyPSA's `optimize()` on the exported network reproduces mambo's DC-OPF
objective on every bundled case (`tests/parity/test_pypsa_export_vs_pypsa.py`).

| Function | Does |
| --- | --- |
| `pypsa.to_network(net) -> pypsa.Network` | Export; report discarded. |
| `pypsa.to_network_with_report(net) -> (pypsa.Network, ExportReport)` | Export and return what PyPSA cannot carry. |

### Field map

| Model | PyPSA | Notes |
| --- | --- | --- |
| `Bus` | `Bus` | `v_nom = base_kv`, `v_mag_pu_min/max`, `control` (`Slack` / `PV` / `PQ`) from `type`, `x`/`y` from `geo` (lon, lat), `v_mag_pu_set` from the bus's **in-service** generators' `v_set_pu`. `area`, `zone` and `in_service` ride along as **custom bus columns** (PyPSA buses have no `active` flag); every element at an out-of-service bus is exported `active = False`, which is what `numerics.NetworkArrays` does with them. |
| `Branch` with `is_transformer` false (a line at nominal tap) | `Line` | Physical units on the from-bus base, `Zb = base_kv² / base_mva`: `r`, `x` in ohm (`× Zb`), `b` in siemens (`÷ Zb`). |
| `Branch` with `is_transformer` (`kind == "transformer"` or an off-nominal tap/shift) | `Transformer(model="pi")` | `r`, `x`, `b` per unit on the transformer's own `s_nom` (impedances `r`, `x` `× s_nom / base_mva`; the admittance `b` `× base_mva / s_nom`), `tap_ratio`, `tap_side = 0` (mambo's tap is on the from side), `phase_shift` in degrees. |
| `rating_mva` | `s_nom` | An unrated branch gets `s_nom = 1e5` (`pypsa.UNRATED_S_NOM_MVA`): PyPSA's optimiser reads `s_nom == 0` as "carries nothing", not "unlimited". Reported per branch as `PYPSA_UNRATED_S_NOM_DEFAULTED`. |
| `Generator` | `Generator` | `p_nom = max(abs(p_min_mw), abs(p_max_mw))`, `p_min_pu` / `p_max_pu` as fractions of it (so `p_nom == p_max_mw` in the ordinary case and a negative-only range survives), `marginal_cost = c1`, `marginal_cost_quadratic = c2`, `ramp_limit_up/down` as fractions of `p_nom`, `start_up_cost` / `shut_down_cost`, `control`, `active`. |
| constant cost term `c0` | `marginal_cost_constant` | A **custom column** (`pypsa.COST_CONSTANT_COLUMN`): `n.objective` excludes constants, so the value is carried beside the objective, not in it. |
| `Load` | `Load(p_set, q_set)` | |
| `Shunt` | `ShuntImpedance(g, b)` | siemens, `MW / kV²`. |
| `Storage` | `StorageUnit` | `p_nom`, `max_hours`, `state_of_charge_initial`, `efficiency_store`, `efficiency_dispatch`. |
| `base_mva` | `n.meta["base_mva"]` | |

**`p_set` is never written on a generator.** A non-NaN `p_set` pins the dispatch in
`optimize()` — that was the root cause behind M3's first PyPSA parity mismatch.

### Warnings (dropped or defaulted, never silently)

| Code | Dropped |
| --- | --- |
| `PYPSA_PWL_COST_DROPPED` | A piecewise-linear cost; the generator is exported with `marginal_cost 0`. |
| `PYPSA_COST_DEGREE_DROPPED` | A polynomial cost of effective degree > 2; exported with `marginal_cost 0`. |
| `PYPSA_LOAD_BID_DROPPED` | A load's demand bid; the load is exported as a fixed `p_set`. |
| `PYPSA_ZONE_DROPPED` | The `zones` list (PyPSA has no zone component); the bus `zone` column still names them. |
| `PYPSA_GEN_Q_LIMITS_DROPPED` | `q_min_mvar` / `q_max_mvar` (PyPSA generators carry no reactive limits). |
| `PYPSA_GEN_RAMP_DROPPED` | A ramp on a zero-capacity generator (cannot be a fraction of `p_nom = 0`). |
| `PYPSA_GEN_VSET_CONFLICT` | In-service generators at one bus disagreeing on `v_set_pu`; PyPSA has one `v_mag_pu_set` per bus, the first in-service generator's wins (out-of-service units do not take part). |
| `PYPSA_COST_NONCONVEX` | A quadratic cost with `c2 < 0` (concave). Exported unchanged as `marginal_cost_quadratic` — nothing is dropped — but PyPSA's solver will reject the non-convex objective with its own error, so the report names the generator up front. |
| `PYPSA_UNRATED_S_NOM_DEFAULTED` | A branch with `rating_mva = None`, written with `s_nom = 1e5` (`pypsa.UNRATED_S_NOM_MVA`); one entry per branch naming it and the sentinel. |

Every issue names the element id and the field. The exporter raises nothing of its own: a
`Network` is already valid, and PyPSA's constructors are given only values they accept.

### Limitations

- PyPSA cannot express piecewise costs, polynomial costs of degree > 2, demand bids, zones
  or generator reactive limits (measured on PyPSA 1.2.4); each is dropped and reported under
  the codes above.
- PyPSA 1.2.4's `optimize()` **ignores `phase_shift`** — only `lpf()` / `pf()` read it. The
  exporter carries the shift faithfully (`n.lpf()` agrees with `pf.solve_dc` on a shifted
  loop, sign included), so it is not reported, but DC-OPF parity is a statement about
  shift-free networks.
- On the mambo side, a network with a non-zero `shift_deg` gets wrong or infeasible `opf` /
  `market` results until the phase-shifter fix lands (F1 / A19): `opf.dc_opf`'s flow rows omit
  the shifter's PTDF term, so the flows are wrong when the LP solves and a generously rated
  loop with one shifter can come back `Infeasible` with no flows at all. `pf.solve_dc` is right
  and matches PyPSA's `lpf()`.
- Parity, measured (F3): the DC-OPF objective agrees to 1e-8 relative on case14, case30 and
  case118 (worst 1.3e-12) and the dispatch to 1e-4 MW on case14 and case30. On case118 one
  generator differs by 1.87e-3 MW — the oracle's residual, not the mapping's: both dispatches
  balance 4242.0 MW, the exact polynomial puts mambo's point 1.6e-7 $/h *below* PyPSA's, and
  HiGHS reports a 1.1e-6 primal-dual objective error that no tolerance or algorithm setting
  moves. The parity test pins 2e-3 MW for case118 only.

### Example

```python
from mambo_power.io import matpower, pypsa

net = matpower.load("fixtures/matpower/case14.m")
n, report = pypsa.to_network_with_report(net)
print(sorted(report.codes), len(report.warnings))
print(n.generators[["p_nom", "marginal_cost", "marginal_cost_quadratic"]].head(2))
```

```text
['PYPSA_GEN_Q_LIMITS_DROPPED', 'PYPSA_UNRATED_S_NOM_DEFAULTED', 'PYPSA_ZONE_DROPPED'] 26
       p_nom  marginal_cost  marginal_cost_quadratic
name
gen-1  332.4           20.0                 0.043029
gen-2  140.0           20.0                 0.250000
```

## PSS/E RAW v33 importer

`mambo_power.io.psse_raw` reads PSS/E RAW files in the **version 33** layout only (`REV` must
be 33). It is a record parser: fields are comma-separated, single-quoted strings may contain
commas and slashes, `/` outside quotes starts a comment, blank lines are skipped, each section
ends with a line whose first field is `0`, and `Q` (or the end of the text) after the zone
section ends the file. Field order and units follow grg-pssedata's `struct.py`; every
conversion follows MATPOWER's `psse_convert.m` / `psse_convert_xfmr.m`.

| Function | Does |
| --- | --- |
| `psse_raw.load(path) -> Network` | Parse a file; report discarded. |
| `psse_raw.loads(text) -> Network` | Parse RAW text. |
| `psse_raw.load_with_report(path) -> (Network, ImportReport)` | Parse and return every fold, drop and repair. |
| `psse_raw.loads_with_report(text) -> (Network, ImportReport)` | Same, from text. |

### Sections read

Case identification (`SBASE` → `base_mva`), bus, load, fixed shunt, generator,
non-transformer branch, transformer (two-winding, the four-line record), area, zone. Every
other section — two-terminal and VSC DC lines, impedance-correction tables, multi-terminal DC,
multi-section lines, inter-area transfers, owners, FACTS, switched shunts, GNE devices,
induction machines — is skipped with **one report entry per record**. Three-winding
transformer records (five lines, `K != 0`) inside the transformer section are skipped the same
way. Sections through zone must be present and terminated.

### Derived ids

| Element | Id |
| --- | --- |
| Bus | `bus-<I>` |
| Load / fixed shunt / generator | `load-<I>-<ID>`, `shunt-<I>-<ID>`, `gen-<I>-<ID>` (`ID` stripped of blanks) |
| Branch and two-winding transformer | `branch-<I>-<J>-<CKT>` |
| Folded branch end shunt | `shunt-branch-<I>-<J>-<CKT>-i` / `-j` |
| Folded transformer magnetising shunt | `shunt-xfmr-<I>-<J>-<CKT>` |
| Zone | `<ZONE>` as a compact string; one per distinct value |

### Record map

| Record | Fields used | Field |
| --- | --- | --- |
| bus | `I, NAME, BASKV, IDE, AREA, ZONE, OWNER, VM, VA[, NVHI, NVLO]` | `base_kv` (`<= 0` → `1.0` with `BASE_KV_REPLACED`), `type` / `in_service` (`IDE` 1 → `pq`, 2 → `pv`, 3 → `slack`, 4 → `pq` out of service), `area`, `zone`, `vm_pu`, `va_deg`, `v_max_pu`, `v_min_pu`; `NAME` and `OWNER` dropped |
| load | `I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ` | `p_mw`, `q_mvar`; a non-zero `IP IQ YP YQ` is folded as `P = PL + IP·VM + YP·VM²` at the bus's `VM` (`RAW_LOAD_ZIP_FOLDED`) |
| fixed shunt | `I, ID, STATUS, GL, BL` | `g_mw`, `b_mvar` (MW / MVAr at 1 pu) |
| generator | `I, ID, PG, QG, QT, QB, VS, ..., STAT, ..., PT, PB` | `p_mw`, `q_mvar`, `q_max_mvar`, `q_min_mvar`, `v_set_pu`, `in_service`, `p_max_mw`, `p_min_mw`; `cost = None` (`RAW_NO_COSTS`); `IREG`, `MBASE`, `ZR/ZX`, `RT/XT`, `GTAP`, `RMPCT`, owners and `WMOD/WPF` dropped |
| branch | `I, J, CKT, R, X, B, RATEA, ..., GI, BI, GJ, BJ, ST` | `r`, `x`, `b` (pu on `SBASE`), `rating_mva` (`RATEA`, `0` → `None`), `in_service`, `kind = "line"`; end shunts become `Shunt` entries (`RAW_BRANCH_END_SHUNT_FOLDED`); `RATEB/C`, `LEN`, owners dropped |
| transformer (4 lines) | line 1 `I, J, K, CKT, CW, CZ, CM, MAG1, MAG2, ..., STAT`; line 2 `R1-2, X1-2, SBASE1-2`; line 3 `WINDV1, NOMV1, ANG1, RATA1`; line 4 `WINDV2, NOMV2` | `r`, `x`, `tap_ratio`, `shift_deg = ANG1`, `rating_mva = RATA1`, `b = 0`, `kind = "transformer"` (set from the record, not inferred from the tap); magnetising admittance becomes a `Shunt` at the from bus (`RAW_XFMR_MAGNETISING_FOLDED`) |
| zone | `I, ZONAME` | zone names → `Zone.name`. The **area** section is not read — only the bus `AREA` labels survive, as `Bus.area` — so each area record (`I, ISW, PDES, PTOL, ARNAME`) is reported `RAW_SECTION_IGNORED` |

### The CZ / CW / CM conversions

| Code | Meaning | Conversion (MATPOWER's) |
| --- | --- | --- |
| `CZ = 1` | `R1-2, X1-2` pu on `SBASE` | as is |
| `CZ = 2` | pu on `SBASE1-2` and `NOMV1` (`0` = the from bus's base kV) | scaled by `(NOMV1 / BASKV_I)² · SBASE / SBASE1-2` |
| `CZ = 3` | `R1-2` = load loss in W, `X1-2` = `abs(Z)` pu on the winding base | `R = R/(1e6·SBASE1-2)`, `X = √(Z² − R²)`, then scaled as for 2 |
| `CW = 1` | `WINDV` pu of bus base kV | `t = WINDV` |
| `CW = 2` | `WINDV` in kV | `t = WINDV / BASKV` |
| `CW = 3` | `WINDV` pu of `NOMV` | `t = WINDV · NOMV / BASKV` |
| — | | `tap_ratio = t1 / t2` |
| `CM = 1` | `MAG1 + j·MAG2` pu on `SBASE` | shunt `G + jB` at the from bus |
| `CM = 2` | `MAG1` = no-load loss in W, `MAG2` = exciting current pu on the winding base | `G = MAG1/(1e6·SBASE1-2)`, `B = −√(MAG2² − G²)`, both scaled to the system base |

### Warnings (repairs and folds)

| Code | Repair |
| --- | --- |
| `BASE_KV_REPLACED` | `BASKV <= 0` becomes `1.0`; one issue per bus, as for MATPOWER. |
| `ISLAND_DEACTIVATED` | Buses that cannot reach the slack are switched off with their elements ([islands](#islands)). |
| `RAW_NO_COSTS` | Emitted once per file: RAW has no cost section, so every generator imports with `cost = None`. |
| `RAW_LOAD_ZIP_FOLDED` | A load's constant-current / constant-admittance parts were folded into `p_mw` / `q_mvar` at the bus's stored `VM`. |
| `RAW_BRANCH_END_SHUNT_FOLDED` | A branch's `GI/BI` or `GJ/BJ` became a `Shunt` at that end. |
| `RAW_XFMR_MAGNETISING_FOLDED` | A transformer's `MAG1/MAG2` became a `Shunt` at the from bus. |
| `RAW_THREE_WINDING_IGNORED` | A three-winding transformer record was skipped (one issue per record). |
| `RAW_SWITCHED_SHUNT_IGNORED` | A switched shunt was skipped; its `BINIT` is **not** folded into a fixed shunt (`bus_ids` names the bus). |
| `RAW_SECTION_IGNORED` | A record of a section that is not read (areas, owners, DC lines, FACTS, ...) was skipped; one issue per record naming the section and the key. |

### Errors

Anything wrong with the **file** raises `RawImportError` with a stable `code` and a 1-based
`line` when known. This is the one importer with its own exception: a RAW file is read
record by record and the first structural fault (a missing terminator, a bad `REV`) makes
everything after it unreadable, so it stops there with the line number; the CSV bundle, whose
tables are independent, collects every problem into an `ImportReport` and raises `ReportError`
instead (its Errors section below). Both are `ValueError`s. `RawImportError` codes are the
`RawImportCode` literal, not `ImportIssueCode`:

| Code | Cause |
| --- | --- |
| `BAD_HEADER` | Fewer than three case-identification lines, or `IC != 0` (only a full case is read). |
| `UNSUPPORTED_VERSION` | `REV` is not 33. |
| `BAD_NUMBER` | A token that is not a finite number where one is required; `IDE` not in 1–4; `CZ` / `CW` not in 1–3; `CZ` 2 or 3 with `SBASE1-2 <= 0`; `CZ = 3` with `abs(Z) < R`. |
| `BAD_RECORD` | A record with fewer fields than its layout needs, or a multi-line record the file ends inside. |
| `UNTERMINATED_SECTION` | A section (through zone) without its `0` terminator. When the next `0` line's comment names a later section (`0 / END OF LOAD DATA` while buses are still being read), the message names the section that lacks its terminator and `line` is that `0` line; without such a comment it names the section the file ended in, at the line it ended, and says an earlier terminator is the likely defect. |
| `UNKNOWN_BUS` | A load, shunt, generator, branch or transformer naming a bus number the bus section does not have. |

Anything wrong with the **network** raises `NetworkValidationError`, as for every format.

### Limitations

- Version 33 only. Older layouts (v30–v32 differ in the bus and transformer records) and
  the v34+ layouts are refused with `UNSUPPORTED_VERSION`.
- No costs: an imported RAW network flows (`pf`); `opf.solve_dc_opf` and every `market`
  clearing on it raise `mambo_power.opf.MissingCostError` (a `ValueError`) naming every
  generator without a cost, before any solve — and `jobs.run` reports that as a `VALIDATION`
  failure. The importer never invents costs; set `Generator.cost` on each generator (or pass
  `costs=` to `opf.gen_cost_coeffs`) before pricing dispatch.
- Three-winding transformers, switched shunts, DC lines, FACTS, impedance-correction tables
  and owners are skipped, not modelled. A switched shunt's `BINIT` is not folded, so a case
  whose voltage profile relies on it solves to a different voltage.
- Transformers have `b = 0`; the magnetising branch is a bus shunt, not line charging.
- Only `RATEA` becomes `rating_mva`; `RATEB` / `RATEC` are dropped.
- A network with a non-zero `shift_deg` (any transformer with `ANG1 != 0`) gets wrong or
  infeasible `opf` / `market` results until the phase-shifter fix lands (F1 / A19):
  `opf.dc_opf`'s flow rows omit the shifter's PTDF term, so the flows are wrong when the LP
  solves and a generously rated loop with one shifter can come back `Infeasible` with no flows
  at all. `pf.solve_dc` is right.

### Example

```python
from mambo_power.io import psse_raw

net, report = psse_raw.load_with_report("fixtures/case14_v33.raw")
print(len(net.buses), len(net.branches), sorted(report.codes), len(report.warnings))
print([b.id for b in net.branches if b.kind == "transformer"])
print(next(str(w) for w in report.warnings if w.code == "RAW_NO_COSTS"))
```

```text
14 20 ['BASE_KV_REPLACED', 'RAW_NO_COSTS', 'RAW_SECTION_IGNORED'] 16
['branch-4-7-1', 'branch-4-9-1', 'branch-5-6-1']
RAW_NO_COSTS: RAW carries no cost data; all 5 generators imported with cost=None
```

`fixtures/case14_v33.raw` is IEEE case14 re-spelled as a RAW file (provenance in
`fixtures/PROVENANCE-raw.md`); `fixtures/synthetic_quirks_v33.raw` exercises every fold and
skip above.

## CSV bundle

`mambo_power.io.csv_bundle` writes a `Network` as one directory — `manifest.json` plus one CSV
per entity table — and reads it back **identically**: `load(dump(net)) == net` and every
`numerics.NetworkArrays` matrix is `array_equal`, on every bundled fixture, with no tolerance.
The bundle is a machine-facing, bit-exact spelling of the native schema, for spreadsheet
tooling; it is not a second schema.

| Function | Does |
| --- | --- |
| `csv_bundle.dump(net, directory)` | Write the manifest and every table (the directory is created). All-or-nothing: the files are rendered first and written into a temporary sibling directory (`.<name>.tmp-<pid>`) that is moved in only once complete, so a failure — the `""` refusal below, a full disk — leaves the previous bundle untouched. |
| `csv_bundle.load(directory) -> Network` | Read and validate a bundle. |
| `csv_bundle.load_with_report(directory) -> (Network, ImportReport)` | Same; the report is always empty on success, because there is nothing a bundle can repair. |

### Layout

`manifest.json` carries what is not tabular:

```json
{"format": "mambo-power-csv", "schema_version": 1, "base_mva": 100.0,
 "tables": {"buses.csv": 14, "branches.csv": 20, "...": 0}}
```

`schema_version` is `Network.schema_version` — the native format's own version. The tables,
in manifest order (`csv_bundle.TABLES`):

| File | Rows | Columns |
| --- | --- | --- |
| `buses.csv` | one per `Bus` | the model's field names verbatim and in field order; `geo` flattened to `geo_lat, geo_lon` |
| `branches.csv` | one per `Branch` | `id, from_bus, to_bus, r, x, b, rating_mva, tap_ratio, shift_deg, in_service, kind` |
| `generators.csv` | one per `Generator` | field names; `cost` flattened to `cost_kind, cost_startup, cost_shutdown` |
| `generator_costs.csv` | one per coefficient or breakpoint | `generator_id, index, p_mw, value` — polynomial: `p_mw` empty, `value` = coefficient, highest order first; piecewise: `p_mw`, `value` = cost; `index` is the 0-based position |
| `loads.csv` | one per `Load` | field names; `bid` flattened to `bid_kind` |
| `load_bids.csv` | one per coefficient or breakpoint | `load_id, index, p_mw, value`, same shape as the cost side table |
| `shunts.csv`, `storage.csv`, `zones.csv` | one per entity | field names |

Long format for costs and bids was chosen over a JSON cell because a coefficient is then a
cell and a breakpoint a row — the spreadsheet-friendly form.

### Cell rules

- **Empty cell ⇔ `None`.** Consequently an *optional* string field (`Bus.area`, `Bus.zone`,
  `Zone.name`) cannot carry `""`: `dump` raises `ValueError` rather than write a bundle that
  would read back differently. Required string fields (ids, bus references) round-trip `""`.
- Ids and every other string are written and read as text; nothing is ever passed to `int()`,
  so `"01"` and `"1"` stay distinct.
- Floats are written with `repr` (the shortest round-trip form) and read with `float`;
  `nan` / `inf` are rejected on read, as the model rejects them.
- Booleans are written `true` / `false`; `true / false / 1 / 0` are accepted on read in any case.
- Empty tables are written header-only, so the manifest's table set never varies.
- Row order is list order and is preserved. A fully blank row is skipped (an editor's trailing
  newline does not change the row count), and a UTF-8 BOM at the start of a table (Excel's
  "CSV UTF-8" save) is ignored; the writer emits plain UTF-8 with no BOM.

### Errors

A bundle is either exact or refused. `load_with_report` validates the whole directory and
collects **every** problem before giving up; the issues are raised as `ReportError`, whose
`.report.errors` carry them (all as errors — nothing here is a repair). This is the other
error surface of the wave: the RAW importer raises `RawImportError` at the first structural
fault because nothing after it can be read, while a bundle's tables are independent, so every
fault can be listed at once. Both are `ValueError`s; only the CSV codes are `ImportIssueCode`s:

| Code | Cause |
| --- | --- |
| `CSV_MANIFEST_INVALID` | `manifest.json` missing, not JSON, not `format = "mambo-power-csv"`, `base_mva` not a finite number, `tables` not exactly the nine files, or a row count that disagrees with the file. |
| `CSV_SCHEMA_VERSION` | `schema_version` is not the one this build reads. |
| `CSV_MISSING_TABLE` | A listed file is absent. |
| `CSV_UNKNOWN_COLUMN` | A header the model does not have. |
| `CSV_MISSING_COLUMN` | A model field without a column. |
| `CSV_DUPLICATE_ID` | The same `id` twice in one table. |
| `CSV_BAD_VALUE` | A required cell empty, a cell that is not a float / boolean / finite, a row with the wrong number of cells, a cell longer than Python's `csv` field limit (131 072 characters — the whole table is then unreadable and reported once), or a per-entity validation failure (`p_mw` must be increasing, ...). |
| `CSV_ORPHAN_ROW` | A `generator_costs.csv` / `load_bids.csv` row whose owner id is absent from its table. |

Cross-entity invariants (dangling references, slack count, connectivity) are the model's own
and raise `NetworkValidationError`, exactly as for the native format.

### Limitations

- The bundle carries what the native schema carries and nothing else; it does not accept
  extra columns (an editor's helper column is `CSV_UNKNOWN_COLUMN`).
- An optional string field holding `""` cannot be written (see the cell rules); the model
  treats `""` and `None` as different values, and the bundle cannot.
- Spreadsheet applications that reformat floats on save (`0.1` → `0,1`, `1e-05` → `0.00001`)
  or coerce `01` to `1` break the bit-exact guarantee; the bundle detects the former as
  `CSV_BAD_VALUE` and cannot detect the latter.
- A network with a non-zero `shift_deg` gets wrong or infeasible `opf` / `market` results
  until the phase-shifter fix lands (F1 / A19), whichever format it was read from — wrong flows
  when the LP solves, and possibly `Infeasible` with no flows at all; `pf.solve_dc` is right.

### Example

```python
import tempfile
from pathlib import Path

from mambo_power.io import csv_bundle, matpower

net = matpower.load("fixtures/matpower/case14.m")
with tempfile.TemporaryDirectory() as directory:
    csv_bundle.dump(net, directory)
    print(sorted(p.name for p in Path(directory).iterdir()))
    print(Path(directory, "branches.csv").read_text().splitlines()[:2])
    print(csv_bundle.load(directory) == net)
```

```text
['branches.csv', 'buses.csv', 'generator_costs.csv', 'generators.csv', 'load_bids.csv', 'loads.csv', 'manifest.json', 'shunts.csv', 'storage.csv', 'zones.csv']
['id,from_bus,to_bus,r,x,b,rating_mva,tap_ratio,shift_deg,in_service,kind', 'branch-1,bus-1,bus-2,0.01938,0.05917,0.0528,,,,true,line']
True
```

## Bundled fixtures

The repository ships MATPOWER cases under `fixtures/matpower/` with their provenance recorded
in `PROVENANCE.md` / `SOURCES.md`: `case14`, `case30`, `case_ieee30`, `case57`, `case118` and
`case300` (verbatim bytes with recorded sha256), plus derived variants under `derived/` that
exercise effective-role and island handling. These are public IEEE test data as distributed
by MATPOWER; see the provenance files for the exact wording.
