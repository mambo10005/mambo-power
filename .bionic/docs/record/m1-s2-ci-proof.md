# M1/S2 — CI red/green proof

Evidence for wave-01-substrate AC-1 (green on every matrix job), AC-2 (a planted failing
unit test turns CI red, then is removed), AC-3 (oracle imports pass in the test session —
`tests/parity/test_oracles_import.py` ran green in every job, see §2b excerpt).

Repo `mambo10005/mambo-power`, workflow `.github/workflows/ci.yml`, 5-job matrix.
All timestamps UTC, 2026-08-20. `gh` authenticated as mambo10005.

Verdict: **the instrument works in both directions.** 2922d8e is green on 5/5 jobs; a planted
`assert 1 == 2` is red on 5/5 jobs at the `pytest` step with ruff/format/mypy green before it.
An unplanned extra: the first planted push was red at `ruff check` instead (E501 on a 102-char
docstring), which additionally proves the lint gate stops the pipeline before pytest runs.

---

## 1. Green run — wave/01-substrate @ 2922d8e

```
$ gh run list --repo mambo10005/mambo-power --branch wave/01-substrate --limit 3 \
    --json databaseId,headSha,status,conclusion,url,createdAt,displayTitle
[{"conclusion":"","createdAt":"2026-08-20T22:20:17Z","databaseId":32423795251,
  "displayTitle":"feat(m1/S1): project scaffold + CI skeleton — uv/hatchling, ruff+mypy…",
  "headSha":"2922d8e3cbb939b03d8e26ad060a79a58a53e32c","status":"in_progress",
  "url":"https://github.com/mambo10005/mambo-power/actions/runs/32423795251"}]

$ gh run watch 32423795251 --repo mambo10005/mambo-power --exit-status --interval 15
Run CI (32423795251) has already completed with 'success'
EXIT=0

$ gh run view 32423795251 --repo mambo10005/mambo-power \
    --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt
{"conclusion":"success","createdAt":"2026-08-20T22:20:17Z",
 "headSha":"2922d8e3cbb939b03d8e26ad060a79a58a53e32c","id":32423795251,
 "status":"completed","updatedAt":"2026-08-20T22:21:07Z",
 "url":"https://github.com/mambo10005/mambo-power/actions/runs/32423795251"}
```

- Run id: **32423795251**
- URL: https://github.com/mambo10005/mambo-power/actions/runs/32423795251
- Created 22:20:17Z, completed 22:21:07Z

| Job | Conclusion | Started | Completed |
|---|---|---|---|
| ubuntu-latest / py3.11 | success | 22:20:20Z | 22:20:46Z |
| ubuntu-latest / py3.12 | success | 22:20:20Z | 22:20:43Z |
| ubuntu-latest / py3.13 | success | 22:20:20Z | 22:20:44Z |
| macos-latest / py3.12 | success | 22:20:20Z | 22:21:01Z |
| windows-latest / py3.12 | success | 22:20:21Z | 22:21:07Z |

Step-level (same for all 5 jobs):

```
$ gh api repos/mambo10005/mambo-power/actions/runs/32423795251/jobs \
    --jq '.jobs[] | "\(.name) [\(.conclusion)]: " + ([.steps[] | "\(.name)=\(.conclusion)"] | join(", "))'
ubuntu-latest / py3.12 [success]: Set up job=success, Run actions/checkout@v4=success,
  Run astral-sh/setup-uv@v5=success, Run uv python install 3.12=success,
  Run uv sync --locked --all-groups=success, Run uv run ruff check .=success,
  Run uv run ruff format --check .=success, Run uv run mypy=success, Run uv run pytest=success,
  Post Run astral-sh/setup-uv@v5=success, Post Run actions/checkout@v4=success, Complete job=success
(ubuntu py3.11, ubuntu py3.13, macos py3.12, windows py3.12: identical — every step success)
```

AC-1 satisfied: `uv sync`, `ruff check`, `ruff format --check`, `mypy`, `pytest` all exit 0 in all 5 jobs.

---

## 2. Planted failure — branch m1/s2-planted-failure

Worktree isolation, so the wave branch and main checkout were never written to:

```
$ git worktree add "C:\Claude Projects\mambo-power-s2" -b m1/s2-planted-failure wave/01-substrate
Preparing worktree (new branch 'm1/s2-planted-failure')
HEAD is now at 2922d8e feat(m1/S1): project scaffold + CI skeleton — ...
```

