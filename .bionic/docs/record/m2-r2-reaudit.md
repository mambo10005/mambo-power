# M2 re-audit — Step 5 exit gate, scoped (AC-5 / AC-8 / AC-11)

Auditor: m2-r2-reaudit (fresh, read-only; implemented nothing in M2). Date: 2026-08-23.
Worktree `C:\Claude Projects\mambo-power-m2`, branch `wave/02-power-flow`, HEAD
`b7711977155976b3194b66e1b1c7b2a628f23aec` (the R1 fold commit, pushed, CI run `32663188881`
8/8 per the fold report — not re-verified via `gh` here, out of scope for a proof-gap
re-audit). `git status --porcelain` empty before and after every command below. `uv` =
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`; `uv sync --locked
--all-groups` → `Resolved 102 packages … Checked 98 packages` (no drift from the fold report).

Scope: this is **not** a fresh Step-5 audit. The original audit (`record/m2-audit.md`) already
ran the full coverage/power/authenticity pass and returned `REFUTED` on exactly two proof gaps
(AC-5, AC-8) plus one coverage hole that produced a new AC-11 matrix row. This re-audit verifies
only that the R1 fold (`record/m2-r1-fold-report.md`, commit `b771197`) actually closed those
three, re-executes the specific new evidence, spot-checks the two critic issues the fold also
claims to have folded in, and confirms no collateral damage from the self-review items (F-J).

---

## 1. AC-5 — repaired `case14_island` AC solve vs pandapower on the main island

**Claim (fold report):** new test `tests/parity/test_ac_vs_pandapower_island.py` proves the
clause at the auditor's original measured tier (≈1e-14 pu / ≈1e-13 deg).

**Re-executed:**

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/parity/test_ac_vs_pandapower_island.py -v
tests\parity\test_ac_vs_pandapower_island.py .                           [100%]
1 passed in 4.58s
```

**Independence check (read, not just run).** `tests/parity/test_ac_vs_pandapower_island.py:58-80`:
- loads `case14_island.m` via `mambo_power.io.matpower.load_with_warnings` — the real repair
  path (bus-8/gen-5 deactivated via `ISLAND_DEACTIVATED`), not a hand-built network;
- independently builds the pandapower oracle from the *same raw MATPOWER matrices*
  (`tests.parity._mpc_reader.read_mpc_numpy` → `pandapower_from_raw`, same `BASE_KV`
  substitution and `trafo_model="pi"` convention `test_ac_vs_pandapower.py` uses for every
  other fixture) and runs pandapower's own `runpp(enforce_q_lims=True, ...)`;
- pandapower reaches the main island through its *own* connectivity check
  (`check_connectivity=True`, the default), not through mambo-power's repair — the test asserts
  `pp.res_bus.loc[bus-8].vm_pu` is `NaN`, i.e. pandapower drops bus 8 independently. The two
  paths converge on the same 13-bus main island from opposite directions;
- compares all 13 main-island buses' `vm`/`va` at `TOL_VM = 1e-14` / `TOL_VA_DEG = 1e-13`, with
  the docstring citing these as one order of magnitude of headroom over the auditor's measured
  figures, not a number picked to be trivially satisfiable.

This is not a rubber stamp: no hardcoded expected value, no self-derived oracle — the two
solves are computed by different code paths (mambo-power's Newton solver vs. pandapower's) from
the same upstream bytes.

**Independent re-measurement** (own script, not the test's own printed output — pytest suppresses
prints on pass, so I re-ran the same computation standalone to get the actual numbers):

```
$ PYTHONPATH=<worktree> uv run --no-sync python <scratch>/verify_ac5.py
worst vm ('bus-7', 8.881784197001252e-16)
worst va ('bus-12', 4.440892098500626e-14)
```

Matches the original auditor's probe (`m2-audit.md` §3: `8.9e-16 pu` / `4.4e-14 deg`) to the
last printed digit, and matches the fold report's claimed re-run figures exactly.

**Verdict: CONFIRMED.**

---

## 2. AC-8 — `pf.ac_newton` API reference coverage

