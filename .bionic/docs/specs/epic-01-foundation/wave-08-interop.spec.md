---
governing-skill: agent-skills:spec-driven-development
sdlc-step: 2
intent: build
rigor: audited
scale: wave
canonical_sdlc_version: 13
surface_type: library
language: python
has_ui: false
multi_agent: true
deploy_target: none
cleanup_on_finish: true
use_worktree: true
rigor-floor: audited
design: specs/epic-01-foundation/epic.spec.md
walk: required
design-interview: true
model_plan:
  orchestrator: fable-5
  implementor: sonnet
  senior-implementor: opus
  researcher: sonnet
  test-runner: sonnet
  auditor: opus
  critic: opus
---

# Wave M8 — interop: pandapower JSON, PyPSA, PSS/E RAW v33, CSV bundle — through one `Network`

Epic requirement R11 (`epic.spec.md`): "Interchange formats: MATPOWER .m import, pandapower JSON
import/export, PyPSA export, PSS/E RAW v33 import, CSV bundle import/export, native JSON
round-trip." M1 shipped `.m` import and native JSON; this wave ships the other four. Scope and the
four Step-1 rulings: `record/m8-scope.md`. Evidence for every field map below: `record/m8-research.md`
(pandapower 3.3.0, PyPSA 1.2.4, linopy 0.9.1 — the versions the CI matrix installs).

## Requirements

- **W1 — pandapower JSON import.** `io.pandapower_json.load(path) / loads(text)` returns a
  `Network`; `load_with_report` returns `(Network, ImportReport)`. Reads `bus`, `ext_grid`, `gen`,
  `sgen`, `load`, `shunt`, `line`, `trafo` (2-winding), `poly_cost`, `pwl_cost`; per-unit conversions
  as measured (line r/x/b on `vn_kv²/sn_mva`; trafo x from `vk_percent` on the system base,
  `tap_ratio = 1 + (tap_pos − tap_neutral)·tap_step_percent/100`; shunt sign flipped). `ext_grid` →
  the slack generator; additional `ext_grid`s → PV generators plus a repair warning. Every column
  the model has no place for (bus `name`, `zone` names by name only, per-end magnetising shunts,
  areas) is dropped **and named in the report** — never silently.
- **W2 — pandapower JSON export.** `io.pandapower_json.dumps(net) / dump(net, path)` and
  `dumps_with_report` returning `(text, ExportReport)`. The exported text loads in pandapower
  (`pp.from_json`) and **pandapower's own solvers agree with mambo's** on it: `rundcpp` with
  `pf.solve_dc`, `runpp` with `pf.solve_ac`. Costs cross as `poly_cost` for degree ≤ 2 and as
  `pwl_cost` for piecewise (offset reported as dropped); degree > 2 and bids are dropped and reported
  (S2).
- **W3 — PyPSA export.** `io.pypsa.to_network(net) -> pypsa.Network` and `to_network_with_report`.
  Lines in ohm/siemens, transformers as `model="pi"` with `x` on `s_nom`, `tap_ratio`,
  `phase_shift`; generators with `p_nom`, `p_min_pu`, `marginal_cost` (+ `marginal_cost_quadratic`
  for degree 2); loads as `p_set`; `p_set` is **never** set on generators (it pins dispatch). PyPSA
  `optimize()` on the exported network agrees with `opf.solve_dc_opf` on networks whose costs it can
  express. Piecewise, degree > 2, bids, zones, generator Q limits: dropped and reported (S2, A4).
- **W4 — PSS/E RAW v33 import.** `io.psse_raw.load / loads / load_with_report`. Reads case
  identification, bus, load, fixed shunt, generator, non-transformer branch, two-winding
  transformer (four-line records; CZ/CW/CM codes converted as MATPOWER's `psse_convert_xfmr`
  does), area, zone; ignores three-winding transformers, switched shunts, owners and every later
  section **with a report entry per ignored record**. Ids: bus number as text; branch `from-to-ckt`
  (T3). No cost section exists in RAW: the imported `Network` carries no generator costs and the
  report says so (A3).
