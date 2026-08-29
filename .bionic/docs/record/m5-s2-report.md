# M5 / S2 domain-model — slice report

Slice S2 of wave M5 (`multiperiod`), Step 4. Commit **`7afa9c5`** on `wave/05-multiperiod`
(worktree `C:\Claude Projects\mambo-power-m5`), not pushed. Delivers W3; discharges the model
half of AC-2 and contributes the `periods=None` half of AC-4.

**Provenance of this file (orchestrator error, corrected).** The `m5-s2-domain-model` agent wrote
its own report here and it was **overwritten by the orchestrator**, which had concluded from an
idle notification that the agent had stopped without reporting and applied the non-response
procedure. That conclusion was wrong: the agent was mid-verification, finished normally, and its
messages simply arrived late. Idle is not a completion signal — and it is equally not a *failure*
signal, which is the half the orchestrator got wrong. The agent's own content below is restored
verbatim from its completion message; the orchestrator's independent re-verification is kept as a
separate section because two independent checks are worth more than one. Nothing in the agent's
committed work was ever changed.

## What landed (agent's report)

Model layer only — `src/mambo_power/model/*` plus tests. `git show --stat 7afa9c5`: 7 files,
+320/−7.

1. **`Period`** (new, `scenario.py`) — `load_p_mw: dict[str, float]`, an id-keyed override, with
   a `field_validator` rejecting negative values.
2. **`Scenario.periods: list[Period] | None = None`** — non-empty-if-present via
   `Field(min_length=1)` on the optional list. Confirmed by direct pydantic probe that this fires
   only on an actual empty list, **not** on `None`.
3. **`Generator.ramp_up_mw` / `ramp_down_mw`: `float | None = None`** (`entities.py`), mirroring
   `Branch.rating_mva`'s description wording; a `BAD_RANGE` check in `network.py`'s
   `validate_network` rejects `<= 0`.

**Dangling-reference check: PROVED firing, not assumed.** It lives on `Scenario` (a `Period` has
no network of its own to check against) as a `model_validator(mode="after")` that runs after
`Network`'s own nested validator. Three tests: `test_scenario_periods_dangling_load_ref_is_rejected`
(construction path), `test_scenario_periods_dangling_load_ref_via_json_is_rejected` (JSON path),
and `test_scenario_periods_referencing_a_real_load_id_is_accepted` as the **paired positive case**
using the identical load id. All three pass.

**TDD.** RED confirmed before implementation (`ImportError: cannot import name 'Period'`, then
`extra_forbidden` on `ramp_up_mw`); GREEN after — 65 passed across
`test_period_scenario.py` + `test_model_invariants.py`.

**Suite reconciliation against the 654 baseline.** This slice adds **exactly 22 tests** — 19 new
in `tests/unit/test_period_scenario.py` plus 3 new `BAD_RANGE` rows in
`test_model_invariants.py`'s existing parametrize catalog (43 → 46) — verified via
`--collect-only` counts before and after, not inferred from diff line counts. 654 + 22 = **676**
is this slice's own contribution. The shared worktree's full run showed `692 passed` (335.54s)
because S1 (`opf/dc_opf.py`, uncommitted at report time) and S3 (`numerics/arrays.py`, committed
separately) are adding their own tests in the same worktree; the extra 16 are theirs. Every
pre-existing test in both touched files is byte-identical (the `test_model_invariants.py` diff is
a pure insertion; `test_load_bid_scenario.py`, the M4 sibling, was not touched and still passes
17/17).

**JSON schema snapshot** regenerated via `MAMBO_UPDATE_SNAPSHOTS=1`; the diff is exactly the two
new `Generator` fields, nothing structural — confirmed by reading the diff, not assumed.

**Lint/type:** `ruff check`, `ruff format --check`, `mypy` all clean on the touched files.

**Scope:** `model/{__init__.py,entities.py,network.py,scenario.py}` + two test files + the
snapshot. `opf/`, `numerics/arrays.py`, `market/`, `jobs/` untouched.

**Process deviation, self-flagged by the agent.** It committed and wrote its report before
sending its completion message, where the brief's report gate asked for the message first. It
disclosed this rather than letting it pass. Worth noting that this deviation is what made the
collision above possible: had the message come first, the orchestrator would not have mistaken
lateness for death.

## Orchestrator's independent re-verification

Re-executed against commit `7afa9c5`, independently of the agent's own runs.

**Scoped test run** — `uv run --no-sync pytest -q -p no:cacheprovider
tests/unit/test_period_scenario.py tests/unit/test_model_invariants.py` → `65 passed in 5.09s`.

**Dangling reference, live probe:**

```
dangling CAUGHT -> ValidationError |
  Value error, periods reference load id(s) not present in network.loads: ['load-NOPE']
real id accepted -> {'load-2': 5.0}
periods=None -> None
```

**Ramp boundaries — and a probe run at the wrong altitude, worth recording.** A first probe
constructed a bare `Generator(...)` and saw `0.0` and `-1.0` accepted, which looked like a spec
violation. It was not: this repo deliberately leaves bare-entity construction unvalidated and
puts range checks in `validate_network`'s `BAD_RANGE` catalog. Re-run through
`Network.model_validate`:

```
ramp_up_mw=0.0    REJECTED  BAD_RANGE at generators[0].ramp_up_mw:
                            generator "gen-1": ramp_up_mw must be > 0 when given, got 0.0
ramp_down_mw=-1.0 REJECTED  BAD_RANGE at generators[0].ramp_down_mw:
                            generator "gen-1": ramp_down_mw must be > 0 when given, got -1.0
ramp_up_mw=5.0    ACCEPTED
```

This is W3's requirement — strictly `> 0` when given, never `0` — closing the trap research §4.2
documented, where every fixture's MATPOWER ramp columns are all-zero and a naive `0` default
would have meant "cannot move at all".

**Lint/type, scoped:** `ruff check` → `All checks passed!`; `ruff format --check` → `8 files
already formatted`.

## Not claimed for this slice

No full-suite reconciliation is claimed as *this slice's* evidence. S1's extraction was in flight
in the shared worktree, so the 692 figure includes other slices' tests; the agent decomposed it
correctly (676 its own, 16 others'), and the authoritative full-suite number belongs to Step 5's
tests floor once every slice has landed.

## Nothing reads these fields yet

`Period`, `Scenario.periods` and the ramp fields are model-present and solver-ignored as of this
commit — S4 (builder) and S5 (market) are the consumers. Correct for the slice, and the same
pattern M1 used for `Storage` and M4 used for `Load.bid`.
