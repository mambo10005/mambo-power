# M8 S7 — walk fixes (resumed after a session restart)

Worktree `C:\Claude Projects\mambo-power-m8-s7`, branch `wave/08-interop-s7`, base `3f2a9a0`.
Seven commits, no amends. Every command below ran from the worktree with `uv run`.

## Resume

`git diff` at start showed the previous agent's fix 1 mid-sabotage: `opf/__init__.py` had
`pass  # SABOTAGE` where the raise belongs. Restored `raise MissingCostError(missing)`, kept the
rest (error class, jobs mapping, re-exports, tests), re-ran everything.

## Commits (`git log --oneline 3f2a9a0..HEAD --stat`)

```
b56e9aa test(m8): audit hygiene — a missing carried column fails the pandapower round trip; match= on the bare ValueError
 tests/parity/test_pandapower_json_vs_pandapower.py | 6 ++++--
 tests/unit/test_branch_kind.py                     | 2 +-
172eb68 docs(m8): formats — shifter limitation reads "wrong or infeasible"; slack state comes from ext_grid (walk surprises 2, 8)
 docs/manual/formats.md | 33 ++++++++++++++++++++++-----------
044b8a9 fix(m8): CSV bundle skips blank lines and ignores a UTF-8 BOM on read (walk surprises 6, 7)
 docs/manual/formats.md           |  4 +++-
 src/mambo_power/io/csv_bundle.py | 17 ++++++++++++++---
 tests/unit/test_io_csv_bundle.py | 28 ++++++++++++++++++++++++++++
d3ca8d4 fix(m8): RAW UNTERMINATED_SECTION names the section that lacks its '0' and the line it gave up at (walk surprise 5)
 docs/manual/formats.md         |  2 +-
 src/mambo_power/io/psse_raw.py | 63 ++++++++++++++++++++++++++++++++-
 tests/unit/test_io_psse_raw.py | 80 ++++++++++++++++++++++++++++++++++++++++++
591f458 docs(m8): pandapower export — say what the file holds for a nominal-tap transformer (walk surprise 1)
 docs/manual/formats.md                |  9 ++++++---
 tests/unit/test_io_pandapower_json.py | 31 +++++++++++++++++++++++++++++++
c46c063 fix(m8): PyPSA export reports every unrated branch it writes with the s_nom sentinel (walk surprise 4)
 docs/manual/formats.md            |  7 ++++---
 src/mambo_power/io/pypsa.py       | 19 ++++++++++++++++---
 src/mambo_power/model/warnings.py |  4 +++-
 tests/unit/test_io_pypsa.py       | 34 ++++++++++++++++++++++++++++++++--
dcbeb5e fix(m8): a cost-less generator is refused by the OPF, not priced at zero (walk surprise 3)
 docs/manual/formats.md              |  7 +++++--
 src/mambo_power/jobs/run.py         |  7 +++++++
 src/mambo_power/market/__init__.py  |  3 ++-
 src/mambo_power/opf/__init__.py     | 42 +++++++++++++++++++++++++++----------
 src/mambo_power/opf/dc_opf.py       | 23 ++++++++++++++++++++
 tests/unit/test_jobs.py             | 25 +++++++++++++++++++++-
 tests/unit/test_opf_solve_dc_opf.py | 38 ++++++++++++++++++++++++++-------
```

## Fix 1 — MissingCostError (dcbeb5e)

- Green: `uv run pytest -q tests/unit` → `1144 passed in 117.81s`.
- Dependency check: `uv run pytest -q tests/parity/test_market_multiperiod_vs_pypsa.py
  test_market_nodal_vs_pandapower.py test_market_zonal_vs_pypsa.py test_opf_vs_pandapower.py
  test_opf_vs_pypsa.py test_pypsa_export_vs_pypsa.py` → `113 passed, 4 skipped` (the 4 skips
  are the pre-existing fixed-load parameters). No fixture or test relied on cost-less generators
  pricing at zero. `examples/13_interop.py` runs only `pf.solve_dc` on the RAW net.
- Sabotage (`raise` → `pass`): `8 failed, 129 deselected` — the 3 opf tests and 5 jobs
  parametrizations (opf.dc, market.nodal, market.multiperiod, market.zonal, market.agents).
- jobs mapping: explicit `except MissingCostError` → `("VALIDATION", str(exc), None)`.
  `NonConvexCostError` itself falls through to INTERNAL (M7 S10 audit note in registry.py), so the
  path followed is the `NetworkValidationError` one, issues=None.
- Docs: RAW limitations sentence now names `mambo_power.opf.MissingCostError` and `VALIDATION`.

## Fix 2 — PYPSA_UNRATED_S_NOM_DEFAULTED (c46c063)

- Red: `2 failed, 90 passed` (new test + the hand-network codes set).
- Green: `uv run pytest -q tests/unit/test_io_pypsa.py tests/unit/test_io_limitations.py
  tests/parity/test_pypsa_export_vs_pypsa.py` → `108 passed`.
