# M6 R1 fold A — code and tests

**Role:** senior-implementor, code half of wave M6's R1 fold.
**Worktree:** `C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`.
**Floor taken at:** `d0ce957` (974 passed / 4 skipped).
**Head at hand-back:** `6edf7f6` — **990 passed / 4 skipped**, 994 collected.
**Gates:** `ruff check src tests`, `ruff format --check src tests`, `mypy` — all clean on every commit.
**Ownership honoured:** `src/**` and `tests/**` only. No `docs/**`, `examples/**` or `mkdocs.yml` touched;
`git status --porcelain` run before every stage and every commit made with explicit paths.

All ten items are done. Nothing was left.

---

## Commits

Fold-b's docs commits are interleaved on the same branch; these seven are mine.

| Commit | Items | What |
|---|---|---|
| `3ac434f` | (k) | case300's price clause becomes a two-solve comparison that locates the degeneracy |
| `39dfb37` | (l) | AC-5(b) asserts the curtailment-compensation identity, not a sign flip |
| `a3db517` | (c) | corridor validation: `BAD_OPTIONS` at the options model, `VALIDATION` at resolution |
| `8f1e187` | (n), (e) | `MAX_CORRIDORS = 500`; `cap_mw = inf` expressible end to end |
| `15ab30b` | (p) | `getNumRow` tripwires on `opf/zonal.py` and `opf/redispatch.py` |
| `781d04f` | (q), (r) | AC-5(a)'s premise conditioned and paired; the netting test made falsifiable |
| `6edf7f6` | (a), (h), (m), (o), (b) | `src` docstring citations stripped, plus the four one-liners |

Test-count arithmetic, all mine: (k) −1/+1, (l) −1/+1, (c) +9, (n) +3, (e) +3, (q) +1, (r) −1/+1.
974 + 16 = 990. `--collect-only` reports 994 = 990 passed + 4 skipped.

---

## Revert-and-watch

Every sabotage ran in a detached scratch worktree
(`git worktree add --detach …/sab-fold-a <sha>`), driven from the main venv with
`PYTHONPATH="$SC/src;$SC"`. The loaded module path was printed for the first run
(`LOADED: …\sab-fold-a\src\mambo_power\opf\redispatch.py`), each sabotage's file sha256 was taken
before and after, and every tree was restored with `git checkout -- src tests` and verified clean
by `git status --porcelain`. The worktree was removed at the end
(`git worktree list` now shows only the two real ones).

Where a test was *replaced*, the condemned test was restored into the scratch tree under a
`test_OLD_…` name so both run in the same pytest invocation — the comparison is then one process,
one solver build, one fixture.

| # | Sabotage | Site | Old test | New test | What it proves |
|---|---|---|---|---|---|
| 1 | anchored-rate objective: `gen_rate = c1` (linearise at 0, not at `p0`) | `opf/redispatch.py:336` | **PASSED** | **FAILED** (energy components, clause 1) | (k): the old case300 clause was complementary slackness; the new one is a price comparison |
| 2 | same, whole AC-4 selection | " | — | 6 failed / 3 passed | the rest of AC-4 was already sensitive; only the case300 clause was not |
| 3 | same, redispatch-level sibling | " | — | **FAILED** (`objective_cost` 706318.04 vs 704462.85) | `test_opf_redispatch.py:375` does *not* have the flaw — it already compares two independent solves |
| 4 | drop the compensation term: `redispatch_payment = cost_final − cost_zonal` | `market/zonal.py:490` | **PASSED** | **FAILED** (obtained 6.05e-5, expected 0.9411 ± 1e-3) | (l): the old AC-5(b) was satisfied by the sign flip alone |
| 5 | vacuous `0 == 0` row family appended after the last tier, **asserts present** | both new builders | — | 43 failed / 28 passed / 14 errors | (p): the tripwires fire |
| 6 | same sabotage, **asserts removed** | " | — | **734 passed** — the entire unit suite green | (p): each assert is the *only* guard on its layout. Same shape as M5 A31 |
| 7 | non-netted split: `+5.0` on both delta columns | `opf/redispatch.py:521` | FAILED | FAILED | (r): **inconclusive** — this breaks `up · down == 0`, which the old test does check. Recorded rather than hidden; superseded by #8 |
| 8 | `gen_net = 1.05 × (col_value[up] − col_value[down])` | `opf/redispatch.py:519` | **PASSED** | **FAILED** | (r): reconstruction, orthogonality and non-negativity all still hold — only a comparison against an independent final point sees it |

On #7: my first attempt at an (r) sabotage was not discriminating, and I say so rather than
reporting the pair that happened to look good. The old netting test's three identities *do* pin the
reported pair — **given `dispatch_mw`**. What they cannot see is `dispatch_mw` itself being wrong,
because all three are computed from the same `gen_net`. Sabotage #8 is aimed there, and it is the
one that separates the two tests.

Sabotage #1 also confirms, in passing, review C13's own claim: the netting test **passed** under the
anchored-rate objective, at a point 106.9 MW away from the right one.

---

## Item by item

### (k) — the vacuous case300 LMP check · `3ac434f` · audit F2 (HIGH)

`test_ac4_case300_flow_duals_are_degenerate_at_the_nodal_optimum` computed both `at_rating` and
`priced` from one solution's own primal and dual rows. That is complementary slackness: every
optimal LP solution satisfies it. The wave's own readback recorded it as "the survivor" of the
anchored-rate sweep, which is the proof it carried no information.

Replaced by `test_ac4_case300_prices_agree_except_across_the_degenerate_face`, three clauses, all
reading `solve_nodal`'s independent decomposition:

1. **The energy components agree** — 5.40e-6 measured on a 40.876 $/MWh price level, pinned at
   1e-3. Degeneracy is freedom in the dual of the *flow* rows; the balance dual is the system-wide
   price level and every vertex of the optimal face shares it. This is the price comparison case300
   did not have.
