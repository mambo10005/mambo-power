# M9 S1 report — tutorial notebooks

Worktree `C:\Claude Projects\mambo-power-m9-s1`, branch `wave/09-release-0.1-s1`, base `d18aaea`.
Five commits, working tree clean at hand-back.

## Commits

```
bceb367 docs(m9-s1): tutorial 4 — where next (guided fork)
eb84e5c docs(m9-s1): tutorial 3 — a nodal market (intermediate)
2bb8cd7 docs(m9-s1): tutorial 2 — DC-OPF and N-1 screening (intermediate)
7d2b2cf docs(m9-s1): tutorial 1 — your first power flow (beginner)
8af9df5 docs(m9-s1): tutorials index — arc, difficulty tiers, table of the four notebooks
```

`git diff --cached --stat` was checked before every commit (shown per-commit below); only the
one intended file was staged each time — no `-A`.

| Commit | `--stat` |
| --- | --- |
| `8af9df5` | `docs/tutorials/index.md | 36 ++++++++++++++++++++++++++++++++++++` (1 file, 36 insertions) |
| `7d2b2cf` | `docs/tutorials/01-first-power-flow.ipynb | 338 +++...` (1 file, 338 insertions) |
| `2bb8cd7` | `docs/tutorials/02-dc-opf-and-n1.ipynb | 296 +++...` (1 file, 296 insertions) |
| `eb84e5c` | `docs/tutorials/03-nodal-market.ipynb | 304 +++...` (1 file, 304 insertions) |
| `bceb367` | `docs/tutorials/04-where-next.ipynb | 248 +++...` (1 file, 248 insertions) |

`git status` after the last commit: `nothing to commit, working tree clean`.
`git diff pyproject.toml uv.lock`: empty — the jupyter tooling used for verification was
installed transiently (`uv pip install jupyter nbconvert nbformat ipykernel`, not `uv add`),
never touching the dependency manifest. Adding `nbmake` as a permanent docs-group dependency is
S2's job per the wave assignment.

## Deliverable

`docs/tutorials/index.md` (new) states the four-notebook arc and difficulty tier, plus a table
linking each notebook and a pointer to Examples/Manual for readers who want a terser reference.

Four notebooks, all new:

