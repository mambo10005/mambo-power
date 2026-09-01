# M8 "interop" — Step-6 adversarial critic

Head `7ec0b0b` on `wave/08-interop`, base `15e71fa`. Reviewed from an isolated `git archive`
copy (`scratchpad/m8-critic-7ec0b0b`, `mambo_power.__file__` proven there); experiments in
`scratchpad/m8-critic-exp/e1_pp.py … e9_kind.py`. pandapower 3.3.0, PyPSA 1.2.4.

Suite on the copy: first run (`-x`) `1 failed, 382 passed, 4 skipped` — the failure was
`test_examples_run[13_interop]` (finding 5); it passes alone in 57.8 s against a 60 s budget.
Second run with that test deselected: exit 0, no `FAILED` line in the short summary (4 skips,
all pre-existing `test_market_zonal_vs_pypsa` parameter skips). The wave's own tests are green;
every finding below is outside what they exercise.

## Findings

### 1. blocking — PyPSA transformer `b` is scaled the wrong way (`io/pypsa.py:185`)

Impedance goes to the `s_nom` base by `× s_nom/base_mva`; admittance goes by `× base_mva/s_nom`.
The code applies the impedance factor to `b`. Every bundled fixture has `b = 0` on its
transformers, so no test sees it.

```
# e2_pypsa.py / e3_pypsa_fix.py: 2-bus, transformer r=0.01 x=0.2 b=0.3 (pu on 100 MVA), s_nom=40
pypsa transformers b column: 0.12  b_pu: 4.8   (x_pu 0.002 is right; b_pu should be 30 = 0.3*100)
mambo  pf.solve_ac  vm_b: 1.00534996
pypsa  n.pf()       vm_b: 0.97977872   (as exported, b = 0.3*40/100)
pypsa  n.pf()       vm_b: 1.00534996   (after setting b = 0.3*100/40 by hand)
```

Fix: `b=[br.b / k for br, k in zip(trafos, scale)]` (the same inversion the line branch already
does with `br.b / z` at `pypsa.py:170`), plus a unit test with a non-zero transformer `b`
compared against `n.pf()`.

### 2. blocking — pandapower import applies a tap that pandapower itself ignores (`io/pandapower_json.py:511-521`)

pandapower ≥ 3.0 applies `tap_pos` only when `tap_changer_type` is set (`"Ratio"`,
`"Symmetrical"`, `"Ideal"`); `create_transformer_from_parameters` defaults it to `None`, in which
case the tap columns are inert. The importer never reads `tap_changer_type` and treats every
tap as a ratio tap on the named side.

```
# e1_pp.py: 110/20 kV trafo, tap_pos=2 tap_neutral=0 tap_step_percent=2.5 tap_side=hv
tap_changer_type=None         pp ppc tap=1.000000  mambo tap=1.05      pp vm_lv 0.993405 / mambo 0.945418
tap_changer_type="Ratio"      pp ppc tap=1.050000  mambo tap=1.05      (agree)
"Symmetrical", tap_step_degree=5   pp tap=1.049819 shift=0.238  mambo tap=1.05 shift=None
"Ideal", tap_step_percent=0, tap_step_degree=5   pp tap=1.0 shift=10.0  mambo tap=None shift=None
```

The `None` case is the silent one: no report entry, and the converted network's AC solution
differs from pandapower's on the same file by 0.048 pu. (`Symmetrical`/`Ideal` at least emit
`COLUMN_DROPPED` for `tap_step_degree`, though the value written is still wrong rather than
dropped.) This breaks the design invariant "importing through any format never changes what
`pf.*` computes".

Fix: apply the tap factor only when `tap_changer_type == "Ratio"`; for `"Ideal"` set
`shift_deg += tap_pos·tap_step_degree`; for `"Symmetrical"` either implement pandapower's
complex-factor formula or drop the whole tap with a `COLUMN_DROPPED` naming `tap_changer_type`.
Add the three cases to `test_io_pandapower_json.py` compared against `net._ppc` after `runpp`.

### 3. blocking — `Branch.kind` goes stale on mutation, and a mutated branch no longer round-trips (`model/entities.py:80-94`)

