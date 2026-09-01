# M5 critic — Step 6, adversarial

Worktree `C:\Claude Projects\mambo-power-m5`, branch `wave/05-multiperiod`, base `0ea463f`.
Commit produced: **`def67f1`** (`tests/_storage.py`, `tests/parity/test_market_multiperiod_vs_pypsa.py`).
Suite **816 passed** (was 815). `ruff`, `ruff format --check`, `mypy` clean.

Every claim below carries the command that proves it. Nothing is labelled `unverified`.

---

## Verdict

**A20 is REFUTED. The weakness does not exist and never did.** The AC-6 fixture, exactly as S6
committed it, already catches an oracle-tier efficiency transposition — at 5.088e-2 MWh against a
1e-2 MWh tolerance. It was disclosed three times and confirmed once because two different probes
were run, and neither of them was the sabotage the property needs.

No fixture change was required. I recommend against making one; the measurement behind that
recommendation is in §4.

---

## 1. The proof: the sabotage nobody ran

The defect class AC-6 exists to catch is an **engine** that wires the two efficiencies into the
SoC row the wrong way round. That sabotage lives in `src/mambo_power/opf/multiperiod.py`, tier 3:

```python
                    (int(charge_cols[t][s]), -float(eta_charge[s])),
                    (int(discharge_cols[t][s]), 1.0 / float(eta_discharge[s])),
```

Transposed in a detached scratch worktree, loaded by `PYTHONPATH`, against the **unmodified**
committed parity file:

```
$ git worktree add --detach <scratch>/sab1 HEAD
$ sha256sum <scratch>/sab1/src/mambo_power/opf/multiperiod.py
a6805eebff3f32e5095848c551aafde22e396d1ca1c144e95ffe8ef4f5a41c22
   ... eta_charge <-> eta_discharge in the tier-3 SoC row ...
$ PYTHONPATH=<scratch>/sab1/src uv run --no-sync python -c \
      "import mambo_power.opf.multiperiod as m; print('LOADED FROM:', m.__file__)"
LOADED FROM: ...\scratchpad\sab1\src\mambo_power\opf\multiperiod.py

$ PYTHONPATH=<scratch>/sab1/src uv run --no-sync pytest -q \
      tests/parity/test_market_multiperiod_vs_pypsa.py
FAILED tests/parity/test_market_multiperiod_vs_pypsa.py::test_soc_matches_pypsa_every_period
E   AssertionError: (13, 0.05087921605550605, 78.82244957605305, 78.87332879210855)
E   assert 0.05087921605550605 <= 0.01
1 failed, 9 passed in 60.41s
```

**5.088e-2 MWh against `SOC_ABS_TOL_MWH` = 1e-2** — 5.1x over tolerance and 407x over the
1.25e-4 MWh baseline noise. Restored afterwards; sha256 back to `a6805eeb...`, `git status
--porcelain` empty in both trees, worktree removed.

---

## 2. Why three rounds of disclosure got it wrong

Two different flawed probes, each wrong in a different way.

### 2.1 S6's sweep never measured the residual that moves

`record/m5-s6-report.md` §4.5 reports `worst_gen` and `worst_storage` and nothing else. Its
numbers are correct — I reproduced them exactly, driving the test module's own
`_fixture_network()` / `_profile()` and perturbing only the network fed to `mambo_power`:

```
[BASELINE 0.92/0.88] obj_rel=4.349e-13 gen=3.008288e-04 stnet=1.099842e-04 soc=1.249821e-04 lmp=4.244264e-05
[SABOTAGE transposed] obj_rel=4.312e-13 gen=3.136775e-04 stnet=1.242729e-04 soc=5.087922e-02 lmp=4.405316e-05
RED under sabotage? {'rel': False, 'gen': False, 'st': False, 'soc': True, 'lmp': False}
```

S6's `0.000314` and `0.000124` are the `gen` and `stnet` columns above. The `soc` column —
5.087922e-02, the only one that moves — was never in the table.

**The mechanism, which is why exactly one of five comparisons can see it.** `eta_c * eta_d` is
symmetric under transposition. A transposed engine therefore converts grid-in to grid-out at
exactly the same ratio, and with no SoC bound and no energy cap binding on this fixture it picks
the *same* charge/discharge schedule. Objective, generator dispatch, net storage power and LMPs
all agree, necessarily. What diverges is the internal SoC trajectory, by

```
soc_transposed[t] - soc_true[t] = sum_{tau<=t} [ (eta_d - eta_c)*charge[tau]
                                                 - (1/eta_c - 1/eta_d)*discharge[tau] ]
```