**Claim (fold report):** `docs/api/pf.md` now carries a `::: mambo_power.pf.ac_newton` block;
new test `tests/unit/test_api_docs_coverage.py` is a real regression guard; `mkdocs build
--strict` still exits 0 and the built site renders the five previously-missing public names.

**Read** `docs/api/pf.md:14-16` — `## AC solver over arrays` / `::: mambo_power.pf.ac_newton`,
same style as the pre-existing `pf.dc` block.

**Re-executed the new test:**

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_api_docs_coverage.py -v
tests\unit\test_api_docs_coverage.py ..                                  [100%]
2 passed in 0.78s
```

**Planted-miss check** (not just reasoning about the assertion shape — actually removed the
fix and re-ran): commented out `## AC solver over arrays` + `::: mambo_power.pf.ac_newton` from
`docs/api/pf.md` (backed up first), re-ran:

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_api_docs_coverage.py -v
FAILED tests/unit/test_api_docs_coverage.py::test_every_public_symbol_is_reachable_from_an_api_page
AssertionError: submodule symbols missing from docs/api pages:
  mambo_power.pf.ac_newton: allocate_generation, flat_start, newton, newton_raphson, specified_injection
1 failed, 1 passed in 0.90s
```

This reproduces the **exact five names** the original auditor's hand probe found missing
(`m2-audit.md` §3: `newton, newton_raphson, flat_start, specified_injection,
allocate_generation`). Restored the file (`git status --porcelain` clean immediately after).
This is a genuine regression guard, not a test that would pass regardless.

**mkdocs build + rendered-site grep (mirroring the original auditor's probe):**

```
$ uv run --no-sync mkdocs build --strict -d <scratch>/audit-site
INFO    -  Documentation built in 4.88 seconds
exit 0
$ grep -rl newton_raphson <site>/api | wc -l        -> 1  (was 0)
$ grep -rl allocate_generation <site>/api | wc -l   -> 1  (was 0)
$ grep -rl flat_start <site>/api | wc -l            -> 1  (was 0)
$ grep -rl specified_injection <site>/api | wc -l   -> 1  (was 0)
```

**Verdict: CONFIRMED.**

---

## 3. AC-11 — `PROVENANCE.md` case300 licence wording

**Claim (fold report):** new test asserts the MATPOWER licence-exclusion sentence text and the
no-BSD-claim property, not just the sha256 (already covered by a pre-existing test).

**Read** `tests/unit/test_fixture_case300.py::test_provenance_case300_entry_carries_the_licence_exclusion_and_no_bsd_claim`
(lines 45-57): extracts the `### case300.m` entry from `PROVENANCE.md`, asserts (a)
`"not covered by MATPOWER's BSD licence"` is present in the entry, (b) the sha256 is quoted
there (secondary, cross-referencing — the primary sha256 proof is the pre-existing
`test_bytes_are_the_recorded_upstream_blob`), and (c) none of `"is BSD"` / `"under the BSD"` /
`"BSD-licensed"` / `"BSD licensed"` appears anywhere in the entry — the property the audit's
coverage-hole finding was actually about (W7 had no criterion for this clause at all).

**Re-executed:**

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_fixture_case300.py -v
tests\unit\test_fixture_case300.py ....                                  [100%]
4 passed in 0.47s
```

**Verdict: CONFIRMED.**

---

## 4. Critic issue 1 — architecture diagram edges

```
$ grep -n "ac -->\|pf -->\|jobs -->" docs/design/architecture.md
33:    pf --> numerics
34:    pf --> results
35:    pf --> model
37:    ac --> numerics
38:    jobs --> pf
39:    jobs --> results
40:    jobs --> model
41:    jobs --> numerics
```

`ac --> results` is gone (the fabricated edge); `pf --> model` and `jobs --> numerics` are both
present (the two missing real edges). Matches the fix claimed in the fold report. `mkdocs build
--strict` (run above) still exits 0, so the corrected diagram still parses. **Closed.**

## 5. Critic issue 2 — fabricated gridlab-w1 provenance text

```
$ grep -n "packages/\|Node suite\|browser harness\|engine-pf\|W1-R5" \
    fixtures/matpower/PROVENANCE.md fixtures/matpower/SOURCES.md
