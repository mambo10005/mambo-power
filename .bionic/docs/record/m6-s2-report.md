# M6 S2 report — `tests/_zones.py` zones fixture helper

Wave M6 "zonal-redispatch", Step 4, slice S2. Implementor role, worktree
`C:\Claude Projects\mambo-power-m6`, branch `wave/06-zonal-redispatch`, base `4cfd1d7`. Owned
files only: `tests/_zones.py`, `tests/unit/test_zones_helper.py`. No `src/` files touched. A
sibling (`m6-s1-preamble`) worked concurrently in the same worktree on
`src/mambo_power/opf/dc_opf.py`/`multiperiod.py`; those files stayed unstaged and untouched by
every command below.

Commit: `e8108e4` (`test(m6/S2): ...`), staged and committed with explicit paths
(`git add tests/_zones.py tests/unit/test_zones_helper.py`), never `git add -A`.

## What was built

**`promote_areas_to_zones(net: Network) -> Network`** — deep copy; for a network carrying only
one real zone (`len(net.zones) <= 1`), promotes each bus's free-form `Bus.area` label into a real
`Zone` entity and sets `Bus.zone` to it. On a network that already carries more than one real zone
(`len(net.zones) > 1`), it is a documented no-op: returns an unchanged deep copy rather than
re-deriving from `Bus.area`, because on case300 that column is a single group and would silently
collapse a real 4-zone partition to 1.

**`corridors(net: Network) -> dict[tuple[str, str], float]`** — for every unordered zone pair with
at least one crossing branch (`from_bus`/`to_bus` in different zones), sums `Branch.rating_mva`
over that pair's cut-set. Requires a `tests/_rated.py`-rated network; raises `ValueError` naming
the branch if any crossing branch is unrated. Keys are sorted pairs. Out-of-service branches are
excluded.

**`zone_of_bus(net) -> dict[str, str]`** and **`buses_by_zone(net) -> dict[str, list[str]]`** —
small accessors.

## Measured facts (re-confirmed directly, not re-asserted from research)

Ran directly against the fixtures (`.venv/Scripts/python.exe`, `tests._fixtures.FIXTURES_DIR`):

```
case30 area counts:  {'1': 11, '2': 10, '3': 9}          -- matches research §1 exactly
case300 zone counts: {'1': 122, '2': 80, '3': 63, '9': 35} -- matches research §1 exactly
case14 zone counts:  {'1': 14}                            -- single zone, single area
case30 area-crossing branches: 7, split across all 3 possible zone pairs:
  ('1','3'): 3   ('2','3'): 3   ('1','2'): 1
```

Corridor caps on `rated_network(case30)` (measured, not assumed):

```
('1','3') -> 16.576768909781237
('1','2') ->  1.5237037054530278
('2','3') -> 19.456188360964873
```

**One finding worth flagging, not a defect.** `tests/_rated.py`'s own module docstring says "every
branch of all five OPF fixtures reads `RATE_A == 0`" — but case30 actually ships real `RATE_A`
values on its branches (32/65/65/32/32/16/65 MVA on the 7 tie branches specifically, confirmed by
reading the loaded `Network` before calling `rated_network`). That docstring is evidently about a
different five-fixture set (case30 is not one of the five OPF-parity fixtures it names elsewhere),
so no action was needed here — but it meant my first version of the
"unrated-crossing-branch raises" test was wrong (it assumed `promote_areas_to_zones(_case30())`
alone would be unrated, and it wasn't — TDD RED for that specific test caught this immediately:
`DID NOT RAISE ValueError`). Fixed by constructing the unrated case by hand (strip
`branch-12.rating_mva` after `rated_network`). Any downstream S3+ work that assumes
`rated_network(case30)`'s ratings are 100% test-time-synthetic should know case30's *unrated*
branches are the ones without real `RATE_A`, not all of them.

## TDD RED, proven

Wrote `tests/unit/test_zones_helper.py` before `tests/_zones.py` existed, ran it:

```
$ .venv/Scripts/python.exe -m pytest tests/unit/test_zones_helper.py -q
ModuleNotFoundError: No module named 'tests._zones'
1 error in 12.35s
```