- Sabotage (`if br.rating_mva is None` → `if False`): `2 failed, 18 passed`.
- case14's 20 branches are all unrated (`matpower.load` → 20/20 `rating_mva is None`), so the
  formats.md example output changed to
  `['PYPSA_GEN_Q_LIMITS_DROPPED', 'PYPSA_UNRATED_S_NOM_DEFAULTED', 'PYPSA_ZONE_DROPPED'] 26`.
  `test_empty_report_when_nothing_is_lost` got `rating_mva=10.0` on its branch (its export was
  not lossless under the rule).

## Fix 3 — nominal-tap transformer (591f458) — DEVIATION from the brief

Measured `pandapower.converter.matpower.from_ppc` (3.3.0) on a TAP=0 trafo:
`tap_side hv, tap_neutral 0.0, tap_pos 0.0, tap_step_percent 0.0, tap_changer_type None`.
Writing that reddened `tests/parity/test_pandapower_json_vs_pandapower.py::
test_carried_values_survive_the_round_trip[case14]`:

```
E  AssertionError: ('trafo', 'tap_side')
E  assert ['hv', 'hv', 'hv', None, None] == ['hv', 'hv', 'hv', 'hv', 'hv']
```

`pandapower.networks.case14()` stores its two nominal-tap transformers as `tap_side None` /
NaN — what mambo writes today. Kept the NaN encoding (A16 round trip of pandapower's own case
outranks matching from_ppc's cosmetics; both re-import to a transformer at nominal tap), fixed the
doc sentence, and pinned the columns + re-import in a test.
- Green: `46 passed` (unit + parity file). Sabotage (write from_ppc's hv/0/0/0): `2 failed`.

## Fix 4 — UNTERMINATED_SECTION (d3ca8d4)

- Red on the walker's exact mutation (WALK_TINY line 7 deleted):
  `RawImportError("vsc dc section is not terminated by a '0' line").line == 31` — the walk verbatim.
- Now: `bus section is not terminated by a '0' line: the '0' at line 9 ends the load section, so
  the records between were read as bus records` (line 9). Comment-less variant:
  `file ended inside the vsc dc section before its '0' terminator (line 31); if every section is
  present, an earlier section is missing its '0' terminator`.
- Green: `tests/unit/test_io_psse_raw.py tests/unit/test_jobs.py` → `154 passed`.
- Sabotage (comment parsing disabled): `1 failed, 2 passed`.

## Fix 5 — CSV blank lines + BOM (044b8a9)

- Red reproduced both walk messages: `CSV_MANIFEST_INVALID: loads.csv: manifest says 1 rows,
  file has 3` and `CSV_UNKNOWN_COLUMN: buses.csv: unknown column "\ufeffid"; CSV_MISSING_COLUMN`.
- `_blank_line`: only a line with nothing on it; `,,,,,,,` is still a row (test asserts
  CSV_MANIFEST_INVALID on it). Writer unchanged (test asserts no BOM written).
- Green: `132 passed`. Sabotage A (keep blank rows): `1 failed`; B (`utf-8`): `1 failed`.

## Fix 6 — docs (172eb68)

Four shifter paragraphs → "wrong or infeasible ... a generously rated loop with one shifter can
come back `Infeasible` with no flows at all; `pf.solve_dc` is right". pandapower Tables read:
slack `vm_pu`/`va_deg` from `ext_grid` `vm_pu`/`va_degree` (source: `pandapower_json.py:336-337`),
warm-start rule does not apply.

## Fix 7 — hygiene (b56e9aa)

- Parity carried-values: `continue` → `assert col in a.columns` / `assert col in b.columns`
  naming (table, col). Green on case14/30 (`2 passed`); sabotage with `not_a_column` → red naming
  `('sgen', 'not_a_column', "absent from pandapower's own table")`.
- `test_branch_kind.py:77`: `match=r"kind\s+Input should be 'line' or 'transformer'"`; sabotage
  (`kind must be a cable`) → `Regex pattern did not match`.

## Gates

- `uv run ruff check . && uv run ruff format --check . && uv run mypy` → All checks passed! /
  199 files already formatted / Success: no issues found in 58 source files (exit 0).
- `uv run pytest -q tests/unit` → `1154 passed in 56.77s`.
- `uv run pytest -q tests/parity/test_pypsa_export_vs_pypsa.py
  test_pandapower_json_vs_pandapower.py test_opf_vs_pypsa.py test_opf_vs_pandapower.py`
  → `78 passed in 43.05s`.
- `uv run --group docs mkdocs build --strict` → `Documentation built in 19.92 seconds` (exit 0).
- `git status --short` clean after the last commit.

## Friction

The Bash tool on this machine turns `\\n` inside a quoted heredoc into a literal newline; two
test files needed the Edit tool for byte/escape literals. No effect on the code.