PROVENANCE.md:204: (Note: earlier drafts of this file carried references to a `packages/`
PROVENANCE.md:205: monorepo, a Node/TypeScript test suite and a browser harness, inherited …
```

Only 2 hits remain, both inside the fold's own explanatory note describing what was removed
(not a live claim) — matches the fold report's account (8 → 2, both in the new note).
`SOURCES.md` has zero hits (was 2 pre-fold). Sha256/licence content re-verified intact:

```
$ grep -n "69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5\|BSD license\|not covered" \
    fixtures/matpower/PROVENANCE.md
29:> The code in MATPOWER is distributed under the 3-clause BSD license below. The
30:> MATPOWER case files distributed with MATPOWER are not covered by the BSD
119:- **Source:** … Pinned: … sha256 `69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5` …
134:  MATPOWER, not covered by MATPOWER's BSD licence (`record/m2-research.md` …
```

**Closed.**

---

## 6. No collateral damage

```
$ uv run --no-sync pytest -q -p no:cacheprovider
492 passed, 10 warnings in 39.59s
```

Matches the fold report's claimed 484 → 492 exactly (+8: island parity, api-docs-coverage ×2,
provenance wording, RecursionError regression, bound + divergence guard ×2, DC
UNSOLVABLE_NETWORK).

```
$ uv run --no-sync ruff check .            -> All checks passed!
$ uv run --no-sync ruff format --check .   -> 101 files already formatted
$ uv run --no-sync mypy                    -> Success: no issues found in 32 source files
$ uv run --no-sync mkdocs build --strict   -> exit 0, "Documentation built in 4.88 seconds"
```

**AC-1/AC-2 (and AC-3) tiers untouched despite the divergence guard and iteration-bound edits
sharing the same solver loop:**

```
$ uv run --no-sync pytest -q -p no:cacheprovider \
    tests/parity/test_ac_vs_pandapower.py tests/parity/test_dc_vs_pandapower.py -v
62 passed in 11.79s   (37 AC + 25 DC — same counts as the original audit's re-execution)
```

All AC parity tests still pass at their original tolerances; nothing in items F-J (RecursionError
catch, max_iter/max_q_rounds bounds + divergence guard, `AcPowerFlowResult.message`,
`UnsolvableNetworkError`/`UNSOLVABLE_NETWORK`, shared `absorb_slack_p`) weakened or broke an
already-CONFIRMED row. The self-review's own items F-J each carry their own new/edited tests,
all included in the 492-pass full-suite run above.

---

## Verdict

| Row | Verdict | Evidence |
|---|---|---|
| AC-5 | **CONFIRMED** | `test_ac_vs_pandapower_island.py` passes, is a genuine independent comparison (repair path vs. pandapower's own connectivity check), re-measured 8.88e-16 pu / 4.44e-14 deg — matches the original audit's probe exactly. |
| AC-8 | **CONFIRMED** | `docs/api/pf.md` carries the `:::` block; `mkdocs build --strict` exit 0; built site renders all 4 previously-missing names; the new coverage test, planted-miss-verified, reproduces the exact original 5-name gap when the fix is reverted. |
| AC-11 | **CONFIRMED** | New test asserts both the licence-exclusion sentence text and the no-BSD-claim property (distinct from the pre-existing sha256 test) — matches what the coverage hole actually required. |

**Wave verdict: CONFIRMED** (replacing `auditor-wave: REFUTED` from `m2-audit.md` §4,
2026-08-21). The fold closed all three proof gaps the original audit found, with real,
independently-verified evidence — not rubber-stamped tests. The two critic issues (architecture
diagram, fabricated provenance text) it also claims to have folded in are both spot-checked
closed. No collateral damage: full suite 492/492, ruff/mypy/mkdocs all clean, and the solver
parity tiers the self-review's fixes shared code with (AC-1/AC-2/AC-3) are unchanged at their
original tolerances.

No open items. Nothing in this re-audit's scope is short.
