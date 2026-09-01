# M7 S10 — audit should-fixes + idle tolerance

Worktree `C:\Claude Projects\mambo-power-m7`, branch `wave/07-agents`, base `c0cfd12`.
Four commits, one per fix. Gates at the end: `ruff check .`, `ruff format --check .`, `mypy`
(53 files, no issues), `examples/12_agent_market.py` exit 0. Full suite not run (per brief);
the affected files were: `test_jobs.py` (116), `test_market_agents.py`, `test_market_strategy.py`
(35), `test_opf_multiperiod.py` (39), `test_api_docs_coverage.py`, `test_docstrings.py`.

## Fix A — `e635eb0` the agents runner catches `AgentSetError`, not every `ValueError`

- Files: `src/mambo_power/market/agents.py` (new `AgentSetError(ValueError)` with docstring;
  raised at all six `_resolve_agents` / `_initial_offers` sites; `__all__`),
  `src/mambo_power/market/__init__.py` (export), `src/mambo_power/jobs/registry.py`
  (`except AgentSetError`; docstring rewritten — the old one claimed `NonConvexCostError` was
  not a `ValueError`), `docs/manual/agents.md` (raises table names the type),
  `tests/unit/test_jobs.py`.
- Red: `test_market_agents_reports_an_engine_error_with_the_same_code_as_market_nodal` —
  case14, gen 0 `c2 = -0.01`, all price-takers: `INTERNAL` (nodal) != `VALIDATION` (agents).
- Green: same code (`INTERNAL`), not `VALIDATION`, `issues is None`, message names
  `NonConvexCostError`. All prior AC-6 tests and S9's non-linear-cost test still `VALIDATION`.
- Sabotage: catch reverted to bare `ValueError` → the new test reddens on `INTERNAL != VALIDATION`.
- `docs/api/market.md` untouched: the `:::` directive renders from `__all__`, and
  `test_api_docs_coverage` / `test_docstrings` pass.

## Fix B — `cacbf4f` multiperiod sees its own Hessian diagonal through a hand oracle

- Files: `tests/unit/test_opf_multiperiod.py` only.
- Case (derived in the comment above the test, MC = MV): `gq` cost `0.05p² + 10p` on [0, 200],
  `gl` 12 $/MWh on [0, 50], elastic load value `−0.05d² + 40d` bounded 300 MW at t=0 and 100 MW
  at t=1, T=2, no ramp, no storage. Closed form: dispatch `[[125, 50], [50, 50]]`, demand
  `[[175], [100]]`, prices `[22.5, 15]`, generation cost 3856.25.
- Tolerance, from measurement: HiGHS's active-set QP stops at `gq = 124.99985` (same at T=1,
  T=2 and via `dc_opf` — the solver, not the builder), so 1e-3 MW on dispatch (7x the residual,
  4.6 orders inside either sabotage), 1e-2 $ objective, 1e-5 $/MWh prices. A 1e-6 band is a
  false alarm on a correct answer; worth knowing that the tree's QP precision is ~1e-4 MW.
- Sabotage 1: `2.0 * c2 → 1.0 * c2` (`dc_opf.py:548`) → reddens at `gq = 166.666` (predicted
  166.67). Sabotage 2: `-2.0 * v2 → -1.0 * v2` (`:549`) → reddens at `gq = 183.333` (predicted
  183.33). Both restored with `git checkout -- src/`. No bid-side variant needed.

## Fix C — `bfd25d4` `run_json` rejects a duplicated JSON key at any depth as `BAD_REQUEST`

- Files: `src/mambo_power/jobs/run.py` (`_reject_duplicate_keys` pre-parse with an
  `object_pairs_hook` that marks an object carrying a duplicate and lets each parent prepend its
  key, so the message carries key **and** path; `_DuplicateKeyError` → `BAD_REQUEST`, the code
  malformed JSON already gets; malformed/too-deep text is left to pydantic as before; `run_json`
  docstring), `docs/manual/jobs.md` (one sentence on the `BAD_REQUEST` row), `tests/unit/test_jobs.py`.
- Red: both new tests ran to `status=ok` / wrong code.
- Green: duplicated `agent_a` under `options.strategies` → `BAD_REQUEST`, message
  `duplicate key "agent_a" at options.strategies: ...`, kind/job_id echoed; the same text without
  the duplicate → ok. Duplicated top-level `kind` on `pf.dc` and duplicated `base_mva` inside
  `network` → `BAD_REQUEST` naming key and path. Existing malformed-JSON and 5000-deep tests unchanged.
- Sabotage: pre-parse call replaced with `pass` → both new tests redden.
- Cost: the request text is parsed twice (json + pydantic). Accepted for correctness.

## Fix D — `01f8c7b` the idle rule tolerates solver dust, and two stale notes

- Files: `src/mambo_power/market/strategy.py` (`_IDLE_MW_ABS_TOL = 1e-9` beside
  `_PROFIT_TIE_REL_TOL`; `<= _IDLE_MW_ABS_TOL`; docstring bullet), `src/mambo_power/market/agents.py`
  (`_settled` figures), `tests/unit/test_market_agents.py` (docstring repeating the figures),
  `tests/unit/test_market_strategy.py`.
- Red: `test_markup_treats_solver_dust_as_idle` (both rounds 1e-12 MW) offered 31.0, not 30.0.
- Green: 1e-12 → steps down to 30.0; `test_markup_does_not_call_a_real_microdispatch_idle`
  (1e-6 MW) → 31.0, not idle.
- Sabotage: `<= 0.0` restored → the 1e-12 test reddens, the 1e-6 test stays green.
- Notes: re-measured amplitude − offer_tol in ULPs of `offer_tol` on the AC-5 duopoly
  (2026-08-29): +102 at step 0.1 (2.83e-15, 404 rounds), +26 at 0.7 (5.77e-15, 61 rounds),
  −51 at 0.3, bit-exact at 0.5 — identical to the audit's own numbers; the old "64/19/42" were
  in some other unit. `pytest.raises` at the three sites now carry `match=` (`union_tag_invalid|'bogus'`,
  `greater than 0` x2).

## Not done / worth knowing

- Fix B's commit was retitled from `test(...)` to `fix(m7/s10)` by amend (unpushed) to match
  the brief's four-`fix` convention.
- `docs/manual/agents.md` mentions the idle rule only qualitatively; no edit was needed there.
- Audit note 5 (halving the demand Hessian entry reddens nothing in `test_opf_dc_demand.py` /
  `test_market_nodal.py`) is now covered by Fix B's test in the multiperiod module; the
  dc_opf/nodal modules themselves still have no bid-side hand oracle. Pre-M7 residual, out of scope.
