# M3 R2 re-audit — Step 5 exit gate, scoped re-audit of AC-1's PyPSA gap

Auditor: m3-r2-reaudit (fresh, read-only; implemented, reviewed, and audited nothing else in M3
before this). Written 2026-08-23/24 in worktree `C:\Claude Projects\mambo-power-m3` (branch
`wave/03-opf-n1`, head `8fc8581`). `git status --porcelain` empty before and after every command
below; no edits or commits made in the worktree by this agent at any point (only scratchpad files
outside the worktree and two throwaway local HTTP servers in the scratchpad directory, stopped
after use). `uv` = `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`.

Scope: this is **not** a fresh full audit. `record/m3-audit.md` already ran the full
coverage/power/authenticity pass and returned `auditor-wave: REFUTED` on exactly one ground —
AC-1's PyPSA-secondary-oracle half had zero committed evidence. `record/m3-r1-fold-report.md`
(commit `8fc8581`, pushed, CI `32685413387` success) claims to have closed that gap plus 5 other
items. This re-audit verifies AC-1 is now actually proven, spot-checks the other 5 fold items for
new problems, and issues an updated verdict.

---

## 1. AC-1's PyPSA half — re-executed, not just read

**Read `tests/parity/test_opf_vs_pypsa.py` in full.** It is a genuine independent comparison, not
a rubber stamp:
- Builds a real PyPSA network via `pypsa.Network().import_from_pypower_ppc(ppc, ...)` from the
  same raw MATPOWER matrices `mambo_power.io.matpower` reads, not from anything `dc_opf` produces.
