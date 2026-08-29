# M1 S4 report — MATPOWER .m importer incl. gencost, parity vs pandapower, native round-trip

Agent: m1-s4-matpower · 2026-08-20 · worktree `C:\Claude Projects\mambo-power-m1`, branch `wave/01-substrate`
Base: 8c82e9d (S3 model) → **commit c9b5a9076989d1bd321e7ac2968c5c3649cabb08** (not pushed).
Every claim below carries its command and trimmed output, or is labelled `unverified`.

## 1. Delivered

| Path | Contents |
|---|---|
| `src/mambo_power/io/matpower.py` (411 lines) | `load(path)`, `loads(text)`, `load_with_warnings(path)`, `loads_with_warnings(text)` → `(Network, list[str])`; `MatpowerImportError(code, message, line=None)` with `.code ∈ MatpowerImportCode` = {MISSING_BASE_MVA, MISSING_SECTION, UNTERMINATED_MATRIX, BAD_NUMBER, BAD_ROW} and `.line` (1-based, when known); `DEFAULT_BASE_KV = 1.0` |
| `src/mambo_power/io/__init__.py` | re-exports `matpower` beside `native` |
| `tests/unit/test_matpower_parser.py` | 38 tests: tiny inline cases, every error code with line numbers, format tolerance, column semantics, gencost poly/pwl/absent/2·ngen |
| `tests/unit/test_native_roundtrip_fixtures.py` | 16 tests: AC-5 on all five fixtures (three forms) + case14 VM/VA spot check |
| `tests/parity/test_matpower_vs_pandapower.py` | 30 tests: AC-6, 6 checks × 5 fixtures (counts, bus types, raw columns, pandapower-aligned values, gen reconciliation, warning causes) |

Parser shape: line-based scanner (no MATLAB execution). Recognises `mpc.<name> = <scalar>;`, `mpc.<name> = [ ... ];`, `mpc.<name> = { ... };`; quote-aware `%` stripping; rows split on `;` *and* newlines; commas treated as whitespace; `]` may sit on a row line; `baseMVA` with or without `;`; CRLF via `str.splitlines()`; scientific notation via `float()`. Unknown fields (`version`, `areas`, `gen_name`, anything) are ignored; `{...}` blocks (`bus_name`) are skipped. Columns beyond the required width (bus 13, gen 10, branch 11, gencost 4 + NCOST·{1,2}) are ignored.

## 2. RED — tests written first

Command: `uv run pytest tests/unit/test_matpower_parser.py tests/unit/test_native_roundtrip_fixtures.py tests/parity/test_matpower_vs_pandapower.py -q` → **exit 2**

```
ERROR collecting tests/unit/test_native_roundtrip_fixtures.py
tests\unit\test_native_roundtrip_fixtures.py:7: in <module>
    from mambo_power.io import matpower, native
E   ImportError: cannot import name 'matpower' from 'mambo_power.io' (...\src\mambo_power\io\__init__.py)
ERROR collecting tests/parity/test_matpower_vs_pandapower.py
tests\parity\test_matpower_vs_pandapower.py:32: in <module>
    from mambo_power.io import matpower
E   ImportError: cannot import name 'matpower' from 'mambo_power.io' (...)
ERROR tests/unit/test_matpower_parser.py
3 errors in 0.61s
```

Second RED, after the importer landed, from the parity suite (`uv run pytest tests/parity/test_matpower_vs_pandapower.py -q -x` → exit 1, `12 passed, 1 error`): case14 and case30 passed all six checks, case_ieee30 raised **inside pandapower**:

```
.venv\Lib\site-packages\pandapower\converter\pypower\from_ppc.py:303: IndexError
>               sn[sn_is_zero] = MAX_VAL
E               IndexError: boolean index did not match indexed array along axis 0; size of axis is 4 but size of corresponding boolean axis is 3
```

That is an oracle defect, not an importer defect — see §5 item 2. After the oracle workaround: `30 passed in 4.49s`, exit 0.

