# M8 research — four interchange formats against `Network`

Date: 2026-08-29. Branch `epic/01-foundation` at `473b718`. Read-only survey; scratch scripts
under `%TEMP%\claude\C--Claude-Projects-mambo-power\0d397067-…\scratchpad\m8-research\`
(`pp_probe.py`, `pp_probe2.py`, `pp_probe3.py`, `pypsa_probe.py`, `pypsa_probe2.py`,
`iti_ieee14_v33.raw`). Every number below was produced by those scripts in this session.

## Versions found

```
$ uv run python -c "import pandapower, pypsa, linopy; print(...)"
pandapower 3.3.0   pypsa 1.2.4   linopy 0.9.1   pandas 2.3.3   numpy 2.5.2
highspy: installed (pyproject dep), no __version__ attribute
$ uv run python -c "import grg_pssedata"      -> ModuleNotFoundError
$ uv run python -c "import pypower"           -> ModuleNotFoundError
$ uv run python -c "import pandapower.converter.psse" -> ModuleNotFoundError
pandapower/converter/ contains: cim jao matpower pandamodels powerfactory pypower ucte  (no PSS/E)
pypsa/network/io.py import_from_*: csv_folder, excel, hdf5, netcdf, pypower_ppc, pandapower_net (no RAW)
find .venv -iname "*.raw"                     -> nothing
```

pandapower's `numba` is absent (warning printed on `runpp`); irrelevant for I/O.

## Reference: what `Network` holds (`src/mambo_power/model/entities.py`)

`Network{schema_version=1, base_mva, buses, branches, generators, loads, shunts, storage,
zones}`. Units physical (MW/MVAr/kV/deg), branch `r/x/b` pu on `base_mva`, tap on the
from side, `b` = total charging. Optional fields default to `None` and are omitted by
`io.native.dumps` (`model_dump_json(exclude_none=True)`); `extra="forbid"` everywhere.
Costs: `PolynomialCost{coefficients hi→lo, startup, shutdown}` |
`PiecewiseCost{points[(p,cost)], startup, shutdown}`; loads carry an optional
`LoadBid` of the same two shapes; `Storage{p_max_mw, energy_mwh, soc_initial, eff_c, eff_d}`;
`Zone{id, name}`; `Bus.area` is a free string, `Bus.geo{lat, lon}`.

---

## 1. pandapower JSON (`pp.to_json` / `pp.from_json`)

### Evidence

`pp_probe.py` — `pp.from_json_string(pp.to_json(pn.case14()))`, non-empty tables and every
table's columns:

```
bus        n= 14 cols=['name','vn_kv','type','zone','in_service','max_vm_pu','min_vm_pu','geo']
gen        n=  4 cols=['name','bus','p_mw','vm_pu','sn_mva','min_q_mvar','max_q_mvar','scaling','slack','in_service','slack_weight','type','controllable','max_p_mw','min_p_mw','id_q_capability_characteristic','reactive_capability_curve','curve_style']
ext_grid   n=  1 cols=['name','bus','vm_pu','va_degree','slack_weight','in_service','max_p_mw','min_p_mw','max_q_mvar','min_q_mvar']
load       n= 11 cols=['name','bus','p_mw','q_mvar','const_z_p_percent','const_z_q_percent','const_i_p_percent','const_i_q_percent','sn_mva','scaling','in_service','type','controllable']
line       n= 15 cols=['name','std_type','from_bus','to_bus','length_km','r_ohm_per_km','x_ohm_per_km','c_nf_per_km','g_us_per_km','max_i_ka','df','parallel','type','in_service','max_loading_percent','geo']
trafo      n=  5 cols=['name','std_type','hv_bus','lv_bus','sn_mva','vn_hv_kv','vn_lv_kv','vk_percent','vkr_percent','pfe_kw','i0_percent','shift_degree','tap_side','tap_neutral','tap_min','tap_max','tap_step_percent','tap_step_degree','tap_pos','parallel','df','in_service','max_loading_percent','tap_changer_type']
shunt      n=  1 cols=['bus','name','q_mvar','p_mw','vn_kv','step','max_step','in_service','id_characteristic_table','step_dependency_table']
sgen       n=  0 cols=['name','bus','p_mw','q_mvar','sn_mva','scaling','in_service','type','current_source',...]
storage    n=  0 cols=['name','bus','p_mw','q_mvar','sn_mva','soc_percent','min_e_mwh','max_e_mwh','scaling','in_service','type']
poly_cost  n=  5 cols=['element','et','cp0_eur','cp1_eur_per_mw','cp2_eur_per_mw2','cq0_eur','cq1_eur_per_mvar','cq2_eur_per_mvar2']
pwl_cost   n=  0 cols=['power_type','element','et','points']
(trafo3w, dcline, switch, impedance, ward, xward all empty)
sn_mva 100  f_hz 60  version 3.3.0 ; bus.geo is a GeoJSON string column, no bus_geodata table
```

JSON payload shape (`pp_probe3.py`): top level `{"_module","_class","_object"}`; `_object`
has one key per table plus `version, format_version, converged, OPF_converged, name, f_hz,
sn_mva`; each table is a pandas `orient="split"` DataFrame string with a `dtype` map:

```
{"_module":"pandas.core.frame","_class":"DataFrame","_object":"{\"columns\":[...],\"index\":[0],\"data\":[[...]]}","orient":"split","dtype":{...}}
```

`pp.nets_equal(net, from_json_string(to_json(net)))` → `True` on case14. So the exporter
should build a `pandapowerNet` via `pp.create_*` and let `pp.to_json` serialise it; writing
that JSON by hand is not worth it.

Unit conventions, checked against `matpower.load("fixtures/matpower/case14.m")`
(`pp_probe.py` / `pp_probe2.py`):

```
line ohm -> pu, Zbase = vn_kv^2/sn_mva:
  0->1  r_pu 0.01938 x_pu 0.05917 b_pu 0.0528   (mambo branch-1: 0.01938 0.05917 0.0528)  exact
  0->4  r_pu 0.05403 x_pu 0.22304 b_pu 0.0492   (mambo branch-2)                            exact
  b_pu = 2*pi*f_hz*c_nf_per_km*1e-9*length_km*parallel*Zbase ; max_i_ka -> rating_mva = max_i_ka*vn_kv*sqrt(3) = 9900 (pn.case14's "unrated" sentinel)
trafo: x_pu_sys = vk_percent/100 * sn_mva_sys/sn_mva_trafo ; r from vkr_percent ; tap = 1+(tap_pos-tap_neutral)*tap_step_percent/100
  hv3->lv6  x_pu 0.20912 tap 0.978 tap_side hv  (mambo branch-8: x 0.20912 tap 0.978)  exact
  hv3->lv8  x_pu 0.55618 tap 0.969               (mambo branch-9)                        exact
  hv4->lv5  x_pu 0.25202 tap 0.932               (mambo branch-10)                       exact
  hv6->lv7  x_pu 0.17615 tap 1.0  tap_side None  (mambo branch-12: a plain line in the .m; pn.case14 made it a trafo because vn differs 14 vs 12 kV)
pn.case14 bus vn_kv: {0.208, 12, 14, 135}   -- mambo's case14 has base_kv = 1.0 on every bus (BASE_KV 0 -> 1.0 repair)
gen limits: pp gen[bus1] max_p 140 min_p 0 min_q -40 max_q 50 vm 1.045   == mambo gen-2 (bus-2) p_max 140 q -40..50 v_set 1.045
ext_grid: bus 0, vm 1.06, va 0, max_p 332.4, q 0..10                       == mambo gen-1 on slack bus-1
shunt: bus 8, q_mvar -19.0 (pp: + = consumption)                           == mambo shunt-9 b_mvar +19 (injects)
poly_cost: (ext_grid 0) cp1 20 cp2 0.043029 ; (gen 0) 20, 0.25 ; (gen 1..3) 40, 0.01   == mambo coefficients [c2,c1,c0]
pwl_cost.points = [[p_start, p_end, slope_eur_per_mw], ...]   e.g. [[0,50,10],[50,100,20]]  (pp_probe3.py)
```

`pandapower.converter.pypower.from_ppc(case14 raw)` yields `bus.vn_kv == 0.0`, trafo
`sn_mva 99999`, `vk_percent 20911.79`, lines with `r_ohm_per_km 0.0, c_nf inf, max_i_ka NaN`;
`to_ppc()` of that net raises `FloatingPointError: invalid value encountered in divide` in
`_wye_delta`. Conclusion: do not route through pandapower's own MATPOWER converter; build
from `Network` (whose `base_kv > 0` invariant avoids the zero-Zbase trap).

### Field map — pandapower

| mambo field | pandapower | unit / derivation | lossless? |
| --- | --- | --- | --- |
| `Network.base_mva` | `net.sn_mva` | MVA | yes |
| — | `net.f_hz` | needed for `c_nf_per_km`; use 50 or 60, only affects the b↔c conversion, choose one and invert with the same value | derived (must be recorded to round-trip `b`) |
| `Bus.id` | `bus.name` (index is int) | id→name, int index assigned in order; import: `name` if present else `str(index)` | yes (via name) |
| `Bus.base_kv` | `bus.vn_kv` | kV | yes |
| `Bus.type` | none; slack = the bus with `ext_grid`, pv = bus of a `gen` with `vm_pu`, pq = rest | derived on import from ext_grid/gen presence; export: slack→`ext_grid`, pv→`gen`, pq→`sgen`/`gen(controllable)`? — see gap G2 | derived |
| `Bus.in_service` | `bus.in_service` | | yes |
| `Bus.vm_pu`, `va_deg` | `res_bus.vm_pu`, `res_bus.va_degree` (absent until `runpp`) or `ext_grid.vm_pu/va_degree`, `gen.vm_pu` | state; not an input column on `bus` | no (drop, or write `res_bus`) |
| `Bus.v_min_pu`, `v_max_pu` | `bus.min_vm_pu`, `bus.max_vm_pu` | pu | yes |
| `Bus.area` | none | `bus.zone` is the only label column | no (custom column possible: pandapower keeps extra columns through `to_json`; unverified) |
| `Bus.zone` | `bus.zone` (object) | string | yes; `Zone.name` lost |
| `Bus.geo` | `bus.geo` GeoJSON `{"type":"Point","coordinates":[x,y]}` | lon/lat order = [x,y] | yes |
| `Branch` (no tap/shift) | `line` | `r_ohm_per_km = r*Zb`, `x_ohm_per_km = x*Zb`, `c_nf_per_km = b/Zb/(2πf)*1e9`, `length_km=1`, `parallel=1`, `Zb = vn_kv(from)^2/sn_mva`; `max_i_ka = rating_mva/(√3·vn_kv)`; unrated → a large sentinel (pn uses 9900 MVA) or `NaN` | derived, exact to 1e-15 in probe |
| `Branch` (tap or shift, or from/to kV differ) | `trafo` | `vn_hv_kv=vn(from)`, `vn_lv_kv=vn(to)`, `sn_mva = base_mva` (or `rating_mva`), `vk_percent = 100·√(r²+x²)·sn_trafo/base_mva`, `vkr_percent = 100·r·sn_trafo/base_mva`, `tap_side="hv"`, `tap_neutral=0`, `tap_step_percent=100·(tap−1)`, `tap_pos=1`, `shift_degree=shift`, `pfe_kw=0`, `i0_percent=0`; mambo `b` on a transformer branch has no home (pandapower magnetising is `i0_percent`/`pfe_kw`, a shunt admittance, not line charging) | derived; `b≠0` on a trafo branch is lost |
| `Branch.rating_mva` | line `max_i_ka`; trafo `sn_mva` + `max_loading_percent` | | derived |
| `Branch.in_service` | `line/trafo.in_service` | | yes |
| `Branch.id` | `line.name` / `trafo.name` | | yes |
| `Generator` on slack bus | `ext_grid` (`vm_pu`, `va_degree`, `min/max_p_mw`, `min/max_q_mvar`) | no `p_mw` setpoint on ext_grid; `q_mvar` setpoint lost; cost row `et="ext_grid"` | derived; `p_mw/q_mvar` setpoint lost |
| `Generator` on pv bus | `gen` (`p_mw`, `vm_pu`, `min/max_p_mw`, `min/max_q_mvar`, `controllable`) | `q_mvar` setpoint lost (gen is PV) | derived |
| `Generator` on pq bus | `sgen` (`p_mw`, `q_mvar`) — but sgen has no `vm_pu`, `min/max_q` | mambo lets a PQ bus host a generator; pandapower `gen` would turn the bus PV | derived, `v_set_pu` lost |
| `Generator.v_set_pu` | `gen.vm_pu` / `ext_grid.vm_pu` | pu | yes |
| `Generator.in_service` | `gen.in_service` | | yes |
| `Generator.cost` polynomial (deg ≤ 2) | `poly_cost{cp0_eur, cp1_eur_per_mw, cp2_eur_per_mw2}` | coefficients reversed (`[c2,c1,c0]` → cp2,cp1,cp0) | yes for deg ≤ 2; deg ≥ 3 has no column → no |
| `Generator.cost` piecewise | `pwl_cost.points = [[p0,p1,slope],[p1,p2,slope],…]` | slope = Δcost/Δp per segment; absolute cost offset at `p0` (mambo `points[0][1]`) is lost | derived, offset lost |
| `PolynomialCost.startup/shutdown` | none | | no |
| `Generator.ramp_up_mw/ramp_down_mw` | none | | no |
| `Load` | `load{p_mw, q_mvar, in_service, name}` | MW/MVAr | yes |
| `Load.bid` | none (`load.controllable` + `min/max_p_mw` exist for OPF but no value curve) | | no |
| `Shunt.g_mw`, `b_mvar` | `shunt.p_mw`, `shunt.q_mvar` | pandapower + = consumption for both, so `q_mvar = −b_mvar`, `p_mw = g_mw`; `vn_kv = bus vn_kv`, `step=1` | yes (sign flip) |
| `Storage` | `storage{p_mw, max_e_mwh, soc_percent, min_e_mwh}` | `energy_mwh→max_e_mwh`, `soc_initial→soc_percent·100`, `p_max_mw→max_p_mw/min_p_mw=±`; efficiencies have no column | derived, efficiencies lost |
| `Zone.name` | none | | no |
| — (pandapower-only) | `trafo3w`, `switch`, `impedance`, `ward/xward`, `dcline`, `load.const_z/const_i`, `gen.slack_weight`, `line.g_us_per_km` | no mambo counterpart | import: reject or warn |

---

## 2. PyPSA export

### Evidence

`pypsa_probe.py` builds a `pypsa.Network` directly from `matpower.load(case14)` (not from
the ppc as `tests/parity/test_opf_vs_pypsa.py` does), solves with `optimize(solver_name="highs")`
and compares with `solve_dc_opf`:

```
components: {'Bus': 14, 'Line': 17, 'Transformer': 3, 'Generator': 5, 'Load': 11, 'ShuntImpedance': 1}
optimize: ok optimal  solver=highs via linopy; objective 7642.59177695936
mambo dc_opf objective 7642.591776958784 | pypsa+c0 7642.59177695936 | rel diff 7.53e-14
dispatch max abs diff MW: 2.29e-05  {'gen-1': (220.968, 220.968), 'gen-2': (38.032, 38.032), gen-3..5: (0,0)}
```

Mapping used (the exporter's core):

- `Bus`: `v_nom=base_kv`, `v_mag_pu_min/max`, `carrier="AC"`.
- `Line` (no tap/shift): `x = x_pu·Zb`, `r = r_pu·Zb`, `b = b_pu/Zb` (siemens), `Zb = base_kv²/base_mva`,
  `s_nom = rating_mva or 9999`. PyPSA re-derives `x_pu = x/v_nom²` (1 MVA base) — consistent.
- `Transformer` (tap or shift): `model="pi"`, `s_nom = base_mva` (or `rating_mva`),
  `x = x_pu·s_nom/base_mva` (pu on `s_nom`), `tap_ratio`, `phase_shift`, `tap_side=0`
  (tap on bus0 = mambo's from side). `transformers.csv` shows PyPSA storing exactly
  `x 0.20912, s_nom 100, tap_ratio 0.978` for branch-8.
- `Generator`: `p_nom=p_max_mw`, `p_min_pu=p_min_mw/p_max_mw`, `marginal_cost=c1`,
  `marginal_cost_quadratic=c2`, `control="Slack"|"PV"`; `c0` must be added outside
  (`n.objective` excludes constants; `network.csv` carries `_objective_constant`).
- `Load`: `p_set`, `q_set`. `ShuntImpedance`: `g`, `b` in siemens = `g_mw/base_mva/…`
  (probe used `/base_mva`, only right when `v_nom=1`; exporter must use `MW/kV²`).

What the existing parity test does that an exporter must *replace*: it goes through
`import_from_pypower_ppc(overwrite_zero_s_nom=9999)` on raw matrices and patches
`marginal_cost*` from `gencost` columns, then clears `p_set` (the fixed-dispatch pin).
An exporter starting from `Network` avoids both hacks (no `p_set` on generators, cost
from `Generator.cost`), and must add: transformer construction (ppc import makes every
branch a Line), `ShuntImpedance` (ppc import drops GS/BS — the case300 1.3 MW gap in that
test's docstring), `v_mag_pu_min/max`, `in_service→active`, bus `control`, ids as names.

`pypsa_probe2.py`: quadratic cost is honoured (`objective 750.0 == 50·10 + 0.1·50²`);
custom attributes pass through `n.add("Bus", ..., zone="Z1", area="A1")` → extra columns
`zone, area` appear in `n.buses` and survive `export_to_csv_folder`/`import_from_csv_folder`.
No component attribute contains "piece"/"segment".

`export_to_csv_folder` layout (prior art for §4): `network.csv` (name, pypsa_version,
`_objective`, `_objective_constant`, srid), `snapshots.csv`, `meta.json`, `crs.json`, one
`<component>.csv` per non-empty static table (`buses.csv, lines.csv, transformers.csv,
generators.csv, loads.csv, shunt_impedances.csv, sub_networks.csv`) with only non-default
columns written, plus `<component>-<attr>.csv` per time-varying attribute
(`generators-p.csv, buses-marginal_price.csv, …`). Reimport of the folder succeeded.

### Field map — PyPSA

| mambo field | PyPSA | unit / derivation | lossless? |
| --- | --- | --- | --- |
| `base_mva` | none (PyPSA per-unit is on 1 MVA) | folded into the ohm/siemens conversion; round-trip must store it (`network.csv` extra column or `meta.json`) | derived |
| `Bus.id/base_kv/v_min/v_max/in_service` | `name, v_nom, v_mag_pu_min, v_mag_pu_max, active` | kV, pu | yes |
| `Bus.type` | `control` (Slack/PV/PQ) — PyPSA recomputes it from generators | derived | derived |
| `Bus.vm_pu/va_deg` | `v_mag_pu_set` (input, PV only) / `v_mag_pu`, `v_ang` (outputs) | | no as inputs |
| `Bus.area/zone` | custom columns (survive CSV); `sub_network` is PyPSA-computed | | yes via extra column, not a PyPSA concept |
| `Bus.geo` | `x, y` (lon, lat) | | yes |
| `Branch` no tap/shift | `Line{bus0,bus1,x,r,b,g,s_nom,active,v_ang_min/max}` | ohm, siemens; `s_nom` 0 = unlimited in LOPF only if `s_nom_extendable`—use large sentinel and record "unrated" | derived; `rating_mva=None` needs a sentinel |
| `Branch` with tap/shift | `Transformer{model="pi", x, r, g, b, s_nom, tap_ratio, tap_side, phase_shift}` | pu on `s_nom` | yes |
| `Generator` | `Generator{bus, p_nom, p_min_pu, p_max_pu, control, active, marginal_cost, marginal_cost_quadratic, start_up_cost, shut_down_cost, ramp_limit_up, ramp_limit_down, q_set, p_set}` | `p_nom=p_max`, `p_min_pu=p_min/p_max` (breaks when `p_max=0` — needs a guard), ramps as pu of `p_nom` | derived |
| `Generator.p_mw/q_mvar` setpoints | `p_set/q_set` — but a non-NaN `p_set` pins dispatch in `optimize()` | leave NaN, or write to an `_init` column | no (deliberately) |
| `Generator.v_set_pu` | `Bus.v_mag_pu_set` (bus-level, one per bus) | | derived; several gens/bus collapse |
| `Generator.q_min/q_max` | none on Generator (PyPSA has no Q limits in LOPF; `pf()` ignores) | | no |
| `PolynomialCost` deg ≤ 2 | `marginal_cost`(c1), `marginal_cost_quadratic`(c2), c0 → objective constant | | yes (c0 needs a side channel) |
| `PolynomialCost` deg ≥ 3 | none | | no |
| `PiecewiseCost` | none — split into one Generator per segment with `p_nom = Δp`, `marginal_cost = slope` (offset lost); no native attribute | | no |
| `Load` | `Load{bus, p_set, q_set, active}` | | yes |
| `Load.bid` | none — elastic demand needs a negative-sign `Generator` with `marginal_cost = −value` | | no |
| `Shunt` | `ShuntImpedance{g, b}` siemens = `MW/kV²`, `MVAr/kV²` | | yes |
| `Storage` | `StorageUnit{p_nom, max_hours=energy/p_max, state_of_charge_initial=soc·energy, efficiency_store, efficiency_dispatch}` | | yes |
| `Zone` | none (no zone component) | custom bus column only | no |

Confirmed absent in PyPSA 1.2.4: piecewise-linear costs, polynomial > 2, elastic demand
bids, generator Q limits, zones. Present: `marginal_cost_quadratic` (solved correctly),
`start_up_cost/shut_down_cost` (only with `committable=True`), ramps.

---

## 3. PSS/E RAW v33 import

### Sources actually read

- `lanl-ansi/grg-pssedata` `grg_pssedata/struct.py` (record field lists) and `io.py`
  (section order, terminators, quoting) — BSD-3, LANL 2018. Its parser warns
  "only version 33 is supported".
- `MATPOWER/matpower` `lib/psse_convert.m`, `psse_parse.m`, `psse_convert_xfmr.m` (the
  RAW→mpc column map and CZ/CW impedance conversion; BSD-3).
- Real v33 files: `ITI/models …/ieee-14-bus.raw` (header `0, 100.00, 33, 0, 0, 60.00`),
  `PowerFlowData.jl/test/testfiles/synthetic_data_v33.RAW` (MIT), grg-pssedata
  `tests/data/correct/pglib_opf_case73_ieee_rts.raw` and `WECC240_M21_psse33_v01b.raw`.

No library is bundled and none of the installed ones read RAW (see Versions). A hand-written
parser is needed; grg-pssedata's `io.py` is a 1-file reference implementation under BSD-3.

### File structure (v33)

- Line 1: `IC, SBASE, REV, XFRRAT, NXFRAT, BASFRQ / comment` — `IC=0` full case,
  `SBASE` MVA, `REV=33`, `BASFRQ` Hz. Lines 2–3: free-text titles (≤60 chars).
- Then sections in fixed order, each terminated by a line whose first field is `0`
  (conventionally `0 / END OF … DATA, BEGIN … DATA`), file ends with `Q`:
  **bus, load, fixed shunt, generator, non-transformer branch, transformer, area,
  two-terminal DC, VSC DC, impedance correction, multi-terminal DC, multi-section line,
  zone, inter-area transfer, owner, FACTS, switched shunt, GNE, induction machine.**
  (grg-pssedata `io.py` parse order; the ITI file's terminator lines 18–85 confirm.)
- Fields comma-separated (space-delimited files exist — PowerFlowData `spacedelim.raw`);
  strings single-quoted and may contain commas/slashes; `/` outside quotes starts a comment.
  grg regexes: split on `/` not inside quotes, then on `,` not inside quotes.
- Transformer records span 4 lines (2-winding) or 5 lines (3-winding, `K≠0`).

### Record layouts (v33), field order, units — from `grg_pssedata/struct.py`

| Section | Fields in order | Units / notes | grg field count |
| --- | --- | --- | --- |
| Bus | `I, NAME, BASKV, IDE, AREA, ZONE, OWNER, VM, VA, NVHI, NVLO, EVHI, EVLO` | `IDE` 1 PQ, 2 PV, 3 slack, 4 isolated; kV; pu; deg; `NVHI/NVLO` normal V limits (pu), `EVHI/EVLO` emergency | 9–13 |
| Load | `I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER, SCALE, INTRPT` | `PL/QL` MW/MVAr const-power; `IP/IQ` MW/MVAr at 1 pu (const-current); `YP/YQ` MW/MVAr at 1 pu (const-Z); several loads per bus keyed by `ID` | 13–14 |
| Fixed shunt | `I, ID, STATUS, GL, BL` | MW / MVAr at 1 pu; `BL>0` capacitive (injects) — same sign as MATPOWER `GS/BS` | 5 |
| Generator | `I, ID, PG, QG, QT, QB, VS, IREG, MBASE, ZR, ZX, RT, XT, GTAP, STAT, RMPCT, PT, PB, O1,F1,…,O4,F4, WMOD, WPF` | MW/MVAr; `QT` max, `QB` min; `VS` pu; `PT` max, `PB` min; `STAT` 1/0 | 20–28 |
| Branch | `I, J, CKT, R, X, B, RATEA, RATEB, RATEC, GI, BI, GJ, BJ, ST, MET, LEN, O1,F1,…,O4,F4` | pu on `SBASE`; `B` total charging; MVA; `GI/BI/GJ/BJ` per-end shunts (pu); `ST` 1/0; `J<0` means metered at J (take `abs`) | 18–24 |
| Transformer 2-w line 1 | `I, J, K, CKT, CW, CZ, CM, MAG1, MAG2, NMETR, NAME, STAT, O1,F1,…,O4,F4, VECGRP` | `K=0` → 2-winding; `CW` winding-voltage code (1 pu of bus kV, 2 kV, 3 pu of nominal); `CZ` impedance code (1 pu on `SBASE`, 2 pu on `SBASE1-2`, 3 load loss W + |Z| pu on `SBASE1-2`); `CM` magnetising code | 20–21 |
| line 2 | `R1-2, X1-2, SBASE1-2` | per `CZ`; MVA | 3 |
| line 3 | `WINDV1, NOMV1, ANG1, RATA1, RATB1, RATC1, COD1, CONT1, RMA1, RMI1, VMA1, VMI1, NTP1, TAB1, CR1, CX1, CNXA1` | `WINDV1` per `CW` (pu or kV); `ANG1` deg = phase shift; `RATA1` MVA | 17 |
| line 4 | `WINDV2, NOMV2` | | 2 |
| Area | `I, ISW, PDES, PTOL, ARNAME` | `ISW` slack bus of area | |
| Zone | `I, ZONAME` | | |
| Owner | `I, OWNAME` | | |
| Switched shunt | `I, MODSW, ADJM, STAT, VSWHI, VSWLO, SWREM, RMPCT, RMIDNT, BINIT, N1,B1,…,N8,B8` | `BINIT` MVAr at 1 pu | 12–26 |

Example records from the ITI IEEE-14 v33 file (`iti_ieee14_v33.raw`):

```
    1,'Bus 1       ', 138.0000,3,   1,   1,   1,1.06000,   0.0000                      (bus, 9 fields — no NVHI..EVLO)
    2,'1 ',1,   1,   1,    21.700,    12.700,     0.000,     0.000,     0.000,    -0.000,   1,1   (load)
     9,' 1', 1,     0.000,    19.000                                                    (fixed shunt: GL 0, BL 19)
    1,'1 ',   232.392,   -16.549,     0.000,     0.000,1.06000,    0,   615.000, 0,1,0,0,1,1,100.0, 10000.000,-10000.000, 1,1.0,0,1.0,0,1.0,0,1.0,0,1.0  (generator)
    1,     2,'1 ', 0.01938, 0.05917,0.05280,   0.00,   0.00,   0.00,  0,0,0,0,1,1,   0.0,   1,1.0000,0,1.0,0,1.0,0,1.0   (branch)
    4,    7,    0,'1 ',1,1,1,  0.00000,  0.00000,2,'        ',1,   1,1.0000,0,1.0,0,1.0,0,1.0   (xfmr line 1: CW=1 CZ=1 CM=1)
 0.00000, 0.20912, 100.00                                                               (line 2: R X SBASE1-2)
0.97800,  0.000,   0.000,   0.00,   0.00,   0.00,0,     0, 1.50000, 0.51000, 1.50000, 0.51000,159, 0, 0.00000, 0.00000  (line 3: WINDV1=0.978)
1.00000,  0.000                                                                          (line 4: WINDV2 NOMV2)
   1,    2,     0.000,   999.990,'IEEE14      '                                          (area)
   1,'IEEE 14 '                                                                          (zone)
```

MATPOWER `psse_convert.m` column map (rev ≥ 31), quoted from the fetched source:
`bus(:,[BUS_I BASE_KV BUS_TYPE BUS_AREA ZONE VM VA]) = numbus(:,[1 3 4 5 6 8 9])`, VMAX/VMIN
from cols 10–11 when present; `Pd = load(:,6) + load(:,8)·VM + load(:,10)·VM²` (voltage-
dependent parts folded at the bus's VM); fixed shunt `GS/BS` from cols 4–5; switched-shunt
`BINIT` (col 10 for rev ≥ 32) added to `BS`;
`gen(:,[GEN_BUS PG QG QMAX QMIN VG MBASE GEN_STATUS PMAX PMIN]) = gen(:,[1 3 4 5 6 7 9 15 17 18])`;
branch `[F_BUS T_BUS BR_R BR_X BR_B RATE_A RATE_B RATE_C]` from cols `[1 2 4 5 6 7 8 9]`,
status col 14 (rev > 27), per-end `GI/BI/GJ/BJ` folded into bus shunts.
`psse_convert_xfmr.m`: `CZ=3` → `R = 1e-6·R/SBASE1-2`, `X = sqrt(X²−R²)`; `CZ=2,3` →
`R,X ·= Zb_winding/Zb_system` (i.e. `×SBASE/SBASE1-2` when nominal kV = bus kV);
`tap = WINDV1/WINDV2` with `CW=2` dividing each by its bus kV and `CW=3` multiplying by
`NOMV/BASKV`; `shift = ANG1`; `MAG1/MAG2` (CM=1: pu G/B on SBASE) go to a bus shunt at
the from bus.

### Field map — RAW v33

| mambo field | RAW | unit / derivation | lossless? |
| --- | --- | --- | --- |
| `base_mva` | header `SBASE` | MVA | yes |
| `Bus.id` | `I` (+ `NAME` unused, no Bus.name) | `bus-<I>` like matpower | yes (name lost — gap G1) |
| `Bus.base_kv` | `BASKV` | kV; 0 → repair 1.0 as matpower does | yes |
| `Bus.type/in_service` | `IDE` 1/2/3/4 | same table as MATPOWER `BUS_TYPE` | yes |
| `Bus.vm_pu/va_deg` | `VM, VA` | | yes |
| `Bus.v_min/v_max` | `NVLO, NVHI` (optional; `EVHI/EVLO` dropped) | pu | yes when present |
| `Bus.area`, `zone` | `AREA`, `ZONE` (+ Zone section `ZONAME` → `Zone.name`, Area names lost) | | yes; `OWNER` no |
| `Load` | load records: `p = PL + IP·VM + YP·VM²` (MATPOWER rule) or `PL` only with a warning when `IP/IQ/YP/YQ ≠ 0`; several per bus (`ID`) → `load-<I>-<ID>`; `STATUS` → `in_service` | | derived (ZIP parts folded) |
| `Shunt` | fixed shunt `GL, BL` → `g_mw, b_mvar` (same sign as MATPOWER); switched shunt `BINIT` folded in with a warning | | yes / derived |
| `Generator` | `PG QG QT QB VS STAT PT PB` → `p_mw q_mvar q_max q_min v_set in_service p_max p_min`; id `gen-<I>-<ID>`; `MBASE ZR ZX RT XT GTAP IREG RMPCT WMOD WPF` dropped | | yes |
| `Generator.cost` | **none — RAW has no cost/gencost section at all** (section list above has no economic record; grg struct has no cost class) | | no (every generator `cost=None`) |
| `Branch` line | `I J CKT R X B RATEA ST` (+ `GI BI GJ BJ` → per-end shunts folded into `Shunt` entries, warned) | pu on SBASE, MVA; `RATEA=0` → `None`; id `branch-<I>-<J>-<CKT>` | yes (`RATEB/C, MET, LEN` dropped) |
| `Branch` transformer | 4-line record → one Branch: `r,x` per `CZ`/`SBASE1-2`, `tap = WINDV1/WINDV2` per `CW`, `shift = ANG1`, `rating = RATA1`, `b = 0`, `in_service = STAT`; `MAG1/MAG2` → shunt at `I`; 3-winding (`K≠0`) → reject/warn | | derived |
| `Storage`, `Load.bid`, ramps | none | | no |

RAW has no cost data: confirmed by the full v33 section list (no economic-dispatch record)
and by grg-pssedata's `struct.py` having no cost class. An imported RAW network can run PF
and N-1 but not OPF/markets until costs are added.

---

## 4. CSV bundle

### What the repo does today

No CSV code exists in `src/` (`grep -rn csv src/mambo_power` → nothing). The only prior art
is `examples/07_results_and_export.py:19-61`: `csv.DictWriter` over `row.model_dump()` for
each result table (`buses`, `branches`, `generators`) — one file per table, flat scalar
columns. `results/*.py` are pydantic row models with `to_arrays()` (positional numpy view);
no DataFrame layer anywhere. `docs/manual/results.md` describes those tables only.

PyPSA's `export_to_csv_folder` (see §2) is the closest external precedent: one
`<table>.csv` per component, a `network.csv` with scalars, `meta.json`, only non-default
columns written, and (for us irrelevant) `<table>-<attr>.csv` time series.

### Proposed minimal bundle

A directory (or zip) with:

| File | Rows | Columns |
| --- | --- | --- |
| `manifest.json` | — | `{"format": "mambo-power-csv", "schema_version": 1, "base_mva": …, "tables": {...file → row count}, "engine_version": …}` |
| `buses.csv` | `Bus` | `id, base_kv, type, in_service, vm_pu, va_deg, v_min_pu, v_max_pu, area, zone, geo_lat, geo_lon` |
| `branches.csv` | `Branch` | `id, from_bus, to_bus, r, x, b, rating_mva, tap_ratio, shift_deg, in_service` |
| `generators.csv` | `Generator` | `id, bus, p_mw, q_mvar, p_min_mw, p_max_mw, q_min_mvar, q_max_mvar, v_set_pu, in_service, ramp_up_mw, ramp_down_mw, cost_kind, cost_startup, cost_shutdown` |
| `generator_costs.csv` | one row per coefficient / breakpoint | `generator_id, index, p_mw (piecewise only), value` — or one JSON cell `cost` in `generators.csv` |
| `loads.csv` | `Load` | `id, bus, p_mw, q_mvar, in_service, bid_kind` (+ `load_bids.csv` same shape as costs) |
| `shunts.csv` | `Shunt` | `id, bus, g_mw, b_mvar, in_service` |
| `storage.csv` | `Storage` | `id, bus, p_max_mw, energy_mwh, soc_initial, efficiency_charge, efficiency_discharge, in_service` |
| `zones.csv` | `Zone` | `id, name` |

Fields needing care for a lossless round trip:

- **Nested cost/bid objects**: variable length (`coefficients` 1..n, `points` 2..200). Two
  honest options: a long-format side table (`generator_costs.csv`, `load_bids.csv`) keyed by
  parent id with a `kind` column on the parent, or a JSON-encoded cell. Long format is the
  spreadsheet-friendly one; JSON cell is simpler and exact. Either must preserve coefficient
  order and the `(p, cost)` pairing.
- **Optional fields / `None`**: empty cell ⇔ `None`; `"nan"` must be rejected, not read as
  missing (model forbids non-finite). Empty must not collide with an empty string id.
- **Ids are strings**: `1` and `01` differ; readers must not coerce id columns to int
  (pandas would). Use `csv` stdlib with everything as text, typed per column from the model.
- **Booleans**: write `true/false`; accept `1/0/True/False` on read.
- **Floats**: `repr()` (shortest round-trip); `model_dump` → `str()` in Python 3.12 is exact.
- **Empty tables**: write the header-only file so the manifest's table set is stable;
  `storage.csv`/`zones.csv` will often be empty.
- **`geo`**: flatten to `geo_lat, geo_lon`, both empty ⇔ `None`.
- **`schema_version`** and `base_mva` live in the manifest, not in a table.
- Row order = list order (ids are unique so it is not semantically needed, but `native`
  equality compares lists, so preserve it for `loads(dumps(net)) == net`-style tests).

---

## Native JSON as the pivot

Yes — every format above maps *through* `Network` and nothing else: pandapower/PyPSA
exporters consume a `Network`, RAW/pandapower/CSV importers produce one, and `io.native`
already is `Network.model_dump_json` / `model_validate_json`. All four field maps are
expressed as mambo-field ↔ format-field; no format needs a second intermediate. The
constraint this imposes: anything a format carries that `Network` lacks is dropped at
import, so the gaps below bound what "lossless" can mean.

## Model gaps (Step-1 scope questions, not decisions)

- **G1 `Bus.name`** — RAW `NAME`, pandapower `bus.name`, MATPOWER `bus_name` all carry a
  human name; mambo keeps only `id`. Today ids are `bus-<n>`; a name field (or letting
  importers put the name into `id`) is needed for round-tripping any of the three.
- **G2 Generator-on-PQ-bus and slack identity** — pandapower derives bus role from element
  type (`ext_grid`/`gen`/`sgen`); PyPSA from `control`. mambo's `Bus.type` + `Generator`
  can express states (PQ bus with a generator; PV bus without) pandapower cannot; the
  exporter needs a documented rule (probably `sgen` for PQ-bus generators).
- **G3 Per-branch end shunts / transformer magnetising** — RAW `GI BI GJ BJ`, `MAG1 MAG2`;
  pandapower `pfe_kw`, `i0_percent`, `g_us_per_km`. mambo has only total `b`; folding into
  `Shunt` rows is lossy for the branch-status coupling.
- **G4 `Branch` kind** — nothing marks a branch as a transformer. Exporters must infer it
  (`tap_ratio`/`shift_deg` set, or from/to `base_kv` differ), which mis-classifies a
  nominal-tap transformer between equal-kV buses and pandapower's `line`-with-different-kV.
  An explicit `kind: line|transformer` (or a `transformer` flag) would make both exporters
  exact.
- **G5 Multiple ratings** — RAW `RATEB/RATEC`, MATPOWER `RATE_B/C`, PyPSA `s_max_pu`; only
  `rating_mva` exists. Not needed for round-trip of the shipped fixtures (unrated).
- **G6 Multi-element ids per bus** — RAW loads/generators/branches are keyed `(bus, ID)` /
  `(I, J, CKT)`; ids must encode `ID`/`CKT` to survive (`gen-1-1`, `branch-1-2-1`), and a
  RAW exporter (not in R11) would need to recover them. Only an id convention, no field.
- **G7 Cost degree / offset** — pandapower `poly_cost` stops at degree 2; `pwl_cost` stores
  slopes without the absolute offset; PyPSA has no piecewise at all. Not a model gap, but
  the exporters need a documented lossy rule (warn on degree > 2; drop offset; segment-split).
- **G8 `Zone.name`, `Bus.area` names** — pandapower has `zone` only; PyPSA neither; RAW has
  `ZONAME`/`ARNAME`. `Area` as an entity (like `Zone`) would let RAW areas round-trip.
- **G9 Storage efficiencies** — pandapower `storage` has none; PyPSA has both. Export to
  pandapower is lossy; no model change.
- **G10 Bus `vm_pu/va_deg` as inputs** — pandapower and PyPSA treat them as results;
  export can only put them in `res_bus` / `v_mag_pu_set`. Documented drop, no model change.
- **G11 Generator `q_mvar`, `p_mw` setpoints** — pandapower `ext_grid`/`gen` have no
  `q_mvar`; PyPSA `p_set` pins dispatch. Documented drop.

## Fixture candidates

| Format | Candidate | Licence / provenance | Fit |
| --- | --- | --- | --- |
| pandapower JSON | `pp.to_json(pn.case14())`, `pn.case30()` generated at test time (pandapower ships them; BSD-3) | no file to vendor; a checked-in `fixtures/pandapower/case14.json` generated once from 3.3.0 gives a stable byte target | good; note `vn_kv` 135/14/0.208 vs mambo 1.0 — compare in pu, not ohm |
| pandapower JSON | `pp.to_json(from_ppc(case14))` | crashes on `to_ppc`, `vn_kv=0` | reject |
| PyPSA | none needed; oracle built at test time (as `tests/parity/test_opf_vs_pypsa.py`); `export_to_csv_folder` output as golden | | good |
| RAW v33 | `ITI/models …/ieee-14-bus.raw` — v33, complete section set, matches IEEE-14 values exactly (bus 1 VM 1.06, branch 1-2 `0.01938/0.05917/0.0528`, xfmr 4-7 `X 0.20912 WINDV1 0.978`), 85 lines, BASKV 138 (not 0) | no licence detected on the repo via GitHub API; IEEE-14 data itself is public-domain UW archive | best content; licence must be settled or the file re-authored by hand from `case14.m` + this layout |
| RAW v33 | `grg-pssedata/tests/data/correct/pglib_opf_case73_ieee_rts.raw`, `WECC240_M21_psse33_v01b.raw` | parser BSD-3; data derived from pglib-opf (check its licence) | larger; good for a second, "real-world width" test |
| RAW v33 | `PowerFlowData.jl/test/testfiles/synthetic_data_v33.RAW` | MIT, 75 lines, README: "branches may reference buses not present" | parser-robustness fixture only, not solvable |
| RAW v33 | hand-authored `fixtures/psse/case14_v33.raw` written from `fixtures/matpower/case14.m` using the layout above (IEEE data already vendored under MATPOWER's terms) | ours | cleanest provenance; also gives CZ=2/CW=2 variants for the transformer code paths |
| CSV bundle | generated from every `fixtures/matpower/*.m` via `native` → bundle → `native`, equality test | ours | good |

## Three biggest fidelity limits (summary)

1. **Cost expressiveness**: pandapower caps polynomial at degree 2 and stores piecewise as
   slopes without offset; PyPSA has quadratic only; RAW has none. Piecewise costs and
   elastic bids cannot leave mambo intact in any of the three external formats.
2. **Branch identity and per-branch shunts**: no `kind` on `Branch` (G4) and no per-end
   shunt / magnetising fields (G3) make the line-vs-transformer split heuristic and RAW/
   pandapower transformer import lossy.
3. **Roles and setpoints**: pandapower/PyPSA derive bus roles from element types and treat
   `vm/va`, `q_mvar`, `p_mw` setpoints as results (or, in PyPSA, as dispatch pins), so
   mambo's declared `Bus.type` and generator setpoints do not survive export (G2, G10, G11).
