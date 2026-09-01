# M2 S1 report — fixtures: case300 verbatim + provenance/licence; derived case14 roles/island/no-slack-gen

Wave M2 "power-flow", slice S1 (plan row S1; spec W7, AC-4/5/7, design items 2 and 4).
Worktree `C:\Claude Projects\mambo-power-m2`, branch `wave/02-power-flow`, base `6c94459`.
Written 2026-08-20 (local; UTC 2026-08-21 ~03:25). Every claim below carries its command and
output, or is marked `unverified`.

**Commit:** `011698c0ba0fa077f6b0ca962b4bdbcca6a784f3` — not pushed.
**Tests:** 308 passed (269 at base; +39 = 12 new cases + 27 case300 parametrizations).

## 1. case300 retrieval and verification

```
$ curl -sSL -o <scratchpad>/case300.m https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case300.m
$ sha256sum <scratchpad>/case300.m
69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5
$ wc -c <scratchpad>/case300.m
66034
$ git hash-object <scratchpad>/case300.m
004203b8adae83b3f21ce9ceb4a13db9b18f0132
```
All three equal the values in `m2-research.md` §4.1 / plan row S1. Copied to
`fixtures/matpower/case300.m` (`cp`), re-hashed in place (same three values; `file` -> "ASCII
text", LF). After commit, from the index and object store:
```
$ git ls-files -s fixtures/matpower/case300.m
100644 004203b8adae83b3f21ce9ceb4a13db9b18f0132 0	fixtures/matpower/case300.m
$ git cat-file -p HEAD:fixtures/matpower/case300.m | sha256sum
69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5
```
(`.gitattributes` `*.m -text` held: the committed blob is byte-identical to upstream's blob.)

Importer probe (before any test existed):
```
$ uv run python -c "...matpower.load_with_warnings('fixtures/matpower/case300.m')..."
300 69 411 201 29 []          # buses gens branches loads shunts warnings
Counter({'pq': 231, 'pv': 68, 'slack': 1})
True                          # native.loads(native.dumps(net)) == net
```

Licence sentence verified against the upstream file, not transcribed from research:
```
$ curl -sSL -o <scratchpad>/LICENSE https://raw.githubusercontent.com/MATPOWER/matpower/master/LICENSE
$ sha256sum <scratchpad>/LICENSE
5d14c09b3e4f2adf62c0373e6320163697aa4603186f8925c07c6b84201e1750   # = research §4.2
$ head -c 600 <scratchpad>/LICENSE
The code in MATPOWER is distributed under the 3-clause BSD license
below. The MATPOWER case files distributed with MATPOWER are not covered
by the BSD license. In most cases, the data has either been included
with permission or has been converted from data available from a
public source.
```

Research claims re-checked in the file before transcribing them into PROVENANCE.md
(`uv run python` over `tests.parity._mpc_reader.read_mpc_numpy`):
```
branch row 390: [1.96e+02 2.04e+03 1.00e-04 2.00e-02 0.00e+00] tap 1.0 status 1.0
v2 rows all tap 1.0: True 22
slack row: [7.0490e+03 1.0507e+00 0.0000e+00 1.3800e+01]
```
The 9-bus gate list and magnitudes are transcribed from `m2-research.md` §1.3/§4.3 and are
labelled as such in PROVENANCE.md (`unverified` here — not re-measured in this slice).

## 2. Derived fixtures (synthetic, `fixtures/matpower/derived/`)

Generated from case14.m bytes by a script (`<scratchpad>/gen_derived.py`, described in §6)
that replaces exactly one line per edit (assertion: the original line is unique in the file)
and prepends a header block. `diff` of the non-comment lines against case14:

```
== case14_island.m
1c1   function mpc = case14  ->  function mpc = case14_island
47c47 	7	8	0	0.17615	0	0	0	0	0	0	1	-360	360;  ->  ...	0	-360	360;   (BR_STATUS)
== case14_noslackgen.m
1c1   function mpc = case14  ->  function mpc = case14_noslackgen
26c26 	1	232.4	-16.9	10	0	1.06	100	1	332.4 ...  ->  ... 100	0	332.4 ...       (GEN_STATUS)
== case14_roles.m
1c1   function mpc = case14  ->  function mpc = case14_roles
27c27 	2	40	42.4	50	-40	1.045	100	1	140 ...  ->  	2	20	21.2	50	-40	1.045 ...   (PG, QG)
29c29 	6	0	12.2	24	-6	1.07	100	1	100 ...  ->  ... 100	0	100 ...              (GEN_STATUS)
30a31 +	2	20	21.2	50	-40	1.055	100	1	140	0 ... (appended gen row 6)
61a63 +	2	0	0	3	0.25	20	0;                         (appended gencost row 6)
```
`file fixtures/matpower/derived/*.m` -> "ASCII text" (LF) for all three.

Judgment calls:
- **Bus 6, not bus 8, for the unit-out PV bus.** Both are single-generator PV buses; bus 6
  carries load (11.2 MW / 7.5 MVAr) and is meshed (branches 5-6, 6-11, 6-12, 6-13), so
  solving it as PQ is a meaningful AC-4 check. Bus 8 is radial and unloaded, and is already
  the island fixture's subject.
- **Second bus-2 generator appended as row 6, not inserted after row 2.** Keeps `gen-1..5`
  identical to case14's ids; the new unit `gen-6` (VG 1.055) is the *last* in-service gen
  at bus 2, so MATPOWER's last-wins rule picks 1.055 while pandapower's first-row rule picks
  1.045 — exactly the disagreement W3's warning is for. PG 40 -> 20 + 20, QG 42.4 -> 21.2 +
  21.2 so per-bus totals are unchanged. QMAX/QMIN/PMAX/PMIN duplicated verbatim (not
  halved) — documented; no M2 test depends on bus-2 limits.
- **Branch 7-8 for the island.** The only bridge in case14 (bus 8 has no other branch);
  setting it out isolates bus 8 with its in-service generator — an island without the slack.
- **gencost row added for the sixth generator** because the importer requires `n` or `2n`
  gencost rows (`io/matpower.py::_costs`, BAD_ROW otherwise).
- **Derived files stay out of `FIXTURES`** (team-lead instruction; they are not upstream
  bytes). They are covered by `tests/unit/test_fixtures_derived.py`.

## 3. Tests

New files: `tests/unit/test_fixture_case300.py` (3 tests), `tests/unit/test_fixtures_derived.py`
(9 tests: 3 "case14 + documented edits == derived" matrix-equality checks via the independent
numpy reader, 3 header checks, 3 importer-behaviour checks). `tests/_fixtures.py::FIXTURES`
gained `"case300"`, which is the single edit that puts case300 into the raw-column parity
(`test_matpower_vs_pandapower`, 6), Ybus parity (6), fixture agreement (2), native round-trip
(3) and dense re-derivation (10) tiers.

RED (case300.m moved out of the tree for the run, then restored and re-hashed):
```
$ uv run pytest -q -p no:cacheprovider tests/unit/test_fixture_case300.py tests/unit/test_fixtures_derived.py
E       FileNotFoundError: [Errno 2] No such file or directory: '...\\fixtures\\matpower\\derived\\case14_noslackgen.m'
FAILED tests/unit/test_fixture_case300.py::test_bytes_are_the_recorded_upstream_blob
FAILED tests/unit/test_fixture_case300.py::test_importer_reproduces_the_file_counts
FAILED tests/unit/test_fixture_case300.py::test_native_round_trip_is_identity
FAILED tests/unit/test_fixtures_derived.py::test_roles_is_case14_plus_documented_edits
FAILED tests/unit/test_fixtures_derived.py::test_island_is_case14_plus_documented_edits
FAILED tests/unit/test_fixtures_derived.py::test_noslackgen_is_case14_plus_documented_edits
FAILED tests/unit/test_fixtures_derived.py::test_header_names_base_and_purpose[case14_roles]
FAILED tests/unit/test_fixtures_derived.py::test_header_names_base_and_purpose[case14_island]
FAILED tests/unit/test_fixtures_derived.py::test_header_names_base_and_purpose[case14_noslackgen]
FAILED tests/unit/test_fixtures_derived.py::test_roles_loads_with_one_unit_less_pv_bus_and_one_two_gen_bus
FAILED tests/unit/test_fixtures_derived.py::test_island_raises_disconnected_bus_today
FAILED tests/unit/test_fixtures_derived.py::test_noslackgen_loads_with_no_in_service_generator_on_the_slack
12 failed in 3.47s
$ sha256sum fixtures/matpower/case300.m   # after restore
69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5
```

`test_island_raises_disconnected_bus_today` asserts TODAY's behaviour
(`NetworkValidationError`, codes == {"DISCONNECTED_BUS"}, issue names bus-8) and carries the
comment that S2 flips it to the repair/warn path.

GREEN — first full run, whole tree (before S3's files appeared):
```
$ uv run ruff check .            -> All checks passed!            exit=0
$ uv run ruff format --check .   -> 38 files already formatted   exit=0
$ uv run mypy                    -> Success: no issues found in 14 source files   exit=0
$ uv run pytest -q -p no:cacheprovider
308 passed, 9 warnings in 29.87s                                  exit=0
```
The 9 warnings are the pre-existing pandapower `from_ppc` RuntimeWarnings on case14/case57
and the pandas FutureWarning on case30 — none involves case300.

Collection accounting:
```
$ uv run pytest --co -q | grep -c case300      -> 30 (27 parametrizations + 3 in test_fixture_case300)
      6 tests/parity/test_matpower_vs_pandapower.py
      6 tests/parity/test_ybus_vs_pandapower.py
      2 tests/unit/test_fixture_agreement.py
      3 tests/unit/test_fixture_case300.py
      9 tests/unit/test_fixtures_derived.py
      3 tests/unit/test_native_roundtrip_fixtures.py
     10 tests/unit/test_numerics_dense.py
```

GREEN — final run at commit time. Between the first gate and the commit, S3 (same worktree)
added untracked `tests/unit/test_results_models.py` (ruff I001 import-order error) and
`tests/unit/test_pf_dc.py` (ImportError at collection: `mambo_power.pf` not yet present), and
later `tests/parity/test_dc_vs_pandapower.py`. Those are S3's paths and were not touched; the
gate was re-run with them excluded:
```
$ uv run ruff check . --exclude tests/unit/test_results_models.py --exclude src/mambo_power/pf \
    --exclude src/mambo_power/results --exclude tests/unit/test_pf_dc.py --exclude tests/parity/test_dc_vs_pandapower.py
All checks passed!                                   exit=0
$ uv run ruff format --check . (same excludes)  -> 39 files already formatted   exit=0
$ uv run mypy                                   -> Success: no issues found in 14 source files   exit=0
$ uv run pytest -q -p no:cacheprovider --ignore=tests/unit/test_results_models.py --ignore=tests/unit/test_pf_dc.py
308 passed, 9 warnings in 28.30s                     exit=0
```
An unscoped `uv run ruff check .` on the shared worktree currently fails on S3's
`test_results_models.py` (I001) — S3's to fix, reported here so the lead knows the shared
tree is not gate-clean as a whole at this moment.

## 4. Commit

```
$ git add fixtures/matpower/case300.m fixtures/matpower/PROVENANCE.md fixtures/matpower/SOURCES.md \
    fixtures/matpower/derived/case14_roles.m fixtures/matpower/derived/case14_island.m \
    fixtures/matpower/derived/case14_noslackgen.m fixtures/matpower/derived/PROVENANCE.md \
    tests/_fixtures.py tests/unit/test_fixture_case300.py tests/unit/test_fixtures_derived.py
$ git commit -q -F -    (message + the two trailers exactly as specified)
commit-exit=0
$ git show --stat HEAD
commit 011698c0ba0fa077f6b0ca962b4bdbcca6a784f3
Author: Manho Joung <manhojoung@gmail.com>
Date:   Thu Aug 20 20:24:21 2026 -0700

    feat(m2/S1): fixtures — case300 verbatim with provenance + licence caveat; derived case14 roles/island/no-slack-gen fixtures

    Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01NA3xnvrFVGDqG3azRk8CBs

 fixtures/matpower/PROVENANCE.md               |   71 +-
 fixtures/matpower/SOURCES.md                  |   20 +-
 fixtures/matpower/case300.m                   | 1322 +++++++++++++++++++++++++
 fixtures/matpower/derived/PROVENANCE.md       |   66 ++
 fixtures/matpower/derived/case14_island.m     |  145 +++
 fixtures/matpower/derived/case14_noslackgen.m |  142 +++
 fixtures/matpower/derived/case14_roles.m      |  149 +++
 tests/_fixtures.py                            |    2 +-
 tests/unit/test_fixture_case300.py            |   42 +
 tests/unit/test_fixtures_derived.py           |  116 +++
 10 files changed, 2068 insertions(+), 7 deletions(-)
$ git status --short   (after commit)
?? tests/parity/test_dc_vs_pandapower.py      # S3
?? tests/unit/test_pf_dc.py                   # S3
?? tests/unit/test_results_models.py          # S3
```
No hook blocked the commit. Not pushed. `git diff` shows core.autocrlf warnings ("LF will be
replaced by CRLF in the working copy") for the .md/.py files — the index holds LF, same as
the rest of the repo; `*.m` are exempt via `.gitattributes`.

## 5. Provenance text (what PROVENANCE.md / SOURCES.md now say)

- New "Licence (applies to every file in this directory)" section quoting the LICENSE
  sentence, LICENSE sha256, and stating: public IEEE test data carried as distributed by
  MATPOWER; no BSD claim.
- New `### case300.m` section in the existing Source / Upstream lineage / Reference solution /
  Known reference-quality findings layout: URL, retrieval date, blob SHA-1, sha256, bytes,
  LF; the v2 2025-06-14 tap edit quoted verbatim (22 branches); counts; slack 7049; the
  negative-reactance branch; the stored columns NOT a solution of the shipped data (0.107 pu
  at bus 17) and the v2 taps not the cause; qlim-on non-convergence; the 9 gated buses with
  magnitudes and the branch 196-2040 (row 390) explanation; an explicit "no later wave may
  treat the stored columns as a converged solution" sentence.
- SOURCES.md: retrieval table row for case300 (URL / blob / sha256 / bytes / date), the
  licence sentence, the case300 exception to "stored columns are the reference", and a
  pointer to `derived/`.
- `derived/PROVENANCE.md`: derivation rule, "synthetic, not upstream, no reference
  solution", per-file edited cells with the reasons above, behaviour today vs after S2.

## 6. Generator script (for regeneration; the test is the contract)

`<scratchpad>/gen_derived.py` — reads case14.m bytes, asserts LF-only, replaces each listed
line by exact match (asserting uniqueness), appends the roles rows by position after
`mpc.gencost = [` (+5/+6, asserted), prepends the header block, writes ASCII/LF. Not committed
(a one-shot; `tests/unit/test_fixtures_derived.py` enforces the result independently).

## 7. Open items for the lead

- S3's in-flight files make the unscoped `ruff check .` fail on the shared worktree (I001 in
  `tests/unit/test_results_models.py`) and `pytest` error at collection on
  `tests/unit/test_pf_dc.py` until `mambo_power.pf` exists. Not S1's files; not touched.
- Plan row S1 says "pandapower parity on the new files" for the derived fixtures; the
  dispatch said to keep them out of the parity list. Followed the dispatch. If parity on the
  derived files is wanted, S2 is the natural place (it owns the roles/island semantics the
  oracle comparison depends on).