**Instrument catches (proven on case118, scratch script against the test module's own comparison functions):**

```
MUTATION branch-8 x += 2e-9:      layer A worst=2.00e-09 (>1e-09: True), layer B worst=2.00e-09 (>1e-09: True)
MUTATION gen-4 cost c1 += 1e-8:   layer A worst=1.00e-08 (>1e-09: True), layer B worst=1.00e-08 (>1e-09: True)
MUTATION bus-6 type flip (pv->pq): caught by layer A (AssertionError)
MUTATION branch-1 in_service False: caught by layer B (line in_service)
```

## 3. GREEN gate

`uv` = `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`; `uv sync --locked --all-groups` → `Resolved 81 packages ... Checked 77 packages`, exit 0. Python 3.12.14, pandapower 3.3.0.

| Command | Exit | Trimmed output |
|---|---|---|
| `uv run ruff check .` | 0 | `All checks passed!` |
| `uv run ruff format --check .` | 0 | `21 files already formatted` |
| `uv run mypy` | 0 | `Success: no issues found in 8 source files` |
| `uv run pytest` | 0 | **127 passed in 5.66s** (43 before S4 + 84 new) |

```
tests\parity\test_matpower_vs_pandapower.py ..............................   [ 23%]
tests\parity\test_oracles_import.py ..                                       [ 25%]
tests\unit\test_json_schema_snapshot.py ...                                  [ 27%]
tests\unit\test_matpower_parser.py ......................................    [ 57%]
tests\unit\test_model_examples.py ....                                       [ 60%]
tests\unit\test_model_invariants.py ............................             [ 82%]
tests\unit\test_model_roundtrip.py .....                                     [ 86%]
tests\unit\test_native_roundtrip_fixtures.py ................                [ 99%]
tests\unit\test_version.py .                                                 [100%]
============================= 127 passed in 5.66s =============================
```

One gate fix on the way: first `ruff check` flagged E501 (101 > 100) at `matpower.py:211` and `ruff format --check` wanted two files rewrapped; `uv run ruff format src/mambo_power/io/matpower.py tests/unit/test_matpower_parser.py` → `2 files reformatted`, then all four gates clean as above.

## 4. Commit

`git rev-parse HEAD` → `c9b5a9076989d1bd321e7ac2968c5c3649cabb08`. `git show --stat HEAD`:

```
commit c9b5a9076989d1bd321e7ac2968c5c3649cabb08
Author: Manho Joung <manhojoung@gmail.com>
Date:   Thu Aug 20 15:51:16 2026 -0700

    feat(m1/S4): MATPOWER .m importer incl. gencost — parity vs pandapower on 5 IEEE fixtures, native round-trip

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 src/mambo_power/io/__init__.py               |   4 +-
 src/mambo_power/io/matpower.py               | 411 ++++++++++++++++++++++++
 tests/parity/test_matpower_vs_pandapower.py  | 448 +++++++++++++++++++++++++++
 tests/unit/test_matpower_parser.py           | 410 ++++++++++++++++++++++++
 tests/unit/test_native_roundtrip_fixtures.py |  44 +++
 5 files changed, 1315 insertions(+), 2 deletions(-)
```

No hook blocked the commit; `git status --short` after commit: clean. Nothing pushed. Model, schema snapshot, `uv.lock`, `pyproject.toml`, CI, fixtures: untouched (the stat above is the complete file list).

## 5. Oracle path and reconciliation (AC-6)

### 5.1 Which oracle and why

`pandapower.converter.from_mpc` in 3.3.0 is, for a `.m` path, exactly `_m2ppc(path)` → `_adjust_ppc_indices` → `_change_ppc_TAP_value` → `converter.pypower.from_ppc`. `_m2ppc` delegates the `.m` read to the optional package **`matpowercaseframes`, which is not in the locked environment** (`uv run python -c "import matpowercaseframes"` → `ModuleNotFoundError`; `grep matpowercaseframes uv.lock` → nothing), so `from_mpc('case14.m')` raises `NotImplementedError` here and adding the dependency was out of scope. `inspect.signature(from_mpc)` → `(mpc_file, f_hz=50, casename_mpc_file='mpc', validate_conversion=False, load_case_engine=None, **kwargs)`.

Chosen path (`tests/parity/test_matpower_vs_pandapower.py`): replace only the `_m2ppc` step with an **independent read of the same bytes** — `re.sub(r"%[^\n]*", "")`, regex `mpc\.<name>\s*=\s*\[(.*?)\];`, then `numpy.loadtxt` on the block with `;` turned into newlines — and run pandapower's own `_adjust_ppc_indices`, `_change_ppc_TAP_value` and `from_ppc(ppc, f_hz=60)` unchanged on a copy. numpy's tokenizer and number parser share no code with our importer. Two comparison layers, both at `TOL = 1e-9`:

- **Layer A — raw MATPOWER columns** (numpy read vs our `Network`): every mapped column of bus, gen, branch and gencost, element by element; ids, bus types, in_service flags, None-vs-0 conventions (RATE_A, TAP, SHIFT), zone list order, load/shunt emission rule. This is the exhaustive per-column AC-6 check.
- **Layer B — pandapower tables after unit alignment** (`from_ppc` output vs our `Network`), reconciled row-by-row through `net._from_ppc_lookups["gen"]` / `["branch"]`, the same lookups `from_mpc` returns. Back-conversion formulas are the inverse of `from_ppc`'s: line `r_pu = r_ohm_per_km / Zni`, `Zni = vn_kv(to)² / baseMVA`, `b_pu = c_nf_per_km · 2 · π·f · Zni / 1e9`, `rating = max_i_ka · vn_kv · √3`; trafo `rk = vkr% · base / (100·sn)`, `zk = |vk%| · base / (100·sn)`, `xk = sign(vk%) · √(zk² − rk²)`, `|b| = i0% · sn / (100·base)`, `tap = 1 + tap_pos · tap_step% / 100`, `shift = shift_degree`, `rating = sn_mva`; impedance `r = rft_pu · base / sn`, `b = bf_pu · 2 · sn / base`; shunt `g = p_mw`, `b = −q_mvar`; poly_cost `[cp2, cp1, cp0]`.

### 5.2 Reconciliation rules (from `from_ppc` source, verified on the fixtures)

| MATPOWER | pandapower | Rule |
|---|---|---|
| gen row at a type-3 bus (first at that bus) | `ext_grid` | exactly one per fixture; keeps `vm_pu` (= VG of the *first* gen at the bus), `va_degree` (= bus VA), p/q limits, in_service; **drops PG/QG** |
| gen row at a type-2 bus (first at that bus) | `gen` | keeps p_mw, vm_pu (first-at-bus VG), limits, in_service |
| any further gen at a bus, or gen at a type-1 bus | `sgen` | keeps p_mw, q_mvar, limits, in_service (none in these fixtures) |
| bus with PD>0, or PD=0 & QD≠0 | `load` | p_mw, q_mvar as-is |
| bus with PD<0 | `sgen` (bus-derived) | negated (none in these fixtures); our load count = `len(load) + len(sgen) − gen-derived sgens` |
| bus with GS≠0 or BS≠0 | `shunt` | p_mw = GS, **q_mvar = −BS** |
| branch TAP∈{0,1}, SHIFT=0, same base_kv both ends | `line` | `_change_ppc_TAP_value` first maps TAP 0→1 |
| branch TAP∉{0,1} or SHIFT≠0 | `trafo` | hv/lv swapped when to-side kV is higher; **BR_STATUS dropped** (always in service) |
| branch TAP∈{0,1}, SHIFT=0, different base_kv | `impedance` | **BR_STATUS dropped**; RATE_A 0 crashes pandapower (§5.4) |
| gencost MODEL 2, NCOST ≤ 3 | `poly_cost` | cp0/cp1/cp2; pandapower caps higher orders at 3 (not hit) |
| gencost MODEL 1 | `pwl_cost` | none in fixtures; our pwl parse is unit-tested |

### 5.3 Per-fixture summary (scratch script over the test module's `compare_raw` / `compare_pandapower`)

| fixture | buses | branches (line/trafo/imp) | gens (ext_grid/gen/sgen) | loads | shunts | poly_cost | importer warnings | layer A worst | layer B worst |
|---|---|---|---|---|---|---|---|---|---|
| case14 | 14 | 20 (17/3/0) | 5 (1/4/0) | 11 | 1 | 5 | 14 | 0.0 | 0.0 |
| case30 | 30 | 41 (41/0/0) | 6 (1/5/0) | 20 | 2 | 6 | 0 | 0.0 | 2.8e-14 |
| case_ieee30 | 30 | 41 (34/4/3) | 6 (1/5/0) | 21 | 2 | 6 | 0 | 0.0 | 5.6e-17 |
| case57 | 57 | 80 (65/15/0) | 7 (1/6/0) | 42 | 3 | 7 | 57 | 0.0 | 2.2e-16 |
| case118 | 118 | 186 (175/9/2) | 54 (1/53/0) | 99 | 14 | 54 | 0 | 0.0 | 2.2e-16 |

Layer A max abs diff is **exactly 0.0 on every column group** for every fixture (bus PD/QD/GS/BS/VM/VA/BASE_KV/VMAX/VMIN, gen PG/QG/QMAX/QMIN/VG/PMAX/PMIN, branch BR_R/BR_X/BR_B/RATE_A/TAP, gencost STARTUP/SHUTDOWN/COST(poly)) — both readers produce the same IEEE-754 doubles from the same tokens. No fixture carries SHIFT≠0, BR_STATUS=0, GEN_STATUS=0, PD<0, a multi-gen bus, or bus type 4 (awk survey, §6), so those branches of the mapping are covered by the unit tests, not the fixtures.

Layer B worst diffs are floating-point round-trip noise of pandapower's own unit conversion (largest: case30 `pp.line.rating` 2.8e-14 from `RATE_A / vn_kv / √3 · vn_kv · √3`). Per-group detail for each fixture is in the progress log's companion output; the largest per-group values: `pp.line.rating` 2.8e-14, `pp.trafo.x` 2.2e-16, `pp.line.b` 2.2e-16, everything else ≤ 5.6e-17.

Skipped (counted, never silently passed): case14 / case57 — `vn_kv == 0` on all buses (we substitute 1.0, pandapower keeps 0), so 17 / 65 line rows have degenerate ohm values and are compared for topology and in_service only (their r/x/b are covered at 0.0 diff by layer A); every fixture — ext_grid drops PG/QG (1 row each), trafo/impedance drop BR_STATUS (3/0, 0/0, 4/3, 15/0, 9/2 rows); case_ieee30 / case118 — 3 / 2 impedance rows with RATE_A 0 carry the sentinel (§5.4).

### 5.4 Oracle defect found

`pandapower/converter/pypower/from_ppc.py:303` reads `sn[sn_is_zero] = MAX_VAL` inside the impedance block, where `sn` is the *transformer* `RATE_A` array and the intended target is `sn_mva` (the impedance array). Any case with an impedance-classified branch (TAP∈{0,1} between different base_kv) whose RATE_A is 0 raises `IndexError` when the trafo and impedance counts differ — case_ieee30 (4 trafos, 3 impedances) and case118 (9 / 2) both do. The genuine `from_mpc` would crash identically on these two upstream files. Workaround in `pandapower_from_raw`: after `_change_ppc_TAP_value`, classify with pandapower's own `_branch_to_which` and set RATE_A = 99999.0 (pandapower's `MAX_VAL`) on exactly the impedance rows where it is 0 — in the oracle's copy only. Layer B then asserts `sn_mva == 99999.0` wherever our `rating_mva is None` for those rows. Upstream report: `unverified` (not filed; out of scope).

