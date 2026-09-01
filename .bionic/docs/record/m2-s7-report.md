# M2 / S7 "examples" (+ docs finish) — report

Wave M2 power-flow, slice S7 (W9, AC-9; docs finish for W8/AC-8; A7 rename; A11 provenance
correction; AC-7 timing visibility). Worktree `C:\Claude Projects\mambo-power-m2`, branch
`wave/02-power-flow`, base `0ba1c8d` (S5). Written 2026-08-21 (UTC). Every number below was
produced by a command in this session. Not pushed. No dependency changes.

**Commit:** `e1e7e4febde2b897f4e500c9a60227bce950cfee` — 26 files, +1197 / −165. No hook
blocked. **Tests:** 484 passed whole tree (475 at S5 + 9 new). **Examples:** 7, all exit 0.

## 1. Examples (`examples/`)

Each script is self-contained, runs from the repository root, reads only `fixtures/`, prints a
deterministic summary (no timings, no timestamps), writes nothing outside a
`tempfile.TemporaryDirectory`, and carries a module docstring saying what it shows and how to
run it. Wall time measured by `tests/unit/test_examples_run.py -s` (fresh interpreter per
script, includes import of numpy/scipy/pydantic):

| Script | Wall | Lines | Shows |
| --- | --- | --- | --- |
| `01_load_and_validate.py` | 0.26 s | 14 | `load_with_report` on case14 (14 `BASE_KV_REPLACED` issues, first one printed typed + legacy string), a 3-bus hand-built network, a broken document raising `NetworkValidationError` with **6** issues (`DUPLICATE_ID`, `BAD_BASE`, `DANGLING_REF`, `BAD_RANGE` ×2, `NO_SLACK`), `validate_network` after mutation |
| `02_ac_power_flow.py` | 0.90 s | 33 | `solve_ac` on case14/case118 × q_limits on/off (iterations 4/4/7/4, rounds 0/0/1/0, case118 pins gen-9/15/16/43/48 min + gen-46 max), first 5 bus voltages, bus 103 on/off (1.00071 / 1.01000), branch-loading table (250 MVA stamped on every branch — case118 ships `RATE_A = 0`), losses 132.481 MW, warm start → 0 iterations |
| `03_dc_power_flow.py` | 0.85 s | 16 | `solve_dc` on case300: angle range −19.46…56.63°, top-5 flows, slack gen 47.72 MW, generation = load + shunt G; AC comparison (5 iterations, 408.32 MW losses, median gap 2.60 MW, max 408.23 MW on the slack branch) |
| `04_jobs_api.py` | 1.25 s | 13 | `pf.ac` and `pf.dc` via `run`, options echoed in provenance, `run_json` round trip back to typed result (equal to the direct run), three structured failures (`UNKNOWN_KIND`, `BAD_OPTIONS` with details, `VALIDATION` with issues from a mutated network), `SetpointConflictWarning` captured on `case14_roles` |
| `05_roles_and_islands.py` | 0.72 s | 14 | `effective_roles` on `case14_roles` (bus-6 declared pv → effective pq; conflict at bus-2 gen-2/gen-6 1.045/1.055 → last wins), solved vm bus-2 1.0550; `NoSlackGeneratorError` on `case14_noslackgen`; `case14_island` → `ISLAND_DEACTIVATED` `['bus-8']` / `['gen-5']`, solve on the main island (13 rows); `Network.model_validate` with the island re-enabled → `DISCONNECTED_BUS` at `buses[7]` |
| `06_network_matrices.py` | 1.32 s | 32 | `NetworkArrays` on case14, Ybus (csc, nnz 54, density 27.6 %), PTDF (20×14, zero slack column) with a 100 MW bus-5→bus-14 transfer, `bridges` = [(13, branch-14, bus-7–bus-8)], LODF NaN column 13 == bridge, LODF of branch-1; a 3-bus network with dense Ybus, B', PTDF, LODF printed in full |
| `07_results_and_export.py` | 1.32 s | 18 | AC result JSON (7098 bytes) round trip equal, top-level and provenance keys, `to_arrays()` (voltage envelope bus-3 1.0100 … bus-8 1.0900, largest flow branch-1 158.20 MVA, losses 13.393 MW), CSV export of buses/branches with `csv.DictWriter` into a temp dir |

