# M1 Step 6 — six-axis review (stance 1)

Reviewer: m1-review-6axis (fresh relaunch; implemented nothing). Date: 2026-08-20.
Subject: worktree `C:\Claude Projects\mambo-power-m1`, `git diff ca10b6a..36bd20a` (S1 2922d8e, S3 8c82e9d,
S4 c9b5a90, S5 fc68535, S6 36bd20a; 36 files, +7100). Read-only: nothing edited, committed or pushed;
`git status --porcelain` empty before and after every command below (exit 0, no output, last checked after
the final pytest run). `uv` = `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`, run from the
worktree root with `--no-sync`. Every factual claim carries its command/output or a file:line, or is labelled
`unverified`.

Inputs held: wave spec (W1-W6, AC-1..8, Design 1-7), epic spec §Design (§1 ownership of positional ints,
§2 boundaries, §3 ownership table), plan assumptions A1-A14, `record/m1-audit.md` (F1, F2 carried here),
`record/m1-step5-tests-floor.md`, and every file in the diff.

Severity scale: **high** = wrong answer or boundary breach a later wave will build on · **medium** = a
guarantee the spec/record claims that the suite does not hold · **low** = hygiene, would not change a verdict.

Probe script used for Correctness items 2-7 (inline `uv run --no-sync python - <<EOF`, reproduced in §1
where cited); its full output:

```
BOM-first-line: MatpowerImportError MISSING_BASE_MVA: mpc.baseMVA = ...; not found
underscore token 1_50 -> 150.0
self-loop: accepted; Ybus[b,b] = (0.99009900990099-9.900990099009901j) Bbus row b = [-10.  10.] bridges = [0]
tap=0: accepted; Ybus finite? False warnings: 4 bbus: False
r=x=0: Ybus finite? False warnings: ['divide by zero encountered in divide']
r=x=0 bbus -> DC susceptance undefined: x == 0 on in-service branch(es) ['
duplicate baseMVA -> 7.0
continuation: MatpowerImportError BAD_ROW: mpc.branch row has 5 columns, expected >= 11 (line 11)
type-4: n_bus 2 n_branch 1 p_load_pu [0.  0.5]
lodf slack-invariant: 5.773159728050814e-15
BRIDGE check case14 numeric vs graph: True
```

---

## 1. Correctness — **FLAG**

Formulations are right; what is flagged is guard coverage and validator gaps that let physically
meaningless networks reach the matrix builders and come back as silent NaN.

Verified correct against MATPOWER conventions (by reading, each backed by a named test):

- Ybus: `Yff=(y+jb/2)/|a|²`, `Yft=-y/conj(a)`, `Ytf=-y/a`, `Ytt=y+jb/2` — `src/mambo_power/numerics/ybus.py:30-36`
  matches `makeYbus`; shunt `(Gs+jBs)/baseMVA` on the diagonal via `g_shunt_pu + 1j*b_shunt_pu`
  (`ybus.py:60`). Tests: `tests/unit/test_numerics_dense.py:176` (double loop, 1e-12, tap 0.97 + 5° shift),
  `tests/parity/test_ybus_vs_pandapower.py:93` (pandapower `makeYbus`, 5 fixtures, 1e-9),
  `test_ybus_is_not_symmetric_with_phase_shift` (`test_numerics_dense.py:199`) proves the conjugation is
  not accidentally symmetric.
- DC: `b = 1/(x·tap)`, `Pfinj = -b·shift`, `Pbusinj = Cftᵀ·Pfinj` — `bbus.py:31,61,67` matches `makeBdc`.
  Tests: `test_numerics_dense.py:208` (dense, asserts the shifter contributes, line 215),
  `test_ybus_vs_pandapower.py:110` (`makeBdc` on 5 fixtures incl. `Pbusinj`).
- PTDF: slack row/col removed, `splu` on the reduced Bbus, solve against dense `Bfᵀ`, slack column zero
  (`ptdf.py:26-36`). Tests: direct `Bθ=P` solve per column (`test_numerics_dense.py:235`), explicit
  alternative slack (`:242`), flow conservation at every bus (`:251`), property slack-column-zero.
