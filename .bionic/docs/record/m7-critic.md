# M7 critic review — `852dd38` on `wave/07-agents` (base `6ca9dcc`)

Reviewed from an isolated `git archive` copy under the session scratchpad (`critic-852dd38`;
`mambo_power.__file__` printed from that copy before the first run). Five axes, whole wave diff
(22 commits, 32 files, +5703/-136). Every correctness claim below has a runnable reproduction
and its output from that copy.

Full suite on the copy: `uv run --project <copy> python -m pytest -q tests` ->
**2 failed, 1157 passed, 4 skipped in 408.64s**. Both failures are finding 1.

## Findings

### 1. BLOCKING — the duplicate-JSON-key rejection was never committed; its tests fail and the manual documents behaviour that does not exist

`src/mambo_power/jobs/run.py` (whole file: no `object_pairs_hook`, no pre-parse);
`docs/manual/jobs.md:107`; `tests/unit/test_jobs.py:1316` and `:1345`.

Commit `bfd25d4` ("run_json rejects a duplicated JSON key at any depth as BAD_REQUEST") changed
only the manual and the tests:

```
$ git show bfd25d4 --stat --format=
 docs/manual/jobs.md     |  2 +-
 tests/unit/test_jobs.py | 49 +++++++++++++++++++++++++++++++++++++++++++++++++
$ git diff 6ca9dcc..852dd38 --stat -- src/mambo_power/jobs/
 src/mambo_power/jobs/models.py   |   5 +-
 src/mambo_power/jobs/registry.py | 104 ++++++++---
$ git show 852dd38:src/mambo_power/jobs/run.py | grep -n "pairs\|duplicate"
(nothing)
```

Reproduction — the wave's own tests, on the copy:

```
>       error = _assert_failed(out, "BAD_REQUEST")
out = SolveResult(kind='market.agents', job_id='dup-1', status='ok', result=MarketAgentsResult(...
    'strategies': {'agent_a': {'kind': 'price_taker'}, 'agent_b': {'kind': 'markup', 'step': 0.5}} ...
E       AssertionError: assert 'ok' == 'failed'
FAILED tests/unit/test_jobs.py::test_run_json_rejects_a_duplicated_strategies_key_as_bad_request
FAILED tests/unit/test_jobs.py::test_run_json_rejects_a_duplicated_top_level_key_as_bad_request_for_any_kind
```

So at this head: (a) the suite is red; (b) AC-6's last clause ("never a silently accepted
last-wins duplicate") is unmet — a request naming `agent_a` twice runs to `status=ok` on the
last value, which is the audit finding the commit claims to close; (c) the jobs manual's
`BAD_REQUEST` row promises a check `run_json` does not perform. The commit message describes a
sabotage run ("skip the pre-parse, both tests redden") that cannot have been made against this
tree.

Fix: land the missing `run.py` change — a `json.loads(text, object_pairs_hook=...)` pre-parse at
the top of `run_json`, inside the same `(ValueError, RecursionError)` guard `_peek` uses so
malformed or too-deep text still reaches pydantic's `BAD_REQUEST` path unchanged. Re-run
`tests/unit/test_jobs.py` and show both tests green. For the fixer: the hook is a second full
parse of every request; measure it on case300 and record the cost (nothing exists to measure
yet).

### 2. SHOULD-FIX — a settled markup climb is reported as `cycle` when the profit peak sits between two grid points: the "exactly two steps" derivation (A9) is false there, and the tie rule beneath it is decided by HiGHS tolerance noise

`src/mambo_power/market/strategy.py:304-308` (`really_decreased`, `_PROFIT_TIE_REL_TOL = 1e-9`);
`src/mambo_power/market/agents.py:163-185` and `:291-296` (`offer_tol >= 2 * step`), `:439-469`
(`_settled`).

Sweep: `MarkupStrategy` on the smooth-pivotal and duopoly fixtures, true cost in
{20.0, 20.3, 21.7, 19.9, 33.33} x step in {0.1, 0.2, 0.3, 0.5, 0.7, 0.05, 0.01},
`offer_tol = 2 * step`, `max_iterations = 20000` (`repro2.py`). 68 of 70 converge; two do not:

```
  smooth  tc=33.33 step=0.01: cycle iters=3339 offers=[66.65999999999525]
  duopoly tc=33.33 step=0.01: cycle iters=3345 offers=[66.65999999999525, 66.65999999999525]
```