2. **The congestion difference lives on the at-rating branches** — re-expressed as flow duals on
   those seven alone by least squares, residual **4.02e-16** against a 0.3188 $/MWh sup-norm
   difference, in a 300-dimensional space. Seven vectors span 7 dimensions of 300; landing inside
   to 4e-16 is a statement, not an artefact.
3. **The unpriced part of that face carries the disagreement** — refitting over the five branches
   the chain actually prices leaves **0.2977** (93% of it). Without this, clause 2 could be a
   subspace large enough to absorb anything.

The fit names the degeneracy outright: −0.3188 $/MWh on `branch-48` and −0.3189 on `branch-360`.
One solve prices that at-rating pair one way round, the other the other way. `branch-48` and
`branch-360` are both at rating; only one is priced by each solve.

The old test's structural assertions (`priced ⊆ at_rating`, `at_rating` strictly larger) are kept —
not as the claim, but as the **premise** clause 3 needs. A vacuity guard was added too: if the two
solves' congestion components ever agree on some future build, the test says so and tells the reader
to assert the LMP tolerance flat instead of leaving clauses 2 and 3 silently empty.

Three new constants, each with its measurement and its headroom in the docstring:
`CASE300_ENERGY_ATOL = 1e-3`, `CASE300_DEGENERATE_FACE_ATOL = 1e-6`,
`CASE300_FACE_IS_LOAD_BEARING_ATOL = 0.1`.

The module docstring's A20 paragraph, which still described the old structural property, was
rewritten to describe what is now asserted.

**Applied to the sibling?** No — it does not have the flaw. `test_opf_redispatch.py:375` computes
`priced_nodal` from a *separate* `_nodal(net)` solve, asserts `objective_cost ≈ nodal.objective_cost`
and asserts the two priced sets **differ**. Sabotage #3 takes it red. Left alone.

### (l) — the payment/cost-gap relation · `39dfb37` · audit F4 (MED)

With `A = cost_final − cost_zonal` and `B = value_zonal − value_final`, the three published figures
are `A + B`, `0` and `−A`. Every clause of `test_ac5b_the_three_figures_differ_on_case30` (payment
> 1, gap < −1, the two more than 1.0 apart) is satisfied by the sign flip alone, and would still
hold with `B` identically zero — which is exactly what the fixed-load case is.

`test_ac5b_the_third_figure_is_the_curtailment_compensation` asserts the identity

```
redispatch_payment + generation_cost_gap == value_zonal − value_final
```

with the right-hand side computed independently from the result's own load rows and the network's
bid curves, on a paired fixture:

| fixture | payment | gap | sum | independent RHS | residual |
|---|---|---|---|---|---|
| bid (case30 + `tests/_bids`) | +14.513372 | −13.572257 | +0.9411150 | +0.9410544 | 6.05e-5 |
| fixed load (case30, no bids) | +14.636683 | −14.636683 | −2.649e-11 | 0 exactly | 2.65e-11 |

`COMPENSATION_ATOL = 1e-3` (the bid fixture's residual is float cancellation — the two bid values
are ~3.0e5 $/h and differ by 0.94) and `COMPENSATION_FLOOR = 0.5`, which is what stops the identity
being discharged by `0 == 0`. The paired case also asserts the payment is still large there, so it
shows the two fields *cancelling* rather than both being small.

New module-scope fixture `case30_fixed_load` and helper `_fixed_load_zoned_network`: the same rated,
zone-promoted case30 with `tests/_bids` left off, so the pair differs only in the elasticity.

New helper `_served_bid_value`, deliberately not `_welfare(zonal) − _welfare(final)` — that would
fold the cost difference back in and reproduce `redispatch_payment`'s own definition instead of
testing it.

The identity is now **stated in the code**, per the brief: `market/zonal.py`'s module docstring gets
a named paragraph, and `results/zonal.py` gets it in the module docstring *and* in both field
descriptions. `results/zonal.py`'s "none is derived from another" claim was false and is gone.

### (c) — corridor validation · `a3db517` · walk D1 (HIGH), review F1

RED first: 4 jobs-surface tests and 5 model tests failing before the change. The same-order
duplicate failed by *succeeding* — it cleared the market at 999 MW and returned `status="ok"`.

