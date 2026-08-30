# Interop walk — four formats, from the docs, as a user

## Head and provenance

- Head walked: `7ec0b0b4a612a8714e226fd8198773ce0fdb9f44` (`wave/08-interop`).
- Copy: `git archive 7ec0b0b | tar -x` into
  `C:\Users\mambo\AppData\Local\Temp\claude\C--Claude-Projects-mambo-power\0d397067-49ef-4969-aefa-5709948393ef\scratchpad\m8-walk-7ec0b0b`;
  every command below ran there via `uv run --project <that dir> python ...`. Nothing was run in
  either checkout.
- Proof the package resolves from the archive:

```text
$ uv run --project $D python -c "import mambo_power, sys; print(mambo_power.__file__); print(sys.version)"
C:\Users\mambo\AppData\Local\Temp\claude\...\scratchpad\m8-walk-7ec0b0b\src\mambo_power\__init__.py
3.12.14 (main, Aug 14 2026, 15:40:22) [MSC v.1944 64 bit (AMD64)]
pandapower 3.3.0 pypsa 1.2.4
```

- Inputs: `docs/manual/formats.md`, `docs/manual/model.md`, `docs/manual/results.md`,
  `docs/api/io-*.md`, `docs/examples/index.md`, `examples/13_interop.py`, `docs/changelog.md`.
  I opened `src/mambo_power/io/csv_bundle.py` once, and only because a traceback landed in it
  (the BOM case below); I did not read it.
- Walk scripts: `walk/quiet.py` (captures stdout, stderr, every logging record and every
  warning around a converter call, and diffs `model_dump()` before/after), `walk/w3_pandapower.py`,
  `walk/w3b_trafo.py`, `walk/w4_pypsa.py`, `walk/w5_raw.py`, `walk/w6_csv.py`, `walk/w7_fresh.py`,
  all under the archive directory.

## What I read

`formats.md` cold, top to bottom, then the API stubs, then the example. Places where I did not
know what to type next:

1. The page says a bundle that is not exact is "raised as `ReportError`, whose `.report.errors`
   carry them" and that RAW raises `RawImportError` — but never says which module either lives
   in. I guessed `mambo_power.io.report.ReportError` and `mambo_power.io.psse_raw.RawImportError`;
   both guesses were right, but they were guesses.
2. The four `docs/api/io-*.md` pages are one paragraph plus a `::: mambo_power.io.<module>`
   directive. Read as files they carry no signatures, so every call shape came from the
   `formats.md` tables. The tables were enough for every call I made.
