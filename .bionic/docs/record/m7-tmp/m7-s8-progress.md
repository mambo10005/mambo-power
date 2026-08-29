# M7 S8 — docs, phase 1 — progress

Started 2026-08-28. Worktree `/c/Users/mambo/AppData/Local/Temp/claude/C--Claude-Projects-mambo-power/0d397067-49ef-4969-aefa-5709948393ef/scratchpad/bionic-unified`, branch `wave/07-agents`, head `a22922d`.

## Baseline (measured, this tree)
- `uv run --no-sync mkdocs --version` -> `mkdocs, version 1.6.1 ... (Python 3.12)`.
- `test_api_docs_coverage::test_every_public_symbol_is_reachable_from_an_api_page` **RED**, exactly
  as briefed: `mambo_power.market.strategy: MarkupConfig, MarkupStrategy, Observation,
  PriceTakerConfig, PriceTakerStrategy, RoundRecord, Strategy, build_strategy` (1 failed, 3 passed).
- `test_docs_registry_listing.py` — **4 passed**, i.e. `docs/manual/jobs.md`'s transcripts are
  currently ACCURATE against the 7-kind registry.

## Findings so far
- **F1 — the `jobs.md:267` fix cannot land in phase 1.** `tests/unit/test_docs_registry_listing.py::
  test_the_manual_unknown_kind_message_lists_every_registered_kind` asserts the *current* sorted
  kind list appears verbatim in the page. Registry today is the 7 kinds the transcript already
  lists, so the line is not stale yet; editing it to an 8-kind list turns that test red. Deferred
  to phase 2, where it becomes a 3-site fix (jobs.md:242 `kinds()` block, :250 capability table,
  :267 UNKNOWN_KIND transcript), all three pinned by that same module.

## In flight
- API page section for `mambo_power.market.strategy` in `docs/api/market.md`.
- Architecture edges for the strategy seam.
- `MarketNodalResult.branches` render check on `api/results`.