Evaluated on the fixture's own solved schedule this predicts **5.10e-2 MWh** against the
**5.088e-2 MWh** actually observed under the engine sabotage — agreement to 0.3%.

### 2.2 The audit's sabotage was a no-op by construction

`record/m5-audit.md` transposed the **constants** in `tests/_storage.py` and reported `9 passed`
"against the **unmodified** oracle". The oracle was not unmodified.
`storage_for_network`'s returned unit is handed to *both* engines —
`_run_pypsa_oracle` sets `efficiency_store=unit.efficiency_charge` and
`efficiency_dispatch=unit.efficiency_discharge`. Measured directly:

```
[PRISTINE 0.92/0.88]
  mambo Storage : efficiency_charge=0.92  efficiency_discharge=0.88
  PyPSA oracle  : efficiency_store=0.92   efficiency_dispatch=0.88
[AUDIT SABOTAGE (constants transposed)]
  mambo Storage : efficiency_charge=0.88  efficiency_discharge=0.92
  PyPSA oracle  : efficiency_store=0.88   efficiency_dispatch=0.92
```

A consistent relabel of both sides of a parity comparison is undetectable by construction, for
*any* fixture however strong, and there is nothing there to detect: 0.88/0.92 is simply a
different, equally valid synthetic unit. A parity test cannot validate its own input data. A20 as
written — "the fixture cannot distinguish which efficiency is which" — asks for something no
parity test can do, and is not a statement about AC-6's power.

---

## 3. What was committed (`def67f1`)

### `test_the_fixture_can_tell_which_efficiency_is_which`

A fixture-power precondition in the shape
`test_congestion_binds_in_some_periods_and_not_others` already uses. It reconstructs the SoC
trajectory under both orientations from the fixture's own solved schedule, first proving the
closed form *is* the engine's own SoC (`<= 1e-9` against the reported values), then asserting the
signal clears `TRANSPOSITION_SIGNAL_MIN_MWH = 3e-2` — a floor under the measured 5.10e-2 and
itself 3x `SOC_ABS_TOL_MWH`.

**It is strictly stronger than `test_ramp_and_storage_are_both_genuinely_engaged`.** Both real
test functions driven against Cases built by the module's own factories:

```
eta 0.92/0.88 charge_tot=  1.2755 | engaged: PASS | orientation: PASS
eta 0.9 /0.9  charge_tot=  1.3698 | engaged: PASS | orientation: FAIL equal efficiencies make the
                                                     transposition a no-op by construction
eta 0.7 /0.66 charge_tot=  0.0000 | engaged: FAIL | orientation: FAIL
eta 0.6 /0.56 charge_tot=  0.0000 | engaged: FAIL | orientation: FAIL
```

The 0.90/0.90 row is the point: storage moves 1.37 MWh, the existing "genuinely engaged" test is
green, and orientation power is exactly zero. That is A10's own trap, and it was unguarded.

Under the §1 engine sabotage both tests go red: `2 failed, 9 passed in 11.31s`.

### `SOC_ABS_TOL_MWH` and `tests/_storage.py` docstrings

`SOC_ABS_TOL_MWH` is now named as the tolerance that carries the efficiency-orientation proof, so
a future reader loosening it can see what it costs. `tests/_storage.py` records both traps from §2
— that a sweep reporting only dispatch residuals will see nothing, and that transposing that
module's own constants is not a sabotage.

### A latent bridge defect, found via C3

`_run_pypsa_oracle` added gencost `c0` **once**, not `len(periods)` times, against this
repository's own convention that `c0` is a cost per hour charged in every period. Verified
directly, no oracle needed — a one-generator network with `coefficients=[10.0, 7.0]`:

```
T= 1 objective_cost=  507.0000  energy=  500.0  => c0 counted 1.0000 times
T= 2 objective_cost= 1014.0000  energy= 1000.0  => c0 counted 2.0000 times
T= 5 objective_cost= 2535.0000  energy= 2500.0  => c0 counted 5.0000 times
T=24 objective_cost=12168.0000  energy=12000.0  => c0 counted 24.0000 times
```

Now `len(periods) * c0_sum`. Inert today — measured, every gencost file in `fixtures/` carries
`c0 == 0.0` exactly on all five OPF cases — but wrong for any future `c0`-bearing fixture, and the
comment says so.

---

## 4. Why the efficiencies were NOT raised to 0.97/0.93