### 2a. First planted commit faef8a3 — red at `ruff check` (not the intended step)

Planted file (as specified, docstring verbatim):

```python
"""PLANTED FAILURE — M1/S2 proves CI catches a red suite; this branch is deleted after observation."""


def test_planted_failure() -> None:
    """PLANTED FAILURE — M1/S2 proves CI catches a red suite; this branch is deleted after observation."""
    assert 1 == 2
```

```
$ git commit ...   -> faef8a3c6944bbfb43c8a40490d067cf79726820
  test(m1/S2): PLANTED FAILURE — proves CI catches a red suite
$ git push -u origin m1/s2-planted-failure        (PowerShell, cwd = worktree)
 * [new branch]      m1/s2-planted-failure -> m1/s2-planted-failure
```

- Run id: **32423921545** — URL: https://github.com/mambo10005/mambo-power/actions/runs/32423921545
- Created 22:21:57Z, completed 22:27:17Z, conclusion **failure**

| Job | Conclusion | Failing step | Steps after it |
|---|---|---|---|
| ubuntu-latest / py3.11 | failure | `uv run ruff check .` | format/mypy/pytest skipped |
| ubuntu-latest / py3.12 | failure | `uv run ruff check .` | skipped |
| ubuntu-latest / py3.13 | failure | `uv run ruff check .` | skipped |
| macos-latest / py3.12 | failure | `uv run ruff check .` | skipped |
| windows-latest / py3.12 | failure | `uv run ruff check .` | skipped |

```
$ gh run view 32423921545 --repo mambo10005/mambo-power --log-failed   (ubuntu py3.12, trimmed)
E501 Line too long (102 > 100)
 --> tests/unit/test_planted_failure.py:1:101
E501 Line too long (106 > 100)
 --> tests/unit/test_planted_failure.py:5:101
  |
4 | def test_planted_failure() -> None:
5 |     """PLANTED FAILURE — M1/S2 proves CI catches a red suite; this branch is deleted after observation."""
6 |     assert 1 == 2
Found 2 errors.
##[error]Process completed with exit code 1.
```

Why: `pyproject.toml` sets `[tool.ruff] line-length = 100`; the mandated docstring is 102/106
chars. CI went red, but pytest never ran, so this run alone does not prove the *test* gate.
Decision (reversible, throwaway branch): push a follow-up commit that wraps the docstring and
re-observe. This run is kept in the record as incidental proof that the ruff gate halts the job.

### 2b. Second planted commit c594112 — red at `pytest` (the intended proof)

```python
"""PLANTED FAILURE — M1/S2 proves CI catches a red suite.

This branch is deleted after observation.
"""


def test_planted_failure() -> None:
    """PLANTED FAILURE — M1/S2 proves CI catches a red suite; branch deleted after observation."""
    assert 1 == 2
```

```
$ git commit ...   -> c594112db1a99a994fcb71c0e39211e987d6cc3d
  test(m1/S2): PLANTED FAILURE — wrap docstring so ruff passes and the red reaches pytest
$ git push origin m1/s2-planted-failure           (PowerShell, cwd = worktree)
   faef8a3..c594112  m1/s2-planted-failure -> m1/s2-planted-failure

$ gh run watch 32424408894 --repo mambo10005/mambo-power --exit-status --interval 15
watch exit=1
$ gh run view 32424408894 --repo mambo10005/mambo-power \
    --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt
{"conclusion":"failure","createdAt":"2026-08-20T22:28:29Z",
 "headSha":"c594112db1a99a994fcb71c0e39211e987d6cc3d","id":32424408894,
 "status":"completed","updatedAt":"2026-08-20T22:29:30Z",
 "url":"https://github.com/mambo10005/mambo-power/actions/runs/32424408894"}
```

- Run id: **32424408894** — URL: https://github.com/mambo10005/mambo-power/actions/runs/32424408894
- Created 22:28:29Z, completed 22:29:30Z, conclusion **failure**

| Job | Conclusion | ruff check | ruff format | mypy | pytest | Started | Completed |
|---|---|---|---|---|---|---|---|
| ubuntu-latest / py3.11 | failure | success | success | success | **failure** | 22:28:33Z | 22:28:55Z |
| ubuntu-latest / py3.12 | failure | success | success | success | **failure** | 22:28:33Z | 22:28:56Z |
| ubuntu-latest / py3.13 | failure | success | success | success | **failure** | 22:28:33Z | 22:28:58Z |
| macos-latest / py3.12 | failure | success | success | success | **failure** | 22:28:35Z | 22:29:29Z |
| windows-latest / py3.12 | failure | success | success | success | **failure** | 22:28:33Z | 22:29:24Z |

