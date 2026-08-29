# M3 Step 5/6 — R1 fold report (audit finding)

Agent: m3-r1-fold. Date: 2026-08-23/24. Worktree `C:\Claude Projects\mambo-power-m3`, branch
`wave/03-opf-n1`, base `f37815a` → **commit `8fc8581`** (pushed). `uv` =
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`; `uv sync --locked --all-groups`
→ `Resolved 102 packages … Checked 98 packages` (uv.lock untouched, no new dependencies —
`pypsa` was already a regular, non-dev dependency per `pyproject.toml`). Every claim below
carries its command/output or a `file:line`, or is labelled `unverified`.

Scope: exactly the 6 items (A-F) named in the dispatch — `m3-audit.md`'s one refuted row
(AC-1's undischarged PyPSA half) and citation-precision nit (AC-4), and `m3-walk-docs-site.md`'s
two real findings (stale home page, MathJax rendering) plus a minor docstring leak. Nothing else
from the audit or walk was in scope, and nothing else was touched.

Method: for A (RED/GREEN, TDD), the failing reproduction was confirmed before the fix — since
the "fix" is the PyPSA test itself, RED here means "the test fails without the diagnostic's
proven `p_set`-clear step", demonstrated directly (not inferred). For E, the broken state was
reproduced first, in a real browser against a real build, before any edit — a genuine
before/after, not just an after.

---

## Baseline (before any edit, HEAD f37815a)

```
git status --porcelain   -> (empty)
uv run --no-sync pytest -q -p no:cacheprovider   -> 573 passed (per record/m3-step5-tests-floor.md)
```

---

## Fold items

### A. AC-1's PyPSA gap — promote the diagnostic to a committed test

- **RED**: `tests/parity/test_opf_vs_pypsa.py` written with the diagnostic's proven fix
  (`n.generators["p_set"] = float("nan")` before `optimize()`) temporarily removed. Ran
  `uv run --no-sync pytest -q tests/parity/test_opf_vs_pypsa.py::test_pypsa_itself_converges_optimal -k case14`
  → `1 failed`, HiGHS solver log: `Model status: Infeasible`, `Bound [0e+00, 0e+00]` — the exact
  symptom `.bionic/tmp/m3-pypsa-diag-result.md` diagnosed (every generator's dispatch pinned to
  MATPOWER's unbalanced base-case `PG`, zero degrees of freedom). Restored the fix, re-ran: pass.
- Changed: `tests/parity/test_opf_vs_pypsa.py` (new, 195 lines) — mirrors
  `tests/parity/test_opf_vs_pandapower.py`'s shape exactly (module-scoped `Case` fixture
  parametrized over the 5 fixtures, one test per assertion). Bridges MATPOWER `gencost` columns
  4/5 (`c2`/`c1`) straight into `n.generators["marginal_cost_quadratic"]`/`["marginal_cost"]`
  (PyPSA's import path does not read `gencost` at all — column 6/`c0` is added to `n.objective`
  for comparison, though it is exactly `0.0` on all 5 fixtures, checked directly, not assumed);
  `overwrite_zero_s_nom=9999.0` (the diagnostic's value, matching the pandapower test's own
  confirmed "no branch is rated" fact).
- **Measured fresh, not hardcoded from the diagnostic** (forced with temporary `TOL=0.0` to read
  exact residuals from assertion failures, then restored to real values):

  | fixture | cost rel. diff | worst dispatch abs. diff (MW) |
  |---|---|---|
  | case14 | 7.50e-14 | 2.29e-05 |
  | case_ieee30 | 9.68e-14 | 2.80e-05 |
  | case57 | 2.98e-13 | 3.31e-04 |
  | case118 | 1.27e-12 | 1.87e-03 |
  | case300 | 7.37e-05 (~0.0074%) | 8.21e-02 |

  Tolerances pinned with margin above measured: `TIGHT_COST_REL_TOL=1e-9`,
  `TIGHT_DISPATCH_ABS_TOL_MW=0.01` (case14/case_ieee30/case57/case118); `WIDE_COST_REL_TOL=2e-4`,
  `WIDE_DISPATCH_ABS_TOL_MW=0.5` (case300 alone) — matching the diagnostic's own ~0.007% finding
  almost exactly (7.37e-05 measured vs ~0.007% ≈ 7e-05 diagnosed), not investigated further here
  either (named as a still-open carry-over — see "Not done" below).
- **GREEN**: `uv run --no-sync pytest -q -m parity tests/parity/test_opf_vs_pypsa.py -v` →
  `20 passed` (5 fixtures × 4 tests: converges, PyPSA-itself-converges sanity check, cost match,
  dispatch match).

### B. AC-4's citation nit — `provenance: W3` → `W3, W5`

- Changed: `.bionic/docs/specs/epic-01-foundation/wave-03-opf-n1.spec.md:144` (not git-tracked —
  `.bionic` is entirely gitignored, `.bionic/.gitignore` has a bare `*`; this mirrors M1/M2's own
  fold reports, which reference `.bionic/docs/...` freely as local record/spec/plan scaffolding
  outside the commit history). One line, matching the audit's own recommended fix exactly.

### C. Matrix status-cell precision

- Investigated the summary table's AC-1 status cell (`.bionic/docs/plans/…/wave-03-opf-n1.plan.md`
  Verification Matrix): it already read a bare `discharged` (no qualifier) *before* this fold —
  the audit's finding (§6) was that this bare cell was misleading given the PyPSA gap it sat two
  lines above. With item A closing that gap for real, the bare `discharged` cell is now honestly
  true and needs no qualifier — exactly the target state the brief described ("it should no
  longer need the qualifier the audit asked for"). **No edit was needed to the status cell
  itself.** What *was* edited: AC-1's `tier-run:`/`readback:` evidence block, appending the R1
  fold's PyPSA tier-run (test file, RED/GREEN, measured residuals — same content as item A above)
  and rewriting the readback to state both halves are now fully evidenced. The `auditor-wave:`
  narrative line and each row's own `auditor` column were **not** touched, per the brief (that is
  the re-audit's job, not the fold's).

### D. Home page staleness

- Read the walk artifact's exact quoted text first (`m3-walk-docs-site.md`'s "Home page"
  section: status callout still said "Wave M2 … is in progress", "where to go next" had no
  OPF/N-1 row, roadmap listed M3 as "planned"). Verified independently that M2 is in fact merged
  into `epic/01-foundation` (`dcdc1c9 merge(m2): wave/02-power-flow into epic/01-foundation`,
  confirmed via `git log --oneline epic/01-foundation` in the main checkout) and M3 is not yet
  merged (still on its own wave branch, this fold's own worktree).
- Changed: `docs/index.md` — status callout rewritten: "Wave M1 … and wave M2 … are both merged.
  Wave M3 … is in progress on its own wave branch, with everything below shipped there" (mirrors
  M2's home page's own phrasing pattern for itself, applied one wave later), naming
  `opf.solve_dc_opf`/`manual/opf.md` and `contingency.n1`/`manual/n1.md` and linking both. "Where
  to go next" table gained two rows (DC-OPF, N-1 screening) pointing at the new manual pages.
  Roadmap table: M2 row `in progress` → `merged`; M3 row `planned` → `in progress`, description
  widened to "DC optimal power flow with duals … N-1 branch-contingency screening" (matching the
  wave spec's own title, not the old pre-wave placeholder text).
- **GREEN**: `uv run --no-sync mkdocs build --strict -d <scratch>` → exit 0 both immediately after
  this edit and again in the final full gate below.

### E. MathJax rendering — root-caused and fixed

- **Reproduced the broken state first**, before any edit: `git stash push -- docs/javascripts/mathjax.js mkdocs.yml`
  (isolating just those two files at their pre-fold content), `mkdocs build --strict` to a scratch
  dir, served over a local `python -m http.server`, driven with `chrome-devtools` against
  `manual/opf/` (a page this fold never touches, same page the walk screenshotted):
  ```
  {"total":6,"processed":3,"raw":3, samples: ["\(p0,c0,\dots,pn,cn\)" (raw), "\[...\text{cost}_g...\]" (raw)]}
  ```
  3 of 6 `arithmatex` blocks left unprocessed (raw TeX visible in the DOM, `mjx-container` absent)
  — reproduces the walk's screenshots exactly. Screenshot saved:
  `<scratchpad>/mathjax-before-fix.png`. `git stash pop` restored the fold's working tree.
- **Root cause** (read `docs/javascripts/mathjax.js` and `mkdocs.yml`'s `arithmatex`/MathJax
  config directly, as instructed): the config's `inlineMath`/`displayMath` delimiters were
  written as JavaScript string literals `"\("`, `"\)"`, `"\["`, `"\]"`. In a JS double-quoted
  string, `\(` is not a recognized escape sequence — JavaScript silently drops the backslash,
  so the string MathJax actually receives is `"("`, not `"\("`. MathJax therefore ended up
  configured to match bare `(`/`)`/`[`/`]` characters as math delimiters instead of the literal
  `\(...\)`/`\[...\]` sequences `pymdownx.arithmatex`'s `generic: true` mode actually emits —
  explaining the *partial*, seemingly-arbitrary failure pattern the walk described (not every
  formula fails identically, because the broken delimiter accidentally half-matches some spans
  and not others, depending on surrounding parentheses in the text). Confirmed against
  mkdocs-material's own documented reference config, which uses the doubly-escaped
  `"\\("`/`"\\)"` form. This was **not** the CDN-pin issue M2's deferred item A14 named — a
  version pin alone would not have fixed this; the string-escaping bug is the actual cause.
- Changed: `docs/javascripts/mathjax.js` — `"\("→"\\("`, `"\)"→"\\)"`, `"\["→"\\["`,
  `"\]"→"\\]"`. `mkdocs.yml` — `extra_javascript`'s CDN load pinned
  `unpkg.com/mathjax@3` → `unpkg.com/mathjax@3.2.2`, additionally closing M2 R1 fold's deferred
  A14 ("pin the MathJax CDN version") — investigated per the brief's instruction not to assume
  the pin alone would be sufficient, and confirmed it was not the root cause but is still a
  legitimate, independently-worthwhile fix (an unpinned major floats onto whatever `3.x` unpkg
  serves next, which could reintroduce this exact class of failure or a new one).
- **GREEN, verified in a real browser** (the closest thing to a regression test available, per
  the brief — described here rather than automated into pytest, since MathJax processes
  client-side and a static `mkdocs build` HTML grep cannot see post-render state): rebuilt,
  re-served, re-drove with `chrome-devtools`:
  - `manual/opf/` (the wave's own new page, the walk's first-named finding): `{"total":6,
    "processed":6,"raw":0}` — the epigraph/segment LP formula and all inline math now render.
  - `manual/n1/` (the wave's own new page, the walk's "worst-rendered thing on the whole site"):
    `{"total":1,"processed":1,"raw":0}` — the LODF formula renders. Screenshot:
    `<scratchpad>/mathjax-n1-after-fix.png`.
  - `manual/numerics/` (an **M1/M2-era page this wave never touched** — the audit's own
    site-wide repro, `m3-audit.md` §3): `{"total":23,"processed":23,"raw":0}` — confirms the fix
    is the real, site-wide root cause, not a per-page patch.

### F. Docstring shorthand leak

- Changed: `src/mambo_power/contingency/__init__.py:1` — module docstring's
  `"(epic Design §2 \`contingency/\`; wave M3 W5)"` → `"(epic Design §2 \`contingency/\`)"`,
  dropping the internal wave/requirement-number shorthand a reader with no process context
  cannot parse, keeping the legitimate, stable epic Design citation.
- **Not touched** (deliberately, out of the brief's exact scope): three other files still carry
  the same `"wave M3 W5"`/`"(W5)"` shorthand in their own module docstrings —
  `src/mambo_power/contingency/n1.py:1`, `src/mambo_power/results/n1.py:1`, and
  `tests/unit/test_contingency_n1.py:1` (test-only, never rendered publicly). Of these,
  `contingency/n1.py`'s docstring *is* rendered on the public `docs/api/contingency.md` page
  (its `:::` submodule block) and carries the identical defect — named here as a follow-up the
  brief's exact wording ("`src/mambo_power/contingency/__init__.py`'s module docstring") did not
  cover, not silently missed.

---

## GREEN gate (HEAD `8fc8581`, worktree root)

| Command | Exit | Output |
|---|---|---|
| `uv run --no-sync ruff check .` | 0 | `All checks passed!` |
| `uv run --no-sync ruff format --check .` | 0 | `127 files already formatted` |
| `uv run --no-sync mypy` | 0 | `Success: no issues found in 39 source files` |
| `uv run --no-sync pytest -q -p no:cacheprovider` | 0 | `593 passed, 10 warnings in 197.04s` |
| `uv run --no-sync mkdocs build --strict` | 0 | `Documentation built in 52.66 seconds` |

(The 10 warnings are pre-existing pandapower/pandas `FutureWarning`/`RuntimeWarning`s from the
oracle import path, unrelated to this fold — same warnings the Step-5 floor report already
carries.)

Test count: 573 → **593** (+20: `tests/parity/test_opf_vs_pypsa.py`, 5 fixtures × 4 tests).

---

## Commit

```
8fc8581 chore(m3/R1): fold audit finding — PyPSA parity, citation nit, home page + MathJax + docstring cleanup
```

Trailers `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01Cst4pCPagtiPmT7KSuV2sm` verbatim.
`git status --porcelain` empty before and after.

```
$ git show --stat HEAD
 docs/index.md                           | 22 +++++++++++++---------
 docs/javascripts/mathjax.js             |  4 ++--
 mkdocs.yml                              |  2 +-
 src/mambo_power/contingency/__init__.py |  2 +-
 tests/parity/test_opf_vs_pypsa.py       | 181 +++++++++++++++++++++++
 5 files changed, 198 insertions(+), 13 deletions(-)
```

Pushed: `git push origin wave/03-opf-n1` → `f37815a..8fc8581  wave/03-opf-n1 -> wave/03-opf-n1`.
CI run `32685413387` (dispatched by the push, `headSha 8fc8581`) finished **success**
(`gh run view 32685413387 --json status,conclusion,headSha` → `completed`, `success`,
`8fc8581df99f6c97f5c8e88c2acaa7d9927f8655`) — confirmed before this report was closed out.

---

## Not done / deviations from the brief

- **All 6 items (A-F) closed**, none skipped. Two things worth the orchestrator's eye:
  1. **case300's PyPSA residual (item A) is named, not chased**, per the brief's own explicit
     permission ("If case300's residual turns out to need real investigation to close tighter,
     that's fine — name it as still-open"). Measured fresh at 7.37e-05 relative (~0.0074%),
     consistent with the diagnostic's own ~0.007% finding; plausibly related to case300's
     non-contiguous bus numbering causing a minor index-alignment difference in one of the two
     independent importers (pandapower's vs. PyPSA's), not investigated further within this
     fold's scope.
  2. **Item F's scope was read literally** (the one file the brief named), not extended to the
     three other files carrying the identical `"wave M3 W5"` shorthand — see item F's own
     "Not touched" note above, in particular `contingency/n1.py`'s docstring, which *is*
     publicly rendered and carries the same defect. Flagged, not silently fixed outside scope.
- **Item C required no file edit to the status cell itself** — investigated and found it was
  already in the target state (bare `discharged`, no qualifier), and is now honestly true rather
  than needing correction. The evidence block underneath it *was* edited (readback/tier-run).
- **CI**: pushed successfully, run `32685413387` confirmed **success** before this session closed
  out (see Commit section above) — no open item here.
