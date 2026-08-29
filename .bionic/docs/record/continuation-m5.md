# Continuation — M5 multiperiod closed

Wave M5 (`multiperiod`) completed 2026-08-26 and merged into `epic/01-foundation`.

- **Integration branch:** `epic/01-foundation`
- **Merge SHA:** `f447249` (`--no-ff`, local; wave head `def67f1`, tree byte-identical), plus
  `ad2c7c9` (a `.gitignore` chore M4's record asked for)
- **Suite:** 816/816 (654 at M4 close → 816, +162), verified on the merged tree in the main
  checkout, not only in the worktree
- **Gates:** ruff, `ruff format --check` (154 files), mypy (46 source files), `mkdocs build --strict`
  — all clean at the wave head
- **Next wave:** M6 `zonal-redispatch` (M5 and M6 were `[par]`; M5 is done, M6's dependency was only
  ever M4). M7 `agents` now unblocks. M8 `interop` has been available since M1.
- **Not pushed:** `epic/01-foundation` is local-only past `5fa3285`, per the M1–M4 convention that
  pushing the epic branch is the user's call. `wave/05-multiperiod` is **not** pushed either.
- **CI:** not run on this wave head — the branch is local. M4's close had CI because
  `wave/04-nodal-market` was pushed.

## What M5 shipped

The first wave to couple decisions *across* time. `Period` / `Scenario.periods` and
`Generator.ramp_up_mw` / `ramp_down_mw` in the model; per-storage identity arrays in `numerics`;
`opf.multiperiod_dc_opf`, a T-loop over row families extracted from `dc_opf` and extended with ramp
coupling, storage SoC with charge/discharge efficiency, a cyclic end-of-horizon condition and a
shared charge+discharge power limit; `market.solve_multiperiod` with per-period LMPs, storage
settlement and horizon totals; the `market.multiperiod` jobs kind with `SolveRequest` widened to
`network` XOR `scenario` and a uniform `(Scenario, options)` Runner; a manual page, API pages, an
architecture rebuild from a real import scrape, and example 10.

**ADR-008** records the decision that shapes M6: D1's shared row-family core holds **in substance** —
one helper, two callers, proved by a sabotage taking 18 tests red across five files — but ADR-007's
two stated *consequences* did not come with it. The double-counting contract and the convexity guards
are 54 identical lines out of 68/69 between `dc_opf.py` and `multiperiod.py`, and the wave's one
behavioural defect was a bug in the duplicated copy.

## Carry-overs into M6

1. **ADR-008's decision, and it is the first one.** Unify the extraction-and-validation preamble into
   one shared helper **before** adding zonal redispatch's row families. M6 would otherwise make the
   duplication a third copy. It deserves its own slice and its own behaviour-preservation proof of
   the kind S1 produced — that proof (M4's complete unmodified 654-test suite passing against a tree
   differing in exactly one file) is the template.
2. **Branch rows on the result types (A23).** Neither `MarketNodalResult` nor `MarketPeriodResult`
   carries branch flows or flow duals, so the settlement identity's right-hand side
   (`-Σ μ_k·f_k`) is **not computable from a result object**. Every proof of the identity in this
   repo reaches past the public result type into `numerics`/`opf`; a user following the manual
   cannot reproduce it. An `OpfBranchFlowResult`-shaped row would also give zonal redispatch the
   per-branch surface it needs anyway.
3. **`Scenario.periods` needs `max_length` in the model (A34/C2).** Nothing is network-facing yet,
   but `SolveRequest` is a pydantic model whose purpose is to be a wire format, and a 33,997-byte
   request expands to 20,088,000 matrix nonzeros — a ~7,000x, decompression-bomb ratio. Added after
   the model is treated as stable it becomes a breaking change, so it belongs in the model now.
4. **The combined heterogeneous fixture (A31, refuted by the critic).** m5-fold-a claimed one network
   with two heterogeneous storage units *and* two heterogeneous ramp limits was infeasible; the
   critic solved one **Optimal** on fold-a's own profile and showed the stated mechanism wrong
   (overlap absorbs no net SoC but does absorb grid power — the round-trip loss *is* the absorption,
   which is the escape the cyclic row leaves). Honest caveat: the solutions found use 1.5–3.9 MW of
   overlap, so a clean **overlap-free** hand-derivable combined fixture still needs design work.
5. **Commit the `c0` test (C3).** 12 lines, no oracle: `coefficients=[10.0, 7.0]` on a one-generator
   network gives `objective_cost - 10*50*T == 7*T` exactly for T in {1,2,5,24}. `c0` is exactly 0 in
   every fixture the repo ships, so the per-period constant-term convention is otherwise
   unfalsifiable. The critic verified it but did not own `tests/unit`.
6. **Negative period load on a bid-carrying load returns `Infeasible`** — the column bound becomes the
   empty interval `[0, negative]`. Documented on the multiperiod manual page with a measured contrast
   proving it is pre-existing M4 behaviour reached by a new route, not a multiperiod regression.
7. **Public API pages cite unpublished internals (D10).** 12 rendered `record/*.md` citations from 9
   source lines, plus **~48 bare step labels** (`W1`, `(S7)`, `R2`) across 7 API pages. Only 6 are
   M5's; the rest are M2/M3/M4. Each is a dead end for a reader.
8. **Re-audit this wave's sabotages that edited `tests/_*.py` helpers.** The critic showed one of them
   was a no-op by construction (below). S6's own ramp and rating sabotages were not examined and
   deserve the same question.

## The M5 lessons worth carrying

**A sabotage applied to shared fixture data is not a sabotage.** The wave spent three rounds of
review — S6, the audit, and this orchestrator — accepting that the AC-6 parity fixture "cannot tell
the two storage efficiencies apart." The probe transposed the constants in `tests/_storage.py`, which
the PyPSA oracle bridge *also* reads (`efficiency_store=unit.efficiency_charge`), so it relabelled
both sides of a parity comparison at once. There was nothing to detect. Transposing the **engine's**
SoC row with the oracle held fixed takes the committed file red at 5.088e-2 MWh against a 1e-2
tolerance — 5.1x over, 407x baseline noise. The fixture had been strong all along.

**A sabotage sweep is only as good as the residuals it reads.** `η_c · η_d` is symmetric, so a
transposed engine picks the identical schedule: objective, dispatch, net storage power and LMPs all
agree *by construction*. Only the SoC trajectory diverges — and SoC was the one residual missing from
S6's table.

**Disclosure is not closure — third wave running.** M4 wrote that line about its own AC-6 fixture.
M5 then disclosed A20 three times and confirmed it once, and it was not a limitation at all. When
something is disclosed rather than fixed, the disclosure itself is the thing to attack next time.

**A probe is only evidence if it is the probe the test actually runs.** This orchestrator made the
error three times in one wave: a ramp check on a bare entity where the repo puts range checks in
`validate_network`; nine storage probes rejected as `extra_forbidden` and read as nine correct range
rejections; and a hand-assembled AC-6 fixture (wrong siting bus, no ramp limits) that read storage as
idle when the test's own factory shows it active. **Drive the test's own fixture factory.** The
matching rule for shared worktrees: with live writers in the tree, a file read is a *timestamp*, not
a fact — check `git log` on the file before reporting anything unfixed.

**An override must be at least as general as the field it overrides.** `Period.load_p_mw` rejected
negatives while the `Load.p_mw` it overrides has no lower bound, so the *identity* profile raised on
case300 — a fixture `market.solve_nodal` clears without complaint.

**Silent-plausible beats loud-infeasible, and that is the problem.** Unvalidated
`Storage.energy_mwh=0` cleared **Optimal** with the unit inert and the cyclic condition trivially
satisfied. Negative values gave `Infeasible`; zero gave a confident wrong-shaped answer.

**A green build gate is not a green render.** `mkdocs build --strict` exited 0 throughout while
MathJax emitted literal backslashes in 4 of 6 display equations. The docs AC is structurally
incapable of seeing it. This is the argument for the walk, and the walk found it.

**Hand-maintained restatements of what the code does are stale by the next wave.** The changelog
stopped at M2 and called it "in progress" for three waves; `jobs.md` listed four job kinds through
two. Both are now pinned or removed — `tests/unit/test_docs_registry_listing.py` pins the registry
listing, and the changelog's duplicate wave-status labels were deleted in favour of the home page's
single roadmap table.

**No acceptance criterion covered the wave's own central scope answer.** "Load profile only — demand
scales per period" was the user's first scope decision, and a `Period.load_p_mw` override on a
bid-carrying load was a complete no-op. Eight green rows, four slice-level sabotage sweeps and an
8/8 audit all missed it; the six-axis review found it. When a scope answer names the wave's headline
behaviour, give it a row.

## Process notes for the next wave

- **The two-agent fold on strict file ownership worked and should be repeated.** `src/**` +
  `tests/unit/**` to one agent, `docs/**` + `examples/**` + `tests/_*.py` + `tests/parity/**` to the
  other, each committing with explicit paths and never `git add -A`. Seven commits interleaved in one
  worktree with zero collisions. The one hazard it created was stale cross-reads between the two (see
  the timestamp rule above).
- **Worktree removal has a third failure mode.** A7's junction procedure held again (git-bash `rm`
  on the junction first, main `.bionic` verified intact at 87 records / 8 ADRs before and after).
  But `git worktree remove` then failed *Permission denied*, and `rm -rf` failed *Device or resource
  busy* on `site/` — a `python -m http.server 8777` the walk agent had started hours earlier was
  still holding the directory. Registration was already removed, so the fix was to stop the process
  and delete the directory. **Agents that serve a site should be told to stop the server, and
  worktree teardown should check for listeners before deleting.**
- **`stop-guard.sh`'s Windows-path bug (A11) is still open** — the third of three hook path bugs, the
  other two fixed in M2/M3. Finished agents go idle rather than stopping. Not worked around: forging
  a stop order would fabricate user intent, and editing the hook is the user's call.
- **Agent non-response recurred but cost nothing this wave.** S2, S7 and several review agents went
  idle after reporting. The A9 rule that made this cheap: **idle is neither a completion signal nor a
  failure signal — check whether the artifact exists on disk before taking anything over.** Every
  agent this wave had written its artifact before going quiet.
- **The junk files are now gitignored** (`ad2c7c9`) rather than swept a fourth time.