3. RAW record map: the rows list field *names* ("`I, ID, PG, QG, QT, QB, VS, ..., STAT, ..., PT,
   PB`") but not positions or minimum counts, and the transformer line 1 is
   "`I, J, K, CKT, CW, CZ, CM, MAG1, MAG2, ..., STAT`". To hand-write a file I had to remember
   from elsewhere that `NMETR` and `NAME` sit between `MAG2` and `STAT`. The page points at
   "grg-pssedata's `struct.py`" for the order — an external dependency for anyone writing a
   record by hand.
4. `Branch.kind` is documented in `model.md`, not in `formats.md`; I needed it to build a
   transformer at neutral tap and to build a phase shifter, and only found it by grepping.
5. The phrases "(M8 finding F1, carried as A19)", "(A3)" and "(decision D1)" appear in the
   limitations text. They read as internal ticket tags; a user cannot resolve them.
6. The pandapower section lists `FIELD_DROPPED` for "the slack generator's `p_mw` / `q_mvar`". I
   could not tell from the text whether a zero setpoint is reported too (it is not — see below).

## What I ran

### 1. `examples/13_interop.py` (verbatim, 60 s wall)

```text
$ uv run --project $D python examples/13_interop.py
case14: 14 buses, 20 branches, 5 gens

pandapower export: 104555 chars, report codes ['FIELD_DEFAULTED', 'FIELD_DROPPED']
   FIELD_DROPPED: gen-1: p_mw=232.4 dropped (ext_grid has no setpoint)
   FIELD_DROPPED: gen-1: q_mvar=-16.9 dropped (ext_grid has no setpoint)
   FIELD_DROPPED: gen-2: q_mvar=42.4 dropped (gen is PV: no Q setpoint)
   ... 9 issues in all; none touches a carried value
pp.rundcpp vs pf.solve_dc: worst angle difference 8.9e-15 deg, 14 buses

pandapower import of pp.networks.case14(): report []
   (an empty report means the conversion was lossless)
   14 buses, 20 branches, transformers ['trafo-0', 'trafo-1', 'trafo-2', 'trafo-3', 'trafo-4']
   neutral-tap transformers kept as transformers by the source table: ['trafo-3', 'trafo-4']

PyPSA export: 14 buses, 17 lines, 3 trafos
   report codes ['PYPSA_GEN_Q_LIMITS_DROPPED', 'PYPSA_ZONE_DROPPED'] (6 issues)
   PyPSA optimize ('ok', 'optimal'): objective 7642.5918 $/h (incl. constant 0.0)
   opf.solve_dc_opf Optimal: objective 7642.5918 $/h
   relative difference 7.5e-14

RAW import: 14 buses, 20 branches
   report codes ['BASE_KV_REPLACED', 'RAW_NO_COSTS'] (15 issues)
   RAW_NO_COSTS: RAW carries no cost data; all 5 generators imported with cost=None
   pf.solve_dc on the RAW network vs the MATPOWER one: worst angle diff 0.0e+00 deg

CSV bundle: ['branches.csv', 'buses.csv', 'generator_costs.csv', 'generators.csv', 'load_bids.csv', 'loads.csv', 'manifest.json', 'shunts.csv', 'storage.csv', 'zones.csv']
   load(dump(net)) == net: True

Piecewise cost into PyPSA (which has none):
   PYPSA_PWL_COST_DROPPED: element_ids=['gen-2']
   generator 'gen-2': PyPSA has no piecewise-linear cost; dropped the 3-point cost, exported with marginal_cost 0
```

Every number in the docs' example blocks (`14 20 ['BASE_KV_REPLACED', 'RAW_NO_COSTS'] 15`,
the PyPSA `6` issues, the pandapower `[] 0`) matched what ran.

### 2. pandapower — hand-built net (`walk/w3_pandapower.py`)

Four buses (A, B, D at 110 kV; C at 20 kV), two `ext_grid` (A and D), three lines, one
`trafo` B→C at `tap_pos = tap_neutral = 0`, a `gen` at B with a `poly_cost`, an `sgen` at C with
a `pwl_cost`, a `poly_cost` on the first `ext_grid`, a capacitor `shunt` at C
(`q_mvar = -3`), two loads. Output, trimmed only where marked:

```text
pp tables: {'bus': 4, 'load': 2, 'sgen': 1, 'gen': 1, 'shunt': 1, 'ext_grid': 2, 'line': 3, 'trafo': 1, 'pwl_cost': 1, 'poly_cost': 2}
[check:import] input unchanged=True stdout=0B stderr=0B log-records total=0 from-mambo=0 warnings total=0 from-mambo=0
report: ["EXTRA_EXT_GRID_DEMOTED: ext_grid[1] (grid2) at bus 'D': a second in-service ext_grid; imported as a PV generator (the model has one slack)",
         'FIELD_DEFAULTED: S2: min_q_mvar set to 1.0 (sgen.min_q_mvar missing or NaN)',
         'FIELD_DEFAULTED: S2: max_q_mvar set to 1.0 (sgen.max_q_mvar missing or NaN)']
  bus A 110.0 slack 1.02 0.0 None
  bus B 110.0 pv None None None
  bus C 20.0 pq None None None
  bus D 110.0 pv None None None
  br L01 A B r=0.00826446 x=0.0330579 b=0.00380133 95.26279441628824 None None line
  br L03 A D r=0.0165289 x=0.0661157 b=0.00760265 95.26279441628824 None None line
  br L13 B D r=0.0123967 x=0.0495868 b=0.00570199 95.26279441628824 None None line
  br T12 B C r=0.0125 x=0.249687 b=0 40.0 None None transformer
  gen grid1 A 0.0 0.0 0.0 300.0 -100.0 100.0 1.02 kind='polynomial' coefficients=[0.0, 40.0, 0.0] startup=0.0 shutdown=0.0
  gen grid2 D 0.0 0.0 0.0 100.0 -50.0 50.0 1.0 None
  gen G1 B 40.0 0.0 0.0 80.0 -30.0 30.0 1.01 kind='polynomial' coefficients=[0.05, 25.0, 10.0] startup=0.0 shutdown=0.0
  gen S2 C 5.0 1.0 0.0 10.0 1.0 1.0 1.0 kind='piecewise' points=[(0.0, 0.0), (5.0, 50.0), (10.0, 200.0)] startup=0.0 shutdown=0.0
  load D2 C 20.0 5.0
  load D3 D 30.0 8.0
  shunt SH2 C 0.0 3.0
  zones []
  expected L01 r = 0.008264462809917356 x = 0.03305785123966942 b = 0.00380132711084365 rating = 95.26279441628824
[check:export] input unchanged=True stdout=0B stderr=0B log-records total=0 from-mambo=0 warnings total=0 from-mambo=0
export report: []
back tables: {'bus': 4, 'load': 2, 'sgen': 1, 'gen': 2, 'shunt': 1, 'ext_grid': 1, 'line': 3, 'trafo': 1, 'pwl_cost': 1, 'poly_cost': 2}
  name  hv_bus  lv_bus  ...  tap_pos  tap_step_percent  tap_neutral
0  T12       1       2  ...      NaN               NaN          NaN
  name  bus  p_mw  q_mvar  step  vn_kv
0  SH2    2   0.0    -3.0     1   20.0
  power_type  element    et                                 points
0          p        0  sgen  [[0.0, 5.0, 10.0], [5.0, 10.0, 30.0]]
[check:solve_dc] input unchanged=True stdout=0B stderr=0B log-records total=0 from-mambo=0 warnings total=0 from-mambo=0
  A: mambo 0.000000 pp 0.000000 diff 0.0e+00
  B: mambo 0.115749 pp 0.115749 diff 5.6e-17
  C: mambo -2.030155 pp -2.030155 diff 0.0e+00
  D: mambo -0.420906 pp -0.420906 diff 5.6e-17
pp res_ext_grid p: [4.999999999999991]  pp res_gen p: [0.0, 40.0]
mambo gens: [('grid1', 5.0), ('grid2', 0.0), ('G1', 40.0), ('S2', 5.0)]
```

What came through: the line conversion matches the doc formula digit for digit (I recomputed
`L01` by hand from the table: `r`, `x`, `b`, `rating` all equal). The pwl points
`[[0,5,10],[5,10,30]]` became `(0,0),(5,50),(10,200)` — slope × width, offset 0, as the table
says. The capacitor sign flipped (`q_mvar=-3` → `b_mvar=+3`) as documented. The second
`ext_grid` came back as a PV generator with `p_mw = 0` and no cost, and on export it is a `gen`,
not an `ext_grid` — so a pandapower user round-tripping a two-slack net gets a different table
layout back; the report said so on the way in. `rundcpp` and `pf.solve_dc` agree to 1e-16°.

The export report was **empty** although the slack generator has `p_mw = 0.0` and `q_mvar = 0.0`
— so the `FIELD_DROPPED` for the slack setpoint fires only when the value is non-zero. Sensible,
but not what the table led me to expect.

Transformer tap encoding, six variants (`walk/w3b_trafo.py`, one line each):

```text
== neutral None   report: [FIELD_DROPPED g p_mw]   tap_side None  tap_neutral NaN  tap_pos NaN  tap_step_percent NaN   -> reimport tap_ratio None kind transformer x 0.1
== neutral 1.0    same as above                                                                                       -> reimport tap_ratio None kind transformer
== tap 1.05       tap_side hv  tap_neutral 0.0  tap_pos 1.0   tap_step_percent 5.0                                    -> reimport tap_ratio 1.05
== tap 0.95       tap_side hv  tap_neutral 0.0  tap_pos -1.0  tap_step_percent 5.0                                    -> reimport tap_ratio 0.95
== shift 10       shift_degree 10.0, tap columns NaN                                                                  -> reimport shift 10.0
== unrated        report adds: FIELD_DEFAULTED: t: rating_mva is None; trafo sn_mva set to base_mva 100.0 (...) and re-imports as the rating
                  sn_mva 100.0 vk_percent 10.049876                                                                   -> reimport rating 100.0, x 0.1
```

Round trip of a bundled case (`case30.m` → pandapower JSON → back):

```text
[check:dump30] input unchanged=True stdout=0B stderr=0B log-records total=0 from-mambo=0 warnings total=0 from-mambo=0
export codes: ['FIELD_DROPPED'] 1
[check:load30] input unchanged=True stdout=0B stderr=0B log-records total=0 from-mambo=0 warnings total=0 from-mambo=0
import codes: [] 0
equal: False
1 field differences; first 25:
   .generators[0].p_mw: 23.54 vs 0.0
```

Exactly the one field the export report named, nothing else, to 1e-9 relative on every float.

An unrated *line* (case14 `branch-1` with `rating_mva = None`) exports as `max_i_ka = NaN`,
re-imports as `None`, and is not reported — lossless, and the docs do not need to say more.

### 3. PyPSA (`walk/w4_pypsa.py`)

```text
[check:to_network case30] input unchanged=True stdout=0B stderr=0B log-records total=6 from-mambo=0 warnings total=0 from-mambo=0
   log matplotlib:DEBUG: matplotlib data path: ...      (three matplotlib DEBUG records from PyPSA's own import chain; none from mambo_power)
case30 report: ['PYPSA_GEN_Q_LIMITS_DROPPED', 'PYPSA_ZONE_DROPPED'] 7
   PYPSA_GEN_Q_LIMITS_DROPPED: generator 'gen-1': PyPSA generators carry no reactive limits; dropped q_min_mvar=-20.0, q_max_mvar=150.0
   ... (trimmed: one line per generator)
          bus  p_nom  p_min_pu  p_max_pu  marginal_cost  marginal_cost_quadratic  marginal_cost_constant control
gen-1   bus-1   80.0       0.0       1.0           2.00                   0.0200                     0.0   Slack
gen-2   bus-2   80.0       0.0       1.0           1.75                   0.0175                     0.0      PV
gen-3  bus-22   50.0       0.0       1.0           1.00                   0.0625                     0.0      PV
p_set on generators: [nan, nan, nan, nan, nan, nan]
pypsa ('ok', 'optimal') objective 565.205966 (c0 0.0); mambo Optimal 565.205966; rel 8.8e-13
worst dispatch diff MW: 8.41e-05
[check:pwl export] input unchanged=True ...
pwl report:
   PYPSA_PWL_COST_DROPPED: generator 'gen-3': PyPSA has no piecewise-linear cost; dropped the 3-point cost, exported with marginal_cost 0
  exported marginal_cost for gen-3 = 0.0
[check:unrated export] input unchanged=True ...
unrated report: [... PYPSA_GEN_Q_LIMITS_DROPPED x2 ...] ...codes ['PYPSA_GEN_Q_LIMITS_DROPPED', 'PYPSA_ZONE_DROPPED']
lines s_nom unique: [100000.0] trafos s_nom unique: [] UNRATED const: 100000.0
unrated: pypsa ('ok', 'optimal') obj 565.205966 mambo 565.205966
[check:shift export] input unchanged=True ...
shift report: ["PYPSA_GEN_Q_LIMITS_DROPPED: generator 'g': ..."]
     bus0 bus1  phase_shift  tap_ratio    x  s_nom
ac      a    c         10.0        1.0  0.1  100.0
lpf flows: {'ab': 78.17764173314431, 'bc': 78.17764173314431, 'ac': -18.177641733144327}
mambo solve_dc flows: {'ab': 78.1776, 'bc': 78.1776, 'ac': -18.1776} angles {'a': 0.0, 'b': -4.4792, 'c': -8.9585}
pypsa lpf angles: {'a': 0.0, 'b': -4.4792, 'c': -8.9585}
mambo dc_opf flows: {}
pypsa optimize flows (ignores phase_shift per docs): {'ab': 20.0, 'bc': 20.0, 'ac': 40.0}
```

The empty `dc_opf flows: {}` sent me back for a second look:

```text
shift 10.0 Infeasible "dc_opf: HiGHS reported model status 'Infeasible'" branches [] gens []
   solve_dc [('ab', 78.178), ('bc', 78.178), ('ac', -18.178)]
shift None Optimal None branches [('ab', 20.0), ('bc', 20.0), ('ac', 40.0)] gens [('g', 60.0)]
   solve_dc [('ab', 20.0), ('bc', 20.0), ('ac', 40.0)]
```

Same three-bus loop, one 200 MW generator, one 60 MW load, every branch rated 100 MVA. With a
10° shifter `pf.solve_dc` finds flows well inside every rating; `opf.solve_dc_opf` says
`Infeasible` and returns no rows.

### 4. PSS/E RAW (`walk/w5_raw.py`)

```text
[check:raw case14] input unchanged=True stdout=0B stderr=0B log-records total=0 from-mambo=0 warnings total=0 from-mambo=0
codes: ['BASE_KV_REPLACED', 'RAW_NO_COSTS'] 15
   BASE_KV_REPLACED: bus-1: BASKV is 0; base_kv set to 1.0 (line 4)
   ... (trimmed)
gens: [('gen-1-1', 'bus-1', 232.4, 332.4, None), ('gen-2-1', 'bus-2', 40.0, 140.0, None), ('gen-3-1', 'bus-3', 0.0, 100.0, None)]
trafos: [('branch-4-7-1', 0.978, None, None, 'transformer'), ('branch-4-9-1', 0.969, None, None, 'transformer'), ('branch-5-6-1', 0.932, None, None, 'transformer')]
zones: [Zone(id='1', name='1')] bus1 area/zone: 1 1
solve_dc:  [0.0, -5.012, -12.954, -10.584, -9.094]
solve_ac:  2
```

`opf.solve_dc_opf` on that cost-less network did **not** raise. Checked separately:

```text
dc_opf: Optimal None objective 0.0 gens [('gen-1-1', 259.0), ('gen-2-1', 0.0), ('gen-3-1', 0.0), ('gen-6-1', 0.0), ('gen-8-1', 0.0)]
market.solve_nodal: Optimal None
```

Objective 0, all 259 MW on the slack, status `Optimal`, no message.

Hand-written three-bus file (slack 110 kV, a 110 kV line, a 110/20 kV transformer at unity
winding ratios, two loads, one fixed shunt, one generator, one area, one zone):

```text
tiny codes: ['RAW_NO_COSTS: RAW carries no cost data; all 1 generators imported with cost=None']
  bus bus-1 110.0 slack 1 1 None None
  bus bus-2 110.0 pq 1 1 None None
  bus bus-3 20.0 pq 1 1 None None
  br branch-1-2-1 0.01 0.1 0.02 100.0 None None line
  br branch-2-3-1 0.005 0.08 0.0 40.0 1.0 None transformer
  gen gen-1-1 40.0 50.0 -50.0 1.02 200.0 0.0 True
  load load-2-1 30.0 10.0
  load load-3-1 10.0 2.0
  shunt shunt-3-1 0.0 5.0
  zones [Zone(id='1', name='ZONE1')]
  solve_dc angles: [0.0, -2.2918, -2.7502]
```

Everything I wrote came through where the record map said it would; `tap_ratio` is `1.0`
(not `None`) for a `WINDV1 = WINDV2 = 1.0` record and `kind` is `transformer`.

Deliberately broken variants of that file (exception type, `.code`, `.line`, message —
verbatim):

```text
REV=34:                       mambo_power.io.psse_raw.RawImportError {'code': 'UNSUPPORTED_VERSION', 'line': 1}: UNSUPPORTED_VERSION: only RAW version 33 is read, got 34 (line 1)
bus line with 3 fields:       mambo_power.io.psse_raw.RawImportError {'code': 'BAD_RECORD', 'line': 5}: BAD_RECORD: bus record has 3 fields, expected >= 9 (line 5)
unknown bus in load:          mambo_power.io.psse_raw.RawImportError {'code': 'UNKNOWN_BUS', 'line': 9}: UNKNOWN_BUS: load I: bus 9 is not in the bus section (line 9)
unknown bus in branch:        mambo_power.io.psse_raw.RawImportError {'code': 'UNKNOWN_BUS', 'line': 15}: UNKNOWN_BUS: branch J: bus 7 is not in the bus section (line 15)
missing bus terminator:       mambo_power.io.psse_raw.RawImportError {'code': 'UNTERMINATED_SECTION', 'line': 31}: UNTERMINATED_SECTION: vsc dc section is not terminated by a '0' line (line 31)
non-numeric R:                mambo_power.io.psse_raw.RawImportError {'code': 'BAD_NUMBER', 'line': 15}: BAD_NUMBER: branch: 'abc' is not a number (line 15)
no slack (IDE 3->2):          mambo_power.model.errors.NetworkValidationError {}: Network validation failed with 1 issue:
                                - NO_SLACK at buses: no in-service slack bus defined
truncated inside transformer: mambo_power.io.psse_raw.RawImportError {'code': 'BAD_RECORD', 'line': 17}: BAD_RECORD: transformer record spans 4 lines; file ends first (line 17)
IC=1:                         mambo_power.io.psse_raw.RawImportError {'code': 'BAD_HEADER', 'line': 1}: BAD_HEADER: IC must be 0 (full case), got 1 (line 1)
empty text:                   mambo_power.io.psse_raw.RawImportError {'code': 'BAD_HEADER', 'line': None}: BAD_HEADER: a RAW file starts with three case-identification lines
no Q, file ends after zone:   NO ERROR
extra fields on bus record:   NO ERROR
```

### 5. CSV bundle (`walk/w6_csv.py`)

Dump of case14; the files as written (first two rows of each, trimmed):

```text
manifest: {"format": "mambo-power-csv", "schema_version": 1, "base_mva": 100.0,
  "tables": {"buses.csv": 14, "branches.csv": 20, "generators.csv": 5, "generator_costs.csv": 15, "loads.csv": 11, "load_bids.csv": 0, "shunts.csv": 1, "storage.csv": 0, "zones.csv": 1}}
-- buses.csv (14 rows)
    id,base_kv,type,in_service,vm_pu,va_deg,v_min_pu,v_max_pu,area,zone,geo_lat,geo_lon
    bus-1,1.0,slack,true,1.06,0.0,0.94,1.06,1,1,,
-- generators.csv (5 rows)
    id,bus,p_mw,q_mvar,p_min_mw,p_max_mw,q_min_mvar,q_max_mvar,v_set_pu,in_service,cost_kind,cost_startup,cost_shutdown,ramp_up_mw,ramp_down_mw
    gen-1,bus-1,232.4,-16.9,0.0,332.4,0.0,10.0,1.06,true,polynomial,0.0,0.0,,
-- generator_costs.csv (15 rows)
    generator_id,index,p_mw,value
    gen-1,0,,0.0430292599
-- loads.csv (11 rows)
    id,bus,p_mw,q_mvar,in_service,bid_kind
    load-2,bus-2,21.7,12.7,true,
-- shunts.csv (1 rows)     id,bus,g_mw,b_mvar,in_service / shunt-9,bus-9,0.0,19.0,true
-- zones.csv (1 rows)      id,name / 1,
-- storage.csv (0 rows)    id,bus,p_max_mw,energy_mwh,soc_initial,efficiency_charge,efficiency_discharge,in_service
-- load_bids.csv (0 rows)  load_id,index,p_mw,value
branches.csv rows with tap: ['branch-8,bus-4,bus-7,0.0,0.20912,0.0,,0.978,,true,transformer', ...]
load == net: True report: []
```

Hand edits, one per copy of the bundle (verbatim; `first diffs` compares `model_dump()` text):

```text
float edit branches r 0.01938->0.02:        loaded; == net: False; first diffs: [("'r': 0.01938", "'r': 0.02")]
float edit comma decimal 0,02 (quoted):     ReportError with 1 errors:  CSV_BAD_VALUE: branches.csv line 2: "r" = '0,02' is not a float
float edit 1e-5 written as 0.00001:         loaded; == net: False; first diffs: [("'r': 0.01938", "'r': 1e-05")]
id edit bus-1->bus-01 in buses only:        NetworkValidationError: Network validation failed with 16 issues:
                                              - DANGLING_REF at branches[0].from_bus: branch "branch-1": from_bus references missing bus "bus-1"  (... trimmed)
id edit bus-14 -> bus-XIV everywhere:       loaded; == net: False; first diffs: [("{'id': 'bus-14'", "{'id': 'bus-XIV'"), ("'to_bus': 'bus-14'", "'to_bus': 'bus-XIV'"), ...]
empty required cell (branch x):             ReportError with 1 errors:  CSV_BAD_VALUE: branches.csv line 2: "x" is empty but required
empty optional cell (all bus vm_pu):        loaded; == net: False; first diffs: [("'vm_pu': 1.06", "'vm_pu': None"), ...]
empty in_service cell:                      ReportError with 11 errors: CSV_BAD_VALUE: loads.csv line 2: "in_service" is empty but required  (one per row)
delete shunts.csv:                          ReportError with 1 errors:  CSV_MISSING_TABLE: shunts.csv is missing
delete storage.csv (empty table):           ReportError with 1 errors:  CSV_MISSING_TABLE: storage.csv is missing
delete manifest.json:                       ReportError with 1 errors:  CSV_MANIFEST_INVALID: manifest.json is missing
add column note to loads.csv:               ReportError with 1 errors:  CSV_UNKNOWN_COLUMN: loads.csv: unknown column "note"
bool as TRUE:                               loaded; == net: True
bool as yes:                                ReportError with 1 errors:  CSV_BAD_VALUE: branches.csv line 2: "in_service" = 'yes' is not true/false/1/0
nan float:                                  ReportError with 1 errors:  CSV_BAD_VALUE: branches.csv line 2: "r" = 'nan' is not finite
duplicate id:                               ReportError with 1 errors:  CSV_DUPLICATE_ID: branches.csv: duplicate id "branch-1"
orphan cost row (gen-1 row 0 -> gen-99):    ReportError with 2 errors:  CSV_ORPHAN_ROW: generator_costs.csv: row for generator_id "gen-99" whose owner is absent or has no cost_kind
                                                                        CSV_BAD_VALUE: generators.csv id "gen-1": generator_costs.csv row 0 has index '1', expected 0
row count wrong in manifest:                ReportError with 1 errors:  CSV_MANIFEST_INVALID: buses.csv: manifest says 13 rows, file has 14
schema_version 2:                           ReportError with 1 errors:  CSV_SCHEMA_VERSION: manifest.json schema_version 2; this build reads 1
bus-14 row deleted (dangling refs):         ReportError with 1 errors:  CSV_MANIFEST_INVALID: buses.csv: manifest says 14 rows, file has 13
kind=line on a tapped branch:               ReportError with 1 errors:  CSV_BAD_VALUE: branches.csv id "branch-8": : Value error, branch 'branch-8': kind='line' but tap_ratio=0.978 shift_deg=None; a line cannot have a tap or phase shift
CRLF line endings:                          loaded; == net: True
UTF-8 BOM on buses.csv:                     ReportError with 2 errors:  CSV_UNKNOWN_COLUMN: buses.csv: unknown column "\ufeffid"
                                                                        CSV_MISSING_COLUMN: buses.csv: missing column "id"
columns reordered in loads.csv:             loaded; == net: True
trailing blank line removed:                loaded; == net: True
extra blank line at end (two "\n"):         ReportError with 1 errors:  CSV_MANIFEST_INVALID: loads.csv: manifest says 11 rows, file has 13
dump with zone name '':                     ValueError zones '1': optional string field "name" is "" — the empty cell means None, so an empty string cannot be written
load nonexistent dir:                       ReportError CSV_MANIFEST_INVALID: manifest.json is missing
```

### 6. Unchanged input and silence (every conversion)

Every `[check:...]` line above reads `input unchanged=True stdout=0B stderr=0B ... from-mambo=0`
— `model_dump()` identical before and after, nothing written to stdout or stderr, no logging
record and no warning whose origin is `mambo_power`. The only records seen at all were three
`matplotlib:DEBUG` lines emitted while PyPSA was first imported. A fresh process with no logging
configuration (`walk/w7_fresh.py`: matpower load, pandapower export and import, PyPSA export,
RAW import) wrote nothing but the script's own final line:

```text
$ uv run --project $D python walk/w7_fresh.py
--- end of script (only line the script itself writes)
```

## Surprises

Each is a doc sentence next to what I saw.

1. **Neutral-tap transformer export.** Doc: "On export a nominal-tap transformer is written with
   `tap_pos = 0`". Observed: `tap_side None`, `tap_neutral NaN`, `tap_pos NaN`,
   `tap_step_percent NaN` for both `tap_ratio=None` and `tap_ratio=1.0`. It re-imports as a
   neutral transformer, so nothing is lost; the sentence is just not what the file holds.

2. **Phase shifter and the DC OPF.** Doc (stated under pandapower, PyPSA, RAW and CSV
   limitations): "A network with a non-zero `shift_deg` gets **wrong** `opf` / `market` branch
   flows". Observed on a three-bus loop with one 10° shifter, generously rated: `opf.solve_dc_opf`
   returns `status='Infeasible'`, message `dc_opf: HiGHS reported model status 'Infeasible'`,
   empty `branches` and `generators`, while `pf.solve_dc` and PyPSA's `lpf()` both solve it
   (78.18 / 78.18 / −18.18 MW). "Wrong flows" undersells it: I got no flows.

3. **OPF on a cost-less RAW import.** Doc: "an imported RAW network flows (`pf`), and `opf` /
   `market` on it fails the ordinary 'no cost' validation — the importer never invents costs".
   Observed: `opf.solve_dc_opf(net)` → `Optimal`, `objective_cost 0.0`, 259 MW on the slack and
   zero everywhere else; `market.solve_nodal(Scenario(network=net))` → `Optimal`. Nothing
   failed. The importer did not invent costs, but the solvers quietly treated `cost=None` as
   free, which is the outcome the sentence says cannot happen.

4. **Unrated branches into PyPSA are approximated without a report entry.** Doc, opening rule:
   "an empty report means the conversion was lossless; anything dropped, approximated or repaired
   is an issue naming the element id and the field." Doc, PyPSA field map: "An unrated branch gets
   `s_nom = 1e5`". Observed: with every `rating_mva` set to `None`, all 41 lines carry
   `s_nom = 100000.0` and the report contains only the Q-limit and zone codes — no line is
   named. The field map is honest about the value; the report is not, by the page's own rule.
   (pandapower does the same substitution for a transformer and *does* report it, as
   `FIELD_DEFAULTED`.)

5. **`UNTERMINATED_SECTION` names the wrong section.** Doc: "`UNTERMINATED_SECTION`: A section
   (through zone) without its `0` terminator", with "a 1-based `line` when known". Observed with
   the bus section's `0` line deleted (line 7): `UNTERMINATED_SECTION: vsc dc section is not
   terminated by a '0' line (line 31)`. The parser swallowed the load, shunt, generator and
   branch records as buses and ran out of file five sections later; a user is sent to line 31 of
   a 31-line file to fix line 7.

6. **Blank lines are rows.** Doc, cell rules: "Row order is list order and is preserved"; the
   errors table says a row count "that disagrees with the file" is `CSV_MANIFEST_INVALID`.
   Observed: appending two empty lines to `loads.csv` gives `manifest says 11 rows, file has 13`.
   An editor that adds a blank line on save makes the bundle unreadable, and the message points
   at the manifest rather than at the blank lines.

7. **A UTF-8 BOM breaks the id column.** Doc limitations list decimal-comma and `01 → 1` as the
   spreadsheet hazards. Observed: `buses.csv` saved with a BOM (Excel's "CSV UTF-8" does this)
   fails with `CSV_UNKNOWN_COLUMN: buses.csv: unknown column "\ufeffid"` plus
   `CSV_MISSING_COLUMN: buses.csv: missing column "id"`. The bundle is described as being "for
   spreadsheet tooling"; the most common spreadsheet's default UTF-8 save is refused with a
   message that looks, on a cp1252 console, like the column is named `id`.

8. **Slack bus state from `ext_grid`.** Doc, tables read: "`res_bus` when it is non-empty (a
   stored voltage state → `vm_pu` / `va_deg`)". Observed on a hand-built net with no `res_bus`:
   the slack bus imported with `vm_pu = 1.02`, `va_deg = 0.0` (the `ext_grid`'s `vm_pu` /
   `va_degree`) while every other bus has `None`. Reasonable, undocumented, and it makes the
   "warm start when every in-service bus carries both" rule in `model.md` never apply to such a
   file — one bus has a state, thirteen do not.

## Friction

1. Import paths for `ReportError` and `RawImportError` are never stated in `formats.md`; both
   had to be guessed (`mambo_power.io.report`, `mambo_power.io.psse_raw`).
2. The `docs/api/io-*.md` pages are mkdocstrings stubs. Without a built site, every signature
   comes from the manual's tables; the tables sufficed, but a reader of the repository has no
   second source.
3. Writing a RAW record by hand needs field positions and minimum counts the record map does not
   give (`..., STAT, ...`); the page defers to grg-pssedata's `struct.py`. The error messages
   (`expected >= 9`) reveal the minimums one failure at a time.
4. Hand-editing a bundle that removes or adds a row also means editing `manifest.json`, and the
   error for a removed row is about the manifest, not the missing entity. For a format pitched
   at spreadsheet users this is one more file than they expect to touch.
5. The orphan-row case produces a second, misleading error blaming a generator that is fine
   (`gen-1: generator_costs.csv row 0 has index '1', expected 0`) — a cascade from the
   renamed row, not a second defect.
6. `examples/13_interop.py` takes about 60 s (pandapower/PyPSA import plus two solver runs) and
   must be run from the repository root; both are stated in the docstring, neither on the
   examples index.
7. The limitation paragraphs carry internal tags — "(M8 finding F1, carried as A19)", "(A3)",
   "(decision D1)" — that a user cannot look up.
8. The `FIELD_DROPPED` for the slack generator's `p_mw` / `q_mvar` is silent when the value is
   `0.0`; the table lists the field unconditionally, so an empty export report on a net whose
   slack has a zero setpoint reads as "nothing was dropped" when the doc says it always is.

## Verdict

From a user's chair the four formats do what the manual says on the happy path, and the
reports are the best part: every conversion I ran came back with an empty report when nothing
was lost and a named element and field when something was, the input `Network` was never
touched, and the library never printed or logged a byte — I could read a report, act on it, and
trust the silence. pandapower's `rundcpp` and PyPSA's `optimize()` agree with `pf.solve_dc` and
`opf.solve_dc_opf` to solver noise on both bundled cases and my own nets, the RAW importer's
errors carry a code and a line, and the CSV bundle is genuinely bit-exact and refuses most of
the ways I broke it with a message I could act on. What I would not trust without reading this
record first: three doc sentences say the opposite of what happens — a cost-less RAW network
*solves* an OPF at zero cost instead of failing, a phase-shifted network makes the DC OPF
*infeasible* rather than merely wrong, and an unrated branch into PyPSA becomes a 1e5 MVA line
with no report entry despite the page's one rule. Add the BOM and blank-line refusals for the
spreadsheet audience and the mis-located `UNTERMINATED_SECTION`, and the picture is a solid
interchange layer whose manual is a few sentences behind its own behaviour on exactly the edges
a user meets when something is not case14.
