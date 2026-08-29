# M7 S5 progress — AC-3 and AC-4 (tests/unit/test_market_agents_economics.py)

2026-08-28. Commit `8bc24e5` on `wave/07-agents`.

## State
- [x] Read spec AC-3/AC-4/W5, A1-A4; plan `## Findings the review layers caught`
- [x] Read `market/agents.py`, `market/strategy.py`, `tests/_agents.py`, S3's and S4's modules
- [x] `git archive` overlay of 74a0532 built; import provenance printed
- [x] AC-3 (a)+(b) measured on linear / quadratic / piecewise — bitwise on all three
- [x] AC-4 pivotal / closed form / bid-move / control / rival-move measured
- [x] Test module written — 21 passed on the overlay and at the worktree head
- [x] Sabotage sweep (6 defects) on a separate archive overlay copy
- [x] Committed `8bc24e5` (explicit path)
- [ ] Gates: pytest / ruff check / ruff format --check . / mypy at head
- [ ] Report `.bionic/docs/record/m7-s5-report.md`

## Reported to the lead
Live sabotage of `src/mambo_power/opf/__init__.py` (cost-source application deleted) sitting
uncommitted in the SHARED worktree at 22:59-23:02 PDT; restored by its owner by 23:07. Not mine,
not fixed by me. All my numbers were taken on the archive overlay.