## 6. Design deviations and judgment calls

1. **Oracle API differs from the brief's literal `pandapower.converter.from_mpc(path)`** — unavailable without `matpowercaseframes`; replaced by the same pipeline minus its `.m` reader (§5.1). Independence from our parser is preserved (numpy + pandapower code only).
2. **pandapower bug worked around in the oracle copy** (§5.4); the fixtures and our importer are unchanged.
3. **BAD_ROW is MATLAB-strict**: besides "fewer than the minimum columns" (W1), a *ragged* matrix (rows of differing width) is BAD_ROW at the first offending row. MATLAB rejects ragged literals, so no valid file is lost; it catches a dropped token that would otherwise shift columns silently. Test `test_bad_row_ragged_matrix`.
4. **Non-finite numbers are BAD_NUMBER** (W1 rule: `Number(token)` must be finite). `Inf` in PMAX etc. is valid MATPOWER but would not survive `model_dump_json` (pydantic serialises inf as `null` by default), so AC-5 would break; rejecting at import is the honest choice until the model decides on infinities. Test `test_non_finite_is_bad_number`.
5. **Codes for "wrong value" cells** reuse BAD_NUMBER (the closed code set has no BAD_VALUE): bus type ∉ {1,2,3,4}, non-integer BUS_I/GEN_BUS/F_BUS/T_BUS, gencost MODEL ∉ {1,2}, NCOST < 1. Messages name the column; `.line` points at the row. W1's `BAD_BUS_TYPE` is gone per design item 4 (type 4 → out-of-service bus).
6. **gencost row count**: `ngen` rows → P costs; `2·ngen` rows → first half + one warning (brief); any other count → BAD_ROW (a genuinely inconsistent file; MATPOWER's own OPF rejects it). NCOST governs how many values are read from a row, so zero-padded mixed-order rows work (`test_gencost_ncost_governs_not_row_width`).
7. **`bus_name` is parsed past but not stored** — `Bus` has no name field and adding one is forbidden by the brief. Cost: bus names are dropped on import. Cheap follow-up if wanted: `Bus.name: str | None` (schema snapshot bump).
8. **Zones** are emitted with `name=None` (W1 synthesised `"Zone <id>"`); less invented data, round-trips identically. `Zone.id` and `Bus.zone`/`Bus.area` are integer-valued columns rendered compactly (`1.0` → `"1"`), non-integers fall back to `repr`.
9. **Warnings** are plain strings with the bus id / section and line number (`"bus-1: BASE_KV is 0; base_kv set to 1.0 (line 25)"`), returned, never logged or raised; `load`/`loads` discard them. `loads_with_warnings(text)` is added beside the briefed `load_with_warnings(path)` for symmetry.
10. **File encoding**: `utf-8` with `errors="replace"` — MATPOWER headers occasionally carry Latin-1 author names in comments; a replacement character can only land in a comment or become a BAD_NUMBER.
11. **Slack / connectivity are not the importer's business**: zero or multiple type-3 buses, an out-of-service slack, dangling GEN_BUS, islands — all propagate as `NetworkValidationError` from `Network(...)` (`test_slack_out_of_service_raises_network_validation`). Nothing is invented.
12. **VM/VA/VMIN/VMAX/AREA are always set** (never None) from the bus row — the M2 reference solution rides along on `Bus.vm_pu`/`va_deg` (`test_case14_stored_solution_is_preserved_on_buses`: bus-1 1.06/0, bus-2 1.045/−4.98, bus-9 1.056/−14.94, bus-14 1.036/−16.04 against the raw rows).
13. **No model change.** No bug found in the S3 model; schema snapshot untouched (`git show --stat` §4).
14. **Fixture survey** (awk over the five files): BASE_KV ≤ 0 on 14/0/0/57/0 buses (case14, case30, case_ieee30, case57, case118); off-nominal taps 3/0/4/15/9; phase shifts 0; out-of-service branches 0; out-of-service gens 0; negative loads 0; multi-gen buses 0. The parity test `test_importer_warnings_only_for_known_causes` pins the warning count to the zero-kV count per fixture.
15. **Line endings**: `git add` printed the usual `LF will be replaced by CRLF` warnings (core.autocrlf); the index holds LF, same as S1/S3.

## 7. Progress artifact

`C:\Claude Projects\mambo-power\.bionic\tmp\s4-progress.md` — appended at T+0, T+8, T+22, T+35, T+42.
