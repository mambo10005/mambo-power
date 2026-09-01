# M4 S1 — domain-model (Load.bid, LoadBid, Scenario), completed by the orchestrator

Slice S1 was dispatched as agent `m4-s1-domain-model` (standard, implementor). Same pattern
as S2 in this wave, and several agents across M3: it finished the actual implementation —
17/17 tests passing, lint/mypy clean, schema snapshot regenerated correctly — and was
awaiting a full-suite background check when it went idle without committing or reporting.
Per the non-response procedure, I verified its work independently and landed it as-is, no
changes made to its code.

## What was found

The agent's own progress file (`.bionic/tmp/m4-s1-progress.md`) was precise and current: it
named exactly which files it would stage, and `git status --porcelain` matched that list
exactly — `model/entities.py`, `model/network.py`, `model/scenario.py` (new),
`model/__init__.py`, `tests/unit/test_load_bid_scenario.py` (new),
`tests/unit/snapshots/network.schema.json`. Nothing from S2 (already landed by this point,
commit `f1dfa9b`) or any other slice was mixed in.

One useful process note the agent's own progress file surfaced: `mypy .` (a positional `.`
argument) double-counts `tests/_fixtures.py` as both `_fixtures` and `tests._fixtures`,
overriding `pyproject.toml`'s own `files = ["src"]` setting — a pre-existing repo/mypy
interaction, not something this slice introduced. Bare `uv run mypy` (no positional arg) is
the correct invocation; confirmed clean that way.

## What it built

`PolynomialBid`/`PiecewiseBid` (`model/entities.py`) mirror `GeneratorCost`/`PolynomialCost`/
`PiecewiseCost` field-for-field — deliberately no convexity-direction check here, since that's
`opf.dc_opf`'s job at solve time (S3's `NonConcaveBidError`, per the spec's own Design item 1).
`Load.bid: LoadBid | None = None` — backward compatible, every M1-M3 fixture/test unaffected.
Structural `BAD_RANGE` checks (at least two points, strictly increasing `p_mw`, at least one
coefficient) added to `validate_network`'s loop for loads, mirroring the existing
generator-cost checks exactly — no convexity check added here either, consistent with the
same design split.

`Scenario` (new, `model/scenario.py`): `network: Network` embedded directly, `extra="forbid"`,
no new validation logic added — proven, not assumed, that `Network`'s own nested validator
already catches a dangling reference inside an embedded `Network` (a real test constructs
exactly this case). Mirrors `jobs.models.SolveRequest`'s self-contained pattern per
`m4-research.md` §6.2, not an id/path reference to a `Network` stored elsewhere.

JSON schema snapshot regenerated (`MAMBO_UPDATE_SNAPSHOTS=1`) for the new `Load.bid` field and
the two new `$defs`; the agent reviewed the diff itself before committing.

## Verification (done independently by the orchestrator)

```
$ uv run --no-sync pytest -q -p no:cacheprovider tests/unit/test_load_bid_scenario.py
17 passed in 8.33s
$ uv run --no-sync ruff check .
All checks passed!
$ uv run --no-sync ruff format --check .
129 files already formatted
$ uv run --no-sync mypy
Success: no issues found in 40 source files
$ uv run --no-sync pytest -q -p no:cacheprovider   (full repo suite, run before commit, on this exact tree)
617 passed, 10 warnings in 287.70s
```

617 = 596 (M3 close) + 21 net new (17 from this slice's own new file, +4 net new inside
`test_numerics_arrays.py` from S2, already landed as `f1dfa9b`) — reconciles exactly.

## AC-3 evidence (model half)

- `LoadBid`/`Load.bid` construction and JSON round-trip.
- `Scenario` construction with a valid embedded `Network`; JSON round-trip; a `Network` with a
  genuine validation problem (dangling bus reference) embedded inside a `Scenario` is still
  caught — proven by test, via `Network`'s own nested validator, no explicit `Scenario`-level
  check needed.
- A `Load` with and without a `.bid` — both valid, `bid` defaults to `None`, every existing
  fixture/test unaffected (confirmed by the full 617/617 run, not just the new file).

Exact test cases are in `tests/unit/test_load_bid_scenario.py` — read them directly.

## Commit

`6578709` on `wave/04-nodal-market` (on top of S2's `f1dfa9b`), pushed. Staged exactly the 6
files the agent's own progress notes named.

## Not done by this report

Why the agent went idle at exactly the "awaiting full-suite result" step is not investigated
further — same as S2 and several M3 slices, the evidence-first check found complete, correct,
tested work with nothing left to diagnose. Not force-stopped, per this session's open
`stop-guard.sh` Windows-path bug (see memory `dispatch-preflight-windows-path-bug.md`).