Run log (head of each, verbatim): `01` → `case14: 14 buses, 20 branches, 5 generators, 11
loads, 1 shunts`; `02` → `--- case14, q_limits=True / converged=True iterations=4
q_limit_rounds=0 max_mismatch=8.77e-13 MVA`; `03` → `case300 DC: pf.dc
scipy.sparse.linalg.splu converged = True`; `04` → `registered kinds: ['pf.ac', 'pf.dc']`;
`05` → `case14_roles: declared vs effective role where they differ / bus-6: declared pv,
effective pq (no in-service generator)`; `06` → `case14 arrays: 14 buses, 20 branches, slack
position 0`; `07` → `JSON: 7098 bytes; round trip equal: True`.

### Test + CI

- `tests/unit/test_examples_run.py` (9 tests): directory populated and numbered; **every
  script is embedded in `docs/examples/index.md`** (`--8<-- "examples/<name>"` present — a new
  script that is not embedded fails); each script run in a subprocess from the repo root,
  exit 0, non-empty stdout, no `Traceback`, 60 s hang guard; prints the wall time under `-s`.
- `.github/workflows/ci.yml`: new `examples` job (ubuntu, 3.12, `uv sync --locked
  --all-groups`, `for f in examples/*.py; do uv run python "$f" || exit 1; done` with
  `::group::` per script); new step in the test matrix, **ubuntu 3.12 only**, `uv run pytest
  tests/parity/test_ac_timing.py -q -s -p no:cacheprovider` so the AC-7 figure reaches the log.

## 2. Embedding map (script → page)

| Script | Embedded on | Linked from |
| --- | --- | --- |
| 01 | `docs/examples/index.md#1-load-and-validate` | (gallery table → model, formats) |
| 02 | `#2-ac-power-flow` | `manual/power-flow.md` (header + DC-vs-AC) |
| 03 | `#3-dc-power-flow` | `manual/power-flow.md` (header + DC-vs-AC) |
| 04 | `#4-jobs-api` | gallery table → `manual/jobs.md` (jobs.md itself untouched; its six inline blocks are the S5 convention) |
| 05 | `#5-roles-and-islands` | `manual/power-flow.md` (effective roles), `manual/formats.md` (islands), `manual/model.md` (repair_islands) |
| 06 | `#6-network-matrices` | gallery table → `manual/numerics.md` (numerics.md untouched) |
| 07 | `#7-results-and-export` | `manual/results.md` (building results from arrays) |

Plus `docs/getting-started.md` (Next steps) and `docs/index.md` ("Copy a working script" row)
link the gallery. Rendered-site proof: `site/examples/index.html` contains the scripts'
source (8 hits for `01_load_and_validate|load_with_report`); `site/manual/power-flow/` has 1
mermaid block.

**Embedding form — judgment call.** The snippet lines sit in ```` ``` { .python } ```` fences,
not ```` ```python ````: probed with `ruff format --diff` on a scratch page, ruff rewrites
`--8<-- "x"` inside a python-tagged fence to `--8 < --"x"` (it parses as a valid expression),
which would silently break every embed on the next `ruff format`; the attribute-list fence is
left alone and superfences/highlight render it identically. The gallery's conventions section
says so. The S6 convention text about `--8<-- [start:name]` section markers was dropped —
whole scripts are embedded.

## 3. Docs finish