- **W5 — CSV bundle.** `io.csv_bundle.dump(net, dir) / load(dir)`: `manifest.json` (schema
  version, `base_mva`, table list) plus one CSV per entity table with the model's field names as
  headers; costs and bids as long-format side tables keyed by owner id; empty cell = `None`, ids as
  text, floats via `repr`. `load(dump(net)) == net` for every bundled fixture and every schema
  fixture, **bit-exact** on every float (D3, T6).
- **W6 — `Branch.kind`.** `Branch` gains `kind: Literal["line", "transformer"]`, defaulted at
  construction to `"transformer"` iff `tap_ratio not in (None, 1.0)` or `shift_deg not in (None, 0.0)`,
  else `"line"`; importers set it from the source table; exporters route on it. The JSON schema
  snapshot moves once; no existing fixture, test or example changes (S1, A7).
- **W7 — reports.** `io.report.ExportReport` mirrors `ImportReport` (issue shape, codes, `warnings`,
  `raise_on_error`), and both importers and exporters of this wave populate one (D1, T1). A
  conversion that drops or repairs anything is observable from the report alone.
- **W8 — docs.** `docs/manual/formats.md` gains a section per format in `io.matpower`'s shape
  (sections read, derived ids, column maps, warnings, errors, limitations, example); API pages for
  the four modules and `ExportReport` under the per-model griffe guard; a runnable example
  (`examples/13_interop.py`) embedded in `docs/examples/index.md`; changelog; `mkdocs build --strict`
  exit 0.

## Not doing

Format-to-format conversion; PyPSA import; RAW export; MATPOWER export; a human-editable CSV
dialect; reading pandapower/PyPSA results tables; any change to what the solvers compute (a solver
consuming `Branch.kind` is a later wave); `jobs` kinds for formats (T2); three-winding transformers,
switched shunts, DC lines, FACTS in RAW; time series in PyPSA; any model widening beyond W6.

## Prior art

`io.matpower` (M1) for the importer shape and `ImportReport`; `tests/parity/test_opf_vs_pypsa.py`
(M3) and `tests/parity/test_ac_vs_pandapower.py` (M2) for the mappings the exporters promote;
pandapower `to_json`/`from_json` and PyPSA `export_to_csv_folder` as the conventions imitated;
MATPOWER `psse_convert.m` / `psse_convert_xfmr.m` and grg-pssedata's `struct.py` (BSD-3) for the RAW
v33 record layouts (the PSS/E manual is proprietary).

## Acceptance criteria

- **AC-1** — pandapower JSON import: for pandapower's own `case14` and `case30`
  (`pp.networks.case14()` → `to_json` → `io.pandapower_json.loads`), the `Network` agrees with
  `io.matpower.load(fixtures/case14.m)` on every bus base kV, branch `r/x/b`, `tap_ratio`,
  `shift_deg`, generator limits and cost coefficients to `1e-9`, except the fields the research
  names as pandapower's own deviations (`vn_kv` 135/14/0.208 vs the BASE_KV=0 repair), which are
  listed in the test; a multi-`ext_grid` case yields one slack and a repair warning; every dropped
  column appears in the report.
  provenance: epic R11; user 2026-08-30 "Best effort + report"; `m8-research.md` §1
- **AC-2** — pandapower JSON export: `pp.from_json(dumps(net))` succeeds for every bundled fixture;
  on case14/30/57, pandapower `rundcpp` matches `pf.solve_dc` bus angles and branch flows to
  `1e-6`, and `runpp` matches `pf.solve_ac` voltages to `1e-6` pu; `pp.toolbox.nets_equal(from_json(dumps(loads(to_json(pn)))), pn)`
  on the entity tables the model carries (A6); dropped costs appear in the `ExportReport`.
  provenance: epic R11; user 2026-08-30 "Drop + report"; `m8-research.md` §1