Then implemented `tests/_zones.py`, reran: 14 passed. One iteration in between: the
unrated-crossing-branch test genuinely failed for the reason above (`DID NOT RAISE ValueError`),
fixed by hand-constructing the unrated case rather than assuming case30 ships no ratings.

## Sabotage proof, done for real

In a scratch copy (`.../scratchpad/_zones_sabotaged.py`, never committed), patched `corridors()`
to unconditionally `continue` past `branch-12` inside its cut-set loop (a silent "ignore one real
crossing branch" bug). Swapped it into place at `tests/_zones.py`, reran the suite:

```
3 failed, 11 passed
FAILED test_case30_corridor_caps_equal_the_hand_summed_cut_set_ratings
  assert 13.285773888829546 == 16.576768909781237 -- obtained/expected differ by exactly
  branch-12's own rating (3.29099502095169 MVA), confirming the sabotage's exact effect
FAILED test_case30_corridor_caps_match_directly_measured_values
  (the pinned-literal check, same delta)
FAILED test_corridors_raises_clearly_on_an_unrated_crossing_branch
  (branch-12 gets skipped before the rating-None check ever runs, so the raise never fires --
  a genuine second failure mode the sabotage exposes)
```

The load-bearing catch is `test_case30_corridor_caps_equal_the_hand_summed_cut_set_ratings`: it
reimplements the cut-set sum independently in the test body (reading `net.branches` and
`Bus.zone` directly) rather than calling `corridors()` a second time, so it is not fooled by the
same skip living inside `corridors()` itself -- the "sabotage the engine's own row/column, keep
the oracle-side construction fixed" shape research §5 names, applied here to a test rather than a
parity oracle.

Restored the real `tests/_zones.py` from a backup (`/tmp/_zones_good_backup.py` -- note: this
Windows/Git-Bash environment does have a working `/tmp`, unlike the scratchpad-only convention
elsewhere; first restore attempt used the wrong path and needed a second, verified attempt via
`diff`), reconfirmed 14/14 green before committing.

## Gates

```
$ uv run --no-sync ruff check tests/          -> All checks passed!
$ uv run --no-sync ruff format --check tests/ -> 67 files already formatted
$ uv run --no-sync mypy                       -> Success: no issues found in 46 source files
```

The repo's actual mypy gate (as CI runs it, `uv run mypy` with no args) is scoped by
`pyproject.toml`'s `[tool.mypy] files = ["src"]` -- `tests/` is outside mypy's checked set
entirely. Direct invocation (`mypy tests/_zones.py tests/unit/test_zones_helper.py`) errors with
a module-identity collision (`Source file found twice under different module names`), which is a
mypy path-resolution artifact of invoking it standalone against a PEP 420 namespace package, not
a real type error -- the CI-equivalent invocation above is the one that matters and is clean.

## Suite count

```
$ git status --short
 M src/mambo_power/opf/dc_opf.py       <- sibling's, untouched by me
 M src/mambo_power/opf/multiperiod.py  <- sibling's, untouched by me
?? tests/_zones.py                     <- mine, now committed
?? tests/unit/test_zones_helper.py     <- mine, now committed

$ uv run --no-sync pytest --collect-only -q
830 tests collected
```

816 baseline (`4cfd1d7`) + 14 new = 830, reconciled via `--collect-only` rather than a full run,
because a full run would be contaminated by the sibling's uncommitted `src/` edits in this shared
worktree (standing rule). All 14 of my own tests run and pass (`pytest
tests/unit/test_zones_helper.py -q` -> `14 passed`).

## Scope discipline

Touched only `tests/_zones.py` and `tests/unit/test_zones_helper.py`. Read but did not modify:
`tests/_rated.py` (used unmodified, per the spec's own requirement), `.bionic/docs/record/
m6-research.md`, `.bionic/docs/specs/epic-01-foundation/wave-06-zonal-redispatch.spec.md`,
`src/mambo_power/model/entities.py`, `src/mambo_power/model/network.py`,
`src/mambo_power/io/matpower.py` (read-only, to confirm the ZONE-vs-AREA column split and the
`Bus.zone`/`net.zones` validation contract before writing the promotion logic).