- LODF: `h_k = PTDF(e_f − e_t)`, `LODF[l,k] = h_k[l]/(1−h_k[k])`, diagonal −1, bridge → NaN column
  (`lodf.py:34-41`). Tests: actual branch-removal rebuild at 1e-8 (`test_numerics_dense.py:284`),
  graph-theoretic `bridges` vs removal-BFS on 5 fixtures (`test_ybus_vs_pandapower.py:124`) and on
  hypothesis nets. Probe: LODF is invariant to the PTDF's slack (max |Δ| 5.77e-15 on case14 with
  `ptdf(a, slack=5)`), as the formula predicts.
- Parser column map (bus VMAX=row[11]/VMIN=row[12], gen QMAX/QMIN/PMAX/PMIN order, branch TAP=row[8]
  SHIFT=row[9] STATUS=row[10], gencost MODEL/STARTUP/SHUTDOWN/NCOST then values, PWL as (p,cost) pairs) —
  `src/mambo_power/io/matpower.py:297-340,374-401` verified against the manual; layer-A parity
  (`tests/parity/test_matpower_vs_pandapower.py:129-234`) compares every mapped column at 1e-9 on all five
  fixtures. CRLF (`splitlines`, `matpower.py:158`), `%` comments with quote tracking (`:146`), tabs/commas,
  rows split by `;` or newline, type-4 → `in_service=False` (`:73,282`), ragged rows → BAD_ROW (`:244`),
  gencost 2·ngen → first half + warning (`:361`) — each has a unit test in `tests/unit/test_matpower_parser.py`
  (`:291,:306,:172,:384,:127`).
- Validator: connectivity is BFS from the in-service slack over in-service branches whose *both* ends are
  in-service buses (`src/mambo_power/model/network.py:197-213`); negative cases at
  `tests/unit/test_model_invariants.py:107,115` and the positive type-4 tolerance at `:124`.
- pu conversion: `grep -rn "/ base" src` → only `numerics/arrays.py:132,143,171`. No other division by
  `base_mva` anywhere in `src` (the model reads `base_mva` only to check `> 0`, `network.py:89`). Design 7 holds.

Findings:

1. **medium — F1 (carried from audit).** AC-7 "for every fixture … dense re-derivation … LODF equals the
   brute-force single-outage PTDF difference": the dense double-loop Ybus/Bbus and the brute-force LODF run
   only on the hand-built 6-bus case (`tests/unit/test_numerics_dense.py:94-101`, module-scoped `net`). The
   fixtures get the pandapower oracle and a bridge oracle, not these two. The auditor's probe shows the
   property holds (worst 5.68e-14 / 8.10e-15), so this is a proof gap, not a defect. Fix: make `net` a
   module-scoped fixture parametrised over `[six_bus] + FIXTURES` (the helpers `dense_ybus`/`dense_bbus` are
   already written for any all-in-service network) and move `test_lodf_matches_brute_force_outage` to
   `tests/parity/` if its case118 leg (177 rebuilds) pushes the unit tier past its 10 s budget.
2. **medium — validator accepts self-loop branches.** `Branch(from_bus="b", to_bus="b")` passes
   `validate_network` (no check, `network.py:104-112` only tests existence). Probe: Ybus gets a spurious
   diagonal term `(0.99−9.90j)`, Bbus contributes 0, and `bridges()` reports the *other* branch as a bridge —
   consistent but physically meaningless. The suite itself leans on this: `tests/unit/test_model_invariants.py:134,221`
   use `line("l1", "b1", "b1")` as filler. Fix: add a `BAD_RANGE` issue at `branches[i].to_bus` when
   `from_bus == to_bus` (no new code needed) and replace the two test fillers.
3. **medium — `tap_ratio <= 0` and `r == x == 0` reach the builders and return NaN silently.** The importer
   maps TAP 0 → `None` (`matpower.py:337`), but a native JSON document can carry `tap_ratio: 0.0`; probe:
   `Network` accepts it, `ybus` returns non-finite entries with 4 RuntimeWarnings, `bbus` returns non-finite.
   Likewise `r = x = 0` gives a non-finite Ybus (`ybus.py:30`, `1/(0+0j)`); only `bbus` guards `x == 0`
   (`bbus.py:28-30`). Fix: `BAD_RANGE` for `tap_ratio` not `> 0` in the validator; in `branch_admittances`
   raise `ValueError` naming the branch ids where `r == x == 0` (mirror of `branch_susceptance`).
