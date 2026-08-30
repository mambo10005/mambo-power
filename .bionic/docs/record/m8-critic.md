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
