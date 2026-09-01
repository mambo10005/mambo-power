# shifter-fix T6-T8 progress (worktree: C:\Claude Projects\mambo-power-shifter, branch task/shifter-flow-fix)

- T6 DONE, commit `8a6fb11` — opf/multiperiod.py:485 folded p_shift_mw into per-period const.
- T7 DONE, commit `eb771b1` — opf/redispatch.py:424 folded p_shift_mw into const; line 550
  branch_flow_mw now calls numerics.flow_from_ptdf directly.
- T8 tests DONE, commit `272d84c` — tests/_shifter.py:zoned_shifter_loop_network +
  tests/unit/test_shifter_flow_fix_multiperiod_redispatch.py (24 tests). Red/green/sabotage
  independently verified for both T6 and T7 (temporarily reverted each site, confirmed only its
  own tests reddened, restored, confirmed clean diff both times, both files match commits above).
- T8 docs DONE, commit `9e0cbb4` — docs/changelog.md names all 5 sites now. Exhaustive grep sweep
  (`ptdf_matrix @|ptdf @` across src/mambo_power) clean: only the 5 fixed sites +
  numerics/bbus.py's own flow_from_ptdf definition. formats.md needs no caveat restoration.
- T8 gates: ruff check clean, ruff format clean (205 files), mypy clean (59 files), mkdocs
  --strict clean (69s). tests/unit and tests/parity full runs in progress (background,
  task ids bmmgdtnc9 / b4e2o43x7) -- large suites, ~1000s expected per the plan's own prior
  timing. NOT YET COMMITTED beyond above four commits; nothing further needed unless the full
  regression surfaces something.

If resumed after a restart: `git log --oneline -6` in the worktree first -- commits 8a6fb11,
eb771b1, 272d84c, 9e0cbb4 should already be present; do not redo them. Re-run
`uv run pytest -q tests/unit` and `uv run pytest -q tests/parity` if their results were not
yet reported back.
