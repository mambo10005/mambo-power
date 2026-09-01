# M8 S8 — Step-6 critic fixes

Worktree `C:\Claude Projects\mambo-power-m8`, branch `wave/08-interop`, base `a78db18`, head
`e2d6da8`. Eleven commits, no amends; `git status --short` clean at the end. Every command below
ran from the worktree with `uv run`. Critic repros (`scratchpad/m8-critic-exp/e1_pp.py`,
`e2_pypsa.py`, `e9_kind.py`) were run against `a78db18` first: all three findings reproduced
verbatim (b_pu 4.8 vs 30; tap 1.05 imported under `tap_changer_type=None`; `NO_SLACK` for
`gen.slack`; `kind` stale after mutation).

## Commits (`git log --oneline a78db18..HEAD --stat`)

| Hash | Finding | Files | Red → green | Sabotage |
| --- | --- | --- | --- | --- |
| `36e8398` | B1 PyPSA trafo `b` | pypsa.py, formats.md, tests/parity/test_pypsa_export_vs_pypsa.py (+58) | 2 failed → 36 passed | factor reverted: 2 failed |
| `9e2c9b3` | B2 `tap_changer_type` | pandapower_json.py (+103), warnings.py, formats.md, test_io_pandapower_json.py (+136) | 11 failed → 15 passed | `None` routed into Ratio: 3 failed |
| `df51ee8` | B3 kind promotion + `is_transformer` | entities.py, pypsa.py, pandapower_json.py, model.md, formats.md, changelog, test_branch_kind.py, +1 test each pypsa/pandapower | 220 passed | raise restored: 4 failed |
| `738dcf8` | schema snapshot | tests/unit/snapshots/network.schema.json (1 line: kind description) | 22 passed | — |
| `1f442d6` | S10 `res_bus` out | pandapower_json.py, formats.md, changelog, tests | 82 passed (unit+parity) | read restored: 1 failed |
| `841fb46` | S4 bulk export | pandapower_json.py (354 lines), test (+118) | 40 unit + 49 parity | gen text cells left `""`: 2 failed |
| `c6f9894` | S6 `gen.slack` | pandapower_json.py, warnings.py, formats.md, tests (+59) | 2 failed → 146 passed | promotion disabled: 2 failed |
| `c5070ac` | S7 atomic csv dump | csv_bundle.py, formats.md, test (+37) | 1 failed → 59 passed | write straight into target: 1 failed |
| `53b084a` | S9 `io/limitations.py` | limitations.py (new), report.py, io/__init__.py, docs (api page, nav, formats, architecture, changelog), test (+60) | 94 passed | format import at report bottom: 8 failed |
| `e2d6da8` | nits 13–15 | psse_raw.py, csv_bundle.py, pandapower_json.py, pypsa.py, warnings.py, formats.md, 4 test files | 245 passed | all four reverted: 5 failed |

## Per fix