`kind` is derived once, in a `mode="before"` validator. `Branch` is not frozen and the tree
mutates entities routinely (`examples/13_interop.py:122` does). After `br.tap_ratio = 1.05`
on a line-classified branch:

```
# e5 (e1_pp.py) and e9_kind.py, case14 line
kind after mutation: line
pandapower export report mentions tap? False   re-imported tap: None      <- tap silently lost
Branch.model_validate(br.model_dump()) -> ValidationError: kind='line' but tap_ratio=1.05 ...
```

Two consequences: (a) every exporter routes on `kind`, so the tap is dropped **without a report
entry** — the one thing D1 forbids; (b) `native.dumps` → `native.loads` of that network now
raises, which is a regression for any pre-M8 script that sets a tap and saves (`model_copy(
update=...)` has the same hole). AC-6's "every pre-M8 test passes" holds only because no test
mutates a tap.

Fix (pick one, the first is smallest): in `_default_kind`, when `kind == "line"` and the tap is
off-nominal, *promote* to `"transformer"` instead of raising (an explicit `"line"` with a tap
is then a typo that heals rather than a trap); and make exporters route on
`br.kind == "transformer" or not _is_nominal(br.tap_ratio, br.shift_deg)`. Or add
`validate_assignment=True` with an `after` validator that recomputes `kind` from the fields.

### 4. should-fix — pandapower export is quadratic: 24–33 s on case300 (`io/pandapower_json.py:672-848`)

```
# e7_time.py / e8_prof.py (best of 3)
pandapower dumps (case300)   24332 ms     _to_pandapower 33.4 s of which pp.to_json 0.5 s
pandapower loads (case300)    3814 ms     pp.from_json_string 5.2 s, _from_pandapower 1.2 s
pypsa to_network (case300)    1147 ms
csv dump / load (case300)       95 / 117 ms
raw loads (case14)              12.8 ms
matpower load (case300)         59 ms
```

cProfile: 55 s of the 68 s profiled run is pandapower's per-row `_set_entries` /
`_preserve_dtypes` (1079 single-element `create_*` calls, 13 789 `.at` writes). Fix: build the
column lists and call the vectorised creators once per table — `pp.create_buses`,
`create_lines_from_parameters`, `create_transformers_from_parameters`, `create_gens`,
`create_sgens`, `create_loads`, `create_shunts` — then set `res_bus`/`area` as whole columns.
Expect < 1 s.

### 5. should-fix — `test_examples_run[13_interop]` is a 58 s script under a 60 s budget

`tests/unit/test_examples_run.py:23` says "each script is ~1 s locally; the budget only guards
against a hang". `13_interop` imports pandapower and PyPSA, builds `pn.case14()`, exports,
runs `runpp`, `optimize()`; measured 57.79 s alone on this machine and it **timed out in the
full-suite run** (the only failure). Either raise the budget for this script explicitly or trim
the example (finding 4 makes the export itself part of the cost).

### 6. should-fix — `gen.slack=True` (pandapower's ext_grid-less slack) is not a slack (`io/pandapower_json.py:367-395`)

pandapower documents `gen.slack = True` as the alternative to an `ext_grid`; `runpp` solves it.
The importer only flags the column as `COLUMN_DROPPED` and the bus stays `pq`:

```
# e2 (e1_pp.py)
pp solves: True
EXC NetworkValidationError: NO_SLACK at buses: no in-service slack bus defined
```

Fix: if no in-service `ext_grid` exists, the first in-service `gen` with `slack == True` takes
the slack role (`bus.type = "slack"`, `bus.vm_pu = vm_pu`), reported as a repair. The same code
path should give a *report* (not a validation traceback) when every `ext_grid` is out of
service (`e11`: same `NO_SLACK` exception).

### 7. should-fix — `csv_bundle.dump` can leave a stale-manifest Frankenstein bundle (`io/csv_bundle.py:309-347`)

`dump` writes table by table and raises `ValueError` mid-way when an optional string field is
`""`; the manifest is written last. If the directory already held a bundle, the old manifest
now sits beside a mix of new and old tables — and **loads**, because row counts still match:

