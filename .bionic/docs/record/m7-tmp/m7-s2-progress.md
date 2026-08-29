# M7 / S2 progress — the `Strategy` seam

Owned files: `src/mambo_power/market/strategy.py` (new), `tests/unit/test_market_strategy.py` (new).

## Plan
1. Read spec W2, A4/A8/A9, D3 design ledger, reference probe `.bionic/tmp/m7-a4-two-point-climb.py`. DONE.
2. Design `RoundRecord` / `Observation` (own-node, two optional prior rounds, contiguity validator).
3. Design `Strategy` Protocol, `PriceTakerStrategy`, `MarkupStrategy` (scoped to linear `PolynomialCost`).
4. Design `PriceTakerConfig` / `MarkupConfig` / `StrategyConfig` union + `build_strategy`.
5. Write `strategy.py`.
6. TDD: write `test_market_strategy.py` against the team-lead's required coverage list + sabotage sweep.
7. Run pytest / ruff check / ruff format --check / mypy at head. Fix to green.
8. Commit with explicit paths.
9. Write final report, send completion message.

## Status: DONE

Commits `df3c849` (initial) + `aade93b` (amendment, review feedback: stale-record guard on
Observation, explicit PWL coverage, stricter purity tests) + `20ba1e7` (defect fix: MarkupStrategy
tie-tolerance on the profit-reversal check, found downstream by S4 on AC-5). Fix verified and
accepted by team-lead. Report at `.bionic/docs/record/m7-s2-report.md`, updated with a process
note: any further sabotage sweep in this slice runs against a `git archive` overlay via
`PYTHONPATH`, not in-place in the shared worktree (team-lead's ruling after the sweep briefly
broke a concurrent S4 measurement -- no code change needed, just methodology going forward).
Completion message sent.