- Bridges `gencost` columns 4/5 (`c2`/`c1`) into `marginal_cost_quadratic`/`marginal_cost` by hand
  (PyPSA's importer does not read `gencost` at all), and folds `c0` into the comparison.
- Clears `n.generators["p_set"] = float("nan")` before `n.optimize()` — the diagnostic's proven
  fix for PyPSA's import path otherwise pinning every generator to MATPOWER's unbalanced
  base-case `PG`, which makes the nodal balance infeasible.
- Calls `solve_dc_opf(net)` fresh, on the same fixture file, inside the same test fixture — the
  "ours" side is not hardcoded or reused from another test.
- Carries its own negative/sanity test (`test_pypsa_itself_converges_optimal`) asserting the
  oracle itself reached `("ok", "optimal")` — a broken oracle would fail this before the
  comparison tests could pass vacuously.

This would fail if `opf.solve_dc_opf` were broken: `test_dispatch_matches_pypsa` and
`test_objective_cost_matches_pypsa` compare `dc_opf`'s own `objective_cost`/generator dispatch
against PyPSA's, independently computed.

**Re-executed:**
```
$ uv run --no-sync pytest -q -m parity tests/parity/test_opf_vs_pypsa.py -v
20 passed in 35.54s
```
Matches the fold report's claim (5 fixtures × 4 tests, 20 passed) exactly.

**Residuals independently recomputed** — not by reading the test's own printed numbers, but by a
standalone script (`scratchpad/pypsa_residual_check.py`) that re-imports the test module's own
`run_pypsa_dcopf`/`CASES` and independently recomputes cost/dispatch residuals outside the
test's assertions:

| fixture | cost rel. diff (mine) | cost rel. diff (fold report) | worst dispatch abs. diff MW (mine) | worst dispatch abs. diff MW (fold report) |
|---|---|---|---|---|
| case14 | 7.497217e-14 | 7.50e-14 | 2.291156e-05 | 2.29e-05 |
| case_ieee30 | 9.679880e-14 | 9.68e-14 | 2.796969e-05 | 2.80e-05 |
| case57 | 2.977330e-13 | 2.98e-13 | 3.310310e-04 | 3.31e-04 |
| case118 | 1.265732e-12 | 1.27e-12 | 1.866749e-03 | 1.87e-03 |
| case300 | 7.367680e-05 | 7.37e-05 | 8.206023e-02 | 8.21e-02 |

Exact match on all 5 fixtures, to the reported precision. This was not achieved by reading the
report and copying its numbers — the script is a fresh, independent computation over the same
fixtures via the test module's own helper functions, run separately from pytest.

case14/case_ieee30/case57/case118 sit comfortably inside the pinned tight band
(`TIGHT_COST_REL_TOL=1e-9`, `TIGHT_DISPATCH_ABS_TOL_MW=0.01`); case300 sits inside its own,
separately-pinned wide band (`WIDE_COST_REL_TOL=2e-4`, `WIDE_DISPATCH_ABS_TOL_MW=0.5`). Both
bands are pinned with real margin over what is actually measured, not padded arbitrarily.

**Verdict on AC-1: CONFIRMED**, with a named, bounded exception on case300 (wider PyPSA band,
~0.0074% relative cost / 0.082 MW dispatch). This is not a new
refutation: the wave spec's own AC-1 text already anticipated and permitted exactly this shape
("a separately documented, wider band on case300"). Both halves of the literal criterion —
pandapower primary oracle and PyPSA secondary oracle — now have committed, repeatable,
independently-verified evidence.

> **Correction (R3 fold, superseding this section's original root-cause guess):** the paragraph
> above originally read "...root cause named but not chased — plausibly a bus-numbering
> index-alignment artifact between the two independent importers". That guess was untested when
> this re-audit repeated it, and `m3-critic.md` Issue 1 subsequently closed the real root cause:
> case300 is the only one of the 5 OPF fixtures with nonzero MATPOWER bus `GS` (shunt
> conductance), 17 buses summing to exactly 1.3 MW. `dc_opf`'s own balance row correctly includes
> it; PyPSA's `import_from_pypower_ppc`/DC-LOPF silently drops it, under-serving load by exactly
> 1.3 MW, spread thinly across 68/69 generators by the QP's cost-minimizing redistribution — a
> dropped fixed term, not a mislabelled index (an index swap would produce a handful of large,
> lumpy discrepancies without shifting either dispatch total, not this signature). `dc_opf` is
> provably *more* complete than this oracle on this one point, not less.

---

## 2. Spot-check of the other 5 fold items

### AC-4 provenance line

```
$ grep -n "provenance: W3" .bionic/docs/specs/epic-01-foundation/wave-03-opf-n1.spec.md
144:  provenance: W3, W5
```
Confirmed — reads `W3, W5`, matching the audit's citation-precision finding.

### Home page staleness

```
docs/index.md:18-21: "Wave M1 (...) and wave M2 (...) (...) are both merged. Wave M3 (DC optimal
power flow with duals, N-1 branch-contingency screening) is in progress on its own wave branch,
with everything below shipped there."
docs/index.md:103-105 (roadmap table): M1 merged | M2 merged | M3 in progress
```
No occurrence of "M2 ... is in progress" remains. Confirmed — matches the fold's claimed edit.

### MathJax fix — root cause and fix confirmed real

`git show f37815a:docs/javascripts/mathjax.js` (before) vs. the current worktree file (after):

```
before: inlineMath: [["\(", "\)"]],   displayMath: [["\[", "\]"]],
after:  inlineMath: [["\\(", "\\)"]], displayMath: [["\\[", "\\]"]],
```
This is a real, correctly-diagnosed bug: in a JavaScript double-quoted string literal, `\(` is
not a recognized escape sequence, so JS silently drops the backslash — the "before" config was
actually matching bare `(`/`)`/`[`/`]`, not the literal `\(...\)`/`\[...\]` sequences
`pymdownx.arithmatex`'s `generic: true` mode emits. The fix (doubling the backslash so the JS
string literal itself contains a literal backslash) matches mkdocs-material's own documented
reference config. This is a genuine root-cause fix, not a guess.

**Browser-verified** (built a fresh site from the current HEAD, `mkdocs build --strict -d
<scratchpad>/r2-site2`, served over a throwaway local HTTP server, driven with `chrome-devtools`):
first attempt against `localhost:8793` returned a stale, pre-fix `mathjax.js` and 3/6
`arithmatex` blocks unprocessed on `manual/opf/` — traced to a leftover HTTP server process from
an earlier session/agent still bound to that port on this shared machine, confirmed via
`netstat -ano` (two listeners already on 8793, neither started by this agent) and by diffing the
byte-for-byte-different file it served against the actual `r2-site2` build on disk. Re-served on
a fresh port (8799, verified via `netstat` to be exclusively mine, killed after use):

| page | processed/total |
|---|---|
| `manual/opf/` | 6/6 |
| `manual/n1/` | 1/1 |

Both match the fold report's claimed post-fix counts exactly. Screenshot of `manual/n1/` (saved
at `<scratchpad>/mathjax-r2-verify-n1.png`) shows the LODF formula rendering as real typeset math
(fraction/subscript/absolute-value glyphs), not raw TeX. I did not separately re-drive
`manual/numerics.md` (the audit's own site-wide repro) — the code-level diff above is sufficient
to confirm the fix is a single, page-independent config change, and the fold report's own
browser re-execution already covered that page (23/23 processed).

### Docstring cleanup + Assumption A6

```
$ sed -n '1,2p' src/mambo_power/contingency/__init__.py
"""N-1 branch-contingency screening (epic Design §2 ``contingency/``).
```
No "wave M3 W5" shorthand remains. Confirmed.

**A6's pervasiveness claim, spot-checked** (not the full 22-file list, a representative sample
across all three waves plus the specific files the dispatch named):
`pf/ac_newton.py` — `"""...Newton-Raphson over NetworkArrays (W1)."""`; `model/entities.py` —
`"Units are physical (wave M1 design item 1): ..."`; `model/errors.py`, `model/islands.py`,
`numerics/__init__.py` (via `numerics/roles.py` — `"...derived from the declared roles... (W3)"`),
`pf/__init__.py`, `pf/dc.py`, `jobs/__init__.py`, `jobs/registry.py`, `opf/__init__.py` — all
carry an inline `W<n>` or `wave M<n> design item <n>` citation in a module or class docstring.
Three files (`results/from_arrays.py`, `results/power_flow.py`, `results/tables.py`) do **not**
carry the pattern in their top module docstring but do carry it one level down, in a class or
type-alias docstring (`class AcPowerFlowResult: """...(W1)..."""`, a `Literal` type alias
comment reading `"...(W3: the effective role...)"`) — still a public, API-reference-rendered
docstring, so A6's claim holds under closer reading, not just at a glance. This is a real,
verifiable, pre-existing house convention spanning M1/M2/M3 code, not an excuse invented to avoid
finishing item F's fix. Reverting the one over-scope attempt and leaving it as a named carry-over
(A6) was the right call — fixing 3 more of 22 files in isolation would have made the codebase
less consistent, not more.

