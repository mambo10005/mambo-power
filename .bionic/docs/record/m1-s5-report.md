# M1 S5 report — numerics: NetworkArrays pu view, Ybus/Bbus/PTDF/LODF with dense, pandapower and property oracles

Agent: m1-s5-numerics · 2026-08-20 · worktree `C:\Claude Projects\mambo-power-m1`, branch `wave/01-substrate`
Base: c9b5a90 (S4 importer) → **commit fc68535b31bdbcff19ce295e269888450fa5a64f** (not pushed).
Every claim below carries its command and trimmed output, or is labelled `unverified`.

**Read this first — one deviation from the brief.** `pyproject.toml` lost one line,
`[tool.mypy] python_version = "3.11"`. Reason: the locked numpy for Python ≥ 3.12 is 2.5.2, whose
stubs use PEP 695 `type` statements; mypy refuses to parse them under a 3.11 target
(`numpy\__init__.pyi:737: error: Type statement is only supported in Python 3.12 and greater`).
S1–S4 never imported numpy from `src`, so the pin was a latent defect that S5's first
`import numpy` exposed; with it in place `uv run mypy` exits 2 on this machine and on 4 of the 5 CI
legs. Without the pin mypy follows the running interpreter, which is what the matrix intends
(ruff's `target-version = "py311"` still guards syntax). Proven on both interpreters — §3.2.

## 1. Delivered

| Path | Contents |
|---|---|
| `src/mambo_power/numerics/arrays.py` (211 lines) | `NetworkArrays.from_network(net)` — frozen dataclass over the in-service subset; index maps, positions, pu arrays per bus and per generator; the single `/ base_mva` site |
| `src/mambo_power/numerics/ybus.py` (63) | `ybus(arr)` complex CSC, `yf_yt(arr)` → `(Yf, Yt)`, `branch_admittances(arr)` |
| `src/mambo_power/numerics/bbus.py` (68) | `bbus(arr)`, `bf(arr)`, `p_shift(arr)` (bus vector), plus `pf_shift(arr)` (branch vector), `incidence(arr)`, `branch_susceptance(arr)` |
| `src/mambo_power/numerics/ptdf.py` (36) | `ptdf(arr, slack=None)` dense `n_branch × n_bus`, sparse LU of the reduced Bbus |
| `src/mambo_power/numerics/lodf.py` (89) | `lodf(arr, ptdf_matrix=None)`, `bridges(arr)` (iterative Tarjan over the multigraph), `BRIDGE_TOL = 1e-10` |
| `src/mambo_power/numerics/__init__.py` | re-exports exactly `NetworkArrays, ybus, yf_yt, bbus, bf, p_shift, ptdf, lodf, bridges` |
| `tests/unit/test_numerics_arrays.py` | 11 tests on a hand-built 4-bus network (out-of-service bus, out-of-service branch with live endpoints, three gens on one bus with the first out of service, live + dead load, shunts) |
| `tests/unit/test_numerics_dense.py` | 15 tests, AC-7 dense re-derivation on a 6-bus case (5-bus meshed core with a 0.97-tap / 5° transformer, a parallel pair and a shunt, plus one radial bus so exactly one bridge exists) |
| `tests/parity/test_ybus_vs_pandapower.py` | 3 checks × 5 fixtures = 15 tests, AC-7 pandapower oracle (Ybus/Yf/Yt, Bbus/Bf/Pbusinj, bridges vs removal-BFS) |
| `tests/property/test_numerics_properties.py` | 5 hypothesis properties, `max_examples=40`, `deadline=None`, `derandomize=True` |

Conventions implemented (W1 extract §4, MATPOWER `makeYbus`/`makeBdc`): `y = 1/(r + jx)`, total
`b` with `b/2` per end, from-side tap `a = tap·e^{j·shift}`, `Yff = (y + jb/2)/|a|²`,
`Yft = −y/conj(a)`, `Ytf = −y/a`, `Ytt = y + jb/2`, shunt `(g + jb)/base_mva` on the diagonal with
MATPOWER signs; DC `b = 1/(x·tap)`, `pf_shift = −b·shift_rad`, `p_shift = Cftᵀ·pf_shift`, so
`P = Bbus·θ + p_shift`; PTDF with the slack column zero; `LODF[l,k] = h_k[l]/(1 − h_k[k])`,
diagonal −1, bridge columns NaN.

## 2. RED — tests written first

Command: `uv run pytest tests/unit/test_numerics_arrays.py tests/unit/test_numerics_dense.py tests/parity/test_ybus_vs_pandapower.py tests/property/test_numerics_properties.py -q` → **exit 2**

```
ERROR collecting tests/unit/test_numerics_arrays.py
tests\unit\test_numerics_arrays.py:23: in <module>
    from mambo_power.numerics import NetworkArrays
E   ModuleNotFoundError: No module named 'mambo_power.numerics'
ERROR collecting tests/unit/test_numerics_dense.py
tests\unit\test_numerics_dense.py:22: in <module>
    from mambo_power.numerics import NetworkArrays, bbus, bf, bridges, lodf, p_shift, ptdf, ybus, yf_yt
E   ModuleNotFoundError: No module named 'mambo_power.numerics'
ERROR collecting tests/parity/test_ybus_vs_pandapower.py
tests\parity\test_ybus_vs_pandapower.py:30: in <module>
    from mambo_power.numerics import NetworkArrays, bbus, bf, bridges, p_shift, ybus, yf_yt
E   ModuleNotFoundError: No module named 'mambo_power.numerics'
ERROR collecting tests/property/test_numerics_properties.py
tests\property\test_numerics_properties.py:20: in <module>
    from mambo_power.numerics import NetworkArrays, bbus, bridges, lodf, ptdf, ybus
E   ModuleNotFoundError: No module named 'mambo_power.numerics'
4 errors in 0.63s
```

After the package landed, the same command: `45 passed in 7.04s`, exit 0 — first run, no
implementation fix needed.

**Instrument catches** (scratch scripts monkey-patching one builder at a time, against the
test modules' own comparisons; `src` restored and `git status` clean afterwards):

```
MUTATION Ybus Yff/|a| not |a|^2   : case118 max|diff| vs pandapower = 2.010e+00  caught(>1e-9)=True
MUTATION Ybus b not b/2           : case118 max|diff| vs pandapower = 1.196e+00  caught(>1e-9)=True
MUTATION Bbus forget tap divide   : case118 max|diff| vs pandapower = 1.879e+00  caught(>1e-9)=True
MUTATION Ybus yft/ytf swapped     : case118 max|diff| vs pandapower = 2.930e-14  caught(>1e-9)=False   <- see below
MUTATION yft/ytf swapped vs dense 6-bus (5 deg shifter): caught — Max absolute difference among violations: 1.49234855
MUTATION LODF denominator sign    : 2 failed, 2 passed, 10 deselected in 0.78s  exit 1
MUTATION bridges parent-skip      : 1 failed, 2 passed, 16 deselected in 42.93s  exit 1
```

The swapped-conjugate slip is invisible to the fixture oracle because no fixture carries a phase
shift (S4 report §6.14: `SHIFT` is 0 everywhere), so `Yft == Ytf` there. The dense unit test's
5° shifter is what holds that convention — which is why the dense case carries one. The
`bridges parent-skip` mutant (skipping the parent *vertex* instead of the arriving *edge*, the
classic parallel-edge bug) is caught by the property tier's removal-BFS oracle, not by the
fixtures (none has parallel branches); the 42.9 s is hypothesis shrinking the counter-example.

## 3. GREEN gate

`uv` = `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe`; `uv sync --locked --all-groups` → `Resolved 81 packages … Checked 77 packages`, exit 0. Python 3.12.14, pandapower 3.3.0, scipy 1.18.0, numpy 2.5.2, hypothesis 6.165.10, mypy 2.3.1.

### 3.1 Project venv (Python 3.12)

| Command | Exit | Trimmed output |
|---|---|---|
| `uv run ruff check .` | 0 | `All checks passed!` |
| `uv run ruff format --check .` | 0 | `31 files already formatted` |
| `uv run mypy` | 0 | `Success: no issues found in 14 source files` |
| `uv run pytest` | 0 | **172 passed in 11.19s** (127 before S5 + 45 new; 9 pre-existing pandapower RuntimeWarnings from S4's oracle) |

Gate fixes on the way, in order: (1) `ruff check` E501 ×4 and `ruff format --check` wanted three
files rewrapped → `uv run ruff format <3 files>` (`3 files reformatted`) and two comment rulers
shortened; (2) mypy: the `python_version` pin (see top) then, with a 3.12 target, one real error —
`ybus.py:37 Incompatible return value type (got tuple[ndarray[…float64]…], expected …complex128…)`
— fixed by building the four branch vectors as explicit `complex128` arrays; (3) on the 3.11 leg
only (§3.2): `arrays.py:140 Incompatible types in assignment (expression has type "ndarray[…signedinteger…]", variable has type "ndarray[…float64]")` — numpy 2.4.6's stub types
`np.bincount(weights=…)` as integer; fixed with `np.asarray(…, dtype=np.float64)`. The final
172-pass run above (and a re-run alongside the 3.11 suite: `172 passed in 14.01s`) is after all
three.

### 3.2 CI 3.11 leg, proven locally in a scratch venv

No Python 3.11 was installed (`uv python list --only-installed` → 3.14.2, 3.12.14 only). With
`UV_PROJECT_ENVIRONMENT=<scratchpad>/venv311` (project `.venv` untouched):

| Command | Exit | Trimmed output |
|---|---|---|
| `uv run --python 3.11 --locked python -c "…"` | 0 | `3.11.16 numpy 2.4.6` (`Installed 79 packages`) |
| `uv run --python 3.11 --locked mypy` | 0 | `Success: no issues found in 14 source files` |
| `uv run --python 3.11 --locked pytest -q -p no:warnings -p no:cacheprovider` | 0 | `172 passed in 29.81s` |

So the numpy-stub surface is proven on both locked numpy versions (2.4.6 for < 3.12, 2.5.2 for
≥ 3.12). The 3.13 leg (numpy 2.5.2, same stubs as 3.12) is `unverified` locally.

Suite runtime: 11.2 s solo on 3.12, well under the ~60 s budget. The 45 new tests alone: 7.0 s.

## 4. Commit

`git rev-parse HEAD` → `fc68535b31bdbcff19ce295e269888450fa5a64f`. `git show --stat HEAD`:

```
commit fc68535b31bdbcff19ce295e269888450fa5a64f
Author: Manho Joung <manhojoung@gmail.com>
Date:   Thu Aug 20 16:12:30 2026 -0700

    feat(m1/S5): numerics — NetworkArrays pu view, Ybus/Bbus/PTDF/LODF with dense, pandapower and property oracles

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 pyproject.toml                             |   1 -
 src/mambo_power/numerics/__init__.py       |  23 +++
 src/mambo_power/numerics/arrays.py         | 211 +++++++++++++++++++
 src/mambo_power/numerics/bbus.py           |  68 ++++++
 src/mambo_power/numerics/lodf.py           |  89 ++++++++
 src/mambo_power/numerics/ptdf.py           |  36 ++++
 src/mambo_power/numerics/ybus.py           |  63 ++++++
 tests/parity/test_ybus_vs_pandapower.py    | 144 +++++++++++++
 tests/property/test_numerics_properties.py | 146 +++++++++++++
 tests/unit/test_numerics_arrays.py         | 215 +++++++++++++++++++
 tests/unit/test_numerics_dense.py          | 322 +++++++++++++++++++++++++++++
 11 files changed, 1317 insertions(+), 1 deletion(-)
```

No hook blocked the commit; `git status --short` after commit: empty. Nothing pushed. Model,
schema snapshot, `uv.lock`, CI, fixtures: untouched (the stat above is the complete file list;
`pyproject.toml` is the one-line mypy deviation).

## 5. Oracle path (AC-7) and per-fixture figures

### 5.1 Which Ybus oracle and why

**Primary path worked — spec Design assumption (b) holds.** `pandapower.pypower.makeYbus.makeYbus`
is importable in 3.3.0 with signature `(baseMVA, bus, branch)` (`inspect.signature` → `(baseMVA, bus, branch)`); `pandapower.pypower.makeBdc.makeBdc(bus, branch, return_csr=True)` likewise. No
`runpp` / `net._ppc['internal']` fallback was needed. Details:

- The ppc comes from the S4 parity module's `read_mpc_numpy` (regex + `numpy.loadtxt`, shares no
  code with our importer), loaded by path via `importlib.util` because `--import-mode=importlib`
  gives the tests no package to import from.
- pandapower's `branch_vectors` reads its extended columns (`BR_G` = 23, `BR_R_ASYM` = 21 …;
  `branch_cols` = 26; `bus_cols` = 18), so the 13-column MATPOWER matrices are zero-padded to those
  widths. `BUS_I` is rewritten to `0..nb−1` in row order and `F_BUS`/`T_BUS` to those positions;
  `makeBdc` logs an error otherwise.
- Alignment is `BUS_I → bus-<n> → NetworkArrays.bus_index`, never row order; the comparison is
  `ours[k] == theirs[perm[k]]`.
- Precondition asserted per fixture: every bus and branch in service (true for all five), so the
  oracle's all-bus Ybus and our in-service Ybus have the same dimension.

### 5.2 Per-fixture figures (scratch script over the same oracle construction as the test)

| fixture | nb | nl | max abs Ybus diff | Yf / Yt | Bbus | Bf | Pbusinj | bridges | max abs finite LODF | ptdf ms | lodf ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| case14 | 14 | 20 | 0.00e+00 | 0 / 0 | 0.00e+00 | 0.00e+00 | 0 | 1 | 1.000 | 2.6 | 0.1 |
| case30 | 30 | 41 | 8.88e-16 | 0 / 0 | 0.00e+00 | 0.00e+00 | 0 | 3 | 1.000 | 1.9 | 0.1 |
| case_ieee30 | 30 | 41 | 7.11e-15 | 0 / 0 | 0.00e+00 | 0.00e+00 | 0 | 3 | 1.000 | 1.8 | 0.1 |
| case57 | 57 | 80 | 1.42e-14 | 0 / 0 | 3.55e-15 | 1.78e-15 | 0 | 1 | 1.000 | 1.1 | 0.1 |
| case118 | 118 | 186 | 2.93e-14 | 0 / 0 | 1.42e-14 | 7.11e-15 | 0 | 9 | 1.000 | 5.8 | 0.4 |

Tolerance in the test is 1e-9 (brief); observed diffs are summation-order noise (the branch
vectors match pandapower's bit-for-bit, Ybus differs only in the order duplicates are summed).
`Pbusinj` is identically zero because no fixture has a phase shifter. Bridge counts are from
`bridges()` and are cross-checked in-test against a removal-BFS oracle
(`test_bridges_are_consistent_with_a_removal_bfs`) and against the NaN columns of `lodf()`
(unit and property tiers).

## 6. Design deviations and judgment calls

1. **`[tool.mypy] python_version` pin removed** — the one forbidden-file touch; reasoning and
   proof at the top and in §3. Reversible in one line if the lead prefers `python_version = "3.12"`
   instead (that would also pass, but would type-check the 3.11 leg as 3.12).
2. **Per-generator arrays go beyond the brief's four**: besides `gen_ids, gen_bus, gen_p_pu,
   gen_p_min_pu, gen_p_max_pu` there are `gen_q_pu, gen_q_min_pu, gen_q_max_pu, gen_v_set` — the
   same data M2's Q-limit logic needs per generator, added now so the view is not reshaped a wave
   later. `base_mva` is carried on the view so consumers can scale results back without touching
   the model.
3. **`bus_type` is the declared type.** A PV bus with no in-service generator stays 2 in the view;
   W1's "degrade to PQ" is solver behaviour (M2) and belongs there, not in the data view.
4. **`NetworkArrays.from_network` raises `ValueError` if the in-service slack count ≠ 1.** Cannot
   happen for a validated `Network`, but the view is also reachable from a mutated one; failing
   loudly beats a silent `slack=-1`.
5. **`branch_susceptance` raises `ValueError` on `x == 0` for an in-service branch** (W1 §4.2:
   DC throws), naming the branch ids. The AC path (`ybus`) has no such guard: `1/(r + jx)` with
   both zero would give `inf`/`nan`, which the model does not forbid. Left as-is and noted for the
   model owner; a `BAD_RANGE` on `r == x == 0` would be the right layer.
6. **`p_shift` is the bus vector** (MATPOWER `Pbusinj`); the branch vector is exposed as
   `bbus.pf_shift` without a top-level re-export, keeping `__init__` exactly the nine names the
   brief lists. Sign: `P = Bbus·θ + p_shift`, i.e. a DC solve is `Bbus·θ = P − p_shift`.
7. **PTDF solve**: `splu(B_red)` then one `solve` against the dense `Bfᵀ_red` (Bbus is symmetric, so
   the transpose solve is the same factor); memory `n_bus × n_branch` doubles, never a dense
   inverse. `ptdf(arr, slack=k)` accepts any position and zeroes that column; out-of-range raises.
8. **LODF bridge columns are all-NaN including the diagonal** — "column set to NaN" read literally;
   non-bridge diagonals are exactly −1. `lodf(arr, ptdf_matrix=…)` validates the shape.
9. **`bridges()` is an iterative Tarjan** (no recursion — a 2000-bus radial feeder would exceed
   CPython's default recursion limit) that skips only the arriving *edge id*, so parallel
   branches are correctly never bridges. It returns sorted positions.
10. **The dense test case is 6 buses, not the brief's "5-bus"**: a 5-bus meshed core plus one
    radial leaf, so that `bridges()` / NaN-column logic is exercised on the same case as the
    PTDF/LODF oracle. The LODF oracle rebuilds the network with branch k `in_service=False` and
    re-validates it, then compares `(post − pre)/pre[k]` row-by-row through branch ids.
11. **Hypothesis `derandomize=True`**: CI reproducibility over per-run exploration;
    `max_examples=40` (≤ 50). The strategy bounds `x ∈ [0.01, 1]` so `1 − h_kk` stays far from
    `BRIDGE_TOL` on non-bridges, and includes optional taps (0.9–1.1) but no phase shifters
    (the symmetry property needs shift = 0).
12. **Parity test reads the S4 module by path.** Loading it executes its module-level fixtures'
    definitions but not their bodies; nothing from S4 runs twice.
13. **Line endings**: `git add` printed the usual `LF will be replaced by CRLF` warnings
    (core.autocrlf); the index holds LF, same as S1–S4.

## 7. Progress artifact

`C:\Claude Projects\mambo-power\.bionic\tmp\s5-progress.md` — appended at T+0, T+9, T+19, T+41.
Scratch scripts (figures, mutations) live only in the session scratchpad; nothing was added to
the repo beyond the stat in §4.