- `docs/manual/power-flow.md`: the AC "landing" admonition and contract are gone. Now: entry
  table (all four shipped, real signatures), executed API block on case118 (7 iterations,
  1 round, 6 pins), `AcOptions` table as implemented, non-convergence block (`max_iter=1` →
  `False 1 82.538 MVA`), which exceptions escape, NR formulation with `dSbus_dV` partials and
  the ≤-before-step / zero-iterations semantics (S4 judgment 1), start rules, generator
  allocation (`pfsoln`), **Q-limit section with the pandapower 3.3.0
  `run_newton_raphson_pf.py:182-249` / MATPOWER `runpf.m:366-440` citations and the
  line-level rules from S4's module docstring**, a **mermaid flowchart of the NR + Q-limit
  outer loop**, warm-start block (`0 0 True`) with the re-pin caveat, effective-roles table with
  links, islands links, **verification table** (six rows from S4: iterations, rounds, pins,
  max Δ vs runpp, stored-column residual + exclusions), the band rationale, the bus-103
  negative pair, and the **timing statement** (0.029 s cold / 0.018 s warm, Windows, with the
  explicit "not a CI measurement; CI ubuntu 3.12 prints it" caveat).
- `docs/manual/model.md`: new section "Import issues and island repair" — `ImportIssue` field
  table, `ImportIssueCode`, rename note, `repair_islands` / `repair_islands_entities`
  semantics (per island, already-out not listed, no-slack → untouched, input never mutated),
  executed block (`[('ISLAND_DEACTIVATED', ['bus-8'], ['gen-5'])]`, 13 of 14 / 14 untouched).
- `docs/manual/formats.md`: function table gains `load_with_report` / `loads_with_report`,
  the warnings section is rewritten around `ImportReport` / `ImportIssue` with an executed
  block on `case14_island` (`['BASE_KV_REPLACED', 'ISLAND_DEACTIVATED'] 15`), islands section
  links `repair_islands` and example 05.
- `docs/getting-started.md`: new "Run an AC power flow" step (executed; case14 `True 4 0
  8.8e-13 MVA`, three bus rows, losses 13.393 MW); Next steps updated.
- `docs/changelog.md` Unreleased: the "landing" bullet replaced by S4 (AC solver), S2
  (effective roles, island repair / `ImportIssue` / `ImportReport`), S7 (examples, docs)
  entries; Changed: rename note, PROVENANCE correction.
