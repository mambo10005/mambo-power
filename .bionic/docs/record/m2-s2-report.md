# M2 S2 report — effective bus roles (W3) and importer island repair (W4)

Wave M2 "power-flow", slice S2 "roles-islands" (spec W3, W4, AC-4, AC-5; design items 2 and 4).
Worktree `C:\Claude Projects\mambo-power-m2`, branch `wave/02-power-flow`, base `011698c` (S1);
S3 committed `41e531b` in the same worktree while this slice ran. Written 2026-08-20 (local;
UTC 2026-08-21 ~03:45). Every claim carries its command and output or is marked `unverified`.

**Commit:** `5d4110304fb64e281f251377fece2f7d9b189a8b` — not pushed. No hook blocked.
**Tests:** 380 passed whole tree (308 at S1 + S3's + **25 new in this slice** + 1 rewritten).

## 1. Warnings API decision

Kept `load_with_warnings` / `loads_with_warnings` → `tuple[Network, list[str]]` **unchanged
in type** (M1 callers: `test_matpower_parser`, `test_matpower_vs_pandapower`,
`test_fixture_case300` — all untouched and green) and **added** the typed path:

- `model/warnings.py`: `ImportWarning` (pydantic, frozen, `extra="forbid"`) with
  `code: Literal["ISLAND_DEACTIVATED", "BASE_KV_REPLACED", "GENCOST_REACTIVE_IGNORED"]`,
  `message`, `bus_ids`, `element_ids`; `str(w) == f"{code}: {message}"`.
- `io/report.py`: `ImportReport(warnings: list[ImportWarning])` with `.codes` and
  `.as_strings()`.
- `io/matpower.py`: `load_with_report` / `loads_with_report` → `(Network, ImportReport)`.
  `load_with_warnings` is now literally `report.as_strings()`, so **both APIs come from the
  same objects** — there is no second warning path to drift.

Consequence for the legacy strings: M1's two existing warnings now carry a code prefix
(`BASE_KV_REPLACED: bus-1: BASE_KV is 0; base_kv set to 1.0 (line 41)`,
`GENCOST_REACTIVE_IGNORED: mpc.gencost has …`). Existing tests only substring-match
(`"bus-1" in w`, `"gencost" in w`, `"base_kv" in w or "BASE_KV" in w`) so nothing broke; the
prefix makes the legacy list uniform with the island line the dispatch asked for
(`ISLAND_DEACTIVATED: …`). If anyone parses those strings exactly, this is the change to know
about.

Name collision, acknowledged: `mambo_power.model.ImportWarning` shadows
`builtins.ImportWarning` inside any module that imports it unqualified. The spec names the
type so; it is a pydantic record, never passed to `warnings.warn`, and the module docstring
says so. Renaming is a one-line follow-up if the lead prefers (`ImportNotice`?).

## 2. Effective roles (W3, design item 2)

`numerics/roles.py` — `EffectiveRoles` (frozen dataclass: `bus_type`, `v_set`, `demoted_pv`,
`setpoint_conflicts`) and `effective_roles(arr)`; `numerics/errors.py` —
`NoSlackGeneratorError(Exception)` with `.bus_id`, `.position`; `SetpointConflictWarning(UserWarning)`.
All exported from `mambo_power.numerics`. `NetworkArrays` unchanged (declared roles; its
`v_set` still first-gen — `effective_roles` is where last-gen lives).

Rules implemented exactly as the spec/research state: PV without in-service gen → PQ
(MATPOWER `bustypes`, pandapower `build_gen`); slack without in-service gen → raise (no
MATPOWER re-slack); multi-gen setpoint = last in-service generator in generator order
(MATPOWER `runpf.m:296`), `warnings.warn(SetpointConflictWarning)` naming bus, gens and both
values when they differ by more than `SETPOINT_TOL = 1e-9` pu. `v_set = 1.0` at buses with
no generator; PQ buses with a generator still carry its setpoint (MATPOWER sets `V0` at every
generator bus) — solvers pick by role.

## 3. Island repair (W4, design item 4)

`model/islands.py` — `repair_islands_entities(buses, branches, generators, loads, shunts,
storage) -> (…six lists…, list[ImportWarning])` operates on raw entity lists **before**
validation (BFS from every in-service slack over in-service branches with in-service
endpoints; unreached in-service buses and their in-service branches/gens/loads/shunts/storage
get `model_copy(update={"in_service": False})`; inputs never mutated; one warning **per
island component**, in bus order; already-out elements are not listed). `repair_islands(net)`
runs it on `net`'s lists and constructs a new `Network(...)` (re-validates). With no
in-service slack nothing is changed (that is `NO_SLACK`'s job). Both exported from
`mambo_power.model`.

`io/matpower.py::_build` calls `repair_islands_entities` right before `Network(...)`;
`load`/`loads` discard the warnings. `Network.model_validate(raw)` with the island re-enabled
still raises `DISCONNECTED_BUS` (asserted in two tests). `_check_connectivity` in the model
is untouched.

## 4. Tests

New: `tests/unit/test_effective_roles.py` (10 collected: 6 single tests + 1 test over 4
upstream fixtures), `tests/unit/test_islands.py` (12), `tests/parity/test_roles_vs_pandapower.py` (3).
Rewritten: `tests/unit/test_fixtures_derived.py::test_island_raises_disconnected_bus_today` →
`test_island_is_repaired_by_the_importer_and_rejected_by_the_model`.

```
$ uv run pytest --co -q tests/unit/test_effective_roles.py tests/unit/test_islands.py tests/parity/test_roles_vs_pandapower.py
25 tests collected in 1.12s
```

RED (tests written first; before any `src` change):
```
$ uv run pytest -q -p no:cacheprovider tests/unit/test_effective_roles.py tests/unit/test_islands.py \
    tests/parity/test_roles_vs_pandapower.py tests/unit/test_fixtures_derived.py
E   ImportError: cannot import name 'EffectiveRoles' from 'mambo_power.numerics'
E   ImportError: cannot import name 'ImportWarning' from 'mambo_power.model'
E   ImportError: cannot import name 'SetpointConflictWarning' from 'mambo_power.numerics'
ERROR tests/unit/test_effective_roles.py
ERROR tests/unit/test_islands.py
ERROR tests/parity/test_roles_vs_pandapower.py
3 errors in 3.14s
$ uv run pytest -q -p no:cacheprovider tests/unit/test_fixtures_derived.py
E           mambo_power.model.errors.NetworkValidationError: Network validation failed with 1 issue:
FAILED tests/unit/test_fixtures_derived.py::test_island_is_repaired_by_the_importer_and_rejected_by_the_model
1 failed, 8 passed in 0.93s
```

First run after implementation: 66 passed, 4 failed, 3 errors — all three were **test
premises**, not code: (a) case14 carries `BASE_KV = 0` on every bus, so the legacy list holds
14 `BASE_KV_REPLACED` lines *plus* the island line (tests now filter by prefix/code; "exactly
one ISLAND_DEACTIVATED" still holds); (b) the two-slack hand case also trips
`DISCONNECTED_BUS` because the model's own BFS starts from the first slack only (asserted
`{"MULTIPLE_SLACK", "DISCONNECTED_BUS"}`); (c) pandapower's trafo model divides by
`BASE_KV`, so the oracle copy gets the importer's `1.0` substitution first — the same step
the research probes took (record/m2-research.md §1.2).

GREEN — static, whole tree minus `docs/` (another agent's uncommitted docs slice; see §6):
```
$ uv run ruff check . --exclude docs          -> All checks passed!         exit=0
$ uv run ruff format --check . --exclude docs -> 57 files already formatted exit=0
$ uv run mypy                                 -> Success: no issues found in 26 source files  exit=0
```
GREEN — tests, whole tree, nothing excluded (S3 had committed by then):
```
$ uv run pytest -q -p no:cacheprovider
380 passed, 10 warnings in 32.32s            exit=0
```
The 10 warnings are the pre-existing pandapower `from_ppc` RuntimeWarnings (case14/case57
`BASE_KV = 0`) and the case30 pandas FutureWarning; my parity module adds one more of the
same `from_ppc` kind on case14_roles.

### AC-4 oracle facts pinned by `test_roles_vs_pandapower.py`

- bus 6 (declared PV, only gen out): pandapower `_ppc.bus[5, BUS_TYPE] == 1` (PQ) and
  `res_bus.vm_pu` differs from VG 1.07 by > 1e-3 → PQ behaviour; ours: effective PQ, declared PV.
- buses 3 and 8 (single in-service gens) pinned at 1.01 / 1.09 within 1e-9.
- bus 2 (two gens, VG 1.045 then 1.055): pandapower's **converter** pins 1.045 (first row,
  `from_ppc` `drop_duplicates(keep="first")`), ours 1.055 (MATPOWER last-wins) with the
  warning. Both numbers are asserted so a change on either side is visible. This is the one
  place W3 and the pandapower *converter* disagree by design; pandapower's *solver* would
  refuse the input outright.

### AC-5 on case14_island

bus-8 and gen-5 deactivated, branch-14 (7-8) already out (it is the edit), 13/19/4 live
buses/branches/gens, one `ISLAND_DEACTIVATED` warning with `bus_ids=["bus-8"]`,
`element_ids=["gen-5"]`. Note for the lead: the dispatch expected "its load" — bus 8 carries
no load or shunt in case14 (PD = QD = GS = BS = 0), so there is none to deactivate; the
hand case in `test_islands.py` covers loads, open/closed branches, already-out generators
and two separate islands.

## 5. Commit

```
$ git add <the 12 paths below>     (explicit; nothing of S3's or the docs slice)
$ git commit -q -F <message with the two trailers exactly>   commit-exit=0
$ git show --stat HEAD
commit 5d4110304fb64e281f251377fece2f7d9b189a8b
Author: Manho Joung <manhojoung@gmail.com>
Date:   Thu Aug 20 20:40:23 2026 -0700

    feat(m2/S2): effective bus roles (MATPOWER last-VG + conflict warning) and importer island repair with ISLAND_DEACTIVATED warnings; model stays strict

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 src/mambo_power/io/matpower.py           |  90 +++++++++---
 src/mambo_power/io/report.py             |  31 +++++
 src/mambo_power/model/__init__.py        |   9 +-
 src/mambo_power/model/islands.py         | 196 ++++++++++++++++++++++++++
 src/mambo_power/model/warnings.py        |  47 +++++++
 src/mambo_power/numerics/__init__.py     |   7 +
 src/mambo_power/numerics/errors.py       |  39 ++++++
 src/mambo_power/numerics/roles.py        | 107 +++++++++++++++
 tests/parity/test_roles_vs_pandapower.py |  80 +++++++++++
 tests/unit/test_effective_roles.py       | 131 ++++++++++++++++++
 tests/unit/test_fixtures_derived.py      |  24 ++--
 tests/unit/test_islands.py               | 229 +++++++++++++++++++++++++++++++
 12 files changed, 963 insertions(+), 27 deletions(-)
$ git status --short   (after)
 M pyproject.toml        # not mine — docs slice in flight
 M uv.lock               # not mine
?? docs/                 # not mine
?? mkdocs.yml            # not mine
```

## 6. Judgment calls and open items

1. **Per-island warnings, not one global warning.** One `ImportWarning` per connected
   component of the unreached set; case14_island has one island so AC-5's "an
   `ISLAND_DEACTIVATED` warning" holds; the hand case shows two.
2. **Already-out elements are not listed** in `element_ids` (only what the repair flipped).
   So for case14_island `branch-14` is out of service but not in the warning — it was the
   file's own edit, not a repair.
3. **No slack → no repair.** Deactivating everything would turn a `NO_SLACK` file into an
   empty valid-looking network; leaving it alone lets the model name the real problem.
4. **Per-island slacks out of scope.** The repair keeps both islands (neither is unreachable
   from *a* slack); the model rejects with `MULTIPLE_SLACK` + `DISCONNECTED_BUS`. Documented
   in `islands.py` and the test.
5. **`SETPOINT_TOL = 1e-9` abs** for "setpoints differ" (pandapower uses `np.allclose`
   defaults, 1e-5 rel; MATPOWER never compares). Tight on purpose: a 1e-6 pu disagreement is
   still a disagreement worth a warning; easy to loosen.
6. **`ImportWarning` name shadows the builtin** (spec-named; see §1). Flag if unwanted.
7. **Shared worktree state.** A docs slice has uncommitted `docs/`, `mkdocs.yml`,
   `pyproject.toml` (+5 lines, a `docs` group, presumably) and `uv.lock`. `ruff format
   --check docs/hooks/rest_roles.py` fails on that file today — not mine, not touched; my
   static gate ran with `--exclude docs`. `uv run` resynced against the modified lock without
   error, so the 380-test run is on the tree as it stands.
8. `results/from_arrays.py:50` and `pf/dc.py` (S3) still say "until W3's `effective_roles`
   is routed through here" — routing the effective roles into `pf.ac`/`results` is the AC
   solver slice's job; `effective_roles` has the shape S3's docstrings anticipate.