Source of the table:

```
$ gh api repos/mambo10005/mambo-power/actions/runs/32424408894/jobs \
    --jq '.jobs[] | "\(.name) [\(.conclusion)] \(.started_at)..\(.completed_at): " + ([.steps[] | "\(.name)=\(.conclusion)"] | join(", "))'
ubuntu-latest / py3.12 [failure] 2026-08-20T22:28:33Z..2026-08-20T22:28:56Z: ...,
  Run uv run ruff check .=success, Run uv run ruff format --check .=success,
  Run uv run mypy=success, Run uv run pytest=failure, ...
(other 4 jobs identical pattern)
```

Failing-step excerpt (ubuntu py3.12; the other four jobs show the same FAILED line):

```
$ gh run view 32424408894 --repo mambo10005/mambo-power --log-failed   (trimmed)
collected 4 items

tests/parity/test_oracles_import.py ..                                   [ 50%]
tests/unit/test_planted_failure.py F                                     [ 75%]
tests/unit/test_version.py .                                             [100%]

=================================== FAILURES ===================================
_____________________________ test_planted_failure _____________________________

    def test_planted_failure() -> None:
        """PLANTED FAILURE — M1/S2 proves CI catches a red suite; branch deleted after observation."""
>       assert 1 == 2
E       assert 1 == 2

tests/unit/test_planted_failure.py:9: AssertionError
=========================== short test summary info ============================
FAILED tests/unit/test_planted_failure.py::test_planted_failure - assert 1 == 2
========================= 1 failed, 3 passed in 8.41s ==========================
```

Per-job pytest summary lines from the same log:

```
windows-latest / py3.12   1 failed, 3 passed in 16.13s
ubuntu-latest / py3.13    1 failed, 3 passed in 10.08s
ubuntu-latest / py3.11    1 failed, 3 passed in 9.68s
ubuntu-latest / py3.12    1 failed, 3 passed in 8.41s
macos-latest / py3.12     1 failed, 3 passed in 29.04s
```

AC-2 satisfied: planted red observed on 5/5 jobs at pytest; the branch is removed below, and
the wave branch (which never carried the planted test) remains on its green run. AC-3 evidence:
`tests/parity/test_oracles_import.py ..` passed in every job, including macOS and Windows.

---

## 3. Cleanup verification

```
$ git push origin --delete m1/s2-planted-failure      (PowerShell, cwd = worktree)
 - [deleted]         m1/s2-planted-failure

$ git -C "C:\Claude Projects\mambo-power" worktree remove "C:\Claude Projects\mambo-power-s2" --force
(ok)
$ git -C "C:\Claude Projects\mambo-power" branch -D m1/s2-planted-failure
Deleted branch m1/s2-planted-failure (was c594112).

$ git -C "C:\Claude Projects\mambo-power" worktree list
C:/Claude Projects/mambo-power     ca10b6a [main]
C:/Claude Projects/mambo-power-m1  8c82e9d [wave/01-substrate]

$ git -C "C:\Claude Projects\mambo-power" branch --list 'm1/*'
(empty)
$ test -d "/c/Claude Projects/mambo-power-s2"
directory gone

$ gh api repos/mambo10005/mambo-power/branches --jq '.[].name'
main
wave/01-substrate

$ git -C "C:\Claude Projects\mambo-power" fetch --prune origin; git branch -r
  origin/main
  origin/wave/01-substrate

$ git -C "C:\Claude Projects\mambo-power-m1" status --porcelain --branch
## wave/01-substrate...origin/wave/01-substrate [ahead 1]
$ git -C "C:\Claude Projects\mambo-power-m1" log -1 --format='%H %s'
8c82e9dc2d01c490e565e3abe8f7d3ebe1f28dfb feat(m1/S3): Network model — pydantic v2 entities, ...
$ git -C "C:\Claude Projects\mambo-power" status --porcelain --branch
## main...origin/main
```

The wave checkout's "ahead 1" is commit 8c82e9d (S3, another agent's work) — S2 wrote nothing
there. Main checkout is clean.