```
# e8d (e4_csv.py): dump(net) then dump(bad) with zones[-1].name == "" and buses[0].base_kv = 999
ValueError: zones 'z': optional string field "name" is "" ...
bundle still loads: True | buses.csv now from bad net? 999.0 | == original: False
```

Fix: render every table (all `_cell` calls) into memory first, then write; or write to a temp
directory and rename. Cheap, and it also makes the `""` refusal an all-or-nothing contract.

### 8. should-fix — CSV tables saved from Excel (UTF-8 BOM) are refused (`io/csv_bundle.py:453`)

The module docstring sells the bundle as "inspected and edited with spreadsheet tooling"; Excel's
"CSV UTF-8" writes a BOM, and the reader opens with `encoding="utf-8"`:

```
# e8b: ReportError ['CSV_UNKNOWN_COLUMN: buses.csv: unknown column "﻿id"', 'CSV_MISSING_COLUMN: ... "id"']
```

Fix: `encoding="utf-8-sig"` (what `psse_raw.load_with_report` already does). CRLF, embedded
commas/quotes/newlines in ids all round-trip fine (e8a, e8c).

### 9. should-fix — the `LIMITATIONS` registry inverts the dependency (`io/report.py:77-90`)

`report.py` — the leaf every format module imports — imports all four format modules at its
bottom, and `io/__init__.py` has to comment "`report` must be imported first". It works today
only because `from mambo_power.io.report import ...` inside the format modules finds a
half-initialised module whose classes already exist; the first person to add a module-level
`from mambo_power.io import psse_raw` elsewhere, or to move the import above the class
definitions, gets an `ImportError` with a confusing partial-module message. It also leaves
`mambo_power.io.report.pypsa` bound to the mambo module (verified), a name that will bite
anyone grepping for the library.

Fix: move `LIMITATIONS` to `io/__init__.py` (which already imports every format) or to a new
`io/limitations.py` that imports the formats; `report.py` stays a leaf. Optional-dependency
import is otherwise clean: `mambo_power.io` imports with `pypsa`, `pandapower` and `pandas`
blocked (e9).

### 10. should-fix — importer reads `res_bus`, which the spec lists under "Not doing"

Spec "Not doing": "reading pandapower/PyPSA results tables". `_Importer.buses` reads `res_bus`
for `vm_pu`/`va_degree` (`pandapower_json.py:267, 280-282`) and the exporter writes `res_bus`
(`:689-692`). Neither the spec's Assumptions nor the docstring's "Tables read on import" line
flags the deviation as one. Either record it as a ruling (it is a reasonable one — the stored
state is model data, not a result) or drop it; the `Bus.vm_pu` initial state survives the
native format either way.

### 11. nit — `ext_grid` without limits imports as a slack that can generate 0 MW

`limits()` defaults a missing `min/max_p_mw` on `ext_grid` to the setpoint, which is 0 for an
`ext_grid` (`:351`, e3). Documented in `formats.md:334` and reported, so not silent — but for
the commonest hand-built pandapower net (`create_ext_grid` with no limits) it makes every
`opf.*` call infeasible or wrong. Consider `±base_mva·10` or a documented large bound for the
slack only, still reported.

### 12. nit — `psse_raw` and `csv_bundle` disagree on how a broken *file* is reported

`csv_bundle` collects every problem into `ImportReport.errors` and raises `ReportError`
(codes in `ImportIssueCode`); `psse_raw` raises its own `RawImportError` with a separate
`RawImportCode` literal on the first problem. Same wave, same "importer" role, two error
surfaces; W7's "`raise_on_error` behaves as `ImportReport`'s" is only true for one of them.

### 13. nit — RAW `area` section is silently discarded

`read_ignored` skips `"area"` and nothing else reads it (e5: `ARNAME` gone, no report). The
docstring says the section is "read". Either report the record (`RAW_SECTION_IGNORED`) or say
in the docstring/`formats.md:516` that only bus `AREA` labels survive.

