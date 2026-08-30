# M8 S2 report — `io.pandapower_json` (W1, W2, AC-1, AC-2)

Worktree `C:\Claude Projects\mambo-power-m8-s2`, branch `wave/08-interop-s2`, base `a51250f`.
Every claim below carries its command/output or the label `unverified`.

## Commits (`git log --oneline`, `git show --stat`)

| hash | subject | files |
|---|---|---|
| `bd05df7` | feat(m8/s2): io.pandapower_json — import/export + 7 codes (W1, W2, AC-1) | `src/mambo_power/io/pandapower_json.py` +890, `src/mambo_power/model/warnings.py` +19, `tests/unit/test_io_pandapower_json.py` +437 |
| `bb539c3` | test(m8/s2): parity — rundcpp/runpp vs solve_dc/solve_ac, every fixture loads, A16 measured (AC-2) | `tests/parity/test_pandapower_json_vs_pandapower.py` +240 |
| `cf9652e` | fix(m8/s2): report messages print Python scalars, not np.float64(...) | `pandapower_json.py` +2 |

`git status --short` after the last commit: clean.

## Codes (`pandapower_json.CODES`)

`EXTRA_EXT_GRID_DEMOTED, COLUMN_DROPPED, ELEMENT_DROPPED, FIELD_DEFAULTED, ISLAND_DEACTIVATED,
FIELD_DROPPED, COST_DROPPED, BID_DROPPED`. All but `ISLAND_DEACTIVATED` appended to
`ImportIssueCode`. Not registered in `LIMITATIONS` and not documented — S6 owns both.

## A16 measurement (pandapower 3.3.0, `scratchpad/probe_a16.py`, `smoke.py`, parity test)

1. `pp.toolbox.nets_equal(pp.from_json_string(pp.to_json(pn)), pn)` → `True` on `case14` and
   `case30` (probe output `case14 nets_equal(from_json(to_json(pn)), pn) = True`, same for case30).
2. `nets_equal(from_json(dumps(loads(to_json(pn)), f_hz=pn.f_hz)), pn, name_selection=[t])`:
   - holds: `poly_cost`, `pwl_cost`
   - does not hold: `bus, ext_grid, gen, sgen, load, shunt, line, trafo`
   Measured causes (smoke output, differing columns): `name` (None in pn vs ids), `bus.name`
   int→str, `bus.zone` 1.0→"1", `geo` whitespace, column-set differences from `create_*`
   (`line.type`, `load.type`, `max_loading_percent`, `controllable`, `tap_dependency_table`…),
   float noise 5e-13 on `vk_percent`/`tap_step_percent`. Every value column the model carries
   survives at rtol 1e-12 (`test_carried_values_survive_the_round_trip`). **Finding against A6 as
   literally stated; no tolerance added** — `test_nets_equal_round_trip_measured` pins the set.

## AC-1 evidence

`pytest tests/unit/test_io_pandapower_json.py` → 20 passed. Import report empty on pn.case14/
case30; branch worst diff 1.1e-16 / 5.6e-17 (smoke). Deviations listed in `KNOWN_DEVIATIONS`
and asserted present: case14 `vn_kv` per bus vs BASE_KV=0 repair; branch-14/15 nominal-tap
trafos (A7); cost cp2 0.0430293 vs 0.0430292599; rating 9900 sentinel vs fixture RATE_A 0;
case30 zones 1/2/3 vs fixture ZONE 1.

## AC-2 evidence

`pytest tests/parity/test_pandapower_json_vs_pandapower.py` → 24 passed. DC angle worst
8.9e-15 / 1.8e-15 / 1.3e-13 deg (case14/30/57); AC vm worst 6.7e-16 / 8.9e-16 / 2.4e-15 pu
(smoke output). All six fixtures load in `pp.from_json`.

## Red → green

Tests were written after the first implementation. The genuine red: smoke run showed AC
parity off (case14 vm 2.4e-3, case30 `Power Flow nr did not converge after 50 iterations`)
while DC matched at 1e-14 → ppc diff `branch col 4 oracle 0.0528 mine 5.28e-06` → exporter's
`c_nf_per_km` used `b·Zb` instead of `b/Zb`; fixed before commit 1. Second: unrated trafo
round trip invented rating 100 → now `FIELD_DEFAULTED` on export + test.

## Sabotages (each restored with `git checkout --`, status clean)

1. shunt sign flip → `assert {('9', 0.0, -19.0)} == {('9', 0.0, 19.0)}` (both cases + hand-built).
2a. import ignores tap changer → `branch-8: 0.022 <= 1e-09`; hand-built `None == 1.025`.
2b. export drops tap args → parity DC angles case57 `bus-32 0.2149635 <= 1e-06`.
3. drop `g_us_per_km` report entry → drop-reporting test red (only const_z + switch listed);
   side finding `np.float64(50.0)` in message → `cf9652e`.

## Gates

`uv run ruff check .` All checks passed · `uv run ruff format --check .` 186 files already
formatted · `uv run mypy` Success: no issues found in 55 source files.
`pytest tests/unit tests/parity/test_pandapower_json_vs_pandapower.py --deselect
tests/unit/test_api_docs_coverage.py::test_every_public_symbol_is_reachable_from_an_api_page`
→ 994 passed, 1 deselected (164.9 s). The deselected test fails on HEAD naming
`mambo_power.io.pandapower_json: dump, dumps, …` as missing from `docs/api` — the W8 API page
S6 owns.

## Design notes

Exporter `f_hz` kwarg (default 50); `Bus.area` as extra `bus.area` column (survives to_json,
measured); `vm_pu/va_deg` via `res_bus`; ids = `name` else `<table>-<index>`; sgen on PQ bus →
`v_set_pu=1.0`; tap encoding `tap_pos=±1, step=|tap−1|·100` (pandapower's own from_ppc form);
pandapower `storage` dropped both ways with `ELEMENT_DROPPED`.