4. **low — four defensive guards have no test.** `grep -rn` over `tests/` for the messages
   "expected exactly one in-service slack" (`arrays.py:101`), "DC susceptance undefined" (`bbus.py:30`),
   "out of range for" (`ptdf.py:25`), "ptdf_matrix has shape" (`lodf.py:32`) → no hits. Each is reachable
   only by mutating a validated `Network` or passing a bad argument; one-line `pytest.raises` tests each.
5. **low — UTF-8 BOM defeats the assignment regex.** `_ASSIGNMENT` anchors on `^\s*mpc\.` (`matpower.py:75`)
   and `\s` does not match U+FEFF; `read_text(encoding="utf-8")` (`matpower.py:109`) keeps the BOM. Probe:
   a BOM-prefixed file whose first line is `mpc.baseMVA` → `MISSING_BASE_MVA`. Real MATPOWER files start
   with `function mpc = …`, so the fixtures are unaffected. Fix: `encoding="utf-8-sig"` for `load_with_warnings`,
   and `text.lstrip("\ufeff")` in `loads_with_warnings`.
6. **low — `float(token)` is more lenient than MATLAB.** `matpower.py:209`: `1_50` parses as 150.0 (probe),
   as do `+1`, `infinity`, `nan` (the last two caught by `isfinite`, `:214`). Harmless for valid files; a
   stricter regex (`[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?`) would make BAD_NUMBER precise.
7. **low — duplicate `mpc.<name>` assignments: last wins silently** (`matpower.py:170,174`; probe
   `duplicate baseMVA -> 7.0`). A second `mpc.bus` block would silently replace the first. Either reject with
   BAD_ROW or document; documenting is enough for M1.
8. **note — `...` line continuation is not supported** (probe → BAD_ROW with a correct line number). The
   module docstring lists what is tolerated and this is not in it; the error is honest. No action.
9. **note — BRIDGE_TOL is absolute** (`lodf.py:24`, `|1 − h_kk| < 1e-10`). A non-bridge branch whose only
   alternative path has ~1e10× its reactance would be classed as a bridge by `lodf` but not by `bridges`,
   breaking the documented "must agree" invariant (`lodf.py:11`). Unreachable with realistic data; the
   property test's x-range (0.01-1.0) cannot produce it. No action for M1; worth a comment.

F2 (`load` signature) is assessed under Architecture.

---

## 2. Readability — **FLAG** (low)