---

## 3. No collateral damage

```
$ git show --stat 8fc8581
 docs/index.md                           | 22 +++++++++++++---------
 docs/javascripts/mathjax.js             |  4 ++--
 mkdocs.yml                              |  2 +-
 src/mambo_power/contingency/__init__.py |  2 +-
 tests/parity/test_opf_vs_pypsa.py       | 181 +++++++++++++++++++++++
 5 files changed, 198 insertions(+), 13 deletions(-)
```
Exactly the 5 files the fold report claims, nothing else. `mkdocs.yml`'s 1-line change is the
MathJax CDN version pin (`unpkg.com/mathjax@3` → `@3.2.2`), also claimed and in scope (closes M2
R1's deferred A14 as a bonus, not a scope violation — the fold report names this explicitly).

Full gate, re-executed fresh in this session:

```
$ uv run --no-sync ruff check .                          -> All checks passed!
$ uv run --no-sync mypy                                  -> Success: no issues found in 39 source files
$ uv run --no-sync mkdocs build --strict -d <scratch>     -> exit 0, "Documentation built in 18.20 seconds"
$ uv run --no-sync pytest -q -p no:cacheprovider          -> 593 passed, 10 warnings in 175.72s
```
593 matches the fold report's claimed count exactly (573 + 20 new PyPSA tests). The 10 warnings
are the same pre-existing pandapower/pandas `FutureWarning`/`RuntimeWarning`s the Step-5 floor
report already carries — not new.

---

## 4. Verdicts

**AC-1: CONFIRMED**, with a named, bounded exception (case300's PyPSA band is separately wider,
~0.0074% relative cost / 0.082 MW dispatch vs. the tight band the other 4 fixtures meet) —
precisely the shape the wave spec's own AC-1 text anticipated and permitted, not a new refutation
ground. Both the pandapower-primary and PyPSA-secondary halves of the literal criterion now have
committed, repeatable, independently re-executed and independently re-measured evidence.

**Wave — overall: CONFIRMED.** The original audit's sole refutation ground — AC-1's undischarged
PyPSA half — is closed with real, re-executed, re-measured evidence, not merely asserted closed.
The fold's other 5 items (AC-4 provenance citation, home page staleness, MathJax root-cause fix,
docstring shorthand cleanup, and the orchestrator's own A6 investigation of that cleanup's
follow-up) all check out as genuine on independent inspection — no rubber-stamping, no new defect
introduced, and no scope creep beyond the 5 files the fold commit touches. Every other row from
the original audit (AC-2 through AC-9) was already CONFIRMED and is untouched by this fold; full
suite green (593/593), ruff/mypy/mkdocs --strict clean, CI green on the pushed commit.

Replacing `.bionic/docs/plans/epic-01-foundation/wave-03-opf-n1.plan.md`'s Verification Matrix
AC-1 `auditor` cell and the `auditor-wave:` line accordingly (below), per this re-audit. `current:`
in `## SDLC State` is left untouched — that is the orchestrator's call.