- **AC-3** — PyPSA export: on case14/30/118 with polynomial costs of degree ≤ 2, PyPSA `optimize()`
  on `to_network(net)` agrees with `opf.solve_dc_opf` on objective (`1e-8` relative) and dispatch
  (`1e-4` MW), extending M3's parity tolerances; a piecewise-cost network exports with those units
  at `marginal_cost` 0 and each named in the `ExportReport`; no generator carries `p_set`.
  provenance: epic R11; user 2026-08-30 "Drop + report"; `m8-research.md` §2; M3 spec AC-3
- **AC-4** — PSS/E RAW v33 import: `io.psse_raw.load(fixtures/case14_v33.raw)` equals
  `io.matpower.load(fixtures/case14.m)` on every bus, branch (`kind` included), generator limits and
  load field to `1e-9`, with costs absent and the report saying so; the synthetic quirks fixture
  (CZ=2/3, CW=2/3, CM=2, continuation, two circuits between one bus pair) imports to hand-derived
  values; a file with a three-winding transformer imports with one report entry per ignored record.
  provenance: epic R11; user 2026-08-30 "Hand-author from case14.m"; `m8-research.md` §3
- **AC-5** — CSV bundle: `load(dump(net))` is `==` on the model and `array_equal` on every
  `NetworkArrays` matrix for all six MATPOWER fixtures, `tests/_agents.py`'s three networks and the
  schema fixtures; a bundle with a hand-edited unknown column, a missing table and a duplicated id
  each fail with a named `ImportReport` error; `manifest.json` names the schema version.
  provenance: epic R11; user 2026-08-30 "Machine round-trip"; `m8-research.md` §4
- **AC-6** — `Branch.kind`: constructing a `Branch` with no `kind` yields `"line"` at nominal tap
  and `"transformer"` otherwise; the schema snapshot changes by exactly that one property; every
  pre-M8 test passes unmodified; pandapower's case14 neutral-tap transformer imports as
  `"transformer"` and round-trips as one (A7).
  provenance: user 2026-08-30 "Explicit kind, defaulted"; `m8-research.md` G4
- **AC-7** — reports: for each of the four modules, a conversion that drops something produces a
  report whose issues name the element id and the field; a lossless conversion produces an empty
  report; `raise_on_error` behaves as `ImportReport`'s; no importer or exporter of this wave logs or
  prints — the report is the only channel.
  provenance: user 2026-08-30 "Best effort + report"; M1 `io.report`
- **AC-8** — docs: the four formats sections, API pages rendering every new function and
  `ExportReport`'s fields under the per-model griffe guard, `examples/13_interop.py` running
  exit 0 and embedded, changelog entry, `mkdocs build --strict` exit 0.
  provenance: epic R14; M6/M7 docs rows

## Design

### Domain model

- **`Network` is the pivot.** Every format is `import → Network → export`; no second intermediate.
  Invariant: importing then exporting through any format never changes what `pf.*`, `opf.*` or
  `market.*` compute on the `Network` — the oracles (pandapower, PyPSA) run the *converted* network
  and are compared with mambo running the *original*.
- **`Branch.kind`** (`line | transformer`), defaulted from `tap_ratio`/`shift_deg` at construction.
  Invariant: `kind == "transformer"` whenever tap or shift is non-nominal; a nominal-tap transformer
  is representable only because the field is explicit (S1).
- **`ExportReport`** mirrors `ImportReport`: a list of issues with code, element id, field,
  message; `warnings` for repairs; `errors` that `raise_on_error` raises. Invariant: an empty report
  means lossless.
- **Fidelity classes** (`m8-scope.md`): lossless target (pandapower JSON on the entities the model
  carries; CSV by construction), lossy by nature (PyPSA — no piecewise/bids/zones; RAW — no costs).