That run has settled at its optimum by every economic reading — the closed-form peak is
`(100 + 33.33) / 2 = 66.665`, the offer is one half-step off it. The window the classifier saw
(`repro7.py`, `_amplitude` instrumented):

```
   level=66.67 lmp=66.67003 q=333.2993 profit=11112.210884
   level=66.68 lmp=66.68003 q=333.1993 profit=11112.208878
   level=66.67 ...
   level=66.66 lmp=66.66003 q=333.3993 profit=11112.210891
   level=66.65 lmp=66.65003 q=333.4993 profit=11112.208898
   level=66.66 ...
  amplitude 0.030000000000015348      offer_tol = 0.02  ->  "cycle"
```

Mechanism: the peak is equidistant from grid points 66.66 and 66.67, so their profits tie
(6.7e-6 $/h apart on 11,112 — inside the relative 1e-9 band); the tie rule reads "not worse",
keeps direction, overshoots one more step before the real decrease reverses it, and the settled
orbit is **period 6, three steps wide**, not two. `offer_tol = 2 * step` then classifies a
settled run as a genuine cycle — the confident wrong diagnosis the module docstring says the
three-word enum exists to prevent. Every true cost `c` for which `(100 + c) / 2` lands on a
half-step of the grid is exposed; at the wave's own step of 0.5 that is every `c` ending in
`.5`.

The second half of the same window shows why the sweep did not catch `c = 20.5, step = 0.5`
(`repro6.py`/`repro7.py`: reported `converged`, amplitude 1.0): HiGHS's QP tolerance puts the
LMP at 60.50004 for an offer of 60.5 and the dispatch at 394.9992 for a closed-form 395, so the
two "tied" profits differ by **4.0e-4 $/h** (relative 2.5e-8), which is *outside* the 1e-9 tie
band. The direction at the peak is therefore decided by solver noise — it happened to favour
the lower point here. The strategy docstring measures that noise at "order 1e-12" for an agent
at capacity; at a marginal agent it is four orders larger, and the band was sized to the wrong
case.

Fix, two parts. (a) The derived constant is `3 * step`, not `2 * step` — a tie at the peak
widens the settled orbit by exactly one step, and a strictly concave profit cannot tie three
points in a row — so change the validator, `_resolve_agents` and `_settled`'s docstring
together, and pin `(33.33, 0.01, offer_tol=0.03)` as the regression. (b) Size
`_PROFIT_TIE_REL_TOL` to the solver, not to arithmetic: `dc_opf` sets no HiGHS tolerance
(`dc_opf.py:806` sets only `output_flag`), so the primal/dual feasibility defaults of 1e-7
bound the LMP/dispatch error the profit is computed from, and a relative band
of order 1e-6 turns the peak comparison from a coin flip into a tie every time the closed form
says it is one. Re-run the sweep after both and expect 70 of 70.

### 3. SHOULD-FIX — the loop recomputes the PTDF (and B-bus, incidence) every round; 70% of a 200-round run rebuilds a matrix that never changes

`src/mambo_power/market/agents.py:615-623` (`dc_opf(arr, ...)` per round) ->
`src/mambo_power/opf/dc_opf.py:875` (`ptdf_matrix = compute_ptdf(arr)`).

Offers change per round; the network does not. `dc_opf` cannot accept a precomputed PTDF, so every
round pays `ptdf() -> bbus() -> bf() -> incidence()` plus scipy sparse construction. cProfile, 200
update rounds on case14 with a never-settling strategy (every agent creeps `c1` by
`1e-6 * round_index`), from the copy:

```
reason iteration_cap iters 200 wall 5.20s
   ncalls  tottime  cumtime  filename:lineno(function)
      201    0.054    2.794  numerics/ptdf.py:21(ptdf)           <- 70% of 3.99s profiled
2211/2010    0.127    1.654  scipy/sparse/_compressed.py:30(__init__)
      201    0.015    1.382  numerics/bbus.py:55(bbus)
      402    0.041    0.778  numerics/bbus.py:46(bf)
      201    0.025    0.407  numerics/bbus.py:38(incidence)
      201    0.259    0.338  highspy/highs.py:1525(enableCallbacks)
```

HiGHS is a rounding error next to the PTDF rebuild at this size; on case300 (dense
`n_branch x n_bus` PTDF from a sparse solve per round) the ratio worsens. `dc_opf.py:223` already
records PTDF as "~31% of a warm `solve_dc_opf`"; the loop multiplies that by `iterations + 1`.