### 14. nit — pathological inputs surface as tracebacks rather than reports

`csv_bundle`: a cell over `csv.field_size_limit()` (131 072 chars) raises `_csv.Error`
uncaught (e8e). `pandapower_json._label(float("inf"))` → `OverflowError`. Neither is
exploitable — no `eval`/`exec`/`pickle` anywhere in the wave (grepped), pandapower's JSON
decoder is registry-bound (`io_utils.py:483-496`), `csv_bundle` never derives a path from
input, RAW with a 200 000-field record parses in bounded time — but the "report is the only
channel" contract has holes at the edges.

### 15. nit — PyPSA `v_mag_pu_set` takes the first generator at the bus, in service or not

`_add_buses` (`pypsa.py:128`) keeps `gens[0].v_set_pu`; e6c shows an out-of-service unit's
1.05 winning over the live unit's 1.0. Filter to in-service generators first. Also
`marginal_cost_quadratic` accepts a negative `c2` with no report (e6b) — PyPSA/HiGHS will
reject the non-convex QP later with a solver error rather than a mambo issue.

### 16. nit — readability: where the fat is

- `pandapower_json.generators` (`:321-419`) is three near-identical 30-line blocks for
  `ext_grid`/`gen`/`sgen`; one loop over a `(table, role, q_from_setpoint)` tuple table halves
  it. The export side mirrors this with three `create_*` calls that differ in two kwargs.
- `check_columns` expectation dicts are scattered across six call sites; one module-level
  `_INERT = {"bus": {...}, "gen": {...}}` reads as the documentation it is trying to be.
- `psse_raw._scan` (`:243-273`) has the same "EOF or Q" test twice with different `>=`/`<=`
  logic against `_SECTIONS.index`; a single `while` with an explicit `after_zone` flag is
  clearer. `read_ignored`'s hard-coded 8-name skip tuple duplicates `_IGNORED_RECORD_LINES`'
  keys — derive one from the other.
- `psse_raw.__all__` re-exports `ImportReport`, which it does not define.

## Falsification attempts that failed

- **Per-unit maps on the pandapower path.** Checked line `r/x/b`, `max_i_ka` → rating, trafo
  `vk/vkr` → `z/r/x` on the tap-adjusted lv base, `tap_side="lv"`, `shift_degree`, shunt sign
  and `(vn/vn_kv)²`, `sn_mva ≠ base` against `net._ppc` and `runpp` on hand-built two-bus
  cases (e1): all agree to 1e-6 except the `tap_changer_type` cases in finding 2. Export →
  `from_json` → `runpp` on case14 reproduces pandapower's own solution to 4e-16 (e13).
- **RAW CZ/CW/CM combinations not in the fixtures** (e6): CW=2/CZ=1/CM=1 with non-zero MAG,
  CZ=2 with NOMV=0, CW=3 with NOMV2=0, CM=2 with SBASE1-2=0 — all hand-checked values match
  (`tap 144.9/138 = 1.05`, `r,x = 0.02,0.2`, magnetising shunt `1 MW, 5 MVAr`). Quoted names
  with `/` and `,`, negative load P, IDE=4 with a generator, records under the minimum field
  count, missing `REV`, EOF right after the zone terminator, a 200 000-field record: all
  behave as documented.
- **Real pandapower networks** (`mv_oberrhein`, `example_multivoltage`, `cigre_mv`) import
  without id collisions or exceptions (e4).

## Verdict

**Not merge-ready.** Three demonstrable correctness defects in shipped maps: the PyPSA
transformer `b` inversion (1) changes the AC solution on any transformer with charging; the
pandapower `tap_changer_type` blind spot (2) imports a tap pandapower does not apply, with no
report entry; and `Branch.kind` (3) goes stale on the ordinary mutation the tree already uses,
so exporters silently drop a tap and the native round-trip of such a network now raises — a
regression outside M8's own scope. Each fix is small and testable. After those, the
should-fixes 4–10 (quadratic export, the example's 58-of-60 s budget that already failed once
in the suite, `gen.slack`, non-atomic CSV dump, BOM, the inverted `report.py` import, and the
undeclared `res_bus` scope) are the difference between "works on the fixtures" and "works on
what users will feed it"; I would land 4, 5 and 7 with the blockers and file the rest.