**B1.** `b=[br.b / k ...]` (was `* k`). Parity test `test_transformer_charging_b_matches_pypsa_ac_pf[b]`
for b = 0.3 and −0.05: PyPSA `n.pf()` vs `pf.solve_ac` at bus b within 1e-6, and the charged
answer differs from the uncharged one by > 1e-4 (so the map is exercised). Pinned column is
`n.transformers.b` (PyPSA's `b_pu` re-multiplies by `s_nom`; my first draft pinned the wrong one).

**B2.** Verified against pandapower 3.3 `build_branch._calc_tap_from_dataframe` (arctan there is
`rad2deg(np.arctan)`, so `trafo_shift` is degrees). New `_Importer.tap_changer`:
`None` → nominal, non-neutral `tap_pos` reported `COLUMN_DROPPED` (neutral/NaN, i.e. from_ppc and
case14 encodings, stay silent); `Ratio`/`Symmetrical` → `|vn + du·e^(jθ)|`, shift `+= atan(±du·sinθ/(vn+du·cosθ))`;
`Ideal` → `±diff·degree` or `±2·asin(diff·percent/200)`; unknown type / Ideal with both steps /
`tap_side` not hv|lv → `TAP_CHANGER_TYPE_UNSUPPORTED`, nominal. `tap_step_degree` left the
`check_columns` expectations (it is consumed now). Ten configurations vs `net._ppc` TAP/SHIFT
(1e-9) and `runpp` voltages (1e-6). First sabotage attempt was ineffective (the block's `return`
still ran); the recorded one routes `None` into the Ratio path.

**B3.** `_default_kind` promotes instead of raising; `Branch.is_transformer` property; both
exporters route on it. `test_tap_assigned_after_construction_round_trips_through_native`:
mutate a line's tap/shift, `native.loads(native.dumps(net)) == Network built fresh with that tap`.
Snapshot regenerated in `738dcf8` (description text only).

**S10.** Importer no longer reads `res_bus`; exporter no longer writes it; `_drop_bus_state`
emits one `FIELD_DROPPED` with `bus_ids` for non-slack buses carrying a state (slack excluded when
its `vm_pu` equals the exported `ext_grid` setpoint). formats.md "Tables read" rewritten.

**S4.** Timing (`scratchpad/s8_time.py`, best of 2 on case300 / 3 on case14):

```
before  pandapower dumps (case14)    210.7 ms   pandapower dumps (case300)   3062.3 ms
after   pandapower dumps (case14)    144.1 ms   pandapower dumps (case300)    112.3 ms
```

(The critic's 24–33 s was their machine; the ratio is the point.) Identity check on the saved
before/after JSON: `pp.nets_equal` True for case14 and case300; **not byte-identical** — bulk
creators append `max_vm_pu`/`max_p_mw` before the `min_*` twin, so `bus`/`gen` column order
differs. Value differences found and undone: `""` for `None` in gen/sgen `curve_style`, gen
`type`, line `std_type`/`type`, trafo `std_type`, untapped `tap_side`/`tap_changer_type`; an extra
sgen `generator_type` column (dropped). sgen `type` is `"wye"` on both sides (I nulled it once,
wrongly, and put it back). The pinning test builds a per-row reference with pandapower's single
creators, round-trips both through `to_json`, and asserts `nets_equal`, equal column sets, and
every cell including None/NaN/"" per table, plus `pj.loads` equality.

**S6.** `GEN_SLACK_PROMOTED`; tests for no ext_grid, ext_grid off, ext_grid on (stays PV,
`COLUMN_DROPPED`), and neither (`NetworkValidationError` matching `NO_SLACK`, documented as
correct). Process slip: a `cp` restore after a failed `&&` chain reverted pandapower_json.py to
its pre-S6 state mid-work; re-applied the file's part of the patch and re-ran gates (146 passed)
before committing.

**S7.** `_render` builds every table first; staging dir `.<name>.tmp-<pid>` beside the target;
`os.replace` per file; `shutil.rmtree` on exception. Test asserts the old bundle's bytes are
unchanged, it loads, no `.tmp-` residue, and the `""` refusal also leaves it intact.

**S9.** No re-export of `LIMITATIONS` from `report` (it would recreate the cycle); every
reference updated (grep for `report.LIMITATIONS` empty). New test spawns a fresh interpreter per
io module with `pypsa`/`pandapower`/`pandas` set to `None` in `sys.modules`.

**Nits.** `case14_v33.raw` has one area record and the quirks fixture two, so the two RAW
report-count tests moved (documented in the tests) and formats.md's printed example became
`14 20 ['BASE_KV_REPLACED', 'RAW_NO_COSTS', 'RAW_SECTION_IGNORED'] 16` (recomputed). `inf` cannot
reach `_label` through pandapower JSON (it becomes null), so that test calls the helper directly.

New codes: `TAP_CHANGER_TYPE_UNSUPPORTED`, `GEN_SLACK_PROMOTED`, `PYPSA_COST_NONCONVEX` — each in
`ImportIssueCode`, the module `CODES`, and formats.md (`test_io_limitations.py` green).

## Gates

- `uv run ruff check .` → All checks passed!; `ruff format --check .` → 201 files already
  formatted; `uv run mypy` → Success: no issues found in 59 source files.
- `uv run pytest -q tests/unit` → `1199 passed in 77.37s`.
- Parity: `test_pypsa_export_vs_pypsa test_pandapower_json_vs_pandapower test_opf_vs_pypsa
  test_opf_vs_pandapower test_matpower_vs_pandapower test_market_nodal_vs_pandapower
  test_market_zonal_vs_pypsa test_market_multiperiod_vs_pypsa` → `175 passed, 4 skipped`
  (the pre-existing fixed-load skips).
- `uv run --group docs mkdocs build --strict` → Documentation built in 18.41 seconds, exit 0.
- `uv run python examples/13_interop.py` → exit 0. Printed codes changed: pandapower export
  `['FIELD_DEFAULTED', 'FIELD_DROPPED']` now includes the vm_pu/va_deg drop on 13 buses (S10;
  "10 issues in all"); RAW `['BASE_KV_REPLACED', 'RAW_NO_COSTS', 'RAW_SECTION_IGNORED'] (16 issues)`.

## Not done

Critic finding 5 (example budget) was outside the brief; S4 makes the script fast regardless
(unverified against the 60 s budget in the suite — `test_examples_run` was not run).
