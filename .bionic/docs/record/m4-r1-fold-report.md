# M4 Step 5/6 — R1 fold report (audit finding)

Agent: m4-r1-fold. Date: 2026-08-24. Worktree `C:\Claude Projects\mambo-power-m4`, branch
`wave/04-nodal-market`, base `aa53140` → **commit `f5e20d9`** (pushed). `uv` =
`C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`; `uv sync --locked --all-groups`
→ `Resolved 102 packages … Checked 98 packages` (uv.lock untouched, no dependency changes).

Scope: exactly the 5 items (A-E) named in the dispatch — `m4-audit.md`'s coverage-hole finding
(§1, W7 has no numbered design decision) and documentation-substance findings (§5, home-page
staleness, an internal file-path citation leaking into public docstrings, `MarketNodalResult`
absent from the Results manual), plus a wording-only precision fix to AC-6's evidence block in
the plan (§2/§3's revert-and-watch finding). Nothing else from the audit or walk was in scope,
and nothing else was touched.

Method: A and D are additions, verified with `mkdocs build --strict` after. B and C are
corrections — verified the actual current facts (git log on `epic/01-foundation`, the actual
current docstring text) before writing replacement text, rather than trusting the walk/audit's
quoted excerpts as still-current. E is a plan-wording edit only, no code touched.

---

## Baseline (before any edit, HEAD `aa53140`)

```
git status --porcelain   -> (empty)
uv run --no-sync pytest -q -p no:cacheprovider   -> 646 passed (per m4-s7 slice's own report)
```

---

## Fold items

### A. W7's missing design decision — added

The wave spec's Design section (`.bionic/docs/specs/epic-01-foundation/wave-04-nodal-market.spec.md`)
numbered exactly 7 decisions, one each for W1-W6 (W2 gets two: items 2 and 3) — W7 (documentation)
had no corresponding item, unlike every other requirement. Added **item 8**, mirroring M3's own
spec's Design item 9 pattern (its own W9/docs deliverable) but naming this wave's actual shipped
docs surface:

```
8. **Docs (W7).** A new manual page (`docs/manual/market.md`) for nodal-market clearing under
   the existing `docs/manual/`; `docs/api/market.md` following the mkdocstrings pattern the M2
   R1 fold's coverage test already enforces generically; the design/architecture diagram
   updated to show `market.nodal`; one new `examples/09_nodal_market.py`, CI-executed and
   snippet-embedded.
```

Placed after item 7 (Oracle & fixtures), before the "Ownership additions" paragraph. `.bionic`
is entirely gitignored (mirrors M3's own precedent — its item B touched the same directory), so
this edit is not part of the pushed commit; it is local record/spec scaffolding, same status as
every prior fold's spec/plan edits in this project.

**GREEN**: `mkdocs build --strict` unaffected by a spec-only edit (spec files are not part of
the built site) — verified in the final gate below regardless, since C/D also touch the docs
build.

### B. Home page staleness — fixed

Verified the actual current facts first, not the walk's quoted text taken on faith:
`git log --oneline epic/01-foundation` shows `5fa3285 merge(m3): wave/03-opf-n1 into
epic/01-foundation` — **M3 is merged**, not "in progress" as the page still said. M4 itself is
**not yet merged** — still on its own `wave/04-nodal-market` branch (this fold's own worktree,
head `aa53140` before this commit), exactly the situation M3's own R1 fold was in when it wrote
its own equivalent update (`m3-r1-fold-report.md` item D: M1/M2 merged, M3 "in progress ... with
everything below shipped there").

Changed: `docs/index.md`:
- **Status callout**: rewritten to "Wave M1 ... wave M2 ... and wave M3 ... are all merged.
  Wave M4 (nodal-market clearing: elastic demand, LMP-based settlement) is in progress on its
  own wave branch, with everything below shipped there" — naming `market.solve_nodal` /
  `manual/market.md`, the LMP/settlement decomposition, `jobs.run` `kind="market.nodal"`, and
  the new example, mirroring M3's own home-page phrasing pattern applied one wave later (same
  pattern M2→M3's fold used, now M3→M4).
- **"Where to go next" table**: gained one row — "Clear a nodal market with elastic demand,
  LMPs and settlement | [Manual › Nodal market](manual/market.md)" — inserted between the N-1
  screening row and the Results row, matching the manual's own nav order (confirmed via
  `mkdocs.yml`: `Nodal market` sits between `N-1 screening` and `Results`).
- **Roadmap table**: M3 row `in progress` → `merged`; the combined "M4-M7 ... planned" row
  split into its own M4 row ("Nodal market: elastic-demand DC-OPF, LMP clearing, settlement" —
  `in progress`) and a narrowed "M5-M7 ... planned" row (zonal/multi-period/agent-based, the
  three remaining not-yet-started waves).

**GREEN**: `uv run --no-sync mkdocs build --strict` — exit 0, confirmed in the final gate below.

### C. Internal file-path citation and wave-shorthand leaks — fixed, scope widened within M4's own code

Started from the audit's three explicitly-named locations (`market/nodal.py`'s module docstring
and inline comment, `market/__init__.py`'s module docstring, `examples/09_nodal_market.py`'s
module docstring and inline comment), then grepped the rest of `src/` and `examples/` for the
same two patterns (`record/m4-research\.md`, `wave M4 W`) before closing this item out — the
brief's own scoping language is "M4's own new code only," not "only these three files," and the
audit's explicit instruction is to not extend M3's Assumption A6 to *any* of this wave's own new
leaks. That search surfaced four more files carrying the identical defect, all genuinely M4-new
code and all confirmed publicly rendered (not just theoretically reachable):

- `src/mambo_power/jobs/registry.py` — `mambo_power.jobs.registry` is directly `:::`-included on
  `docs/api/jobs.md`.
- `src/mambo_power/model/scenario.py` — `Scenario` is re-exported at `mambo_power.model` top
  level (`docs/api/model.md`'s `::: mambo_power.model` block renders re-exported members' own
  docstrings).
- `src/mambo_power/numerics/arrays.py` — `mambo_power.numerics.arrays` is directly
  `:::`-included on `docs/api/numerics.md`; the leak was in the `load_p_max_pu` field's own
  docstring.
- `src/mambo_power/results/market.py` — `MarketNodalResult`/`LoadDispatchResult` are re-exported
  at `mambo_power.results` top level (`docs/api/results.md`'s `::: mambo_power.results` block),
  same rendering mechanism as `Scenario` above; this file alone carried 3 of the 9 total leak
  instances fixed.

Verified this did **not** touch any of A6's 22 pre-existing M1/M2/M3 files: re-grepped after all
edits — the only remaining `spec design item`/`W#`-shorthand matches are in `opf/dc_opf.py`,
`opf/__init__.py`, `pf/ac_newton.py`, `results/feasibility.py`, `results/opf.py` (all M2/M3-era),
none of which use the `record/m4-research.md` or `wave M4 W#` forms — left untouched, per scope.

All 9 fixes replace the leak with either plain prose (the settlement identity, the self-contained
pattern, the per-load bound) or drop the parenthetical entirely when the surrounding sentence
reads fine without it — no replacement citation was added except in `market/nodal.py`'s module
docstring, where the settlement identity sentence now points to "the wave spec's AC-4" (a bare
requirement-number form, never a `record/` path), per the brief's own explicit permission for
that specific case.

**GREEN**: `uv run --no-sync mkdocs build --strict` — exit 0; `uv run --no-sync pytest -q` — 646
passed (docstring-only changes, no behavior touched); bare `uv run mypy` — clean.

### D. `MarketNodalResult` — added to the Results manual page

Added a new `## MarketNodalResult` section to `docs/manual/results.md`, between `to_arrays()`/
"Building results from arrays" and the closing example (placed right before "JSON round-trip",
alongside the other typed-result descriptions on the page) naming the type, its constituent row
models (`LoadDispatchResult`, reused `GenDispatchResult`/`BusLmpResult`), its settlement fields,
and linking to `manual/market.md` for the fuller treatment — a paragraph, not a duplicate of the
market manual's depth, per the brief.

**GREEN**: `uv run --no-sync mkdocs build --strict` — exit 0, confirmed in the final gate below.

### E. AC-6's evidence-block wording — tightened (plan only, no code)

Changed: `.bionic/docs/plans/epic-01-foundation/wave-04-nodal-market.plan.md`'s AC-6 `tier-run:`
block — appended a "Precision note" paragraph stating exactly what `m4-audit.md` §2/§3's
revert-and-watch found: reverting S3's double-counting subtraction turned only 1 of AC-6's 4
parametrized sub-tests red (the LMP-parity check), not all 4, because case14's derived bids
(`tests/_bids.py`'s anchor rule) are all fully price-taking, so raw dispatch quantities cannot
distinguish correct dispatch from double-counted dispatch on this fixture — the three
dispatch-quantity sub-checks stayed green under the stub. AC-6 still genuinely discharges (the
LMP sub-check's residual blew out from the measured `1.94e-5 $/MWh` to `2.485 $/MWh` against a
`1e-3` tolerance, a >2400x margin) — the note states this precisely rather than implying uniform
power across all 4 sub-tests, matching the audit's own §2 conclusion verbatim in substance.

Also appended a "R1-fold closure" note to AC-8's `readback:` block, naming what A-D closed
(coverage hole, home-page staleness, docstring leaks — with the full list of files C actually
touched — and the Results manual gap), explicitly not re-issuing the `auditor-wave:` verdict or
touching any row's `auditor` column, per the brief's own instruction (mirrors M3's own R1 fold's
treatment of its item C).

No code or test file touched by this item.

---

## GREEN gate (HEAD `f5e20d9`, worktree root)

| Command | Exit | Output |
|---|---|---|
| `uv run --no-sync ruff check .` | 0 | `All checks passed!` |
| `uv run --no-sync ruff format --check .` | 0 | `140 files already formatted` |
| `uv run --no-sync mypy` | 0 | `Success: no issues found in 43 source files` |
| `uv run --no-sync pytest -q -p no:cacheprovider` | 0 | `646 passed, 10 warnings in 53.56s` |
| `uv run --no-sync mkdocs build --strict` | 0 | `Documentation built in 4.72 seconds` |

(The 10 warnings are the same pre-existing pandapower/pandas `FutureWarning`/`RuntimeWarning`s
from the oracle import path every prior gate in this wave carries — unrelated to this fold.)

Test count: 646 → **646** (unchanged — this fold is documentation-only, no test file touched).

---

## Commit

```
f5e20d9 chore(m4/R1): fold audit findings — W7 design decision, home page + docstring-leak fixes, Results manual mention, AC-6 wording precision
```

Trailers `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01Cst4pCPagtiPmT7KSuV2sm` verbatim.
`git status --porcelain` empty before and after.

```
$ git show --stat HEAD
 docs/index.md                      | 23 +++++++++++++----------
 docs/manual/results.md             | 11 +++++++++++
 examples/09_nodal_market.py        | 11 +++++------
 src/mambo_power/jobs/registry.py   |  2 +-
 src/mambo_power/market/__init__.py |  2 +-
 src/mambo_power/market/nodal.py    | 17 +++++++++--------
 src/mambo_power/model/scenario.py  |  6 +++---
 src/mambo_power/numerics/arrays.py |  6 +++---
 src/mambo_power/results/market.py  | 16 +++++++---------
 9 files changed, 53 insertions(+), 41 deletions(-)
```

Pushed: `git push origin wave/04-nodal-market` → `aa53140..f5e20d9  wave/04-nodal-market ->
wave/04-nodal-market`. CI run `32800006341` (dispatched by the push, `headSha f5e20d9`) finished
**success** (`gh run view 32800006341 --json status,conclusion,headSha` → `completed`, `success`,
`f5e20d9b4c23d96bd527b958ddd4025ee8ab15c6`) — confirmed before this report was closed out.

---

## Not done / deviations from the brief

- **All 5 items (A-E) closed**, none skipped.
- **Item C's scope was widened beyond the brief's 3 explicitly-named files**, to 7 files total —
  disclosed above, not silently done. The brief's own scoping language ("this item is scoped to
  M4's own new code only," and the audit's explicit instruction not to extend A6 to "this wave's
  own new leaks") reads as applying to the defect class generally, not just the three files the
  walk happened to click through; all four additional files were confirmed to carry the
  identical `record/m4-research.md`-path or bare-`wave M4 W#` defect, confirmed publicly
  rendered (not just theoretically reachable), and confirmed to be M4's own new code, not one of
  A6's 22 pre-existing M1/M2/M3 files. Flagged here for the orchestrator's eye in case a
  narrower reading was intended.
- **CI**: pushed successfully, run `32800006341` confirmed **success** before this session closed
  out (see Commit section above) — no open item here.