## Re-review at e2d6da8

Head `e2d6da8` on `wave/08-interop` (fix commits `3f2a9a0..e2d6da8`, base `15e71fa`). Reviewed
from a fresh `git archive` copy (`scratchpad/m8-critic-e2d6da8`, `mambo_power.__file__` proven
under its `src/`). Every first-round script (`e1`–`e9`) re-run there unchanged; the new attacks are
`scratchpad/m8-critic-exp/x1_tap.py … x7_slack.py`, `x1b_legacy.py`, `x3b_mixed.py`, `x5b_cost.py`.

Suite on the copy: `1494 passed, 4 skipped` (the same four pre-existing zonal parameter skips),
0 failed, 225 s. `test_example_runs_to_completion[13_interop]` is now the slowest test at 8.5 s
(was 57.8 s).

### Status of the sixteen first-round findings

| # | sev | status | evidence at e2d6da8 |
|---|-----|--------|---------------------|
| 1 | blocking | **FIXED** | e2/e3: trafo `b` column 0.75 → `b_pu` 30.0 (= 0.3·100); `n.pf()` vm_b 1.00534996 = mambo 1.00534996 (was 0.97977872) |
| 2 | blocking | **FIXED** | e1: `tap_changer_type=None` → nominal + `COLUMN_DROPPED`; `Ratio` hv/lv, `Symmetrical` (tap 1.049819, shift 0.238), `Ideal` (shift 10.0) all match `net._ppc` and `runpp` to 1e-6; x1 B–G, L (negative steps, lv side, `tap_pos == neutral`, `tap_side` None, `Ideal` with neither step) agree too. Three edges it does not cover are new findings 17–19 |
| 3 | blocking | **FIXED DIFFERENTLY — accepted** | Promotion at validation + `Branch.is_transformer` for routing. e5: after `br.tap_ratio = 1.1` the pandapower round trip returns tap 1.1 (was `None`); e9: `model_validate(dump)` of the mutated branch → `transformer` (was `ValidationError`); x2: PyPSA puts it in `transformers`, CSV/native/pandapower all re-import it as a transformer. `kind` itself stays `"line"` until the next validation, which is what the docstring now says; see nit 24 for the file-level residue |
| 4 | should-fix | **FIXED** | e7 (best of 3): pandapower `dumps` case300 24 332 → **333 ms**, `loads` 3 814 → 646 ms; the bulk-creator ruling is `nets_equal` + per-cell equality, not byte identity — accepted (column order is pandapower's), but see finding 21 |
| 5 | should-fix | **FIXED** | per-script budget (`BUDGETS_S["13_interop"] = 240`), and the script itself now runs in 8.5 s in the suite |
| 6 | should-fix | **FIXED** | E2: `['slack', 'pq']` with `GEN_SLACK_PROMOTED`; x7: flagged gen out of service or on a dead bus → `NO_SLACK` (pandapower cannot solve those either), two flagged → first wins + `COLUMN_DROPPED` on the second, a live `ext_grid` wins over the flag. E11 (every `ext_grid` out of service) is still a `NetworkValidationError`, now stated in the module docstring — accepted as a ruling |
| 7 | should-fix | **PARTLY FIXED** | e8d: the `""` refusal now leaves the old bundle intact (`== original: True`). A failure in the *move* phase does not — finding 20 |
| 8 | should-fix | **FIXED** | e8b: BOM bundle loads (`utf-8-sig`) |
| 9 | should-fix | **FIXED** | x4: `report` is a leaf; `import mambo_power.io.{report,limitations,pypsa,pandapower_json,csv_bundle}` each succeed first in a fresh interpreter with `pandapower`/`pypsa`/`pandas` blocked; `mambo_power.io.report` no longer carries `pypsa`/`LIMITATIONS` attributes |
| 10 | should-fix | **FIXED** | `res_bus` neither read nor written; the export reports `FIELD_DROPPED` naming every non-slack bus with a stored state — recorded in the module docstring and the changelog |
| 11 | nit | not fixed | e3: `ext_grid` without limits still imports `min = max = 0`; documented, stands as a nit |
| 12 | nit | not fixed | e5: `psse_raw` still raises `RawImportError` on the first problem; stands |
| 13 | nit | **FIXED** | e5: area record → `RAW_SECTION_IGNORED`; docstring says only the bus `AREA` labels survive |
| 14 | nit | **FIXED** | e8e: over-limit cell → `CSV_BAD_VALUE`; `_label(inf)` → `"inf"` |
| 15 | nit | **FIXED** | e6c: in-service unit's 1.0 wins; e6b: `PYPSA_COST_NONCONVEX` reported |
| 16 | nit | not fixed | `generators()` is still 122 lines of three near-identical blocks; `psse_raw.__all__` still re-exports `ImportReport`; stands |

### New findings

#### 17. should-fix — `tap_neutral` NaN with a `Ratio` changer imports a tap pandapower does not apply (`pandapower_json.py`, `_Importer.tap_changer`)

`tap_neutral` defaults to `nan` in `create_transformer_from_parameters` (checked on 3.3.0), so a
user who sets `tap_pos`, `tap_step_percent`, `tap_side` and `tap_changer_type` and forgets it is
an ordinary file. pandapower computes `tap_diff = nan` and `_replace_nan` turns the step into 0;
the importer defaults the missing neutral to 0 and applies the tap:

```
# x1_tap.py case A: tap_pos=2, tap_step_percent=2.5, tap_side=hv, tap_changer_type=Ratio, no tap_neutral
pp    tap=1.0  vm=[1.0, 0.993405]
mambo tap=1.05 vm=[1.0, 0.945418] codes=['FIELD_DEFAULTED']      <- no tap-related report entry
```

Same invariant as finding 2, same silence. Fix: when `tap_pos` or `tap_neutral` is missing,
`diff = 0` (pandapower's rule) and report `COLUMN_DROPPED` naming the missing column.

#### 18. should-fix — pandapower ≤ 2.x files (`tap_phase_shifter`, no `tap_changer_type`) import at nominal tap while pandapower 3.3 still applies the tap, and the report says the opposite

`_calc_tap_from_dataframe` keeps an `elif "tap_phase_shifter" in trafo_df` branch (with a
`DeprecationWarning`) that applies the old-style tap; `from_json` of a `format_version 2.14.0`
file does **not** add `tap_changer_type` (measured: column absent after `from_json_string`).
The importer sees no `tap_changer_type` column, takes the changer as `None`, and writes a
`COLUMN_DROPPED` message asserting "pandapower applies no tap without a changer type":

```
# x1b_legacy.py: 2.x-style file, tap_pos=2 tap_neutral=0 tap_step_percent=2.5 tap_side=hv tap_phase_shifter=False
pp 3.3  ppc tap=1.05  vm=[1.0, 0.945418]
mambo   tap=None      codes=['COLUMN_DROPPED', 'FIELD_DEFAULTED']
        "…with tap_changer_type=None: pandapower applies no tap without a changer type; imported at the nominal tap"
```

Reported, but wrong — a reader of the report would believe the two engines agree. Fix: when the
`tap_changer_type` column is absent and `tap_phase_shifter` is present, map `True → "Ideal"`,
`False → "Ratio"` (exactly pandapower's fallback), and keep the `None` wording for files that have
the new column with an empty cell.

#### 19. should-fix — the second tap changer (`tap2_*`) is silently ignored

pandapower 3.3's `create_transformer_from_parameters` accepts `tap2_side/neutral/pos/
step_percent/step_degree/changer_type` and `_calc_tap_from_dataframe` loops over `("", "2")`.
The importer reads only `tap_*` and `check_columns` lists no `tap2_*` expectation:

```
# x1_tap.py case I: no tap1; tap2_side=lv tap2_pos=2 tap2_neutral=0 tap2_step_percent=2.5 tap2_changer_type=Ratio
pp    tap=0.952381 vm=[1.0, 1.043075]
mambo tap=None     vm=[1.0, 0.993405] codes=['FIELD_DEFAULTED']   <- nothing names tap2
```

Fix: run `tap_changer` twice (prefix `""`, `"2"`) and compose — the same function with a column
prefix — or at minimum report `COLUMN_DROPPED` for a `tap2_pos ≠ tap2_neutral`.

#### 20. should-fix — the "all-or-nothing" CSV dump is atomic against the `""` refusal but not against a failed move (`csv_bundle.py:dump`)

The staging directory is written under `try/except`, but the `os.replace` loop that follows is
not: on Windows a read-only target file or a file another process holds open (Excel with
`buses.csv` open is precisely the "spreadsheet tooling" use the docstring sells) fails mid-loop.
Tables before it are new, tables after it are old, the manifest is old, and the bundle loads:

```
# x3b_mixed.py: dump(a); hold generators.csv open; dump(b)  (b: buses[0].base_kv=999, generators[0].p_max_mw=12345)
dump(b) failed: PermissionError
buses.csv from b? True | generators.csv from b? False | == a: False | == b: False
orphaned staging dirs: ['.bundle.tmp-8352']
# x3_csv_atomic.py: read-only generators.csv → same PermissionError, same orphan; target that is a file →
# FileExistsError with an orphaned '.file.txt.tmp-<pid>'
```

Finding 7's Frankenstein bundle is back through a different door, plus an orphan `.<name>.tmp-
<pid>` per failure. Fix: swap at the directory level (rename `target` → `.<name>.old-<pid>`,
`staging` → `target`, `rmtree` the old; a directory rename with an open file inside fails on
Windows *before* anything moves, which is the atomic property wanted), and put the cleanup of
`staging` in a `finally`. Add the read-only-file test; it is one `os.chmod`.

#### 21. should-fix — a dead assertion in the bulk-export test (`tests/unit/test_io_pandapower_json.py:765`)

```python
def test_bulk_export_is_byte_identical_to_pandapowers_per_row_creators(build):
    ...
    assert text == pp.to_json(reference) or True  # column order (docstring) breaks byte equality
```

`… or True` cannot fail; the name promises what the body explicitly cannot prove. The real
contract the test does prove — `nets_equal`, identical column *sets*, per-cell equality including
`None`/`NaN`/`""`, identical re-import — is the right one (pandapower's bulk creators append
`max_*` before `min_*`; that is theirs). Delete the line and rename the test to what it checks.

#### 22. should-fix — `MissingCostError` is a behaviour change to `opf`/`market`/`jobs` that the changelog does not mention

`opf.solve_dc_opf`, `market.solve_nodal/multiperiod/zonal/agents` and the `opf.dc`,
`market.*` job kinds now refuse a network with an in-service cost-less generator
(x5b: `MissingCostError` from each; jobs → `failed` / `VALIDATION`); before M8 such a generator
was dispatched free (`test_solve_dc_opf_treats_a_costless_generator_as_free` was deleted). The
change is right (spec A3) and the manual pages say it, but `docs/changelog.md` has no line for it
— its only "cost" mention is `RAW_NO_COSTS`. A user upgrading gets a new exception from a
module M8 does not advertise touching. Add it to the changelog under a "behaviour change"
line, and extend the spec's `### Assumptions` with the rulings this round made (`kind`
promotion, no results tables, `gen.slack` promotion, `nets_equal` not byte identity, cost-less
generators refused): none of the five is there.

#### 23. nit — `MissingCostError`'s advice cannot be followed from the public API

The message ends "set `Generator.cost` or pass `costs=`", but `OpfDcOptions` has only
`ac_check` and no `market.solve_*` takes `costs` (`costs=` is `gen_cost_coeffs`'s private-ish
parameter; the agents path fills it from strategies, which refuse a cost-less generator with
`AgentSetError` anyway). Jobs carry the ids only in the message (`error.issues is None`), so a
client cannot read them structurally. Drop the `costs=` clause, or say where it applies.

#### 24. nit — a mutated branch's CSV/native row says `kind=line` beside a tap

x2: `csv row: {'kind': 'line', 'tap_ratio': '1.05'}`; native JSON the same. It heals on load
(promotion), so nothing is lost, but the file carries two truths and a spreadsheet reader
sees a "line" with a tap. Either write `is_transformer` into the `kind` column or say in the
CSV docstring that `kind` is the value at last validation.

#### 25. nit — three trafo edges where pandapower itself cannot solve

`tap_dependency_table=True` without a characteristic table: `runpp` raises `UserWarning`; the
importer applies the plain formula with a `COLUMN_DROPPED` on the flag (reported, so fine).
`tap_changer_type` as `pd.NA` (pandas `string` dtype): both sides `TypeError` — the "report is
the only channel" hole again, at an input pandapower rejects too. `Ideal` with `tap_neutral`
NaN: pandapower `FloatingPointError`, importer shift 10°. None is worth code; listed so the
next reviewer does not re-derive them.

#### 26. nit — a pre-existing `.<name>.tmp-<pid>` directory is `rmtree`'d without a word

x3 case 7: foreign content under that exact name is destroyed. The pid suffix makes a
collision unlikely; `tempfile.mkdtemp(prefix=f".{name}.tmp-", dir=parent)` makes it impossible.

### Attacks on the fixes that held

- **Tap formulas vs `_calc_tap_from_dataframe`** (x1): `Ideal` with negative steps
  (−8.6024°), `Ideal` on the lv side (−10°), `Symmetrical` lv side with a negative position
  (tap 1.051747, shift 0.5232°), `Ratio` with `tap_step_degree` (pandapower applies the angle to
  `Ratio` too and so does the importer), `tap_pos == tap_neutral`, `tap_side` None
  (`TAP_CHANGER_TYPE_UNSUPPORTED`, and pandapower applies nothing either) — all match `_ppc` to
  1e-6 and `runpp` voltages to 1e-6.
- **`kind` leak** (x2): an explicit `kind="line"` with a tap in the constructor, `model_copy`,
  `Network(**objects)`, numpy taps, `-0.0` shift — every exporter routes on `is_transformer`
  and every importer/loader re-derives; the schema text changed once as A2 allows.
- **PyPSA `b` with the `s_nom` sentinel** (x6): unrated trafo with `b = 0.3`, `r, x` `× k` and
  `b / k` with the same `k = UNRATED_S_NOM_MVA / base` → `n.pf()` 1.00534996 = mambo; a zero
  rating is refused by the model (`BAD_RANGE`), so no division by zero is reachable.
- **`MissingCostError` callers** (x5/x5b): an out-of-service cost-less generator is not in
  `gen_ids` and does not raise (`Optimal`); `pf.dc`, `pf.ac`, `n1` job kinds untouched (`ok`);
  a strategy on a cost-less generator was already `AgentSetError`; the `VALIDATION` failure
  round-trips through JSON; every RAW fixture now raises with all five generator ids named.
- **Import order** (x4): each `io` submodule importable first with the three third-party
  packages blocked; `report` carries no format-module attributes.
- **`GEN_SLACK_PROMOTED`** (x7): out-of-service or dead-bus flagged gen → `NO_SLACK` (pandapower
  cannot solve those either); two flags → first promoted, second `COLUMN_DROPPED`; a live
  `ext_grid` always wins.

## Verdict

**Merge after the listed should-fixes (17–22).** All three first-round blockers are fixed —
1 and 2 verified against PyPSA's and pandapower's own solvers, 3 by a design I accept — and
findings 4, 5, 8, 9, 10, 13, 14, 15 are closed with reproductions. What survives is a second
ring of the same invariant around the tap changer (17: `tap_neutral` NaN, pandapower's own
default; 18: pre-3.0 files, where the report now says the wrong thing; 19: `tap2_*`), the CSV
dump's atomicity gap on the failure Windows users will actually hit (20 — finding 7's bundle is
back through the move loop), a dead `or True` assertion (21) and a changelog that omits the
one behaviour change outside `io` (22). None needs design; 17, 18 and 20 are the ones I would
not merge without, since each reproduces the class of defect the first round was about.
