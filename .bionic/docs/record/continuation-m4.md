# Continuation — M4 nodal-market closed

Wave M4 (`nodal-market`) completed 2026-08-25 and merged into `epic/01-foundation`.

- **Integration branch:** `epic/01-foundation`
- **Merge SHA:** `e88752c` (`--no-ff`, local; wave head `66ff908`, tree byte-identical)
- **CI:** run `32889587198` success on `66ff908` — the exact tree merged
- **Suite:** 654/654 (596 at M3 close → 654, +58)
- **Next wave:** M5 `multiperiod` and M6 `zonal-redispatch` both unblock (epic plan marks them
  `[par]` with each other, both depending only on M4). M8 `interop` has been available since M1.
- **Not pushed:** `epic/01-foundation` is local-only past `5fa3285`, per the M1-M3 convention that
  pushing the epic branch is the user's call. `wave/04-nodal-market` is pushed.

## What M4 shipped

`Load.bid` + `Scenario` in the model; per-load identity in `NetworkArrays`; `opf.dc_opf` extended
with demand-side columns, concave-PWL hypograph rows and the matching balance/flow-row terms;
`market.solve_nodal` with `MarketNodalResult` and settlement; the `market.nodal` jobs kind; a
manual page, API page, architecture-diagram update and example 09.

ADR-007 records the decision that shapes the remaining market waves: elastic demand extends the
**one** array-level LP builder rather than being translated into pseudo-generators. M5, M6 and
M7 all add column/row families to that same builder.

## Carry-overs into M5

1. **Rate a branch in the fixture set (plan Assumption A7, from `m4-critic.md` §3).** case14
   rates no branch — all 20 `Branch.rating_mva` are `None`, inherited from M3's fixture set
   (`m3-research.md` §6) — so no wave fixture yet proves the settlement identity under
   *simultaneous* congestion and elastic demand against an independent oracle engine. AC-4
   covers that interaction on a hand-built network against `dc_opf`'s own arithmetic, which is
   why it is disclosed rather than blocking. The `tests/_rated.py` pattern already exists; this
   is cheap and M5 inherits the same fixtures.
2. ~~**PyPSA infeasibility on generator-only OPF (A4, from M3).** Still open.~~ **CORRECTED
   2026-08-25 (M5 Step 1 research, record/m5-research.md §1).** A4 was ALREADY CLOSED in M3's
   own R1/R3 folds and this carry-over was stale when written — it was copied forward from the
   M4 plan's assumption list, which in turn read the frozen `m3-research.md` rather than the
   shipped code. Root cause of the original infeasibility: `import_from_pypower_ppc` populates
   `n.generators.p_set` from MATPOWER's raw, unbalanced base-case `Pg`, and PyPSA treats a
   non-null `p_set` as a fixed-dispatch constraint. The fix (`n.generators["p_set"] = NaN`
   before `n.optimize()`) ships in `tests/parity/test_opf_vs_pypsa.py`, committed at `4bd67d9`.
   Verified independently 2026-08-25: `uv run --no-sync pytest -q tests/parity/test_opf_vs_pypsa.py`
   -> **20 passed** across all five fixtures (case14/case_ieee30/case57/case118/case300).
   **PyPSA is available as an oracle.** M5's AC-6 does not need a tier downgrade on this
   account.
3. **`stop-guard.sh` Windows-path bug (A6).** Known, TaskStop-only, non-blocking, still open —
   the third of the three hook path bugs; the other two were fixed in M2/M3.

## The M4 lesson worth carrying

**A fixture whose answer is pinned by a bound cannot test the term that moves the answer.** M4's
AC-6 parity fixture derived every bid by an anchor rule that made every load price-taking, so
three of its four sub-checks stayed green with `dc_opf`'s double-counting subtraction removed.
The Step-5 audit found this and disclosed it; the audit, the dispatch brief and the R1 fold all
then accepted it as *structurally* unfixable without abandoning the fixture strategy. The Step-6
critic checked that assumption and refuted it with a reproducible experiment, and the R2 fold
closed it by anchoring one load around the fixture's own clearing price. Measured after: the
dispatch residual under revert-and-watch went from 7.14e-10 MW (undetecting) to 1.569 MW,
~1,570x over tolerance.

Two process points fall out of that, both worth repeating rather than re-learning:

- The critic earned its keep on a wave the auditor had already CONFIRMED. Its finding was not a
  defect the audit missed — it was an unchecked *claim of impossibility* the audit had accepted.
- Disclosure is not closure. "Not blocking, disclosed" was true three times in a row about
  something that turned out to cost roughly fifteen lines to fix.

## Process notes for the next wave

- **Worktree junction removal (A5) held again.** Remove the `.bionic` junction with git-bash `rm`
  *before* `git worktree remove`; PowerShell/cmd `rmdir` is sandbox-blocked on this path, and
  removing the worktree first risks the junction target. Verified after removal that the main
  checkout's `.bionic` was intact (69 records, 7 ADRs).
- **The evidence gate now requires a `## Tasks` heading** on an audited multi-agent wave plan.
  M1-M3's plans title that section "Dispatch ledger" and predate the check; M4's was renamed
  (same table, same rows). M5's plan should use `## Tasks` from the start, and the three older
  plans will block if anything ever commits against them again.
- **Agent non-response recurred, and cost real work this time.** The `m4-r2-fold`
  senior-implementor completed three of four items and left them **uncommitted** before going
  idle across a session boundary. Nothing was lost only because the progress artifact
  (`.bionic/tmp/m4-r2-progress.md`, cadence 10m) said exactly what had been done, and the
  worktree still held the diff. This is the fourth-plus instance across M3/M4 of the same
  pattern. The mitigations that worked: a mandated progress artifact, and the non-response
  procedure's rule that a writing agent is never resumed — examine its output, verify it
  independently, take over.
- **Junk files reaccumulate in the main checkout** (`.playwright-cli/`, `bash.exe.stackdump`),
  same two M3 had to clear. Worth a `.gitignore` entry rather than a third manual sweep.