### Component boundaries and interfaces

| module | owns | crosses in | crosses out |
|---|---|---|---|
| `io.pandapower_json` | pandapower table ↔ `Network` maps, `ext_grid` rule, unit conversions | JSON text / `pandapowerNet` | `Network` + `ImportReport`; text + `ExportReport` |
| `io.pypsa` | `Network` → `pypsa.Network` map; what is dropped | `Network` | `pypsa.Network` + `ExportReport` |
| `io.psse_raw` | v33 record parser, CZ/CW/CM conversion, id scheme | RAW text | `Network` + `ImportReport` |
| `io.csv_bundle` | manifest + per-table CSV codec, side tables for costs/bids | directory | `Network` + `ImportReport`; directory |
| `io.report` | `ImportReport` (existing), `ExportReport` (new) | — | — |
| `model.entities` | `Branch.kind` (W6) | — | schema snapshot |

pandapower and PyPSA are imported inside `io.pandapower_json` / `io.pypsa` only, lazily, so the
core package keeps its zero-optional-dependency import (they remain dev/extras deps — R9).

### Ownership table

| concept | owning module (SSoT) | rendering surfaces | agreement test |
|---|---|---|---|
| per-unit ↔ physical conversions | `io.pandapower_json` (documented in `formats.md`) | pandapower import, pandapower export | AC-1/AC-2 round-trip on case14 (`nets_equal`) |
| transformer-ness of a branch | `model.Branch.kind` | pandapower `trafo`, PyPSA `Transformer`, RAW transformer records, CSV `kind` column | AC-6 + AC-4 (`kind` equality vs `.m`) |
| what a format cannot carry | each `io.*` module's report | `ExportReport`/`ImportReport`, `formats.md` limitations | AC-7 (drop ⇒ report entry) + a docs test that each module's documented limitation list equals its report codes |
| RAW v33 record layout | `io.psse_raw` | parser, `formats.md` column map | AC-4 quirks fixture with hand-derived values |
| CSV bundle schema | `io.csv_bundle` + `manifest.json` version | dump, load, `formats.md` | AC-5 bit-exact round-trip |

### Rejected alternatives

Inference-only `Branch.kind` (neutral-tap transformer imports as a line); required `kind` (every
`Branch(...)` in the tree changes); cost approximation on export (moves the optimum by an unbounded
amount, silently); refuse-on-lossy (contradicts D1); the wild IEEE-14 RAW (licence undetected);
PyPSA import (time series, components with no home); RAW export; a human CSV dialect; `jobs` kinds
for formats (M4: requests carry a `Network`); converting via pandapower's `from_ppc` (yields
`vn_kv = 0` on case14 and `to_ppc` raises `FloatingPointError` — measured).

### Assumptions

- **A1** — pandapower 3.3.0 / PyPSA 1.2.4 / linopy 0.9.1 are the targets; drift is recorded, not
  shimmed.
- **A2** — the schema snapshot moves exactly once, for `Branch.kind`.
- **A3** — RAW carries no costs: an imported RAW network flows; `opf` on it is the caller's mistake
  (no costs) and is reported by the existing validation, not by the importer inventing costs.
- **A4** — PyPSA cannot express piecewise costs, degree > 2, demand bids, zones, generator Q limits
  (measured on 1.2.4).
- **A5** — CSV is machine-facing; `repr` floats round-trip bit-exactly through Python's `float()`.
- **A6** — `pp.toolbox.nets_equal` holds for our export re-imported on the tables the model
  carries (true on pandapower's own cases; to be proved on ours — at risk).
- **A7** — a neutral-tap transformer exists in pandapower's case14 (tap 1.0 measured), so S1's
  default is exercised in both directions.
- **A8** — HiGHS via linopy is available on all three CI runners for AC-3 (M3's parity already
  runs PyPSA optimize in CI).
