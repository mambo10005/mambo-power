# M8 "interop" — independent audit at `7ec0b0b`

Auditor: m8-audit (Fable 5), 2026-08-29/30. Rigor: audited. Scope: falsify "requirements implemented
**and proven**", per criterion AC-1…AC-8 of `wave-08-interop.spec.md`, plus one wave-level coverage
verdict. Not a code review (the critic's job).

**Head and isolation.** `7ec0b0b` ("docs(m8): architecture — market.agents is shipped (M7), not a
later wave"), branch `wave/08-interop`, base `cdb4fef`. Two `git archive` copies under the session
scratchpad: `m8-audit-7ec0b0b` (read-only) and `m8-sabotage-7ec0b0b`. `mambo_power.__file__`
proven for each: `…\scratchpad\m8-audit-7ec0b0b\src\mambo_power\__init__.py` and
`…\scratchpad\m8-sabotage-7ec0b0b\src\mambo_power\__init__.py` (via `uv run --project <dir>`). No
command ran in `mambo-power` or `mambo-power-m8`. Slice reports (`m8-s*-report.md`) not read.
Pins measured in the archive env: pandapower 3.3.0, PyPSA 1.2.4, linopy 0.9.1, highspy present (A1, A8).

**Stack health (archive, full suite):** `1 failed, 1429 passed, 4 skipped in 1137 s` — the one
failure is `tests/unit/test_examples_run.py::test_example_runs_to_completion[13_interop]`
(`subprocess.TimeoutExpired`, 60 s budget). See Finding 1: the example itself exits 0 (13/13
examples exit 0 standalone); it runs 33–41 s in isolation, and my run overlapped a `mkdocs build`
and the sabotage series. Every named M8 test file is green in isolation (tails below).

**Pre-M8 tests unmodified:** `git diff --stat cdb4fef 7ec0b0b -- tests` touches only the nine new
files and the schema snapshot. (`test_market_strategy.py` / `test_opf_overlap_guard.py` in the
diff against `473b718` come from the epic merge, not this wave.)

Tier evidence re-executed: T2 (AC-1/2/3 parity through real pandapower/PyPSA), T1 (unit files),
T0 (`mkdocs build --strict`, examples).

---

## AC-1 — pandapower JSON import — DISCHARGED

> for pandapower's own `case14` and `case30` … the `Network` agrees with `io.matpower.load` on every
> bus base kV, branch `r/x/b`, `tap_ratio`, `shift_deg`, generator limits and cost coefficients to
> `1e-9`, except the fields the research names as pandapower's own deviations … which are listed in
> the test; a multi-`ext_grid` case yields one slack and a repair warning; every dropped column
> appears in the report.

Named tests: `tests/unit/test_io_pandapower_json.py` (T2; fixture-fidelity declared in the plan:
real `pp.networks.case14()/case30()` against `fixtures/matpower/case14.m|case30.m`).
Run: `20 passed in 99.35s`.

Not on trust: `KNOWN_DEVIATIONS` entries are asserted **present**, not tolerated —
`test_buses_match_matpower_except_listed_base_kv` asserts `theirs.base_kv == DEFAULT_BASE_KV` for
every listed bus; `test_branches_match_matpower_to_1e9` asserts `theirs.kind != kinds[...]` and
`theirs.rating_mva is None`; the cost row asserts the deviation exceeds TOL; case30 zones assert
`theirs.zone != zones[...]`. A deviation that vanished would fail.

Sabotage (moves only `tap_ratio`): `pandapower_json.py` factor `1.0 + (pos − neutral)·step/100` →
`1.0 − …`. Result: `test_branches_match_matpower_to_1e9[case14]` and
`test_shunt_sign_and_tap_conversion` FAILED (`2 failed, 1 passed`); restored, `diff` vs archive
identical. Had the tap conversion been absent the case14 taps 0.978/0.969/0.932 would read 1.022/…
and the 1e-9 comparison fails — a positive readback.

Multi-ext_grid: `test_second_ext_grid_becomes_pv_generator_with_one_repair_warning` asserts
`["slack","pv"]` and exactly `["EXTRA_EXT_GRID_DEMOTED"]` naming element `second`, bus `b`.
Dropped columns: `test_dropped_columns_are_reported_with_element_and_field` asserts element id and
field name in the message for `g_us_per_km`, `const_z_p_percent`, `switch[0]`.

## AC-2 — pandapower JSON export — DISCHARGED

> `pp.from_json(dumps(net))` succeeds for every bundled fixture; on case14/30/57 `rundcpp` matches
> `pf.solve_dc` … to `1e-6`, `runpp` matches `pf.solve_ac` voltages to `1e-6` pu; every value column
> survives … to 1e-12 relative on pandapower's case14/case30, and the set of tables on which strict
> `nets_equal` holds is pinned as measured (amended F2: `poly_cost`/`pwl_cost` only); dropped costs
> appear in the `ExportReport`.

Named tests: `tests/parity/test_pandapower_json_vs_pandapower.py` (T2; fixture-fidelity: the six
MATPOWER cases exported by this wave and solved by pandapower 3.3.0) and
`test_export_reports_every_drop_by_element_and_field` (unit). Parity file ran green inside the full
suite (all 24 items; no failures listed) and 2 of its tests passed in the sabotage baseline run.

Independent recomputation (own script, not the test's helpers): case57 DC worst angle diff
`1.31e-13°`, AC worst |Δvm| `2.44e-15` pu. **Power check:** scaling `line[0].x` by 1.5 in the
exported net moves the AC vm diff to `2.64e-4` ≫ 1e-6 — the oracle sees mapping errors.
`nets_equal` set reproduced on both case14 and case30: `{'poly_cost','pwl_cost'}`; the value
tables differ on `name`, `zone` dtype, `geo`, `type`, `max_loading_percent`, `tap_phase_shifter`
and ULP noise (max rel diff `1.0e-15` on `trafo.tap_step_percent`, `1.5e-16` on
`line.r/x_ohm_per_km`) — never a value beyond 1e-12. F2 as stated is what the data shows.

Sabotage (moves only exported `x`): `x_ohm_per_km=br.x*zb` → `*1.001`. `8 failed, 2 passed`:
`dc_angles`/`ac_voltages` on all three cases and `carried_values_survive_the_round_trip` on
case14/case30 FAILED; `test_nets_equal_round_trip_measured` stayed **green** (the pinned set is
cost-tables-only, so it cannot see a value corruption — the 1e-12 value test is the one carrying
that half of the criterion; see Finding 4, note). Restored, identical.

## AC-3 — PyPSA export — DISCHARGED

> on case14/30/118 with polynomial costs of degree ≤ 2, PyPSA `optimize()` on `to_network(net)`
> agrees with `opf.solve_dc_opf` on objective (`1e-8` relative) and dispatch (`1e-4` MW on
> case14/case30; `2e-3` MW on case118 — amended F3 …); a piecewise-cost network exports with those
> units at `marginal_cost` 0 and each named in the `ExportReport`; no generator carries `p_set`.

Named tests: `tests/parity/test_pypsa_export_vs_pypsa.py` (T2; fixture-fidelity: bundled MATPOWER
cases solved by PyPSA 1.2.4/linopy 0.9.1/HiGHS) and `tests/unit/test_io_pypsa.py` (`19 passed in
60.27s`). Parity file green in the full suite; `1 passed` baseline items in the sabotage run.

Independent recomputation of F3 (own script): PyPSA `('ok','optimal')`; worst dispatch diff
**`gen-5  1.86675e-3 MW`** (spec says 1.87e-3); both dispatches sum to 4242.0 MW; evaluating the
**exact polynomial** at both points: ours `125947.8814178661`, PyPSA `125947.8814180257`, ours −
PyPSA = **`−1.596e-7 $/h`** — mambo's point is cheaper, so the residual is the oracle's early stop,
not the mapping. `p_set` all NaN. F3 confirmed and correctly attributed.

Sabotage (moves only the quadratic cost term): `marginal_cost_quadratic=c2` → zeros.
`6 failed, 1 passed`: objective and dispatch FAILED on case30 and case118 (case14's polynomial
costs are effectively linear under merit order, so only its objective/dispatch of the linear part
survives — the pass is `test_objective_matches[case14]`, consistent with case14's c2 being small).
Restored, identical. Piecewise: `test_piecewise_costs_export_at_zero_and_are_named` asserts
`marginal_cost == 0.0` and the `PYPSA_PWL_COST_DROPPED` ids equal the piecewise ids.

## AC-4 — PSS/E RAW v33 import — DISCHARGED

> `load(fixtures/case14_v33.raw)` equals `io.matpower.load(case14.m)` on every bus, branch (`kind`
> included), generator limits and load field to `1e-9`, with costs absent and the report saying so;
> the synthetic quirks fixture (CZ=2/3, CW=2/3, CM=2, continuation, two circuits) imports to
> hand-derived values; a three-winding file imports with one report entry per ignored record.

Named tests: `tests/unit/test_io_psse_raw.py` — `26 passed in 0.88s` (T1).

Hand derivation from `fixtures/PROVENANCE-raw.md` re-done numerically, independent of the parser:
T1 (CZ=2/CW=2/CM=2): factor `(138/138)²·100/50 = 2` → r `0.01`, x `0.16`; taps `144.9/138 = 1.05`,
`13.8/13.8 = 1`; magnetising `G_w = 4e-4`, `B_w = −sqrt(0.02² − G_w²)`, ÷factor ×100 →
`g 0.02 MW`, `b −0.9997999799959989 MVAr`. T2 (CZ=3/CW=3): `R_w = 1e4/(1e6·25) = 4e-4`,
`X_w = sqrt(0.12² − R_w²)`, factor `(14.49/13.8)²·100/25 = 4.41` → r `0.001764`,
x `0.5291970599918333`, tap `0.98·14.49/13.8 = 1.029`. ZIP load at VM 0.95 → `67.55 / 15.51`.
All equal the test's expected constants and match MATPOWER's `psse_convert_xfmr` semantics
(winding base `NOMV1²/SBASE1-2` over system base `BASKV_I²/SBASE`; CW=3 = pu of `NOMV`; CM=2 =
W and exciting current on the winding base; magnetising admittance scaled by 1/factor). Parser
lines `psse_raw.py:553-617` implement exactly this. Neutral-tap T3 imports `kind="transformer"`
from the record type (`test_quirks_neutral_tap_transformer_keeps_kind`).

Sabotage 1 (moves only the CZ impedance factor): drop the `**2` in `factor`. Only
`test_quirks_transformer_cw3_cz3` FAILED (`r=0.00168`), `cw2_cz2` passed — expected, since T1 has
`NOMV1 = BASKV`. Sabotage 2 (moves only `kind`): remove `kind="transformer"` from the transformer
record → `test_quirks_neutral_tap_transformer_keeps_kind` FAILED (T1/T2 still infer transformer
from their taps; T3 is the only witness — and it exists). Both restored, identical.
Three-winding: two records → exactly 2 `RAW_THREE_WINDING_IGNORED` entries with bus ids.

## AC-5 — CSV bundle — DISCHARGED

> `load(dump(net))` is `==` on the model and `array_equal` on every `NetworkArrays` matrix for all
> six MATPOWER fixtures, `tests/_agents.py`'s three networks and the schema fixtures; hand-edited
> unknown column, missing table and duplicated id each fail with a named `ImportReport` error;
> `manifest.json` names the schema version.

Named tests: `tests/unit/test_io_csv_bundle.py` — `56 passed in 18.04s` (T1). `NETWORKS` covers
the six MATPOWER cases, the three agents networks and five schema fixtures; `_errors()` checks each
code is in `ImportIssueCode` and `csv_bundle.CODES`; manifest test pins `schema_version`.

Independent construction (own network: ids `"01"`, `"1"`, `""`; `0.1+0.2`, `5e-324`, `1/3`,
`1e300`, `2.2250738585072014e-308`, `-0.0` in `vm_pu` and `q_mvar`, a nominal-tap
`kind="transformer"`): `load(dump(net)) == net` True; per-field `struct.pack('<d')` byte
equality True on all eight probed floats; ids come back `['01','1','']`; kinds
`['line','transformer']`; **`-0.0` sign preserved** (which `==` alone would not have shown).

Sabotage (moves only the float codec): `repr(float(value))` → `format(value, ".12g")`.
`3 failed`: identity and array-equal on `schema_piecewise_bid_numeric_ids` and
`test_cells_are_repr_floats…` FAILED; the other 53 items were deselected. Restored, identical.

## AC-6 — `Branch.kind` — DISCHARGED

> constructing a `Branch` with no `kind` yields `"line"` at nominal tap and `"transformer"`
> otherwise; the schema snapshot changes by exactly that one property; every pre-M8 test passes
> unmodified; pandapower's case14 neutral-tap transformer imports as `"transformer"` and round-trips
> as one (A7).

Named tests: `tests/unit/test_branch_kind.py` `15 passed`, `tests/unit/test_json_schema_snapshot.py`
`3 passed`, `test_neutral_tap_transformer_routes_on_kind` (pypsa unit), `test_branches_match…`
(pandapower unit, `KNOWN_DEVIATIONS["case14"]["kind"]`).

Snapshot: `git diff cdb4fef 7ec0b0b -- tests/unit/snapshots/network.schema.json` is one hunk
adding the `kind` property (`default "line"`, enum) — nothing else. Pre-M8 tests: unmodified (see
header) and green in the full suite except the example-13 timeout (Finding 1, not a `kind` matter).

Independent check (own script): pandapower's case14 has five `trafo` rows, two with
`tap_pos = NaN` (7-8, 7-9); they import as `trafo-3`/`trafo-4` with `tap_ratio None`,
`kind "transformer"`; after `loads(dumps(net))` both are still `transformer`, and the re-export
has 5 `trafo` / 15 `line` rows. A7 holds.

Revert-and-watch (the wave's one named revert): `_default_kind` reverted to always `"line"`.
`5 failed, 15 passed`: `test_default_is_transformer_off_nominal[fields1..3]`,
`test_branches_match_matpower_to_1e9[case14]` and one more went red; the snapshot test stayed
green (the schema text does not encode the validator — expected). Restored, identical.

## AC-7 — reports — DISCHARGED

> for each of the four modules, a conversion that drops something produces a report whose issues
> name the element id and the field; a lossless conversion produces an empty report;
> `raise_on_error` behaves as `ImportReport`'s; no importer or exporter of this wave logs or prints.

Named tests: `test_export_report.py` `8 passed`; `test_io_limitations.py` `72 passed`; the
per-module drop tests (`test_export_reports_every_drop_by_element_and_field`,
`test_report_names_q_limits_and_zone_only_on_the_hand_network`, `test_quirks_*`,
`test_*_is_a_named_error`) and the lossless tests
(`test_lossless_network_exports_with_an_empty_report_and_round_trips`,
`test_empty_report_when_nothing_is_lost`, `test_load_with_report_is_empty_on_a_clean_bundle`,
`test_import_report_is_empty_on_pandapowers_own_cases`).

Independent (own script, stdout/stderr redirected, root logger at DEBUG with a capturing handler,
`warnings` recorded): pandapower export of the 2-bus lossless net → `[]`; re-import of case14's
export → `[]`; PyPSA lossless net → `[]`; CSV `full_network()` → `[]`; case14 PyPSA export → the
expected `PYPSA_GEN_Q_LIMITS_DROPPED` rows; quirks RAW → 7 warnings. **STDOUT `''`, STDERR `''`,
zero log records from any `mambo*` logger, zero warnings raised from `mambo_power` files.** (34
records arrived from `pypsa.network.transform`, `matplotlib`, `numexpr` — third-party, not this
wave's modules.) Registry: each module's `CODES` equals `LIMITATIONS[module]` exactly, and every
code literal emitted in each module's source is in its `CODES` (A18's union check, redone).

Sabotage 1 (moves only the RAW cost report): `RAW_NO_COSTS` warning gated off →
`test_case14_generators_equal_and_costless` and `test_case14_report_is_only_base_kv_and_costs`
FAILED. Sabotage 2 (moves only one drop entry): the trafo `b` `FIELD_DROPPED` removed →
`test_export_reports_every_drop_by_element_and_field` FAILED. Both restored, identical.
`raise_on_error`: `test_raise_on_error_raises_only_for_errors` parametrised over both classes,
`match=` on the code and message, `info.value.report is r`.

## AC-8 — docs — DISCHARGED (with Finding 1 attached)

> the four formats sections, API pages rendering every new function and `ExportReport`'s fields
> under the per-model griffe guard, `examples/13_interop.py` running exit 0 and embedded, changelog
> entry, `mkdocs build --strict` exit 0.

T0 re-executed from the archive: `uv run --group docs mkdocs build --strict` → **exit 0**
(`pydantic_fields: documented 249 field(s)`; the only "warning" line is the Material team banner,
not a build warning). All 13 `examples/*.py` → exit 0 each (`13_interop` output shows the RAW vs
MATPOWER `solve_dc` diff `0.0`, `load(dump(net)) == net: True`, the `PYPSA_PWL_COST_DROPPED`
entry). `docs/manual/formats.md` has `## pandapower JSON`, `## PyPSA export`,
`## PSS/E RAW v33 importer`, `## CSV bundle`, each with read/ids/map/warnings/errors/limitations/
example subsections. Rendered `site/api/*`: `io-report` names `ExportReport` (10×), `warnings`,
`raise_on_error`; `io-pandapower-json` has `dumps_with_report`/`load_with_report`; `io-pypsa`
`to_network_with_report`; `io-psse-raw` `load_with_report`; `io-csv-bundle` `dump`/
`load_with_report`. `docs/examples/index.md:174` embeds `--8<-- "examples/13_interop.py"`;
`docs/changelog.md:14` `### Added — wave M8 (interop)`.

Sabotage (moves only the docs' code list): rename one code in `formats.md` →
`test_every_registered_code_is_documented[io.psse_raw-RAW_XFMR_MAGNETISING_FOLDED]` FAILED,
34 passed. Restored, identical.

---

## Findings

1. **should-fix — `examples/13_interop.py` sits at 55–70 % of the examples test's 60 s budget and
   timed out in the archive's full-suite run.** `tests/unit/test_examples_run.py:24`
   (`BUDGET_S = 60.0  # each script is ~1 s locally`) — the comment is false for this script.
   Repro: `python examples/13_interop.py` alone: 33 s, 41 s (two runs); `12_agent_market.py`:
   2 s. In the full run (`full-run.txt`, with a concurrent `mkdocs build`)
   `test_example_runs_to_completion[13_interop]` raised `TimeoutExpired`. AC-8's "exit 0" holds;
   the suite's own guard for it is flaky under load, i.e. the green that certifies AC-8 in CI can
   go red for no code reason (or hide a real hang behind a raised budget). Fix at the layer it
   lives: either make the script cheap (it imports pandapower **and** PyPSA and runs an
   `optimize()`; the cost is import + HiGHS, not mambo) or give the examples test a per-script
   budget with the measured figure recorded — not a blanket raise.
2. **should-fix — the plan's `## Verification Matrix` is entirely `(pending)` at the audited
   head.** `wave-08-interop.plan.md:72-135`: every `tier-run`/`readback` is `(pending)`,
   `stack-health: PENDING`, `auditor` column empty. The evidence exists (this audit re-ran it) but
   the artefact the merge gate reads does not carry it. Fill each row with the command, the tail,
   and the readback before Step 6 signs.
3. **note — `test_carried_values_survive_the_round_trip` skips columns silently.**
   `tests/parity/test_pandapower_json_vs_pandapower.py:225-226` `if col not in a.columns: continue`
   — a column that disappears from pandapower's own table (version drift) is skipped rather than
   reported, and nothing asserts that at least one column per table was compared. Add a
   `compared` counter and assert it per table.
4. **note — the pinned `nets_equal` set is powerless against value drift.** By construction
   `NETS_EQUAL_HOLDS_ON = {poly_cost, pwl_cost}` cannot move when a value column is corrupted
   (shown by the AC-2 sabotage: it stayed green while `carried_values` reddened). That is fine
   because the value test exists, but the docstring's "so any drift is visible" oversells it: it
   sees drift in pandapower's *default-column set*, not in values. Reword.
5. **note — `pytest.raises(ValueError)` without `match`.** `tests/unit/test_branch_kind.py:77`
   (`test_unknown_kind_is_rejected`). The other bare `raises` in the new files bind `as info` and
   assert `.code` after, which is fine.
6. **note — third-party logging during `io.pypsa.to_network`.** PyPSA's `pypsa.network.transform`
   logger emits records on every `add()`; mambo's modules emit none (AC-7 holds as written), but a
   caller with a root handler will see PyPSA's chatter. Worth one sentence in `formats.md`'s PyPSA
   limitations so it is not mistaken for the exporter printing.
7. **note — `test_io_limitations` is one-directional.** It proves every registered code is
   documented, not that every documented `` `CODE` `` in `formats.md` is registered (a stale
   documented code would survive). The design's ownership table promises "documented limitation
   list equals its report codes"; the union check I ran (each module's `CODES` == registry, and ==
   codes emitted in source) closes the module side; the docs side is still open in one direction.

No blocking findings.

## Overall

**Criteria: 8 DISCHARGED, 0 PARTIAL, 0 REFUTED.** Findings: 0 blocking, 2 should-fix, 5 notes.

**Wave-level coverage verdict: COVERED, with the amendments F2/F3 recorded truthfully.**
Walked whole: epic R11 → W1…W5 → AC-1…AC-5 (each AC cites R11 and a dated user ruling and a
research section); user ruling "Explicit kind, defaulted" → W6 → AC-6; ruling "Best effort +
report" + M1 `io.report` → W7 → AC-7; epic R14 → W8 → AC-8. Inverting: every W has exactly one
AC; every AC has at least one inbound provenance; the design's ownership table cites AC-1/2/4/5/6/7
and each cited AC exists and is discharged above; design assumptions A1 (versions), A2 (one snapshot
move), A3 (RAW costless), A4 (PyPSA drops), A5 (`repr` bit-exact), A7 (neutral-tap in case14), A8
(HiGHS) were each re-observed here; A6 is amended to what was measured and the measurement is
reproduced. No requirement without an inbound citation; no criterion without evidence I re-ran.
Two amendments (AC-2 `nets_equal` set, AC-3 case118 `2e-3`) are stated inline in the spec and both
reproduce independently — they are honest narrowings, not tolerances hiding a defect.

Evidence files (scratchpad): `full-run.txt`, `mkdocs.txt`, `ex-*.txt`, `sabotage.txt`,
`sabotage2.txt`, `probe/*.py`, `probe/sabotage*.sh`.

---

## Re-audit at e2d6da8

Auditor: m8-audit (Fable 5), 2026-08-30. Same rigor and method as above; every row re-discharged
at the new head with my own sabotage or recomputation, and each of the S7/S8 fixes checked against
the walk/critic finding that motivated it.

**Head and isolation.** `e2d6da8` ("fix(m8): critic nits 13-15 …"), `wave/08-interop`, 19 commits
after `7ec0b0b` (S7 walk fixes `3f2a9a0..a78db18`, S8 critic fixes `36e8398..e2d6da8`). Two fresh
`git archive` copies under the session scratchpad, `m8-audit-e2d6da8` (read-only) and
`m8-sabotage-e2d6da8`; `mambo_power.__file__` proven for each
(`…\scratchpad\m8-audit-e2d6da8\src\mambo_power\__init__.py`,
`…\scratchpad\m8-sabotage-e2d6da8\src\mambo_power\__init__.py`). The 7ec0b0b per-row exporter was
run once from the surviving `m8-audit-7ec0b0b` archive to produce a reference file. Nothing ran in
`mambo-power` or `mambo-power-m8`. Slice reports not read; walk and critic read for their findings.
Pins: pandapower 3.3.0, PyPSA 1.2.4.

**Stack health (archive, full suite):** `1494 passed, 4 skipped, 10 warnings in 269.10s`, exit 0
(`full-run-e2d6da8.txt`). No example-13 timeout: the script now runs in 8.8 s wall here under a
per-script 240 s budget (`test_examples_run.py:28`) — the first audit's should-fix 1 is resolved as
asked (per-script, measured, not a blanket raise). `mkdocs build --strict` exit 0
(`mkdocs-e2d6da8.txt`, 249 fields documented). Four skips are the pre-existing zonal-parity ones.

**Pre-M8 tests:** `git diff --stat cdb4fef e2d6da8 -- tests` touches the nine new files, the schema
snapshot (one property, description text re-worded at `738dcf8`), `test_examples_run.py` (budget),
and two pre-M8 files: `test_jobs.py` (+1 parametrised test, additive) and
`test_opf_solve_dc_opf.py`, where the pre-M8 `test_solve_dc_opf_treats_a_costless_generator_as_free`
is **renamed and inverted** to `test_solve_dc_opf_refuses_a_costless_generator`. See Finding 1.

### AC-1 — pandapower JSON import — DISCHARGED

Named tests green in the full run (`test_io_pandapower_json.py`, now 45 items). Fix check (critic 2,
`tap_changer_type`): my own 110/20 kV two-bus pandapower net, `tap_pos=2`, `tap_step_percent=2.5`,
`tap_side=hv`, run through `runpp` and read back from `net._ppc["branch"][:,8:10]` against the
imported `Branch`:

| changer | `_ppc` tap / shift | mambo `tap_ratio` / `shift_deg` | `vm_lv` pp / mambo | report |
|---|---|---|---|---|
| `None` | 1.000000 / 0.000 | `None` / `None` | 0.992164 / 0.992164 | `COLUMN_DROPPED` naming `tap_pos=2 … tap_changer_type=None` |
| `Ratio` | 1.050000 / 0.000 | 1.05 / `None` | 0.944114 / 0.944114 | — |
| `Symmetrical` (5°) | 1.049819 / 0.238 | 1.0498187795 / 0.2378348844 | 0.944280 / 0.944280 | — |
| `Ideal` (step 0, 5°) | 1.000000 / 10.000 | `None` / 10.0 | 0.992164 / 0.992164 | — |

The critic's silent 0.048 pu case (`None`) is gone and reported. `Ideal` with both step and degree
set is one pandapower's own `runpp` refuses (`UserWarning`); mambo imports it at nominal with
`TAP_CHANGER_TYPE_UNSUPPORTED`. Fix check (critic 6, `gen.slack=True`): no `ext_grid` + a
`slack=True` gen → bus types `['slack','pq']`, `vm_pu` 1.03 from `gen.vm_pu`, `GEN_SLACK_PROMOTED`,
`pf.solve_ac` vm `[1.03, 1.02992]` == `runpp`; with an out-of-service `ext_grid` the same; with a
live `ext_grid` the gen stays PV (`COLUMN_DROPPED` for `slack`); two `slack=True` gens → one slack,
one PV. Sabotage (moves only the `None` gate — `changer = "Ratio"` when `None`): `4 failed,
41 passed` — `test_tap_changer_type_matches_pandapowers_ppc[none-ignored|none-with-shift]`,
`test_tap_columns_without_a_changer_type_are_reported_dropped`,
`test_import_report_is_empty_on_pandapowers_own_cases[case14]`. Sabotage (gen.slack gate off):
`test_slack_gen_without_a_live_ext_grid_is_the_slack[None|off]` FAILED. Both restored, identical.

### AC-2 — pandapower JSON export — DISCHARGED

Independent recomputation (own script): DC worst |Δva| case14 `8.9e-15`°, case30 `1.8e-15`°,
case57 `1.3e-13`°; AC worst |Δvm| `2.1e-12`, `8.8e-11`, `2.1e-13` pu; `res_bus` rows in the export:
0 on all three. Fix check (critic 10, `res_bus`): grep of `pandapower_json.py` for `res_` gives
three hits — the docstring (`:11`), the import-side skip `name.startswith("res_")` (`:698`) and the
`_drop_bus_state` message (`:1051`); nothing reads or writes a results table. Behaviour: importing
`pp.networks.case14()` *after* `runpp` (14 `res_bus` rows) yields `vm_pu` `None` on every bus but
the slack (1.06, the `ext_grid` setpoint); exporting `case14.m` writes no `res_*` table and reports
`FIELD_DROPPED` for `vm_pu/va_deg` on the 13 non-slack buses (Finding 6). Fix check (critic 4,
bulk creators): `dumps(case300)` **0.28 s** (0.28 s repeat) vs **12.39 s** for the 7ec0b0b
exporter on this machine; `loads` 0.61 s. The 7ec0b0b file vs the e2d6da8 file, table by table:
same row counts, same column *sets*, `DataFrame.equals` **True on all ten tables**
(`bus, line, trafo, gen, sgen, ext_grid, load, shunt, poly_cost, pwl_cost`); `rundcpp` angles
identical (max diff 0.0). `pp.toolbox.nets_equal(old, new)` is **False**, for two reasons that are
both intended: column *order* differs on `bus`/`gen` (bulk creators put `max_*` before `min_*`) and
the old file carries `res_bus`. So "nets_equal to the per-row form" (plan S8 row) is literally false
against the previous exporter's file and true against the test's own per-row reference (which
writes no `res_bus`) — see Finding 2 for the test that pins it. Sabotage (`x_ohm_per_km` ×1.001):
`16 failed, 53 passed` across DC/AC angles, voltages, branch flows and `carried_values` on
case14/30/57. Restored, identical.

### AC-3 — PyPSA export — DISCHARGED

Independent recomputation: `('ok','optimal')` on all three; objective rel diff case14 `7.5e-14`,
case30 `8.8e-13`, case118 `1.3e-12`; worst dispatch `2.3e-5`, `8.4e-5`, **`1.867e-3` MW at gen-5**
(F3 reproduced to the digit); `p_set` all NaN. Fix check (critic 1, transformer `b`): own two-bus
110/20 kV case, `r=0.01 x=0.2 s_nom=40`, PyPSA `pf()` vs `pf.solve_ac`:

| `b` (pu, 100 MVA) | PyPSA `b` column | mambo vm_b | PyPSA vm_b | |Δvm| |
|---|---|---|---|---|
| 0.3 | 0.75 | 1.0179358926 | 1.0179358926 | 2.2e-16 |
| −0.2 | −0.5 | 0.9674524581 | 0.9674524581 | 2.2e-16 |
| 0.0 | 0 | 0.9870413907 | 0.9870413907 | 1.1e-16 |

The written column is `b × base_mva / s_nom` (0.3 × 100/40 = 0.75), the admittance direction; angles
agree to 1e-6°. Fix check (walk 4, unrated `s_nom`): case14 has 20 unrated branches → exactly 20
`PYPSA_UNRATED_S_NOM_DEFAULTED` entries whose `element_ids` equal the unrated ids; a fully rated copy
→ 0 entries and `s_nom` = the rating. Sabotage (`b / k` → `b * k`, the original bug): `2 failed,
37 passed` — `test_transformer_charging_b_matches_pypsa_ac_pf[-0.05|0.3]`. Sabotage (unrated report
gated off): `test_unrated_branches_are_reported_one_entry_each_naming_the_sentinel` and
`test_report_names_q_limits_and_zone_only_on_the_hand_network` FAILED. Both restored, identical.

### AC-4 — PSS/E RAW v33 import — DISCHARGED

`git diff 7ec0b0b e2d6da8 -- psse_raw.py` touches the docstring, `_SECTIONS`/terminator tables,
`_scan` (section naming) and the area-record report — not one line of the CZ/CW/CM conversion, so
the hand derivations above stand; `test_io_psse_raw.py` `29 passed`. Fix check (walk 5,
`UNTERMINATED_SECTION`): deleting `case14_v33.raw`'s bus terminator (line 18,
`0 / END OF BUS DATA, BEGIN LOAD DATA`) now gives `UNTERMINATED_SECTION: bus section is not
terminated by a '0' line: the '0' at line 29 ends the load section, so the records between were
read as bus records (line 29)` — the right section, and the line the parser gave up at; the walker
got "vsc dc … (line 31)". The location comes from the terminator comments (`_terminator_section`):
a hand-written file with bare `0` lines and the same deletion surfaces as `BAD_RECORD: generator
record has 15 fields … (line 11)` one section later (Finding 4). Costless: `RAW_NO_COSTS` still
emitted; the report now also carries `RAW_SECTION_IGNORED` for the area record (critic 13).
Sabotage (`_terminator_section` always `None`):
`test_unterminated_section_names_the_section_and_the_line_the_parser_gave_up_at` FAILED, 28 passed.
Restored, identical.

### AC-5 — CSV bundle — DISCHARGED

`csv_bundle.py` diff: docstring, `_blank_line`, `dump` staging, reader encoding — the float codec
and `_cell` are untouched, so the bit-exactness probe above stands; `test_io_csv_bundle.py`
`60 passed`. Fix checks (walk 6/7): on a case14 bundle, three trailing `\n` on `loads.csv` → loads
`== net`; a UTF-8 BOM on `buses.csv` → `== net`; a blank line and a whitespace-only line in the
middle of `branches.csv` → `== net`; a `,,,,,,,,,,` row is still a row (refused
`CSV_MANIFEST_INVALID … 21 rows`); the writer emits no BOM and no trailing blank row. Fix check
(critic 7, atomic dump): after a good `dump(case14, d)`, `dump(bad, d)` with a `""` zone name raises
`ValueError` and every byte of `d` is unchanged, no leftovers; with `_write_csv` made to raise
`OSError` on the third table, `d` is byte-unchanged, loads `== case14`, no stray staging dir in
`d` or beside it. Injecting a failure on the **fourth `os.replace`** of the move-in phase does leave
a mixed bundle (Finding 3). Sabotages, each restored identical: `utf-8-sig`→`utf-8` →
`test_a_utf8_bom_on_a_table_is_ignored` FAILED; blank-line skip removed →
`test_trailing_blank_lines_are_not_rows` FAILED; staging dir = target (old bundle wiped before
write) → `test_dump_that_fails_midway_leaves_the_old_bundle_intact` FAILED.

### AC-6 — `Branch.kind` — DISCHARGED (criterion text needs one amendment, Finding 1)

Snapshot: still exactly one property vs `cdb4fef`; its description text changed at `738dcf8` to
say "promoted". Fix check (critic 3): on case14, `line.tap_ratio = 1.05` → `kind` stays `"line"`,
`is_transformer` **True**; `native.loads(native.dumps(net))` gives `kind="transformer"`, tap 1.05,
no raise (the critic's `ValidationError` is gone); `Branch.model_validate(model_dump())` →
`transformer`; pandapower export writes it as the 4th `trafo` row and re-imports tap 1.05 (nothing
"dropped" in the report); PyPSA puts it in `transformers` with `tap_ratio` 1.05; CSV round-trips
`kind=transformer`. Same for `shift_deg = 10.0`. Construction with `kind="line"` + tap/shift →
`"transformer"`. The round-tripped network is `!=` the mutated one (kind differs) — documented in
the field description (Finding 5). Spec: the working-tree `## Design` S1 item now reads "**promoted**
to `"transformer"` by the validator, not rejected" (`spec:164`) and the plan's AC-6 readback says
"PROMOTED (amended, F7)" — both say so; the committed AC-6 criterion text is unchanged and still
claims "every pre-M8 test passes unmodified" (Finding 1). Revert-and-watch (the wave's one named
revert, now the promotion): `_default_kind` returns the data untouched for an explicit kind and
`is_transformer` reads `kind` only → `7 failed, 142 passed`:
`test_explicit_line_with_tap_is_promoted_to_transformer[×2]`,
`test_is_transformer_reads_the_fields_not_only_kind`,
`test_tap_assigned_after_construction_round_trips_through_native[×2]`,
`test_tap_assigned_to_a_line_after_construction_exports_as_a_trafo` (pandapower) and
`…_as_a_transformer` (PyPSA). Restored, identical.

### AC-7 — reports — DISCHARGED

Silence, re-run on the new head (stdout/stderr redirected, root logger at DEBUG, warnings recorded)
across pandapower export+import, PyPSA export, RAW case14+quirks, CSV dump+load on case14 and a
hand net: **STDOUT `''`, STDERR `''`, 0 log records from mambo, 0 warnings from mambo** (34 records
from `pypsa`, `matplotlib`, `numexpr`). Lossless → empty: CSV on both nets, pandapower import of
`pp.networks.case14()`. Lossy → named: the codes listed per module above. Registry (critic 9):
`report.py` imports only `dataclasses` and `mambo_power.model`; `LIMITATIONS` lives in
`io/limitations.py`; 13 import orders × {libraries free, `pandapower`/`pypsa`/`pandas` blocked via
`sys.modules[...] = None`} = **26 subprocesses, all OK**, `mambo_power.io.report` has no
`pypsa`/`pandapower_json`/`psse_raw`/`csv_bundle` attribute. Union check redone: each module's
`CODES == LIMITATIONS[module]`, every `CODES` ⊆ `ImportIssueCode`, every code literal emitted in
source ∈ `CODES` (RAW's six `RawImportError` codes correctly outside), every `CODES` entry
documented, and — closing the first audit's note 7 — **every code documented in `formats.md` is
registered**. Walk 3 (cost-less RAW): `opf.solve_dc_opf` raises `MissingCostError` naming all five
generators; `jobs.run(kind="opf.dc")` → `status failed`, code **`VALIDATION`**, same message;
`market.solve_nodal` raises the same. Sabotages, each restored identical: `if missing:` → `if
False:` → `8 failed` (`test_costless_generators_fail_as_validation_under_every_pricing_kind[×5]`,
`test_solve_dc_opf_refuses_a_costless_generator`, `…names_every_costless_generator`,
`test_gen_cost_coeffs_accepts_a_costs_override…`); `report.py` given a format import →
`test_io_limitations.py` fails at collection (circular import, `1 error`).

### AC-8 — docs — DISCHARGED

`mkdocs build --strict` exit 0 from the archive; `examples/13_interop.py` exit 0 in 8.8 s, and its
report lines moved honestly (PyPSA `['PYPSA_GEN_Q_LIMITS_DROPPED','PYPSA_UNRATED_S_NOM_DEFAULTED',
'PYPSA_ZONE_DROPPED'] (26 issues)`, RAW `[…,'RAW_SECTION_IGNORED'] (16 issues)`, pandapower
`10 issues`), matching the doc blocks. `io-limitations` API page added to `mkdocs.yml`;
`site/api/model` renders `is_transformer`; `site/api/opf` renders `MissingCostError` (25×);
`model.md:112-118` documents promotion and `is_transformer`; `formats.md:600` documents the
`MissingCostError` refusal under RAW. Sabotage (rename every occurrence of
`RAW_XFMR_MAGNETISING_FOLDED` in `formats.md`):
`test_every_registered_code_is_documented[io.psse_raw-RAW_XFMR_MAGNETISING_FOLDED]` FAILED, 87
passed. (A first attempt renaming only the limitations-table row stayed green because the record map
at `formats.md:543` still named the code — the test is "documented anywhere", which is what it
claims.) Restored, identical.

### Findings at e2d6da8

1. **should-fix — a pre-M8 behaviour changed without its paper trail.** The walk fix `dcbeb5e` makes
   `opf.solve_dc_opf` / `market.*` raise `MissingCostError` on `Generator.cost is None` where they
   priced it at zero before; correct (A3 made true), proven (Finding-free above), and documented in
   `formats.md:600` and the opf API page. But: (a) the pre-M8 test
   `tests/unit/test_opf_solve_dc_opf.py::test_solve_dc_opf_treats_a_costless_generator_as_free` was
   renamed and its assertion inverted, so AC-6's "every pre-M8 test passes unmodified" is no longer
   literally true and the spec's AC-6 text does not say so (the plan's F5 does); (b)
   `docs/changelog.md`'s M8 section has no `### Changed` line for it — the only public behaviour
   change to a pre-M8 module in this wave is absent from the changelog, and `docs/manual/opf.md`
   still does not mention the refusal. Fix: one amendment sentence on AC-6 (or A3) in the spec, one
   `### Changed` bullet, one sentence in `opf.md`.
2. **should-fix — a vacuous assertion under a name that promises byte identity.**
   `tests/unit/test_io_pandapower_json.py:743` `test_bulk_export_is_byte_identical_to_pandapowers_per_row_creators`
   ends with `assert text == pp.to_json(reference) or True` (`:766`), and
   `pandapower_json.py:756-757` says that test "pins" byte identity. What it proves (and what I
   measured) is `nets_equal` + same column sets + cell-for-cell equality + same re-import — value
   identity, with column order legitimately different. Rename the test, delete the `or True` line,
   and fix the docstring sentence; the S8 plan row already states the accepted deviation.
3. **note — `csv_bundle.dump` is atomic against rendering and writing, not against the move-in.**
   `csv_bundle.py:352-354` moves the ten files with sequential `os.replace`; a failure between moves
   (injected on the 4th) leaves a mix of new and old files. Here `load` refused it
   (`CSV_MANIFEST_INVALID`, row counts differed) but a same-shape network would load a hybrid. Narrow
   window on a same-filesystem rename; worth one clause in the docstring ("all-or-nothing up to the
   final rename step").
4. **note — `UNTERMINATED_SECTION`'s location relies on the `/ END OF … DATA` comments.** With bare
   `0` lines (the docstring calls the comment optional) the missing bus terminator surfaces as
   `BAD_RECORD … (line 11)` one section later; the walk's exact case is fixed, the general one is
   not detectable without the comments. Say so in `formats.md`'s error row.
5. **note — a mutated network is not `==` to its native round trip.** After `br.tap_ratio = 1.05`
   on a line, `native.loads(native.dumps(net)) != net` because `kind` differs; nothing is lost and
   the field description says assignment does not re-run the rule. Fine, but a `Network.__eq__`
   caller may be surprised; `model.md:116` covers it.
6. **note — pandapower export of a MATPOWER-derived network is never lossless now.** With
   `res_bus` no longer written, the bus `vm_pu/va_deg` MATPOWER carries are `FIELD_DROPPED` (13
   entries on case14). Right under D1 and reported; the example's "9 issues" became "10".
7. **note — the plan's S8 wording "nets_equal to the per-row form" holds against the test's own
   per-row reference, not against the file the 7ec0b0b exporter wrote** (`res_bus`, column order).
   Substance holds (values identical on all ten tables); the sentence could say "value-identical".

First-audit items: should-fix 1 (example budget) **resolved**; should-fix 2 (matrix pending)
**resolved** in the working-tree plan (rows discharged, stack-health filled, auditor column awaiting
this section); note 3 (skipped columns) **resolved** (`b56e9aa`, assert on both sides); note 5
(bare `raises`) **resolved**; note 7 (docs-side direction) **closed by measurement** above; notes 4
and 6 stand as notes.

Hygiene on the new tests: `match=` on every new `pytest.raises` (`test_opf_solve_dc_opf.py`,
`test_branch_kind.py`); the `continue` at `test_io_pandapower_json.py:718` is loop control in the
per-row reference builder, not a skipped assertion; the injected-failure CSV test monkeypatches and
restores `_write_csv`; the import-order test runs real subprocesses with `sys.modules` blocking. The
one blemish is Finding 2.

### Overall at e2d6da8

**Criteria: 8 DISCHARGED, 0 PARTIAL, 0 REFUTED.** Findings: 0 blocking, 2 should-fix, 5 notes.
Fourteen sabotages (one per criterion, one per fix, plus the promotion revert-and-watch) each
reddened exactly the tests that guard the thing moved, and every file restored byte-identical
(`sabotage-e2d6da8.txt`; the sabotage copy's `src/` and `docs/` diff clean against the read-only
copy at the end).

**Every walk and critic fix verified against its finding:** walk 3 (`MissingCostError` →
`VALIDATION`), 4 (per-branch unrated report), 5 (section + line), 6/7 (blank lines, BOM); critic 1
(`b` as admittance, PyPSA `pf()` to 2e-16), 2 (four changer types against `_ppc`), 3 (promotion +
`is_transformer`, mutated tap survives every exporter and the native round trip), 4 (12.4 s → 0.28 s,
values identical), 6 (`gen.slack`), 7 (atomic up to the move-in), 9 (leaf `report.py`, 26 import
orders), 10 (`res_bus` neither read nor written).

**Wave-level coverage verdict: COVERED.** The chain R11 → W1…W5 → AC-1…AC-5, "Explicit kind,
defaulted" → W6 → AC-6, "Best effort + report" → W7 → AC-7, R14 → W8 → AC-8 is unchanged; the S1
design decision now reads "promote" in the spec's `## Design` and the plan's readback; A1–A8 were
re-observed (A6 as amended, A3 now true by construction rather than by assumption); the two fix
slices added tests for every new behaviour and I found no fix without a guarding test. The one
gap in the paper trail is Finding 1 — a criterion sentence and a changelog line, not evidence.
Merge-ready from the audit's standpoint once Findings 1 and 2 are addressed or explicitly waived.

Evidence files (scratchpad): `full-run-e2d6da8.txt`, `mkdocs-e2d6da8.txt`, `ex13-e2d6da8-1.txt`,
`sabotage-e2d6da8.txt`, `probe2/{walk,critic,imports,ne,parity,quiet,registry,sabotage,old_dump300}.py`,
`probe2/case300_perrow.json`.