- `docs/index.md`: status admonition no longer says AC/jobs "land" (S5's open item); table
  rows for power flow and examples. `docs/design/architecture.md`: the "Landing in M2"
  subgraph folded into "Shipped (M1 + M2)" with `pf.ac_newton`, `jobs`, `effective_roles`,
  `ImportIssue`/`repair_islands`, `ImportReport` named. `docs/manual/results.md`: "AC builder
  when it lands" → `ac_result_from_arrays` signature; also fixed a pre-existing 2-character
  mismatch in its JSON-prefix text block (the page printed `text[:120]`, the stored output
  was 122 characters).
- Untouched: `manual/numerics.md`, `manual/jobs.md`, `api/*`, `design/data-model.md`,
  `design/decisions.md`, `contributing.md`, README (its roadmap row already reads
  "runnable examples · in progress").

**Executed code blocks.** Ad-hoc runner (scratchpad `run_doc_blocks.py`: every ```` ```python ````
block of a page executed in order in one namespace, stdout compared with the following
```` ```text ```` block): power-flow 5, getting-started 10, model 4, formats 2, index 1, results
2, numerics 5, jobs 6 → **35 blocks, 35 outputs match, 0 failures** (after two corrections to
my own expected outputs — case118 `82.538` not `73.533` MVA for the stuck solve; case14 bus-3
`q=6.08` — and the results.md fix above). The two stray files those pages write at the repo
root (`mini.json`, `network.schema.json`) were removed before the commit.

## 4. Rename (A7): `ImportWarning` → `ImportIssue`

`sed` over the seven files that named it (`model/warnings.py`, `model/__init__.py`,
`model/islands.py`, `io/report.py`, `io/matpower.py`, `tests/unit/test_islands.py`,
`docs/changelog.md`): class `ImportIssue`, alias `ImportIssueCode`, exports, annotations,
docstrings. Behaviour identical (`str()` form, fields, codes, `ImportReport.warnings` field
name and `.codes` / `.as_strings()` unchanged — the *field* is still called `warnings`, only
the class was renamed). The `warnings.py` docstring note about sharing the builtin's name now
records the rename instead. `grep -rn ImportWarning src tests docs README.md mkdocs.yml` → no
hits. **The spec's W4 / design item 4 wording (`list[ImportWarning]`) is for the orchestrator
to amend** — the spec lives outside the repo.

## 5. PROVENANCE correction (A11)

`fixtures/matpower/PROVENANCE.md` case300 entry: the "Reference solution" bullet now states
the measured residual against our solver (worst 8.5e-3 pu, 11 of 300 buses beyond 2e-3;
Q-limits on, flat start, 5 iterations; `tests/parity/test_ac_vs_matpower_stored.py`), that
case300 is a column-parity fixture with Q-limits **off and on**, that pandapower converges
qlim-on in 2 iterations with the same 10 pins on a tap-side-correct oracle copy, and an erratum
withdrawing "0.107 pu at bus 17" and "pandapower cannot converge with Q-limits" as
`from_ppc` tap-side artefacts. sha256, blob SHA-1, byte count, line-ending note and the licence
bullet are untouched. **Judgment call:** the separate "Known reference-quality findings" bullet
(the 9-bus 5 MVA gate list, the 927 MVA pair across branch 390) was **not withdrawn** — that
gate is computed from the stored state and the file's own admittances, not from the pandapower
oracle, and A11 names only the two figures above as artefacts; its heading now says it is the
research's transcription, not re-measured by S4, and that the column-parity figure is the
current statement. `tests/unit/test_fixture_case300.py` does not assert PROVENANCE text (it
checks sha256/size/counts) — still passes.

## 6. Timing visibility (AC-7)

`tests/parity/test_ac_timing.py`: the figure string is printed, recorded via
`record_property("case300_ac_cold_s" / "case300_ac_warm_s" / "case300_ac_iterations")`, and
carried in both assertion messages. `uv run pytest -q -s tests/parity/test_ac_timing.py` →
`case300 AC cold 0.0286 s, warm 0.0178 s, 5 iterations`, 1 passed. The dedicated CI step (ubuntu
3.12 leg only) runs it with `-s` so the line appears in the job log; the default `pytest` run
in the matrix still executes the test (the verdict) without the echo. `-s` was not added
globally.

## 7. Gates (final, on the committed tree)

| Gate | Result |
| --- | --- |
| `uv run mkdocs build --strict` | exit 0, `grep -ci 'warning  -'` → 0 (only Material's MkDocs-2.0 banner on stderr) |
| `uv run ruff check .` | All checks passed, exit 0 |
| `uv run ruff format --check .` | 98 files already formatted, exit 0 |
| `uv run mypy` | Success: no issues found in 31 source files |
| `uv run pytest -q -p no:cacheprovider` | **484 passed**, 10 warnings (pre-existing pandapower/pandas), 56.8 s |
| every example once | 7/7 exit 0 (table in §1; output heads above) |
| docs code blocks | 35/35 executed, outputs match |

`git status --short` clean after the commit.

```
$ git show --stat HEAD
commit e1e7e4febde2b897f4e500c9a60227bce950cfee
Author: Manho Joung <manhojoung@gmail.com>
Date:   Thu Aug 20 21:40:55 2026 -0700

    docs(m2/S7): runnable examples gallery (7 scripts, CI-executed, snippet-embedded), AC power-flow manual finished, timing echoed in CI, ImportWarning→ImportIssue, case300 provenance corrected

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 .github/workflows/ci.yml          |  31 +++++
 docs/changelog.md                 |  42 ++++++-
 docs/design/architecture.md       |  18 ++-
 docs/examples/index.md            | 110 ++++++++++++----
 docs/getting-started.md           |  34 ++++-
 docs/index.md                     |  11 +-
 docs/manual/formats.md            |  36 ++++--
 docs/manual/model.md              |  58 ++++++++-
 docs/manual/power-flow.md         | 258 +++++++++++++++++++++++++++++---------
 docs/manual/results.md            |  12 +-
 examples/01_load_and_validate.py  | 112 +++++++++++++++++
 examples/02_ac_power_flow.py      |  84 +++++++++++++
 examples/03_dc_power_flow.py      |  52 ++++++++
 examples/04_jobs_api.py           |  73 +++++++++++
 examples/05_roles_and_islands.py  |  88 +++++++++++++
 examples/06_network_matrices.py   | 108 ++++++++++++++++
 examples/07_results_and_export.py |  68 ++++++++++
 fixtures/matpower/PROVENANCE.md   |  30 +++--
 src/mambo_power/io/matpower.py    |  14 +--
 src/mambo_power/io/report.py      |   6 +-
 src/mambo_power/model/__init__.py |   6 +-
 src/mambo_power/model/islands.py  |  12 +-
 src/mambo_power/model/warnings.py |  15 ++-
 tests/parity/test_ac_timing.py    |  19 ++-
 tests/unit/test_examples_run.py   |  55 ++++++++
 tests/unit/test_islands.py        |  10 +-
 26 files changed, 1197 insertions(+), 165 deletions(-)
```

## 8. Judgment calls (beyond those inline)

1. **No `scripts/run_examples.py`.** The brief offered it *or* the pytest test; the test
   covers the floor and the CI job gives the visible log, so a third runner would be a
   duplicate to maintain.
2. **02's loading table stamps `rating_mva = 250` on every case118 branch** because the file
   carries `RATE_A = 0` (→ `None` → `loading_pct None`) and a loading table of dashes shows
   nothing; the comment in the script says so and that ratings do not affect the solve.
3. **02's warm-start demo uses the `q_limits=False` solution** — warm-starting with limits on
   re-pins in one round (the setpoint override on previously pinned PV buses, S4's "+1 round"),
   so 0 iterations is only demonstrable without pins; the script and the manual both explain
   the re-pin case rather than hide it.
4. **`ImportReport.warnings` keeps its field name** — the brief said rename the class and keep
   behaviour identical; renaming the attribute would be an API change for S2's callers.
5. **`docs/manual/jobs.md` and `numerics.md` not re-based on snippets.** Their inline blocks
   are executed and correct; replacing them with whole-script embeds would put 70–110 lines of
   script into pages whose narrative wants 5-line blocks. The gallery links both ways instead.
6. **`test_examples_run.py` also asserts embedding.** AC-9's "each is embedded" clause
   otherwise has no test; `check_paths: true` catches a stale embed, not a missing one.

## Follow-up commit (lead's addition)

`502dc1b` — `docs/index.md` status admonition now names the shipped jobs surface explicitly
(`kind="pf.dc"` / `"pf.ac"` through `jobs.run(SolveRequest)` / `jobs.run_json`, link to
`manual/jobs.md`, link to the examples). A grep of `docs/` + README for
`landing|lands in|when it lands|design contract|in the same wave|being implemented|Added when`
finds no remaining hit about AC power flow, results or jobs (the only matches are the word
"islands"). `ruff format --check docs/index.md` clean; `mkdocs build --strict` 0 warnings.

## Open for the fold

- Spec W4 / design item 4 still say `ImportWarning` (orchestrator amends).
- `record/m2-research.md` §1.2 / §4.3 erratum note (A11 says "the research file gets an
  erratum note") — outside the repo, not mine.
- `mkdocs.yml` `edit_uri` still points at `epic/01-foundation` (S6's note; switch at 0.1.0).