Fix: an optional `ptdf: FloatArray | None = None` keyword on `dc_opf` (computed when `None`, so
every existing caller is unchanged); `solve_agents` computes it once after
`NetworkArrays.from_network` and passes it every round. `_clearing_rows` already reads
`solution.ptdf`. One test asserting bitwise-equal dispatch/LMPs against the per-round path
(AC-3's `array_equal` discipline).

### 4. SHOULD-FIX — `_clearing_rows` is a verbatim second copy of `solve_nodal`'s rows and branch-flow assembly, written in the same wave as the first

`src/mambo_power/market/agents.py:472-547` vs the M7 block in `src/mambo_power/market/nodal.py`
(`elastic_idx_arr ... flows_mw ... branches = [...]`, plus the generator/load row comprehensions
and the two settlement sums).

`agents.py:521-542` is character-for-character the branch-flow block commit `832a546` added to
`nodal.py`, modulo one `g_shunt_mw` temporary. `nodal.py`'s docstring for that block says "This
is not a parallel formula" — and the wave then adds a parallel copy. The spec's ownership table
names one owner for branch flows; the code has two. The next change to the elastic
double-counting contract or the `pf_shift` sign drifts one of them.

Fix: one function, e.g. `market/_clearing.py: clearing_rows(net, arr, solution, lmp,
elastic_idxs) -> (generators, loads, branches, total_load_payment, total_generator_receipts)`,
called by both solvers. `_clearing_rows` already has that signature; move it and delete the nodal
copy (~60 lines gone).

### 5. SHOULD-FIX — `MarkupStrategy(step=nan)` is accepted on the in-process path and silently runs as a price-taker reporting `converged`

`src/mambo_power/market/strategy.py:283-286` (`if step <= 0`), `:312` (`max(true_level, ...)`).

`nan <= 0` is `False`, so the guard passes; `offer_prev + direction * nan` is `nan`; Python's
`max(true_level, nan)` returns `true_level` because the comparison is `False`, so every round
offers true cost. The config path is safe (pydantic `gt=0` rejects NaN); the object path is not:

```
== NaN step through config / object
config rejects NaN: ValidationError
object accepted NaN step
 run: Optimal converged 2 [20.0, 0.0]
```

`step=inf` is caught only incidentally by `_resolve_agents`' `offer_tol < 2 * step` check.
Fix: `if not (step > 0) or not math.isfinite(step): raise ValueError(...)`. In-process seam
only, but it is exactly the plausible-wrong-answer class the wave names in every docstring.

### 6. SHOULD-FIX — the generator-side double-charge guard steps around an out-of-range `pwl_costs` index, which then dies as a raw `IndexError` instead of the `ValueError` the docstring promises

`src/mambo_power/opf/dc_opf.py:443` (`if 0 <= i < n_gen and ...`).

The load side range-checks its bid index and raises `ValueError` (docstring `:393`). The new
generator-side guard defends *itself* against an out-of-range index and lets it reach numpy:

```
== guard: pwl index out of range, nonzero row -> ?
IndexError index 99 is out of bounds for axis 0 with size 5
```

Through `jobs` that is `INTERNAL`; the load-side mirror is a structured `ValueError`. The guard's
other two edges are right — a `c0`-only nonzero row is rejected (a constant *is* a charge) and a
legitimate all-zero row beside a PWL entry clears:

```
== guard: c0-only nonzero row + pwl
ValueError: generator index(es) [0] appear in both cost_coeffs (nonzero row) and pwl_costs
== guard: legit all-zero row + pwl
status Optimal
```

Fix: drop the `0 <= i < n_gen` clause and add the range check the load side has, before the
double-charge test, raising `ValueError` naming the index. (The `IndexError` predates the wave;
the wave wrote a guard that explicitly avoids fixing it.)

### 7. NIT — `_settled`'s `abs_tol=1e-9` is in cost-coefficient units and doubles the default `offer_tol`

`src/mambo_power/market/agents.py:467-469`, `:151`. `_AMPLITUDE_TIE_REL_TOL` is reused as
`abs_tol`, so with the default `offer_tol=1e-9` any amplitude up to ~2e-9 is "converged". The
docstring argues for a relative band and ships an absolute one the size of the default it
guards. Fix: `abs_tol=0.0`.

### 8. NIT — an all-price-taker (or empty) agent set clears the market three times to report `iterations=2`

`src/mambo_power/market/agents.py:648-659`.

```
== R-A: all-price-taker run: clearings/iterations
iterations 2 reason converged
```

Correct under the stated state model (the state is the *pair* of offer vectors, so a fixed
point needs three equal rounds), and AC-3 relies on the loop actually running — do not change
the loop. But `iterations`'s description ("the number of best-response update rounds") reads
as "two updates happened" for a configuration in which nothing moved. One sentence in the field
description or manual: a fixed point is confirmed after two identical updates, so `iterations`
is at least 2 on any Optimal run.

### 9. NIT — `_cost_at`'s piecewise clamp is dead code

`src/mambo_power/market/agents.py:231-234`. The loop runs `k in range(len(points) - 1)`, so
`lower <= len(points) - 2` already; `min(lower, len(points) - 2)` never changes anything.
Delete it, or replace the scan with `bisect_right` on the abscissae.

### 10. NIT — `offer_tol >= 2 * step` is enforced twice with two message texts

`MarketAgentsOptions._offer_tol_admits_every_stepped_strategy` (`agents.py:163-185`) and
`_resolve_agents` (`agents.py:291-296`). Both paths need it, but the rule belongs to the
strategy: a `MarkupStrategy.min_offer_tol` property (`2 * step`) checked once in
`_resolve_agents` after `build_strategy`, and the pydantic validator deleted. One rule, one
text, and a user-supplied strategy can opt in by exposing the same property.

### Looked for and not found

- **History indexing.** `history[k]` is round `k` by construction; `_observation(agent, r,
  history)` reads `history[r-1]` / `history[r-2]` behind `r >= 1` / `r >= 2` guards, and
  `Observation`'s validator independently pins each record's `round_index`. Round 0's offers are
  collected once in `_initial_offers` and never re-asked. Correct.
- **Cycle window.** Key at round `r` is `(offers[r-1], offers[r])`, first seen at `r0`; the
  window `history[r+1-period:]` is rounds `r0+1..r`, exactly one period; a period-1 repeat gives
  a one-round window with `ptp = 0`. Correct.
- **`_offer_key`.** Exact JSON, so no two distinct vectors collide. `0.0` and `-0.0` serialise
  differently (`[20.0,0.0]` vs `[20.0,-0.0]`), so a strategy alternating signed zeros would never
  match itself — but no shipped strategy can produce `-0.0`, and the failure mode is the benign
  one (iteration cap) the docstring accepts.
- **Float drift in a settled climb.** `MarkupStrategy` on the smooth-pivotal and duopoly
  fixtures, 5 true costs x 7 step sizes, `max_iterations = 20000`: no run ever failed to
  *repeat a state exactly* — accumulated `+step`/`-step` error (4.7e-12 after 3,339 rounds)
  never prevented the pair key from matching. The two non-converging runs are finding 2, a
  classification error, not a drift one.
- **Remaining strict comparisons on solver output.** `offer_prev >= offer_2ago` compares
  strategy outputs, not solver output; the idle rule and profit rule carry tolerances; `_settled`
  carries one. Nothing left I could flip with ULP noise.
- **`_pass_diagonal_hessian` stride.** `dim = n_periods * per_period_dispatch`; generator block
  at `base`, demand at `base + n_gen`, storage columns zero — identical to the inline code it
  replaced in all three callers, and `test_opf_multiperiod.py`'s hand oracle covers the
  multiperiod layout.
- **`AgentSetError` coverage.** `_initial_offers` maps only `NotImplementedError`; the other
  escape is `_checked_offer`'s `TypeError`, reachable only from the in-process seam and correctly
  `INTERNAL` when a caller's own strategy returns `None`.
- **The seam.** Config and object paths meet in `_resolve_agents` as `(label, Strategy)` and are
  one code path from there; `provenance.options` echoes only the config and
  `AgentOfferResult.strategy` records what actually ran, as documented.
- **Boundary.** `run_json` on a 20,000-deep nested request returns `BAD_REQUEST` in 0.00s
  without raising; a strategy config can only select a shipped `kind`. Nothing beyond finding 1.
- **Exports.** No `_`-prefixed name in any `__all__`; `TerminationReason` from `results` is
  appropriate. `market/agents.py` at 725 lines is one thing (the loop) plus finding 3's copy.
- **`examples/12_agent_market.py`** runs to completion on the copy (AC-4/AC-5 numbers and the
  jobs section all print).

## Verdict

**Not merge-ready.** The suite is red at this head: commit `bfd25d4` shipped the tests and the
manual entry for duplicate-JSON-key rejection but not the `run.py` change, so both
`test_run_json_rejects_a_duplicated_*` tests fail, AC-6's last clause is unmet, and
`docs/manual/jobs.md:107` documents a check that does not run (finding 1). That is a one-commit
fix; after it the wave is merge-ready once findings 2-6 land — the settled climb that the amplitude classifier reports as a cycle (finding 2), the per-round PTDF rebuild (70%
of loop time, one keyword on `dc_opf`), the clearing-rows block copy-pasted from `solve_nodal`,
the NaN `step` on the object path, and the guard that steps around an out-of-range PWL index.
The loop's indexing, cycle detection and float-noise handling — the wave's most-repeated defect
class — held up under everything I threw at them.

## Appendix — reproduction scripts

All under the session scratchpad beside the copy: `repro1.py` (loop/strategy edges),
`repro2.py` (drift sweep), `repro3.py` (guard edges + cProfile), `repro4.py` (boundary + NaN).

## Re-review at `12aa3ce`

Fresh `git archive` copy (`critic-12aa3ce`), never run in either checkout; seven commits since
`47b52da`. Full suite on the copy: **1172 passed, 4 skipped in 430.55s**. Every earlier
reproduction re-run against this head (`rr_sweep.py`, `rr_checks.py`, `rr_golden.py`,
`rr_depth.py` in the scratchpad).

| # | finding | status at `12aa3ce` | evidence |
|---|---|---|---|
| 2 | settled climb reported as `cycle` | **fixed** | floor is `MarkupStrategy.min_offer_tol = 3 * step`, one text via `_offer_tol_shortfall`; 70-case sweep at `offer_tol = 3 * step`: **0 of 70** non-converged (was 2); the 33.33 / 0.01 case: `converged 3339 [66.66, 0.0]`; `offer_tol=1.0, step=0.5` is now refused as it must be |
| 2 (tie band) | `_PROFIT_TIE_REL_TOL` left at 1e-9 | **accepted** | the argument: the real profit change between adjacent grid points near a peak is `10·s·(2d + s)` (linear in `s`, vanishing only at an exact half-grid tie), while the solver's ~4e-4 $/h noise is step-independent, so noise can only mis-decide a comparison whose true answer is "tie or nearly" — and a mis-decided near-tie widens the settled orbit by at most one step, which the `3 * step` floor now covers. Adversarial attempt to break the *verdict*: a near-peak fixture (marginal value `25 − 0.1p`, peak 2.5 $/MWh above cost) at steps 0.005 / 0.002 / 0.001, on-grid and half-grid (`tc=20.0`, `20.001`): all six `converged`, offers within one step of the closed-form peak. I could not construct a misclassified verdict; the band is a direction-quality issue only, and the noise-dominated regime (`s ≲ 0.002`) still settles |
| 3 | PTDF rebuilt per round | **fixed** | `dc_opf(..., ptdf=)` keyword; 200-round case14 run **5.20 s → 0.47 s**; cached vs computed dispatch/duals `array_equal` True; wrong shape `(3,3)` → `ValueError ... must have shape (20, 14)`; a right-shape wrong-content matrix is trusted (documented as a cache; acceptable). Non-agents callers byte-identical: `solve_nodal` and `solve_dc_opf` on case14/case30/case57 plus the two elastic fixtures dumped to JSON from the `47b52da` and `12aa3ce` venvs — `cmp` reports identical |
| 4 | duplicated clearing rows | **fixed** | `market/_clearing.py: clearing_rows()` returning a `ClearingRows` NamedTuple, both callers; `agents.py` −222/+~60, `nodal.py` −106; the golden JSON above covers `solve_nodal`'s side, `test_market_agents.py` the other |
| 5 | NaN / inf step | **fixed** | `nan`, `inf`, `0.0`, `-1.0` all refused: "must be positive and finite" |
| 6 | out-of-range PWL index | **fixed** | `ValueError: pwl_costs generator index 99 out of range for 5 generators (NetworkArrays.gen_ids)`; the `0 <= i < n_gen` clause is gone from the double-charge guard |
| 7 | `abs_tol` in `_settled` | **fixed** | `abs_tol=0.0`, with the reason in the docstring |
| 8 | `iterations` ≥ 2 undocumented | **fixed** | field description now says why an all-price-taker run reports 2 |
| 9 | dead clamp in `_cost_at` | **fixed** | removed |
| 10 | two enforcement texts | **fixed** | `_offer_tol_shortfall` shared by validator and `_resolve_agents` |
| 1(a) | `"__dup__"` marker key | **fixed** | `_Node.duplicated` attribute; a request carrying a literal `"__dup__"` key beside a real duplicate now reports the real one (`duplicate key "kind" at network`) |
| 1(b) | public-looking `DuplicateKeyError` | **fixed** | `_DuplicateKeyError`, module-private |

Hook re-probed at this head: list-element path `network.buses[2]`, `\u`-escaped duplicate, a
duplicate under a duplicated parent (reports the parent, first in DFS order — correct),
20,000-deep nesting → `BAD_REQUEST`, 100k duplicated objects → 0.29 s. `examples/12` runs.

### New finding introduced by the seven commits

**11. SHOULD-FIX — `_reject_duplicate_keys` now walks every request, and the walk's Python
recursion overflows outside its `try` at JSON depth ≈1000, turning a `BAD_REQUEST` into
`INTERNAL`.** `src/mambo_power/jobs/run.py:257-281` (`walk` is defined and called after the
`try/except` that guards only `json.loads`). At `47b52da` the walker ran only on a request that
had already failed pass 1; at `12aa3ce` it is the single pass, so it runs on every request and
its recursion is unguarded. Depth ladder through `run_json`, same script on both copies:

```
depth   47b52da        12aa3ce
 990    BAD_REQUEST    BAD_REQUEST
1000    BAD_REQUEST    INTERNAL  RecursionError: maximum recursion depth exceeded
1100    BAD_REQUEST    INTERNAL  RecursionError: maximum recursion depth exceeded
5000    BAD_REQUEST    BAD_REQUEST   (json.loads itself overflows first, inside the try)
```

`run_json`'s catch-all keeps the never-raise promise, but the verdict is wrong: the request is
malformed for pydantic, not an engine fault, and the window (roughly depth 1000-1300, where
the C scanner succeeds but the Python walker does not) is reachable by anyone who sends a
deeply nested payload. Fix: move the `walk(root, "")` call inside the same `try` (a
`RecursionError` there should also "return — pydantic's turn"), or make the walk iterative
with an explicit stack, which also removes the depth coupling entirely. One regression test at
depth 1100 asserting `BAD_REQUEST`.

Also measured, not a finding: the hook's per-request cost rose from 3.1 ms to **7.8 ms** on the
case300 request (the walk now runs on success too, and `_Node` is a Python subclass per
object) — ~5x a plain `json.loads`, ~30% of the request end to end. Acceptable at this scale;
an iterative walk that stops at the first `_Node` in a proven-clean tree cannot help, since
cleanliness is what the walk establishes — but tracking "any duplicate seen" in a closure
during the hook pass and skipping the walk when none was would restore the 3 ms path for every
valid request. Worth folding into the fix for 11.

### Verdict at `12aa3ce`

**Merge after finding 11** — a small, contained regression in the one file the last commit
rewrote; everything else from the first two reviews is fixed and re-verified by my own
reproductions, the suite is green (1172 passed), and no other caller's numbers moved.

## Confirmation at `9739be8`

Fresh archive (`critic-9739be8`); only `jobs/run.py` (+21/−17) and `tests/unit/test_jobs.py`
(+12) differ from `12aa3ce`. Finding 11 is closed: the depth ladder through `run_json` now
reads `BAD_REQUEST` at 990 / 1000 / 1100 / 5000 (was `INTERNAL` at 1000 and 1100), the
explicit-stack walk runs only when the parse hook saw a duplicate, and a clean case300
`pf.dc` request pays 2.3 ms in `_reject_duplicate_keys` against 1.3 ms for a plain
`json.loads` — down from 7.8 ms at `12aa3ce` and below the 3.1 ms of `47b52da`. The
duplicate-position probes all still report the first duplicate in text order: a list element
(`"base_kv" at network.buses[2]`), a `\u`-escaped key (`"kind" at request`), duplicates in two
sibling objects (`"x" at options`), a duplicated parent over a duplicated child (`"options" at
request`), a literal `"__dup__"` key beside a real duplicate (`"kind" at network`), and 100k
duplicated objects in 0.48 s. `tests/unit/test_jobs.py`: 120 passed. **Final verdict:
merge-ready as-is at `9739be8`.**
