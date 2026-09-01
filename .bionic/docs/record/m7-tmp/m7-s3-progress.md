# M7 S3 progress — agents fixtures

Slice: three wave fixtures (`tests/_agents.py`) + their unit test (`tests/unit/test_agents_fixtures.py`).

## Status: measuring + drafting

- Read wave-07 spec (W7, AC-4, AC-5) and the two working probes
  (`m7-a4-control-and-amplitude.py`, `m7-a4-two-point-climb.py`).
- Read house style in `tests/_rated.py`, `tests/_bids.py`, `tests/_zones.py`.
- Re-measured all six table rows through the actual model classes + `opf.dc_opf` directly
  (not the probes' ad hoc `Market` class) — **all agree with the spec table** within HiGHS's
  own ~0.02 solver residual. No disagreement to report so far.
- Ran 5 sabotage-parameter probes (capacity, true cost x2, rival cost, bid-curve) to get
  concrete numbers before writing assertions — all show real, nonzero residual movement.

## Next

- Write `tests/_agents.py` (network factories + shared `clear_with_offers` helper).
- Write `tests/unit/test_agents_fixtures.py` (measured-table tests, closed-form check,
  sabotage sweep).
- Run pytest/ruff/mypy at head, write final report, commit.
