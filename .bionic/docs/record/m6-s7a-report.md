# M6 S7a — `Scenario.periods` `max_length` (M5 carry-over, wave spec W6/AC-7, design D6)

Branch `wave/06-zonal-redispatch`, worktree `C:\Claude Projects\mambo-power-m6`.
Base `55f716d` (S4's redispatch LP, merged onto S1-S3's preamble/fixture/zonal-LP work). Head
**`4d8fc10`**, one commit:

| commit | subject |
|---|---|
| `4d8fc10` | `feat(m6/S7a): Scenario.periods max_length=200 (M5 carry-over, AC-7/D6)` |

Files owned and touched, nothing else:

- `src/mambo_power/model/scenario.py`
- `tests/unit/test_period_scenario.py`

---

## 1. What was built

`MAX_PERIODS = 200`, a module-level constant in `scenario.py`, wired into the field as
`Field(default=None, min_length=1, max_length=MAX_PERIODS, description=...)` on
`Scenario.periods`. `min_length=1` is untouched — this slice adds an upper bound only.

The description states the rationale rather than just the number: `Scenario.periods` is
wire-format data (a `SolveRequest`'s embedded field, per `test_jobs.py`'s own docstring), and M5's
own measurement (`continuation-m5.md` carry-over 3, re-derived in `m6-research.md` §8) found a
33,997-byte request expanding to 20,088,000 constraint-matrix nonzeros before HiGHS even starts —
a ~7,000x ratio. Nonzeros scale as `T * n_branch * n_gen`; `m6-research.md` §8 sizes 200 as the
largest horizon that keeps `case300` (this repo's biggest fixture: `n_branch=411`, `n_gen=69`)
near ~68 MB by that same linear estimate, while still covering 8x the epic's stated 24-period real
use case (`R7`) and more than a full week of hourly periods (168) with slack to spare.

## 2. Tests

Four added to `tests/unit/test_period_scenario.py` (21 -> 25), in a new section between the
existing empty-list-rejection test and the dangling-load-ref section:

- `test_scenario_periods_at_max_length_is_accepted` — `MAX_PERIODS` periods, construction path.
- `test_scenario_periods_over_max_length_is_rejected` — `MAX_PERIODS + 1`, asserts the single
  error's `type == "too_long"` and `loc == ("periods",)` — confirmed this is pydantic's own
  standard error shape for `max_length`, not something this slice invents.
- The same pair via `Scenario.model_validate_json(...)` on a hand-built JSON payload, proving the
  bound holds on the wire path too, not just construction.

`None` and a single-entry list stay accepted — not re-tested here since
`test_scenario_periods_defaults_to_none` and several existing single/multi-period tests (e.g.
`test_scenario_periods_referencing_a_real_load_id_is_accepted`) already cover that ground and
were left unmodified.

**Every list length in the new tests reads `MAX_PERIODS` from the module** (imported directly:
`from mambo_power.model.scenario import MAX_PERIODS`), never a hardcoded `200`/`201` literal —
per the assignment's own instruction that a test hardcoding the number is powerless the day it
moves.

### RED shown first

Before touching `scenario.py`, a scratch script confirmed the pre-change behaviour directly
(the new tests couldn't even collect yet, since `MAX_PERIODS` didn't exist — an `ImportError`,
not the interesting RED):

```
$ uv run --no-sync python -c "
from mambo_power.model import Bus, Load, Network, Period, Scenario
net = Network(base_mva=100.0, buses=[Bus(id='b1', base_kv=110.0, type='slack')], loads=[Load(id='d1', bus='b1', p_mw=10.0, q_mvar=0.0)])
periods = [Period(load_p_mw={}) for _ in range(201)]
s = Scenario(network=net, periods=periods)
print('pre-change: 201 periods accepted, len =', len(s.periods))
"
pre-change: 201 periods accepted, len = 201
```

### Sabotage, both directions

1. Bumped `MAX_PERIODS` to 201 in-place (field still reads the constant): all four new tests
   stayed green — they track the constant rather than a frozen number, which is the desired
   self-adjusting behaviour, not a hole.
2. Decoupled the field from the constant — `max_length=200` hardcoded literally in the `Field()`
   call, `MAX_PERIODS` left at 201 — and reran:

   ```
   $ uv run --no-sync python -m pytest tests/unit/test_period_scenario.py -q -k "max_length"
   F.F.
   2 failed, 2 passed
   ```

   Both `..._at_max_length_is_accepted` tests (construction and JSON) went red with pydantic's
   `too_long`, `List should have at most 200 items ... not 201` — exactly the mismatch the
   sabotage introduces. Confirms the tests are actually checking that the field is bound to the
   constant, not just checking a number that happens to match it.

Both mutations reverted with `sed` immediately after observing the result;
`git diff src/mambo_power/model/scenario.py` against the working tree showed no residual before
committing.

## 3. Schema-snapshot question, checked directly

`tests/unit/snapshots/network.schema.json` is built from `Network.json_schema()` alone
(`test_json_schema_snapshot.py:27`, `Network.json_schema() == Network.model_json_schema()`).
Grepped the committed snapshot for `Scenario`/`Period`: the only hit is a prose mention of
"Period" inside `Load.p_mw`'s own description text (`network.schema.json:378`) — not a `$defs`
entry, and unrelated to this change. **No snapshot regen needed.**

`tests/unit/test_jobs.py` embeds `Scenario` via `SolveRequest` (per its own module docstring):
ran it directly, 57 passed unmodified.

## 4. Verification

All commands run from `C:\Claude Projects\mambo-power-m6` with `uv run --no-sync`.

```
$ uv run --no-sync ruff check src/mambo_power/model/scenario.py tests/unit/test_period_scenario.py
All checks passed!

$ uv run --no-sync ruff format --check src/mambo_power/model/scenario.py tests/unit/test_period_scenario.py
2 files already formatted

$ uv run --no-sync mypy src/mambo_power/model/scenario.py tests/unit/test_period_scenario.py
Success: no issues found in 2 source files

$ uv run --no-sync python -m pytest tests/unit/test_period_scenario.py -q
25 passed

$ uv run --no-sync python -m pytest tests/unit/test_jobs.py -q
57 passed

$ uv run --no-sync python -m pytest tests/unit/test_json_schema_snapshot.py -q
3 passed
```

**Baseline reconcile.** `tests/unit/test_period_scenario.py --collect-only` at the base commit
showed 21 tests; mine adds exactly 4 (25 total), confirmed by rerunning `--collect-only` after
the edit. A full `tests/` run was deliberately skipped: the shared worktree carries
`m6-s3-zonal`'s live uncommitted edits (`src/mambo_power/opf/zonal.py`,
`tests/unit/test_opf_zonal.py`, `src/mambo_power/opf/__init__.py`), so a full-suite count would
be contaminated by work outside this slice's scope — the task's own instruction. My one owned
test file and the two files it touches by import (`test_jobs.py`, `test_json_schema_snapshot.py`)
were run directly instead, all green.

## 5. Not done — out of this slice

- The `opf`/`market`/jobs-side halves of wave M6 (zonal LP, redispatch LP, `market.zonal`,
  jobs kind, docs) — owned by sibling slices (`m6-s2-zones`, `m6-s3-zonal`, `m6-s4-redispatch`,
  and unassigned S5-S8 work), untouched here.
- No `git add -A` was used anywhere; the commit staged exactly the two owned files by explicit
  path, so none of the siblings' uncommitted work was swept in.