Module sizes are proportionate (largest `matpower.py` 411 lines with three labelled phases scan → type →
build; `arrays.py` 211 lines is one dataclass + one constructor). Docstrings state the convention *and*
the sign (`entities.py:112-113` GS/BS, `Branch` "tap is on the from side", `PolynomialCost` "highest order
first"), and every error message names the element id and document path. Tests read as specifications:
`test_matpower_parser.py:39-59` documents the line numbers its error tests rely on; `test_numerics_arrays.py:1-12`
states which exclusion rule each element of the 4-bus case exercises.

Findings:

1. **low — parity-module import hack.** `tests/parity/test_ybus_vs_pandapower.py:37-49` loads
   `test_matpower_vs_pandapower.py` via `importlib.util.spec_from_file_location` under a fake module name
   to reuse `read_mpc_numpy`. A reader must work out that a *test file* is being imported as a library.
   Fix: move `read_mpc_numpy`/`pandapower_from_raw` to `tests/conftest.py` (exposed as fixtures) or to a
   `tests/parity/conftest.py`; both are importable under `--import-mode=importlib` without the hack.
2. **low — `FIXTURES`/`FIXTURES_DIR` declared three times** (`tests/unit/test_native_roundtrip_fixtures.py:10-11`,
   `tests/parity/test_matpower_vs_pandapower.py:35-36`, `tests/parity/test_ybus_vs_pandapower.py:32-33`).
   Adding a sixth fixture means three edits, and nothing fails if one is missed. Fix: one constant in
   `tests/conftest.py`.
3. **low — dead field.** `_Matrix.line` (`matpower.py:129-131`) is written at `:170` and never read
   (`_matrix()` uses `block.rows` only; `MISSING_SECTION` carries no line). Drop it, or use it to give
   `MISSING_SECTION`/`BAD_ROW`-count errors a line.
4. **low — `add: Any`** in `_check_connectivity` (`network.py:194`) where the real type is
   `Callable[[ValidationCode, str, str], None]`; mypy strict passes only because `Any` is permitted. Type it.
5. **low — leftovers.** `tests/property/.gitkeep` sits beside a real test module; `tests/unit/test_version.py`
   is subsumed by `test_packaging_metadata.py::test_dunder_version_matches_distribution_metadata`.
6. **note — two things named "bus index".** `Network.bus_index()` (all buses) and `NetworkArrays.bus_index`
   (in-service buses) share a name and disagree whenever a bus is out of service. See Architecture 1 and
   Duplication 2; the readability cost disappears if the model method goes.

---

## 3. Architecture — **FLAG**

Boundaries per epic §2 hold: `grep -rn "^from mambo_power" src` shows `io` importing only `model`,
`numerics` importing only `model` (`arrays.py:22`) and its own siblings, `model` importing nothing outside
itself. No global state; every public function takes and returns model types or numpy/scipy views.

Closure check (public entry point → code → Step-5 evidence that ran it; floor §6 `175 passed`):

| Primitive | Public entry | Exercised by (ran in floor) | Verdict |
|---|---|---|---|
| `model.Network` + 11 entity/error types | `Network(...)`, `model_validate_json` | `matpower.load` builds it on 5 fixtures; 28 invariant cases; schema snapshot; round-trip | live |
| `model.validate_network` | public (A7 re-check) | called by `Network._check_invariants` (`network.py:38`) on every construction | live |
| `model.Network.json_schema` | public | `test_json_schema_snapshot.py:627,637` | live |
| `model.Network.bus_index` | public | `test_model_examples.py:58` only; no `src` caller | **see finding 1** |
| `io.native.dumps/loads/save/load` | public | `test_native_roundtrip_fixtures.py:502-519` (all four) | live |
| `io.matpower.load/loads/load_with_warnings/loads_with_warnings` | public | parser unit tests `:90-103`; parity uses `load_with_warnings`; CI smoke uses `load` | live |
| `numerics.NetworkArrays` | public | every numerics test; parity | live |
| `numerics.ybus/yf_yt` | public | dense `:176,:184`; pandapower `:93` | live |
| `numerics.bbus/bf/p_shift` | public | dense `:208`; pandapower `:110` | live |
| `numerics.ptdf` | public | dense `:227-262`; property; consumed by `lodf` | live |
| `numerics.lodf/bridges` | public | dense `:268-317`; bridge oracles on 5 fixtures + hypothesis | live |
| `bbus.branch_susceptance/incidence/pf_shift`, `ybus.branch_admittances` | module-level, not in `__all__` | internal callers in the same package | live |

No spec-mandated primitive lacks a caller. Numerics primitives have no `src` consumer yet by design (W5:
"the matrices every later solver consumes"); that is the wave's stated purpose, not dead substrate.

Findings:

1. **high — `Network.bus_index()` puts positional indices in `model`.** `src/mambo_power/model/network.py:52-54`
   returns `{bus.id: position}` over *all* buses. Epic §1 (NetworkArrays row): "positional ints exist only
   here [numerics]"; wave Design 7: "`numerics` is the only module that holds positional indices". Not asked
   for by any requirement; no `src` caller (`grep -rn "bus_index()" src tests` → one test). It also disagrees
   with `NetworkArrays.bus_index` the moment a bus is out of service (M1 tolerates type-4 buses, so this is a
   live case), and its existence invites M2 code to index by it. Fix: delete the method and
   `test_bus_index_is_positional`. Rated high because it is a boundary breach that a later wave would build
   on, not because anything is wrong today; deleting it is a one-line change that leaves no hole.
2. **low — F2 (carried from audit): spec says `load(path_or_text)`, code ships `load(path)` + `loads(text)`**
   (`matpower.py:97,102`). The split is the better contract — `json.load/loads` precedent, and sniffing
   "is this string a path or a case" is the kind of ambiguity that turns a filename containing `mpc.` into a
   parse. AC-8's command uses `load(path)` and works. Recommendation: amend the spec line W4 to
   `load(path) / loads(text)` and record A15; do not change the code.
3. **low — two representations of generator data in one frozen view.** `NetworkArrays` carries per-bus sums
   (`p_gen_pu … q_max_pu`, `v_set`; `arrays.py:156-168`) *and* per-generator arrays (`gen_p_pu … gen_v_set`;
   `:204-210`). Both are untouched by any M1 code; the per-bus set is derivable (`np.bincount(gen_bus, gen_p_pu)`).
   Shipping both before a consumer exists means M2's pf picks one and the other ages unused. Fix options:
   keep only the per-generator arrays and add a `per_bus()` helper, or keep both and add the agreement test
   named in Duplication 3. Either is fine; choosing now is cheaper than after M2 depends on one.
4. **note — the "one pu-conversion site" claim is sound** (`grep "/ base" src` → `arrays.py` only), and the
   importer correctly never converts (`matpower.py:297-345` copies MW/MVAr/kV verbatim).

---

## 4. Security — **PASS**

- Parser: no `eval`/`exec`/`pickle`/`subprocess`/`__import__`/`os.system` in `src` (`grep -rn -E` → none).
  Scanning is a single forward pass with an anchored regex (`^\s*mpc\.([A-Za-z_]\w*)\s*=\s*(.*)$`,
  `matpower.py:75`) — no nested quantifiers, no backtracking blow-up. `_collect_block` is iterative (`:179-201`);
  `bridges` is an explicit-stack Tarjan (`lodf.py:44-88`); `_check_connectivity` is a deque BFS — no recursion
  anywhere, so no depth attack. Token count is bounded by file length; NCOST larger than the row is rejected
  (`:384,:394`), so no allocation is driven by a number in the file.
- `load(path)` opens exactly the path the caller passes (`matpower.py:109`, `native.py:37`); there is no
  base-directory contract to traverse out of — this is a library call, not a service endpoint. Decoding uses
  `errors="replace"`, so undecodable bytes become U+FFFD and fail as BAD_NUMBER if they land in a number.
- CI: top-level `permissions: contents: read` (`.github/workflows/ci.yml:7-8`); no secrets referenced; jobs
  only build, test and install into throwaway venvs.
- Repo: `git grep` at 36bd20a for AWS/GitHub-token/private-key/api-key patterns (excluding `uv.lock`) → no
  hits. `uv.lock` contains only resolver metadata and hashes.
- Dependency surface: runtime `numpy, scipy, highspy, pydantic>=2` (`pyproject.toml:13-18`). `highspy` is
  declared but not imported anywhere (`grep -rn highspy src tests` → none) — it is the M3 LP backend per
  epic §5, so the declaration is a recorded decision, but until M3 every install pulls a compiled wheel
  nothing uses. Not a finding; note it in M3's slice as the moment the dependency earns its place.

Notes (no action required for M1):

1. **low — actions pinned to major tags** (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `ci.yml:32-33,52-53`)
   rather than commit SHAs. With `contents: read` the blast radius of a compromised action is the runner,
   not the repo. SHA-pinning plus Dependabot for actions is the OpenSSF recommendation; reasonable to adopt
   when M9 sets up release automation (which *will* need `id-token: write`).

---

## 5. Performance — **PASS**

- Sparse where it matters: Ybus/Yf/Yt/Bf/Bbus are CSC (`ybus.py:50-63`, `bbus.py:40-56`). PTDF factorises
  the reduced Bbus once with `splu` and solves all `n_branch` right-hand sides in one call
  (`ptdf.py:33-34`); the only dense objects are the PTDF and LODF results, which are dense by nature
  (≤ 3000 × 2000 doubles ≈ 48 MB at the 2000-bus ceiling; LODF ≤ 3000² ≈ 72 MB). No dense inverse anywhere.
- `bridges` is O(V+E) Python; `_check_connectivity` O(V+E); the parser is one pass over tokens. On case118
  `matpower.load` + `NetworkArrays` + Ybus/Bbus/PTDF/LODF all complete inside the 0.25 s parity call
  (durations output below, `test_pandapower_aligned_values_within_tolerance[case118]` 0.25 s *including*
  the pandapower comparison).
- Suite timing. Floor recorded 14.8 s wall (`record/m1-step5-tests-floor.md` §6). My runs on the same head:
  `uv run --no-sync pytest -q --durations=12` → `175 passed in 60.97s`; warm rerun `64.89s` (`WALL_MS=71326`).
  The 4-5× gap is environmental (other agents are active on this machine during the review) — label:
  **the absolute numbers are `unverified` as a regression**; the *distribution* is what matters:

  ```
  22.51s setup    tests/parity/test_matpower_vs_pandapower.py::test_counts_match_pandapower[case14]
   7.62s call     tests/property/test_numerics_properties.py::test_ybus_symmetric_without_phase_shift
   5.18s call     tests/parity/test_oracles_import.py::test_pypsa_imports
   2.49s call     tests/property/test_numerics_properties.py::test_reduced_bbus_is_nonsingular
   2.48s call     tests/property/test_numerics_properties.py::test_ptdf_slack_column_is_zero
   2.21s call     tests/property/test_numerics_properties.py::test_bridges_and_nan_lodf_columns_agree_with_removal
   2.12s call     tests/property/test_numerics_properties.py::test_bbus_row_sums_are_zero
   1.42s setup    tests/parity/test_matpower_vs_pandapower.py::test_counts_match_pandapower[case30]
   ...
   0.25s call     tests/parity/test_matpower_vs_pandapower.py::test_pandapower_aligned_values_within_tolerance[case118]
  ```

  The top item is the first `import pandapower` (+ `from_ppc` on case14), the third is `import pypsa`:
  oracle import cost, not our code. The property tier spends ~2 s per test generating 40 pydantic networks;
  the first test additionally pays hypothesis start-up. Nothing in `src` shows up.

Findings:

1. **low — redundant rebuilds inside one call chain.** `ptdf` calls `bbus(arr)` and `bf(arr)`; `bbus` calls
   `incidence` and `bf`; `bf` and `pf_shift` each recompute `branch_susceptance` (`bbus.py:45,54,61,67`) —
   three susceptance vectors and two incidence matrices per `ptdf` call. Microseconds at 118 buses,
   milliseconds at 2000; fix only if M2 calls `ptdf` in a loop (it should cache the LU instead).
2. **low — each property test regenerates the same 40 networks** (5 tests × 40 examples of
   `networks()`, `tests/property/test_numerics_properties.py:64-97`). Folding the five assertions into two
   tests (one Ybus/Bbus/PTDF invariants, one bridges/LODF) would roughly halve the tier. Optional.
3. **note — `on: push` + `on: pull_request`** (`ci.yml:3-5`) runs every PR commit twice. Free for a public
   repo; restrict `push` to `main`/`epic/**` if the macOS queue becomes the slow leg (A3 already anticipates).

---

## 6. Duplication — **FLAG**

Shared-truth pairs, anchored on wave Design 7 and epic §3:

| # | Concept | Site A | Site B | Agreement test | Status |
|---|---|---|---|---|---|
| 1 | pu conversion | `numerics/arrays.py:132,143,171` | — (no second site in `src`) | `test_ybus_vs_pandapower.py:93` (shunt/base inside Ybus vs pandapower), `test_numerics_arrays.py:209` (base 100 → 50 rescales) | single site, tested — OK |
| 2 | bus id → position | `NetworkArrays.bus_index` (`arrays.py:97`, in-service) | `Network.bus_index()` (`network.py:52`, all buses) | **none**; they *disagree* by construction when any bus is out of service | **FLAG** → Architecture 1 (delete B) |
| 3 | generator quantities | per-bus sums `arrays.py:156-168` | per-generator arrays `arrays.py:204-210` | **none** asserting `bincount(gen_bus, gen_*) == *_pu` (`test_numerics_arrays.py:176,189` check each against hand constants on one 4-bus case only) | **FLAG** → Architecture 3 |
| 4 | MATPOWER bus-type codes | importer decode `matpower.py:69-74` (`_BUS_TYPES`) | arrays encode `arrays.py:27` (`BUS_TYPE_CODE`) | **none** round-tripping file → model → `arr.bus_type` against the raw BUS_TYPE column; parity checks A against the oracle (`test_matpower_vs_pandapower.py:416`), unit checks B on a hand case (`test_numerics_arrays.py:147`) | **FLAG** (low) — one assertion in `test_ybus_vs_pandapower.py`'s `case` fixture closes it: `arr.bus_type == raw["bus"][perm, 1]` |
| 5 | MATPOWER column semantics | importer `matpower.py:297-340` | parity's `read_mpc_numpy` + `compare_raw` (`test_matpower_vs_pandapower.py:46-63,129-234`) and `internal_ppc` (`test_ybus_vs_pandapower.py:52-67`) | `test_raw_columns_within_tolerance`, `test_bus_types_and_service`, `test_counts_match_pandapower` (5 fixtures each) | **INTENDED** — this is the oracle. The second reader is deliberately written with different tools (`re` + `numpy.loadtxt`, no shared helper) so an importer bug cannot be mirrored. Keep. |
| 6 | dense re-derivation of Ybus/Bbus/PTDF/LODF | `numerics/*` | `test_numerics_dense.py:107-170` | the file *is* the agreement test | **INTENDED** oracle (epic §4). Keep. |
| 7 | bridge detection | numeric `lodf.py:36` (`|1−h_kk| < tol`) | graph `lodf.py:44` (Tarjan) | `test_numerics_dense.py:272-281`, property `:120-130`, plus removal-BFS oracle on 5 fixtures `test_ybus_vs_pandapower.py:124` | **INTENDED** cross-check, documented at `lodf.py:10-12`. OK |
| 8 | slack-count rule | `validate_network` NO_SLACK/MULTIPLE_SLACK (`network.py:170-179`) | `NetworkArrays.from_network` `ValueError` (`arrays.py:100-103`) | none for B (Correctness 4) | low — B is a defensive re-check because models are mutable (A7); acceptable, but test it |
| 9 | validation vs pydantic constraints | all bounds in `validate_network` (A6) | entity `Field(description=…)` text only, no `gt=`/`ge=` | snapshot test proves the schema carries no machine bounds | single site by decision (A6) — OK; A6's "json_schema_extra" candidate stays open |
| 10 | `_label` int-as-string | `matpower.py:409` (handles non-integers via `repr`) | parity `_label` (`test_matpower_vs_pandapower.py:122`, integers only) | `compare_raw` asserts `bus.area/zone == _label(row)` on 5 fixtures | INTENDED oracle side; OK |
| 11 | fixture list | three copies (Readability 2) | — | none | low — not a correctness pair, a maintenance one |

Findings:

1. **high (shared with Architecture 1) — pair 2 has two implementations that legitimately disagree and no
   test.** Fix is deletion of `Network.bus_index()`.
2. **low — pair 3**: if both representations stay, add one assertion in `test_numerics_arrays.py`:
   `np.bincount(arr.gen_bus, weights=arr.gen_p_pu, minlength=arr.n_bus) == arr.p_gen_pu` (and the five
   siblings), plus the same on a fixture-derived `NetworkArrays` where multiple generators share a bus
   (case30 bus 2, case118 several).
3. **low — pair 4**: one line in the parity `case` fixture (`test_ybus_vs_pandapower.py:70-90`) closes it.
4. Explicitly stated, per the brief: the importer-vs-parity-reader duplication (pair 5) and the dense
   re-derivation (pair 6) are **intended** oracles and must *not* be deduplicated; sharing a helper between
   them would remove the independence the AC-6/AC-7 evidence depends on.

---

## Closing table

| Axis | Verdict | Driving finding |
|---|---|---|
| 1. Correctness | **FLAG** | F1 proof gap on fixtures; validator lets self-loop / `tap_ratio<=0` / `r=x=0` through to NaN matrices |
| 2. Readability | **FLAG** (low) | test-module import hack; triplicated fixture list; dead `_Matrix.line` |
| 3. Architecture | **FLAG** | `Network.bus_index()` holds positional ints inside `model` (epic §1 / Design 7); F2 → amend spec, keep code |
| 4. Security | **PASS** | no eval/recursion/traversal; `contents: read`; no secrets; actions tag-pinned (note) |
| 5. Performance | **PASS** | sparse + splu as specified; suite time is oracle import + hypothesis, not `src` |
| 6. Duplication | **FLAG** | bus-index pair with no agreement test; two gen representations; oracle duplication is intended and says so |

Recommended order of fixes for the review-fold commit: Architecture 1 (delete one method + one test) →
Correctness 2-3 (three `BAD_RANGE` checks + one `ValueError`, with negative tests) → Correctness 1 (F1
parametrisation) → Duplication 3-4 and Correctness 4 (agreement/guard tests) → Readability 1-5 as time
allows. F2 is a spec edit plus A15, not a code change.
