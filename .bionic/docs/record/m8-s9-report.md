# M8 S9 report — re-review fixes 17–24

Written by the orchestrator: S9's deliverable phase completed and left seven commits with a clean
worktree and a full progress log, but its bookkeeping phase never ran (no report file, no
completion notification — consistent with a session restart, per F8's pattern) and the agent's own
idle status carried no detail. Every claim below is independently re-verified, not taken from the
agent's progress lines.

**Commits** (`e2d6da8..5baa223`, 7 commits, worktree `C:\Claude Projects\mambo-power-m8`):

| commit | fix |
|---|---|
| `a676800` | 17 — NaN `tap_pos`/`tap_neutral` under a changer type imports no tap (as pandapower solves it), reported |
| `ce3a9df` | 18 — legacy files (`tap_phase_shifter`, no `tap_changer_type`) import the tap pandapower 3.3 still applies |
| `4cb74f2` | 19 — the second tap changer (`tap2_*`) applied and composed as pandapower does |
| `6e61756` | 20 — `csv_bundle.dump` swaps the bundle at the directory level; a failed move leaves the old bundle whole |
| `618aed0` | 21 — the dead `... or True` assertion dropped; test renamed to the contract it proves |
| `39b1f9f` | 24 — every dump writes the promoted `Branch.kind`, never `"line"` beside a tap |
| `5baa223` | 22/23 — changelog `Changed` entry for `MissingCostError` + jobs mapping; the error message names a public remedy |

**Progress log** (`.bionic/tmp/m8-s9-progress.md`, the agent's own record, one line per commit):

```
a676800 fix 17 tap_neutral NaN: red 5 -> green 49 (test_io_pandapower_json), sabotage (rule disabled) 3 failed
ce3a9df fix 18 legacy tap_phase_shifter: red 3 -> green 53, sabotage (mapped to None) 3 failed; x1b_legacy mambo 1.05 = pp 1.05
4cb74f2 fix 19 tap2: red (1.05 vs 1.1023) -> green 58, sabotage (prefix loop cut) 5 failed
6e61756 fix 20 csv dir swap: red 4 -> green 65 (test_io_csv_bundle), sabotage (per-file loop restored) 2 failed; x3b == a True, no orphans
618aed0 fix 21 dead assertion: renamed, green 2, sabotage (gen text undo removed) 2 failed
39b1f9f nit 24 kind serializer: red 2 -> green 92, sabotage serializer 1 failed / csv 1 failed
5baa223 22/23 changelog Changed + message: red 1 -> green (opf/jobs/agents tests), mkdocs strict ok
```

**Orchestrator re-verification at `5baa223`** (independent, `uv run` from the worktree):

```
$ uv run pytest -q -p no:cacheprovider tests/unit/test_io_pandapower_json.py tests/unit/test_io_csv_bundle.py
124 passed in 85.51s (0:01:25)

$ uv run pytest -q -p no:cacheprovider tests/unit
1218 passed in 174.13s (0:02:54)

$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
201 files already formatted

$ uv run mypy
Success: no issues found in 59 source files
```

Not independently re-run by the orchestrator: `tests/parity/test_pandapower_json_vs_pandapower.py`
and `mkdocs --strict` (the S9 log claims both green; the full named sweep below re-proves both at
the final head regardless, so nothing here is taken on trust for the wave's figure of record).

**Nits not done**: 23 was folded into the changelog commit per the agent's own note rather than
split out; nits 25–26 (three trafo edges pandapower itself cannot solve; a pre-existing
`.name.tmp-<pid>` directory rmtree'd) are not addressed and are not blocking per the critic's own
verdict language ("no blockers" once 17/18/20 land, which they have).

**Rulings for the spec** (already applied by the orchestrator in `wave-08-interop.spec.md`, AC-6 +
A9, commit `66b79dc` on `epic/01-foundation`, before this report was written): `MissingCostError`
behaviour change recorded; `Branch.kind` promotion; `res_bus` neither read nor written; bulk export
`nets_equal`-identical not byte-identical; neutral-tap NaN encoding kept; `LIMITATIONS` in
`io/limitations.py`.
