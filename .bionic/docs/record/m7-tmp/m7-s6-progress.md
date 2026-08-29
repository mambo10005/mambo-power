# M7 S6 progress — MarketNodalResult branch rows (W4/AC-8)

## Plan
1. `results/market.py`: add `branches: list[OpfBranchFlowResult]` field to `MarketNodalResult`,
   same field name/type `MarketZonalResult` already carries.
2. `market/nodal.py`: compute branch flows in `solve_nodal` from the already-solved `OpfSolution`
   (dispatch_mw, demand_dispatch_mw, ptdf reused) using the same PTDF-injection construction
   `dc_opf`'s own flow-limit rows use (module docstring there) and `opf/__init__.py`'s
   `solve_dc_opf` / `opf/redispatch.py`'s `redispatch_dc_opf` already apply — no dc_opf.py
   signature change, no new solve.
3. `tests/unit/test_market_nodal.py`: new test(s) for AC-8 —
   (a) branch flows agree with an independent `pf.dc` readback on the same dispatch (pattern:
       `tests/unit/test_opf_redispatch.py::test_branch_flow_mw_matches_an_independent_pf_dc_readback`,
       tol `abs=1e-9`, same as that test's own pin).
   (b) `MarketNodalResult.branches` and `MarketZonalResult.branches` are the same field name and
       row type — asserted, not just observed.
4. Sabotage sweep: perturb the branch-flow construction (sign flip / scale / drop demand term) and
   confirm the pf.dc-agreement test goes red, naming the residual that moves.
5. Verify: pytest / ruff check / ruff format --check / mypy at HEAD. Confirm zero test edits
   elsewhere (additive-only, per A5).

## Status: DONE — committed 832a546, report at .bionic/docs/record/m7-s6-report.md

## Log
- Read spec (W4, AC-8, A5), results/market.py, results/zonal.py, market/nodal.py, market/zonal.py,
  opf/__init__.py (solve_dc_opf branch-flow construction), opf/redispatch.py (elastic-demand
  branch-flow construction), opf/dc_opf.py (flow-limit row derivation — the formula source of
  truth), pf/dc.py, pf/__init__.py, test_market_nodal.py, test_opf_redispatch.py (pf.dc readback
  pattern), test_market_zonal.py (branches field docstring / usage).
- Derived the exact formula to replicate in nodal.py:
  `flow = ptdf @ (gen_by_bus - demand_by_bus - p_load_mw - g_shunt_mw) + pf_shift_mw`
  where `p_load_mw` excludes each elastic load's own historical MW (dc_opf's own double-counting
  contract). Implementing next.