The brief's proposed fix was measured, through the test's own factories, before being declined.
`bind`/`slack` are the committed congestion precondition's own counts; `signal` is §2.1's closed
form:

```
eta 0.92/0.88 (rt .8096): ch=  1.275  obj=4.35e-13 gen=3.01e-4 stnet=1.10e-4 soc=1.25e-4 lmp=4.24e-05  signal=  0.051 (  5.1x)  bind=10 slack=14
eta 0.97/0.93 (rt .9021): ch= 54.241  obj=4.04e-13 gen=2.34e-4 stnet=4.38e-5 soc=5.79e-5 lmp=1.15e+00  signal=  2.170 (217.0x)  bind=19 slack= 5
eta 0.95/0.91 (rt .8645): ch= 43.889  obj=5.44e-13 gen=2.55e-4 stnet=1.44e-4 soc=1.76e-4 lmp=3.74e-05  signal=  1.756 (175.6x)  bind=16 slack= 8
eta 0.99/0.95 (rt .9405): ch= 61.187  obj=3.82e-13 gen=2.27e-4 stnet=2.32e-5 soc=2.44e-5 lmp=9.76e-01  signal=  2.447 (244.7x)  bind=21 slack= 3
eta 0.96/0.88 (rt .8448): ch= 33.666  obj=6.19e-13 gen=2.74e-4 stnet=1.26e-4 soc=3.06e-4 lmp=3.90e-05  signal=  2.693 (269.3x)  bind=13 slack=10
eta 0.98/0.90 (rt .8820): ch= 47.974  obj=3.71e-13 gen=2.26e-4 stnet=2.31e-5 soc=2.57e-5 lmp=3.30e-05  signal=  3.838 (383.8x)  bind=18 slack= 6
```

**The brief's own suggested value breaks AC-6.** At 0.97/0.93 the LMP residual is **1.146 $/MWh**
against a 1e-3 tolerance — over a thousand times out. 0.99/0.95 is the same at 0.976. The fixture's
*dual* agreement sits on a knife-edge with respect to storage activity, and raising the round trip
moves it towards that cliff.

0.96/0.88 and 0.98/0.90 happen to be quiet today and would give a 269x / 384x signal. I still
decline: trading a proven-quiet configuration for one adjacent to a demonstrated dual-degeneracy
region, in order to strengthen a property that is **already proven at 5.1x over tolerance and
407x over noise**, is the wrong trade. If M6 wants a more active unit for its own reasons,
0.98/0.90 is the measured candidate and this table is the starting point.

One honest caveat about the 5.1x margin. It exists because the round trip 0.8096 clears this
horizon's own trough/peak ratio (32.87/41.20 = 0.7978) by 1.5%, so the unit arbitrages a little
rather than not at all. If a solver upgrade moved that, throughput would collapse — and
`test_the_fixture_can_tell_which_efficiency_is_which` is precisely the guard that would say so,
with a number, rather than the fixture going quietly powerless.

---

## 5. Secondary targets

### A18 — sound, and under-claimed

S6's replacement claim does not have the same shape of weakness. It is not one branch crossing a
threshold:

```
 t  total_load  max_util  argmax     #>=0.999
13     262.81    1.0000   branch-14      1
14     278.43    1.0000   branch-18      2
17     308.59    1.0000   branch-18      3
18     310.80    1.0000   branch-11      4
23     262.81    0.8550   branch-1       0

distinct branches that ever bind: branch-11, branch-14, branch-15, branch-16, branch-18
```

Five distinct branches bind across the horizon, the per-hour binding count moves 1 -> 4, and the
identity of the most-loaded branch changes. A18 also *understates* its own case: t=13 and t=23
carry the **same** 262.81 MW total load at max utilisation 1.0000 and 0.8550 respectively. The
profile is symmetric; the fixture is not, because ramp and storage couple the periods. That is a
stronger argument than "flow magnitudes scale with demand", which alone would predict identical
utilisation at identical load.

### A31's disclosed deviation — REFUTED

`m5-fold-a` claims one fixture with two heterogeneous storage units *and* two heterogeneous ramp
limits is infeasible: *"a ramp-down floor forces net absorption in the last period, which the
cyclic row forbids."* It is true only of the profiles it tried.

Fold-a's own two ramped generators and its own two storage units, in one network, on fold-a's own
load profile `[0, 100, 200, 20]`, driving `tests/unit/test_opf_multiperiod.py`'s own `_gen`,
`_linear_costs` and `_ramp_arrays` helpers:

```
=== soc0=0.0 load=[0.0, 100.0, 200.0, 20.0] -> Optimal
  gA: ramp_up binds at [1]   ramp_down binds at [3]
  gB: ramp_up binds at [1]   ramp_down binds at [3]
  st_small: shared power row at its 10 MW rating in periods [0, 3]
  st_big:   shared power row at its 30 MW rating in periods [0, 2]
```

All four heterogeneous limits bind in one fixture, and it solves Optimal, not Infeasible.

**Fold-a's stated mechanism is also wrong.** It reasons that "charge/discharge overlap absorbs
nothing net". Overlap absorbs nothing net *in SoC* — at `eta_c = eta_d = 0.8`, charging 6.0976 and
discharging 3.9024 in the same period is exactly SoC-neutral (`0.8*6.0976 == 3.9024/0.8`) — but it
absorbs **2.195 MW net from the grid**. The round-trip loss *is* the net absorption, and it is the
escape route the cyclic row leaves open. That is what makes the terminal ramp-down floor
satisfiable at `soc_initial = 0`.

Honest caveat: the solutions found lean on 1.5-3.9 MW of that overlap, so a *clean*
hand-derivable, overlap-free combined fixture still needs design work and I did not produce one.
Feasibility — the claim actually made — is refuted. Not fixed here: `tests/unit/**` is
`m5-fold-a`'s, not mine.

### C3 — cheap to verify, 12 lines, no oracle

Verified above (§3). The `c0`-per-period convention holds exactly at T in {1, 2, 5, 24}. It wants
one unit test in `tests/unit/test_market_multiperiod.py`; I left it uncommitted because that file
is not in my ownership. The oracle half of C3 — that the bridge could not see a `(T-1)*sum(c0)`
discrepancy — was a real latent defect and is now fixed.

### C2 — the judgment is right, with one caveat

There is no `fastapi`, `starlette` or `uvicorn` anywhere in `src/` (grep, zero hits). The jobs
surface is in-process. "Nothing is network-facing yet" is factually correct and carrying it is the
right call.

The caveat worth carrying with it: `SolveRequest` is a Pydantic model whose entire purpose is to
be deserialised from JSON, and 34 KB -> ~240 MB is a decompression-bomb ratio. The bound belongs
on `Scenario.periods` as a `max_length`, in the model, **before the model is treated as stable** —
added after an HTTP layer exists it is a breaking change to a published schema rather than a
free tightening. That argues for M6, not "whenever the service appears".

---

## 6. Method notes

- Every fixture measurement drove the test module's own `_fixture_network()` / `_profile()` /
  `_run_pypsa_oracle()`, or `tests/unit/test_opf_multiperiod.py`'s own `_gen` / `_linear_costs` /
  `_ramp_arrays`. Nothing was reconstructed by hand.
- One near-miss worth recording, since it is A32's own lesson: my first `c0` probe built
  `PolynomialCost(gen=..., c2=..., c1=..., c0=...)` and got five pydantic errors — four
  `extra_forbidden` and one missing `coefficients`. Reading those as "the model rejects `c0`"
  would have been exactly the misread A32 warns about. The real field is
  `coefficients: list[float]`, highest order first, hung off `Generator.cost`.
- Sabotage discipline: detached worktree, `PYTHONPATH`, `__file__` printed to prove which copy
  loaded, restored and sha256-checked, worktree removed, `git status --porcelain` empty in the
  live tree throughout.

## 7. Record corrections this artifact makes

| Where | Says | Actually |
|---|---|---|
| plan A20 | the transposition is a no-op at AC-6's oracle tier | it is caught, 5.088e-2 MWh vs 1e-2 tol |
| plan A32 | the mechanism is "efficiencies multiply a nearly-zero quantity" | the mechanism is that `eta_c*eta_d` is symmetric — throughput sets the *size* of the signal but the signal exists and clears tolerance |
| `m5-audit.md` §"A20 attacked directly" | `9 passed` "against the **unmodified** oracle" | the oracle received the transposed values too; a no-op by construction |
| `m5-s6-report.md` §4.5, §7 | "not caught by this fixture's own sabotage sensitivity" | the sweep did not measure SoC |
| `m5-fold-a-report.md` §5 | one combined hetero fixture is infeasible; "overlap absorbs nothing net" | Optimal with all four limits binding; overlap absorbs the round-trip loss net from the grid |
| `m5-review.md` C3 | "documented, defensible, unverified" | verified in 12 lines; its oracle half was a real defect, now fixed |