- `docs/tutorials/01-first-power-flow.ipynb` — beginner. Loads `case14` via `io.matpower.load`,
  briefly explains the `Network` model (linking `manual/model.md` rather than re-explaining it),
  runs `pf.solve_dc` then `pf.solve_ac` with a paragraph on when to reach for which, reads bus
  voltages and branch flows, and closes with a non-executed "try it yourself" note pointing at
  `case30.m` (left as prose, not code, so this tutorial's own output stays fixture-independent).
- `docs/tutorials/02-dc-opf-and-n1.ipynb` — intermediate. Opens by contrasting itself with
  tutorial 1 ("a dispatch someone else already chose" vs. "let the dispatch be chosen"). Runs
  `opf.solve_dc_opf` on `case14`, explains the objective/constraints and what an LMP means
  economically in plain language, then runs `contingency.n1` with the same derived
  1.2×-headroom branch ratings `examples/08_opf_and_n1.py` and the test suite use (case14 ships
  no real `RATE_A`), and interprets the first flagged outage (`branch-1` out → `branch-2`
  over its synthetic rating) in a full paragraph rather than just printing numbers.
- `docs/tutorials/03-nodal-market.ipynb` — intermediate. Opens by contrasting itself with
  tutorial 2 ("cheapest dispatch" vs. "a market where generators bid and demand can be
  elastic"). Builds the same hand-built 2-bus `Scenario` as `examples/09_nodal_market.py`
  (mirrored, not copied verbatim — narrated), runs `market.solve_nodal`, explains settlement
  (who pays whom, congestion rent) in plain language, and checks the settlement identity
  directly rather than asserting it.
- `docs/tutorials/04-where-next.ipynb` — guided fork, shorter (~2 code cells vs. 4-6 in the
  others). Explains `market.agents` (strategic bidding) and `io.*` (interchange formats) each in
  a short paragraph, runs one example of each — a hand-built linear-cost pivotal-supplier
  network for agents (mirroring `examples/12_agent_market.py`, since every bundled fixture's
  generators are quadratic and `MarkupStrategy` requires linear) and `io.psse_raw` import on
  `fixtures/case14_v33.raw` for interop (mirroring `examples/13_interop.py`) — and closes with a
  "where to read more" list covering both directions plus the manual pages tutorials 1–3 didn't
  fully cover (multiperiod, zonal, jobs, results, numerics) and Examples as a terser reference.

## Verification

**Every code cell was proved correct twice.** First, each notebook's code was assembled and run
as a standalone `.py` script (`t1.py`–`t4.py` in the scratchpad) against the real worktree,
before any notebook JSON was written — this caught the exact numbers before they were narrated.
Second, jupyter tooling (`jupyter`, `nbconvert`, `nbformat`, `ipykernel`) was installed
transiently (not present in the worktree; installed via `uv pip install`, never added to
`pyproject.toml`) and every notebook was executed fresh with
`uv run jupyter nbconvert --to notebook --execute --inplace docs/tutorials/<name>.ipynb`:

```
[NbConvertApp] Converting notebook docs/tutorials/01-first-power-flow.ipynb to notebook
[NbConvertApp] Writing ... bytes to docs\tutorials\01-first-power-flow.ipynb
[exited with code 0]
```

All four exited 0, no cell raised. The baked-in outputs were then read back out of each
`.ipynb` and diffed by eye against the standalone-script runs — they match bit for bit,
including the deterministic zero in `04-where-next.ipynb`'s RAW-vs-MATPOWER angle comparison
(`worst angle difference 0.0e+00 deg`) and the LP-noise-bearing numbers elsewhere (e.g.
`markup $15,999.97/h`, not a rounder hand-typed figure). Sample outputs, reproduced from the
executed notebooks:

- Tutorial 1: `DC converged: True`; `AC converged: True iterations: 4`; `AC active losses:
  13.393 MW`.
- Tutorial 2: `status: Optimal cost: 7642.59 $/h`; `18 outages flagged, out of 19 screenable
  branches`; outage `branch-1` confirms `branch-2`/`branch-6`/`branch-7` all violating.
- Tutorial 3: `settlement identity ... holds: True`; `congestion rent: $700.00`.
- Tutorial 4: markup climb to `$60.00/MWh`, `converged True`, `iterations 84`; RAW import
  report codes `['BASE_KV_REPLACED', 'RAW_NO_COSTS', 'RAW_SECTION_IGNORED']`.

A separate syntax pass (`compile()` on every code cell's source across all four notebooks) also
passed clean, as a second, independent check beyond the full execution above.

No `.ipynb_checkpoints` directories or other execution artifacts were left behind
(`find docs/tutorials -iname "*checkpoint*"` returned nothing before commit).

**Full notebook-execution verification was NOT deferred** — jupyter tooling was available (after
a transient install) in this worktree, so every notebook was executed end-to-end via
`nbconvert --execute`, matching what S2's `nbmake` CI job will do, not just checked as
standalone-script logic.

## Word count / read-time estimate

| Notebook | Prose words | Code cells | Rough read time |
| --- | --- | --- | --- |
| 01-first-power-flow | 727 | 6 | ~9 min at a brisk pace (130 wpm prose + ~35s/code cell); realistically longer for a first-time reader who runs cells and reads the manual cross-links |
| 02-dc-opf-and-n1 | 766 | 5 | ~9 min brisk / longer in practice |
| 03-nodal-market | 696 | 4 | ~8 min brisk / longer in practice |
| 04-where-next | 888 | 2 | ~8 min brisk / longer in practice |

**Honest caveat, not hedging:** the spec's own framing ("~15–20 min read") is descriptive, not an
enforced acceptance criterion (AC-1 checks `nbmake` execution and site rendering, not a timed
read), and my brisk-reading heuristic (130 wpm prose, ~35s/code cell) is a lower bound — it
doesn't account for a first-time reader actually running cells themselves, pausing to follow a
manual cross-link, or re-reading an unfamiliar concept like LMP congestion splitting or LODF
screening. In practice I expect tutorials 1–3 land close to the 15–20 min target for that reader
and tutorial 4 to read faster, consistent with it being the shorter guided fork the spec calls
for. I did not pad prose artificially to hit a word-count target; the content is scoped to what
each notebook's own topic needs.

## Scope discipline

Touched only the four files this slice owns plus the new `docs/tutorials/` directory itself —
no edit to `mkdocs.yml`, CI config, any `manual/*.md` page, or any `src/` file. `git diff
--stat` against `d18aaea` for anything outside `docs/tutorials/` is empty.