**`BAD_OPTIONS`** — a `model_validator(mode="after")` on `MarketZonalOptions` rejects a self-pair
(stated in `zone2`'s description since S5, never checked) and a repeated unordered pair in either
order. The same-order case was the worse one: `corridor_map()` is a dict comprehension, so
`[(A,B,10), (A,B,999)]` silently kept the last entry. Caught on the options model, so `jobs.run`
step 2 reports it with pydantic's own `details` and it never reaches a solve. Identical caps are
rejected too — the caller who writes a pair twice has said something ambiguous whatever the numbers,
and making the rule depend on the values rather than the shape would be worse.

The paired positive is committed as well (`test_distinct_corridors_sharing_one_zone_are_accepted`):
a validator that rejected any repeated *zone id* would pass all four negative cases and break every
real fixture.

**`VALIDATION`** — a corridor naming a zone no bus is assigned to is a statement about the pair
(options, network), which an options model cannot make. `solve_zonal` now checks it against the
resolved partition via `_reject_corridors_naming_absent_zones`, which raises
`NetworkValidationError` with a `DANGLING_REF` issue whose `path` is the offending option
(`options.corridors[0].zone2`). `jobs/run.py` already maps that to `VALIDATION` with `.issues`, so
no change to the runner boundary was needed. Every offending end of every corridor is reported in
one pass, following `NetworkValidationError`'s own convention. `DANGLING_REF` was chosen from the
existing closed `ValidationCode` set rather than adding one: an option referencing an id nothing in
the network carries *is* a dangling reference, and the caller gets a path they can act on rather
than a bare message.

**`opf/zonal.py:280`'s guard: kept, not removed.** Review F1 called it unreachable. It is reachable
and covered — `tests/unit/test_opf_zonal.py:594` drives `{AB: CAP, ("B","A"): CAP}` through it and
expects "appears twice in corridors". What is unreachable is the *same-order* duplicate, and that is
not a hole in the function: `corridors` is a `Mapping`, so a pair repeated in the same order is one
key by the time it arrives. That is precisely why the repeat has to be rejected on the *list* one
layer up. `_normalise_corridors`' docstring now says this and names the layer that owns the other
half.

Docstrings brought in line: both `CorridorLimit` field descriptions (each now names the layer that
enforces it and the jobs code the caller sees), `corridor_map`, and `market/zonal.py`'s "never
raises" paragraph, which now says which exception each malformed input raises and therefore which
code reaches the caller.

**Not done, and why — walk D1's fourth leg.** `"N of M in-service buses carry no zone"` still lands
as `INTERNAL`. The brief's item (c) names three cases and this is not one of them, and the fix needs
a decision I do not own: `UnsolvableNetworkError → UNSOLVABLE_NETWORK` is the exact documented fit
("a `Network` that passes `validate_network` but cannot be solved by the numerics it was handed to
… user data, not a solver bug"), but it does **not** subclass `ValueError`, so routing
`zone_partition` through it changes a public contract and breaks
`tests/unit/test_market_zonal.py:1079`'s `pytest.raises(ValueError, match="carry no zone")`.
`DANGLING_REF` does not fit — a bus with `zone=None` is not a dangling reference, and `Bus.zone` is
legitimately optional in the schema. One line each way once the code is chosen. **Decision for the
orchestrator.**

### (n) — `max_length` on `corridors` · `8f1e187` · review F2

`MAX_CORRIDORS = 500`, named and documented in the shape of S7a's `MAX_PERIODS`.

The honest bound is the network's own `n(n−1)/2`, and the docstring says so — but `n` is a property
of the network and this is an options model, which has none. 500 is justified by measurement at both
ends: it exhausts a 32-zone partition (496 pairs, **22,025 bytes** of options JSON), and 32 zones is
already above Europe's day-ahead market at ~25 bidding zones. Above it the growth is quadratic and
paid twice, since `corridors` is echoed verbatim into every result's `provenance.options`: 200 zones
is 19,900 entries and **913,425 bytes** per solve. Review F2 measured 20,000 entries accepted before
the bound existed.

Three tests, all taking the number from the module rather than a literal 500/501 — what they prove
is that the *field's* bound and the *constant* agree, so a bump of one without the other is what
they catch. A `_distinct_corridors` helper was needed because the (c) validator now forbids
repeating an entry the way `_periods` repeats an empty `Period`.

### (e) — `cap_mw = inf` · `8f1e187` · walk D3, review C12 · **wider than the brief**

`opf/zonal.py` accepts an infinite cap and maps it to `kHighsInf`; the manual teaches the copper
plate as a lifted cap; `CorridorLimit` rejected it with `finite_number`. `CorridorLimit` is now the
layer that yields.

The scoping is `cap_mw`'s own `ge=0.0`, not `allow_inf_nan` (a model-wide switch): `-inf` fails the
bound and `NaN` fails it too, since every comparison with `NaN` is false. Measured — `+inf` is the
only non-finite value that gets through, and `zone1`/`zone2` are strings.

**The field alone was not enough, and this is the item to look at.** `SolveRequest.options` and
`ResultProvenance.options` are free `dict[str, Any]`, so `CorridorLimit`'s own serialisation config
never applies to them. Under pydantic's default (`ser_json_inf_nan="null"`) the cap serialised to
`null` and then failed to validate back — measured: `run_json` returned
`BAD_OPTIONS … input_value=None`. A one-way round trip that looks fine until something reads it.

So `SolveRequest`, `SolveResult` and `ResultProvenance` also take
`ser_json_inf_nan="constants"`. That is wider than "allow `inf` on that one field", and I flag it
rather than burying it. Three things bound the risk:

* **Measured byte-neutral for every other kind.** `pf.dc` / `opf.dc` / `market.nodal` / `pf.ac`
  requests hash identically before and after; their full `run_json` responses diff to exactly two
  lines, `started_at` and `elapsed_s`.
* **Structurally impossible for anything else to be affected.** Every model reachable from a
  request's `network`/`scenario`, and every result model, sets `allow_inf_nan=False`. The free
  `options` dict is the only place a non-finite float can exist, and `cap_mw` is the only option
  field in the package that accepts one.
* **The cost is named where it is paid.** `Infinity` is a JSON *extension*: `json.loads` reads it,
  a browser's `JSON.parse` does not. Said in `CorridorLimit`'s config docstring, in `cap_mw`'s
  description, and in `ResultProvenance.options`' description — which previously read "JSON-native
  values only" and now names the one exception. `"strings"` was considered and rejected: it changes
  the field's wire type from number to string, which is a worse break for a schema-validating
  consumer than a token their parser rejects loudly.

If you would rather the options layer be authoritative and finite-only, that is a revert of this
half plus a docs change. **Flagged for the orchestrator.**

Proven as a *market* claim, not a serialisation one. Through `run_json` on promoted case30, an
unbounded corridor between every zone pair clears all three zones at one price (3.789199 / 3.789201
/ 3.789200), against the already-committed empty-corridor case where the same network islands and
prices three ways. On the derivation's hand fixture a lifted cap clears (10, 10) where the true
20 MVA rating clears (10, 50) — paired against the *rating*, deliberately, not against corridor
deletion, which is a different market again and would also pass a sign-flipped corridor column.

### (p) — `getNumRow` tripwires · `15ab30b` · review C1

Both asserts have `multiperiod.py:635`'s exact shape, with the expected-row sum derived from each
module's documented layout and computed from the same `problem` the rows were built from:

```
zonal:      n_zone + Σ(gen segments) + Σ(demand segments)
redispatch: 1 + n_branch + n_pwl + n_demand_pwl + Σ(gen segments) + Σ(demand segments)
```

The comments name what is at risk in each: `zonal.py` reads `row_dual[:n_zone]`, so a family
inserted before the epigraph block silently reassigns every zone's price; `redispatch.py` reads
`row_dual[0]` and `row_dual[1:n_rows]` with three conditionally-present families appended after the
flow rows.

Only-guard proof is sabotages #5/#6 above: **43 failed / 28 passed / 14 errors** with the asserts,
**734 passed — the whole unit suite green** without them. The row family used is a `0 == 0` balance
row over no columns, which adds rows and constrains nothing. (My first attempt, a balance row over
column 0, pinned a generator to zero and moved the LP — it produced 30 failures with the asserts
removed, which proves nothing about the assert. Replaced.)

### (q) — AC-5(a)'s premise · `781d04f` · review C7

Renamed to
`test_ac5a_zonal_welfare_is_never_lower_where_the_corridors_are_looser_than_the_network`, with the
premise in the name and in the docstring: `tests/_zones.py`'s `corridors()` caps each corridor at
the sum of its cut-set's ratings, looser than those branch limits individually and looser still once
Kirchhoff's loop law is added back. Every corridor set committed anywhere in this wave is on that
side.

Paired with `test_ac5a_tight_corridors_reverse_the_inequality_and_the_payment_pays_inward`: case30
with every rating ×20 and every corridor capped at 0. Measured — zonal welfare **301,846.652404**
against nodal's **301,857.892771**, so the inequality fails by **11.240367 $/h**, and
`redispatch_payment` is **−11.240367**, paying inward. (Review C7 measured −11.05 on fixed load; the
difference is the interior bid loads.) With the derived ×20 caps instead, the gap is 0.0 to 6 decimal
places — the relaxation is exact there, which is the control.

The paired test also asserts `welfare_gap ≈ 0`, so it records that D1's theorem holds on the
restriction side too, and asserts `redispatch_payment == margin` to `IDENTITY_ATOL`, tying the
settlement figure to the welfare comparison in the regime where it is negative.

The failure message names the stakes: *"if this passes the inequality above is unconditional after
all and its premise is not load-bearing."*

### (r) — the netting test · `781d04f` · review C13

Kept, not deleted, but rebuilt around an oracle. `test_reported_deltas_are_the_movement_to_an_
independently_computed_final_point` takes the final point from a separate `dc_opf` solve (D1's
theorem), forms `target − p0` outside the solver, and holds the reported pair to it twice:

* the **signed** sum reproduces the movement — what the old reconstruction clause did, now against
  an independent target;
* the **unsigned** sum reproduces its magnitude — the netting claim proper. A report padding both
  columns by α still reconstructs the point and is still non-negative, but overstates the volume by
  2α on every participant.

Non-vacuity is asserted rather than hoped for: the fixture must move more than 1 MW and must move it
in *both* directions, or the unsigned clause is a restatement of the signed one.

Power is sabotage #8: `gen_net × 1.05` keeps reconstruction, orthogonality and non-negativity all
satisfied — old test **PASSED**, new test **FAILED**.

Review C13 suggested asserting on the raw HiGHS columns instead. `RedispatchSolution` does not
surface them and deliberately says so ("The raw columns are never surfaced"), so that route would
have meant widening the public dataclass to test it. The independent-target route gets the same
discrimination without changing the API.

### (a) — `src` docstring citations · `6edf7f6` · A26(i), M5 walk D10 recurrence

`opf/zonal.py`, `opf/redispatch.py`, `market/zonal.py`, `results/zonal.py`: every
`record/*.md` citation, every bare wave label (`W1`..`W6`, `(S6)`, `(S7)`, `AC-2`..`AC-5`,
`D1`..`D4`, `A17`, `A23`, `wave M1`/`M4`/`M5`), every `spec ## Design` / `## Rejected alternatives`
pointer and every `§n` research reference is gone. These render on the public `api/*` pages, where
none of those documents exist.

Machine-checked — `grep -cE "record/[a-z0-9-]+\.md|\bW[1-9]\b|\(S[0-9][ab]?\)|AC-[0-9]|\bD[1-9]\b|
spec \`\`##|\bA[123][0-9]\b|review [FC][0-9]|walk D[0-9]|audit F[0-9]"` returns **0** for all four.

The content is kept, and where the pointer *was* the explanation it is now written out:

* the anchored-rate rejection states the over-curtailment mechanism (an elastic load's marginal
  value evaluated where it started rather than where it ends up) instead of citing research §3(a)/§4(b);
* the "never bitwise" clauses say why — two different LPs reduce their floating-point sums in
  different orders — instead of citing M5's macOS CI finding;
* the corridor sign convention writes out the two-zone balance rows (`p_A − f_AB == L_A`,
  `p_B + f_AB == L_B`) instead of citing the derivation that hand-solved them;
* `CorridorLimit`'s "no fixture carries an NTC" argument now offers the cut-set sum as the
  defensible default and mentions `tests/_zones.py` as where that lives, rather than calling it
  "the fixture half of the wave's acceptance criteria".

ADR-006/007/008 citations stay — fold-b is putting them on the site. My own new prose from items
(c), (e), (l) and (p) was written with citations and then stripped in the same pass, so nothing
this fold added reintroduces the problem.

Out of scope, noted: earlier waves' modules still carry theirs —
`contingency/n1.py` (×2), `numerics/roles.py`, `opf/dc_opf.py` (×4), `opf/multiperiod.py`,
`pf/dc.py`. Same defect, same public pages, a different wave's fold. `tests/_rated.py` also cites
`record/m3-s1-report.md`; tests are not rendered, and item (m) scoped me to the `RATE_A` claim.

### (h), (m), (o), (b) — the four one-liners · `6edf7f6`

**(h)** `MarketNodalOptions` said its options model existed "so a future `jobs` `KindSpec` (S6)"
would have something to validate against. `market.nodal` has been registered since M4 and
`market.multiperiod` since M5. Both now say the registered kind names it, and that a kind with no
options model rejects any key at all — which is the actual reason the empty model has to exist.
`MarketMultiperiodOptions` had the same sentence with `(S7)`; same fix.

**(m)** `tests/_rated.py` opened by claiming no MATPOWER-shipped OPF fixture carries a real
`RATE_A`. case30 does, on all 41 branches, and `rated_network` overwrites them. The docstring now
says so, names the seven inter-zone tie ratings that get overwritten (32/65/65/32/32/16/65 MVA →
1.52–8.97 MVA) and says why that is the *cleaner* story: one derivation rule governs every fixture,
so no test compares a synthetic rating against a shipped one — and it is the overwrite that makes
the corridor caps bind.

**(o)** `_dispatch_rows` claimed `solve_nodal`'s row construction is "shared here". It is not:
`market/nodal.py`, `market/multiperiod.py` and `market/zonal.py` each build these rows inline. Now
says **verbatim copy**, names all three sites and names the seam — "a fix here needs the same fix
there". No refactor: C2/C3 are M7 carries.

**(b)** `test_jobs.py`'s unknown-kind demo used `market.agents`, a real M7 kind. Switched to
**`pf.telepathy`**, matching fold-b's `jobs.md` and example 04. The comment now says why a
*fictional* kind is the right shape rather than logging which files to move next time: this test has
already been moved twice, off `market.nodal` and off `market.zonal`, each time because its example
of an unknown kind got registered and the assertion silently stopped testing what it names.

---

## For fold-b — docs that my changes make stale

I touched no `docs/**`. These are requests, not edits.

1. **`docs/manual/zonal.md:469`** — the errors table says the same pair given twice "in either
   order" raises `ValueError`. That is now true (it was false for the same-order case). Worth saying
   that the same-order repeat previously cleared the market on the last entry's cap, since anyone
   who built a corridor list against the old behaviour has a silent bug.
2. **The same errors table needs the new codes.** Through `jobs.run`: a self-pair and a duplicate
   pair are `BAD_OPTIONS`; a corridor naming an unknown zone is `VALIDATION` with a `DANGLING_REF`
   issue at `options.corridors[i].zoneN`. `"N of M in-service buses carry no zone"` is still
   `INTERNAL` — if the docs currently promise otherwise, they should say `INTERNAL` until the
   decision above is made.
3. **`cap_mw = inf` is now accepted**, and the copper plate no longer needs the `1.0e6`
   approximation the manual and example 11 use. On the wire it is the bare token `Infinity`, which
   `json.loads` reads and a browser's `JSON.parse` does not — worth one sentence wherever the manual
   discusses the JSON surface.
4. **`MAX_CORRIDORS = 500`** joins `MAX_PERIODS = 200` wherever the manual lists request bounds.
5. **The `redispatch_payment + generation_cost_gap` identity** is now stated in `market/zonal.py`
   and `results/zonal.py` and asserted in tests; the manual's three-figures section can use it.

## Carries and observations

* **`market.zonal`'s error surface is now two-layer and worth documenting as such.** What the
  options model can judge alone → `BAD_OPTIONS`. What needs the network → `VALIDATION`. That split
  is the general rule for any future kind whose options reference network ids, and it is the reason
  walk D1 happened: there was no layer holding both until `solve_zonal` was given one.
* **`ResultProvenance.options` is now a documented exception to "JSON-native values only".** If a
  later wave adds another option field that accepts a non-finite value, the exception list in that
  description has to grow with it, or the description goes stale the way `tests/_rated.py`'s did.
* **The four M6 `src` modules are citation-clean; six earlier-wave modules are not.** The same
  `grep -cE` used above works as a CI check if anyone wants to stop the pattern recurring — it
  recurred from M5 to M6 without one.
* **C2 (third verbatim diagonal-Hessian copy) and C3 stay M7 carries**, untouched here. Item (o)
  names the `_dispatch_rows` seam in the docstring precisely so the next person finds it.

---

# Addendum — follow-up round

Two orchestrator decisions and one addition to item (a), after the first hand-back.
**Head:** `cb6dfa9`. **992 passed / 4 skipped** (was 990/4, +2). Gates clean on both commits.

| Commit | Items | What |
|---|---|---|
| `bde1b3c` | (a2) | the whole `results/` package is citation-clean, not just `zonal.py` |
| `cb6dfa9` | (e2), (c2) | copper plate becomes `cap_mw: null`; an unzoned bus becomes `VALIDATION` |

Two commits rather than the one asked for: the (a) addendum is a different concern from the two
decisions and is cheaper to review apart. Both are explicit-path, `src/**` + `tests/**` only.

## Revert-and-watch (addendum)

Detached worktree at `cb6dfa9`, restored and removed afterwards; `git worktree list` shows only the
two real ones.

| # | Sabotage | Site | Result | What it proves |
|---|---|---|---|---|
| 9 | `corridor_map()` maps `None → 0.0` instead of `inf` (islanded, not copper plate) | `market/zonal.py:285` | **3 failed / 124 passed** | (e2): the three copper-plate tests and nothing else. Caught at the *market* level — prices diverge — not only by the mapping unit test |
| 10 | the runner's `UnzonedBusError` translation removed | `jobs/registry.py` | **1 failed / 126 passed** | (c2): exactly the jobs test that owns the claim. The model-level test correctly stays green, being about the exception *type* rather than the translation |

RED-first on the new jobs test: `INTERNAL` before the change, `VALIDATION` after.

## (a2) — the rest of the `results` package · `bde1b3c`

fold-b's field-rendering extension puts every result model's `Field(description=…)` on
`api/results`, which widened item (a)'s blast radius. The two descriptions it named —
`generation_cost_gap` and `generators_final` — were **already** stripped in `6edf7f6`; fold-b
flagged them from the report before that commit landed. Verified at source: no
`Field(description=…)` anywhere in `results/` cites a planning document.

The grep it asked for found twelve more, in module, class and attribute docstrings that render on
the same page and always have: `epic Design §1-2`, `wave M2 W5`, `spec design item 6, W6`, `(W3)`,
`wave M5 W5`, `wave M3 W5, AC-4/AC-6`, `AC-6's brute-force agreement test`,
`spec design item 1-2; wave M3 W1/W2`, `(W1)`, `(AC-6 agreement test)`, `(W3: …)`. All removed,
content kept, and where the pointer *was* the explanation it is written out — `provenance.py` now
states what a provenance stamp holds instead of quoting the epic design document at the reader, and
`n1.py` says why `N1Result` is shared instead of citing the ownership table that decided it.

`grep -rnE` over `src/mambo_power/results/*.py` for the citation pattern now returns nothing.

## (e2) — the copper plate is `null` · `cb6dfa9` · reverses the wide half of `8f1e187`

**Reverted, and provably so.** `ser_json_inf_nan="constants"` is gone from `SolveRequest`,
`SolveResult` and `ResultProvenance`. I diffed the restored `model_config` lines and
`ResultProvenance.options`' description against `d0ce957` — **byte-identical to pre-fold**, no
residue. The byte-neutrality measurement in the main report is what made this safe: nothing else
changed on the way in, so nothing else changes on the way back.

The orchestrator's reasoning is right and worth recording: the bare `Infinity` token is not
RFC 8259. Only Python's `json.loads` is lenient about it; a browser's `JSON.parse` rejects it. On a
wire format under ADR-004, making every client carry a non-standard token to express one edge value
is the wrong trade. My original framing treated it as a documented caveat; it is a contract change.

`CorridorLimit.cap_mw` is now `Annotated[float, Field(ge=0.0)] | None`. Measured, that shape gives
exactly the intended semantics with no extra validator:

| value | outcome |
|---|---|
| `None` | accepted — the copper plate; `{"cap_mw":null}` on the wire, round-trips |
| `0.0` | accepted — a tie that exists and can carry nothing |
| `5.0` | accepted |
| `inf` | rejected, `finite_number` |
| `-inf` | rejected, `finite_number` |
| `NaN` | rejected, `finite_number` |
| `-1.0` | rejected, `greater_than_equal` |

So there is **one** spelling of the copper plate on this model, `0` remains a distinct third thing,
and `inf` is not a synonym. `corridor_map()` is where `None` becomes the `inf`
`zonal_dc_opf` wants — one line, and neither layer has to know the other's spelling. The array
level is untouched and still accepts `inf`; its docstring already said so.

**One judgement call, flagged.** `cap_mw` is **required** — `Field(description=…)` with no default
leaves it so in pydantic v2. An omitted cap is therefore `BAD_OPTIONS`, not a silent copper plate.
Defaulting to `None` would make the most permissive market the one a caller gets by forgetting a
field, which is the wrong default for a market. Trivially changed if the orchestrator disagrees.

The `run_json` round-trip test stays and still proves the *market* claim rather than the
serialisation one — three zones, one price, against the committed empty-corridor case where the
same network islands and prices three ways. It now sends `null` and asserts
`"Infinity" not in out_text`, so the RFC-8259 property is pinned rather than assumed.

A collision worth naming, and named in the test: `_hand_options(None)` means the corridor is
**deleted** (no entry at all — the zones island), while `cap_mw=None` means the corridor is
**unbounded**. Opposite markets, same literal. The copper-plate test builds its options inline
rather than through the helper for that reason, and says so.

## (c2) — an unzoned bus is `VALIDATION` · `cb6dfa9` · closes walk D1's fourth leg

`zone_partition` now raises `UnzonedBusError`, and `_run_market_zonal` translates it into
`NetworkValidationError` — which `run()` already maps to `VALIDATION`. No change to the runner
boundary in `jobs/run.py`; this mirrors exactly how a mutated-invalid network reaches `VALIDATION`
through `resolved_scenario`.

`UnzonedBusError` subclasses `ValueError`, which is the whole design:

* it **has to stay** a `ValueError`, because that is what `zone_partition` has always raised and
  what a direct caller catches. `tests/unit/test_market_zonal.py:1079`'s
  `pytest.raises(ValueError, match="carry no zone")` passes unchanged, and I added an explicit
  `isinstance(excinfo.value, ValueError)` assertion so the narrowing cannot silently widen later;
* it **has to be** a distinguishable type, because a runner catching bare `ValueError` would
  relabel real engine bugs as the caller's fault — the C9 concern inverted;
* it carries `bus_ids` — *every* offender, not just the first the message names — following
  `NetworkValidationError`'s own convention of never stopping at one.

`UNSOLVABLE_NETWORK` was rejected by the orchestrator and the reasoning is recorded: that code is
for a *valid* network the numerics cannot solve, and an unzoned network is not valid input to this
kind. `validate_network` cannot reject it either, because `Bus.zone` is legitimately optional and
every other kind solves such a network happily — it is a requirement of *this* analysis, which is
why it is raised in `market/zonal.py` and translated by `market.zonal`'s own runner.

**The one thing I chose rather than was told: the issue code.** `DANGLING_REF`, one issue per
offending bus, at path `buses[i].zone`. That is exactly the code and path `validate_network`
already uses for the neighbouring failure — a bus whose `zone` references a zone that does not
exist (`model/network.py:103`) — so `market.zonal`'s two zone-resolution failures now report
identically and a consumer handling one handles both. The alternative was adding a code to the
closed `ValidationCode` Literal, which is a schema-shaped change I did not think was mine to make
and which might have needed a docs change fold-b owns. Easy to swap.

With this, **all four** of walk D1's cases are closed:

| caller mistake | before | now |
|---|---|---|
| corridor names th

---

# Addendum — follow-up round

Two orchestrator decisions and one addition to item (a), after the first hand-back.
**Head:** `cb6dfa9`. **992 passed / 4 skipped** (was 990/4, +2). Gates clean on both commits.

| Commit | Items | What |
|---|---|---|
| `bde1b3c` | (a2) | the whole `results/` package is citation-clean, not just `zonal.py` |
| `cb6dfa9` | (e2), (c2) | copper plate becomes `cap_mw: null`; an unzoned bus becomes `VALIDATION` |

Two commits rather than the one asked for: the (a) addendum is a different concern from the two
decisions and is cheaper to review apart. Both are explicit-path, `src/**` + `tests/**` only.

## Revert-and-watch (addendum)

Detached worktree at `cb6dfa9`, restored and removed afterwards; `git worktree list` shows only the
two real ones.

| # | Sabotage | Site | Result | What it proves |
|---|---|---|---|---|
| 9 | `corridor_map()` maps `None` to `0.0` instead of `inf` (islanded, not copper plate) | `market/zonal.py:285` | **3 failed / 124 passed** | (e2): the three copper-plate tests and nothing else. Caught at the *market* level — prices diverge — not only by the mapping unit test |
| 10 | the runner's `UnzonedBusError` translation removed | `jobs/registry.py` | **1 failed / 126 passed** | (c2): exactly the jobs test that owns the claim. The model-level test correctly stays green, being about the exception *type* rather than the translation |

RED-first on the new jobs test: `INTERNAL` before the change, `VALIDATION` after.

## (a2) — the rest of the `results` package · `bde1b3c`

fold-b's field-rendering extension puts every result model's `Field(description=…)` on
`api/results`, which widened item (a)'s blast radius. The two descriptions it named —
`generation_cost_gap` and `generators_final` — were **already** stripped in `6edf7f6`; fold-b
flagged them from the report before that commit landed. Verified at source: no
`Field(description=…)` anywhere in `results/` cites a planning document.

The grep it asked for found twelve more, in module, class and attribute docstrings that render on
the same page and always have: `epic Design §1-2`, `wave M2 W5`, `spec design item 6, W6`, `(W3)`,
`wave M5 W5`, `wave M3 W5, AC-4/AC-6`, `AC-6's brute-force agreement test`,
`spec design item 1-2; wave M3 W1/W2`, `(W1)`, `(AC-6 agreement test)`, `(W3: …)`. All removed,
content kept, and where the pointer *was* the explanation it is written out — `provenance.py` now
states what a provenance stamp holds instead of quoting the epic design document at the reader, and
`n1.py` says why `N1Result` is shared instead of citing the ownership table that decided it.

`grep -rnE` over `src/mambo_power/results/*.py` for the citation pattern now returns nothing.

## (e2) — the copper plate is `null` · `cb6dfa9` · reverses the wide half of `8f1e187`

**Reverted, and provably so.** `ser_json_inf_nan="constants"` is gone from `SolveRequest`,
`SolveResult` and `ResultProvenance`. I diffed the restored `model_config` lines and
`ResultProvenance.options`' description against `d0ce957` — **byte-identical to pre-fold**, no
residue. The byte-neutrality measurement in the main report is what made this safe: nothing else
changed on the way in, so nothing else changes on the way back.

The orchestrator's reasoning is right and worth recording: the bare `Infinity` token is not
RFC 8259. Only Python's `json.loads` is lenient about it; a browser's `JSON.parse` rejects it. On a
wire format under ADR-004, making every client carry a non-standard token to express one edge value
is the wrong trade. My original framing treated it as a documented caveat; it is a contract change.

`CorridorLimit.cap_mw` is now `Annotated[float, Field(ge=0.0)] | None`. Measured, that shape gives
exactly the intended semantics with no extra validator:

| value | outcome |
|---|---|
| `None` | accepted — the copper plate; `{"cap_mw":null}` on the wire, round-trips |
| `0.0` | accepted — a tie that exists and can carry nothing |
| `5.0` | accepted |
| `inf` | rejected, `finite_number` |
| `-inf` | rejected, `finite_number` |
| `NaN` | rejected, `finite_number` |
| `-1.0` | rejected, `greater_than_equal` |

So there is **one** spelling of the copper plate on this model, `0` remains a distinct third thing,
and `inf` is not a synonym. `corridor_map()` is where `None` becomes the `inf` `zonal_dc_opf` wants
— one line, and neither layer has to know the other's spelling. The array level is untouched and
still accepts `inf`; its docstring already said so.

**One judgement call, flagged.** `cap_mw` is **required** — `Field(description=…)` with no default
leaves it so in pydantic v2. An omitted cap is therefore `BAD_OPTIONS`, not a silent copper plate.
Defaulting to `None` would make the most permissive market the one a caller gets by forgetting a
field, which is the wrong default for a market. Trivially changed if the orchestrator disagrees.

The `run_json` round-trip test stays and still proves the *market* claim rather than the
serialisation one — three zones, one price, against the committed empty-corridor case where the
same network islands and prices three ways. It now sends `null` and asserts
`"Infinity" not in out_text`, so the RFC-8259 property is pinned rather than assumed.

A collision worth naming, and named in the test: `_hand_options(None)` means the corridor is
**deleted** (no entry at all — the zones island), while `cap_mw=None` means the corridor is
**unbounded**. Opposite markets, same literal. The copper-plate test builds its options inline
rather than through the helper for that reason, and says so.

## (c2) — an unzoned bus is `VALIDATION` · `cb6dfa9` · closes walk D1's fourth leg

`zone_partition` now raises `UnzonedBusError`, and `_run_market_zonal` translates it into
`NetworkValidationError` — which `run()` already maps to `VALIDATION`. No change to the runner
boundary in `jobs/run.py`; this mirrors exactly how a mutated-invalid network reaches `VALIDATION`
through `resolved_scenario`.

`UnzonedBusError` subclasses `ValueError`, which is the whole design:

* it **has to stay** a `ValueError`, because that is what `zone_partition` has always raised and
  what a direct caller catches. `tests/unit/test_market_zonal.py:1079`'s
  `pytest.raises(ValueError, match="carry no zone")` passes unchanged, and I added an explicit
  `isinstance(excinfo.value, ValueError)` assertion so the narrowing cannot silently widen later;
* it **has to be** a distinguishable type, because a runner catching bare `ValueError` would
  relabel real engine bugs as the caller's fault — the C9 concern inverted;
* it carries `bus_ids` — *every* offender, not just the first the message names — following
  `NetworkValidationError`'s own convention of never stopping at one.

`UNSOLVABLE_NETWORK` was rejected by the orchestrator and the reasoning is recorded: that code is
for a *valid* network the numerics cannot solve, and an unzoned network is not valid input to this
kind. `validate_network` cannot reject it either, because `Bus.zone` is legitimately optional and
every other kind solves such a network happily — it is a requirement of *this* analysis, which is
why it is raised in `market/zonal.py` and translated by `market.zonal`'s own runner.

**The one thing I chose rather than was told: the issue code.** `DANGLING_REF`, one issue per
offending bus, at path `buses[i].zone`. That is exactly the code and path `validate_network`
already uses for the neighbouring failure — a bus whose `zone` references a zone that does not
exist (`model/network.py:103`) — so `market.zonal`'s two zone-resolution failures now report
identically and a consumer handling one handles both. The alternative was adding a code to the
closed `ValidationCode` Literal, which is a schema-shaped change I did not think was mine to make
and which might have needed a docs change fold-b owns. Easy to swap.

With this, **all four** of walk D1's cases are closed:

| caller mistake | before | now |
|---|---|---|
| corridor names the same zone twice | `INTERNAL` | `BAD_OPTIONS` |
| same pair twice, either order | `INTERNAL` (reversed) / silent (same order) | `BAD_OPTIONS` |
| corridor names a missing zone | `INTERNAL` | `VALIDATION`, `DANGLING_REF` at `options.corridors[i].zoneN` |
| buses carry no zone | `INTERNAL` | `VALIDATION`, `DANGLING_REF` at `buses[i].zone` |

## Docs requests — revised

Superseding the main report's list. Request **#3 is withdrawn**: there is no non-standard wire token
any more, which was the point of the decision.

1. `docs/manual/zonal.md:469` — the errors table's "in either order" is now true; worth saying the
   same-order repeat previously cleared the market on the last entry's cap.
2. The errors table needs the codes: self-pair and duplicate to `BAD_OPTIONS`; corridor naming an
   unknown zone to `VALIDATION` with `DANGLING_REF` at `options.corridors[i].zoneN`; **buses
   carrying no zone to `VALIDATION` with `DANGLING_REF` at `buses[i].zone`** (this last one is new
   in the addendum and the manual may still promise `INTERNAL` or say nothing).
3. ~~the `Infinity` wire-token sentence~~ — **withdrawn**.
4. `MAX_CORRIDORS = 500` joins `MAX_PERIODS = 200` wherever request bounds are listed.
5. The `redispatch_payment + generation_cost_gap` identity is now stated in `market/zonal.py` and
   `results/zonal.py` and asserted in tests; the manual's three-figures section can use it.
6. **New — the copper plate is `cap_mw: null`.** Not `1.0e6` and not `inf`. `docs/manual/zonal.md`
   and example 11 should use `null`, and the errors table should say a non-null cap must be finite
   and non-negative. Note for the prose: `null` (unbounded), `0` (a tie that carries nothing) and
   *omitting the corridor entirely* (the zones island) are three different markets.

---

## Correction (R2 fold, `2026-08-27`) — the `(e)` section above is stale

Appended, not rewritten: the record of what fold-a did stays as fold-a wrote it. But the Step-6
critic found that **the `### (e) — cap_mw = inf` section reads as current and is not**, and a
reader taking it at face value will be wrong about the shipped contract. `cb6dfa9` reversed it;
`## (e2)` in the addendum above records the reversal, but `(e)` carries no pointer forward and is
the section a reader looking for "how are corridor caps serialised" lands on first.

Specifically, these sentences in `(e)` no longer describe the tree:

* "`CorridorLimit` is now the layer that yields" and "`+inf` is the only non-finite value that gets
  through" — `+inf` is now **rejected**.
* "`SolveRequest`, `SolveResult` and `ResultProvenance` also take `ser_json_inf_nan="constants"`"
  — none of them do; the token is gone from `src/` entirely.
* "the manual teaches the copper plate as a lifted cap" — the copper plate is `cap_mw: null`.
* The whole "wider than the brief / flagged for the orchestrator" framing was resolved: the
  orchestrator took the revert. There is no open decision here.

Re-measured on `232de50` at R2:

```
$ grep -rn ser_json_inf_nan src/ --include="*.py"
(no matches)

  cap_mw=   inf -> rejected, finite_number
  cap_mw=  -inf -> rejected, finite_number
  cap_mw=   nan -> rejected, finite_number
  cap_mw=  None -> accepted; json={"zone1":"A","zone2":"B","cap_mw":null}
  cap_mw=   0.0 -> accepted; json={"zone1":"A","zone2":"B","cap_mw":0.0}
  cap_mw=   5.0 -> accepted; json={"zone1":"A","zone2":"B","cap_mw":5.0}
```

`(e2)`'s table is the current contract. `(e)`'s is history.

The one claim in `(e)` that still stands is its **market** proof — an unbounded corridor between
every zone pair clears promoted case30 at one price against the empty-corridor case islanding
three ways. That argument is about the cap being unbounded, not about how "unbounded" is spelled,
and it survives the change of spelling from `inf` to `null`.
