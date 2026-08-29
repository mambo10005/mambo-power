# M2 research — stored-solution precision, pandapower/MATPOWER PF conventions, case300, docs tooling

Wave M2 "power-flow" of the mambo-power epic, Step 1/2 research. Read-only; written 2026-08-20 against
repo `C:\Claude Projects\mambo-power` @ `6c94459` (branch `epic/01-foundation`), pandapower 3.3.0 and
PyPSA 1.2.4 from `.venv` (Python 3.12.14). `git status --porcelain` was clean after every probe.

Evidence conventions: `probe:` = a command run here, output quoted; `src:` = a file:line under the
installed package (`PP = .venv/Lib/site-packages/pandapower`) or under the MATPOWER files fetched to the
scratchpad (`MP = <scratchpad>/mp/`, curl'd 2026-08-20 from
`https://raw.githubusercontent.com/MATPOWER/matpower/master/…`, **not** into the repo); `unverified` =
stated from memory / secondary source only. Probe scripts: `<scratchpad>/probe1.py` (flat-start runpp vs
stored columns), `gate.py` (dense stored-state mismatch), `probe2.py` + inline snippets (conventions).

Headline for the wave (the rest is evidence):

- Stored VM/VA carry **3 / 2 decimals** in the four CDF fixtures, **0 / 0** in case30 (flat: VM=1, VA=0 on
  all 30 rows), **4 / 2** in case300. None of the stored states is a converged solution of the shipped
  data at the 1e-8 level; the four CDF fixtures are solutions of *nearly* the shipped data (median
  stored-state mismatch 0.2–0.6 MVA per bus) with a few defective buses — exactly W1's exclusion list.
- pandapower's Q-limit enforcement is MATPOWER's: PV→PQ pins accumulate, **never restored to PV**, slack
  generators never limited; multi-generator setpoints must agree (else `UserWarning`), first row wins in
  the converter; a PV bus whose gens are all out of service is PQ.
- case300 comes from `MATPOWER/matpower` `data/case300.m` (git blob `004203b8…`, sha256 `69a90280…`),
  **but MATPOWER's LICENSE explicitly says the case files are not under its BSD licence** — PROVENANCE.md
  has to say that. pandapower ships a PYPOWER-derived `case300()` (not byte-derived from the v2 file).
  Its stored columns fail the W1 gate at 9 buses (cap 15), dominated by a 927 MVA defect on branch
  196–2040, and **pandapower cannot converge case300 with Q-limits enforced** (100 NR iterations, any
  init) — M2 must not promise Q-limited column parity for case300.
- Docs tooling resolves cleanly for Python 3.12 via `uv pip install --dry-run`: mkdocs-material 9.7.7,
  mkdocstrings 1.0.6 + mkdocstrings-python 2.0.7, mkdocs-jupyter 0.26.3, nbmake 1.5.5,
  pymdown-extensions 11.0.1.

---

## 1. Stored-solution precision per fixture

### 1.1 Decimals carried by the stored `VM` / `VA` columns

probe: awk over the `mpc.bus` rows of each fixture (column 8 = VM, 9 = VA; counts characters after the
decimal point; "VM!=1 / VA!=0" counts rows that are not flat).

```
case14      rows=14  maxVMdec=3 maxVAdec=2 VM!=1:14  VA!=0:13
case30      rows=30  maxVMdec=0 maxVAdec=0 VM!=1:0   VA!=0:0
case_ieee30 rows=30  maxVMdec=3 maxVAdec=2 VM!=1:29  VA!=0:29
case57      rows=57  maxVMdec=3 maxVAdec=2 VM!=1:57  VA!=0:56
case118     rows=118 maxVMdec=3 maxVAdec=2 VM!=1:117 VA!=0:118
case300     rows=300 maxVMdec=4 maxVAdec=2   (MP/case300.m, see §4)
```

| Fixture | VM decimals | VA decimals | Stored state | Slack VA stored |
| --- | --- | --- | --- | --- |
| case14 | 3 | 2 | solved (CDF-era) | 0 |
| case30 | 0 | 0 | **flat — VM = 1, VA = 0 on every row** | 0 |
| case_ieee30 | 3 | 2 | solved | 0 |
| case57 | 3 | 2 | solved | 0 |
| case118 | 3 | 2 | solved | **30°** (bus 69) |
| case300 | 4 | 2 | solved (CDF-era, 1991) | 0 (bus 7049) |

A 3-decimal VM column cannot represent a solution closer than ±5e-4 pu; a 2-decimal VA column than
±5e-3°. That is the floor under any column-parity band, independent of solver quality.

### 1.2 Is the stored state a converged solution? (pandapower flat start, `enforce_q_lims=False`)

probe: `probe1.py` — `tests.parity._mpc_reader.read_mpc_numpy` → the repo's
`tests/parity/test_matpower_vs_pandapower.py::pandapower_from_raw` (pandapower's own `from_ppc` half of
`from_mpc`) → `pp.runpp(net, init="flat", enforce_q_lims=q, tolerance_mva=1e-8, max_iteration=50,
calculate_voltage_angles=True)`. `BASE_KV = 0` rows (all of case14 and case57) were replaced by 1.0 before
conversion, as W1's importer does (`DEFAULT_BASE_KV = 1`); pu data are unchanged by this. Angles are
compared slack-relative (W1 convention). Pandapower's `.m` reader is **not** usable here: `from_mpc` on a
`.m` path raises `NotImplementedError: matpowercaseframes is used to convert .m file` (probe, §4.3), so
the repo's reader is the only in-tree path.

```
case14       qlim=False conv=True it=4 maxdVM=0.0013@4   maxdVA_rel=0.017@4    nVM>2e-3=0  nVA>0.5=0
case14       qlim=True  conv=True it=4 (identical — no limit binds)
case30       qlim=False conv=True it=3 maxdVM=0.0394@8   maxdVA_rel=3.958@19   nVM>2e-3=24 nVA>0.5=28  flat_ref=True
case_ieee30  qlim=False conv=True it=4 maxdVM=0.0020@2   maxdVA_rel=0.431@3    nVM>2e-3=0  nVA>0.5=0
case_ieee30  qlim=True  conv=True it=2 maxdVM=0.0006@16  maxdVA_rel=0.428@3    nVM>2e-3=0  nVA>0.5=0
case57       qlim=False conv=True it=4 maxdVM=0.0098@46  maxdVA_rel=0.774@46   nVM>2e-3=1  nVA>0.5=1
case57       qlim=True  conv=True it=4 (identical)
case118      qlim=False conv=True it=4 maxdVM=0.0173@30  maxdVA_rel=0.303@1    nVM>2e-3=3  nVA>0.5=0
case118      qlim=True  conv=True it=3 maxdVM=0.0175@30  maxdVA_rel=0.312@1    nVM>2e-3=1  nVA>0.5=0
case300      qlim=False conv=True it=5 maxdVM=0.1071@17  maxdVA_rel=11.342@2040 nVM>2e-3=110 nVA>0.5=272
case300      qlim=True  LoadflowNotConverged after 50 iterations
```

| Fixture | max \|ΔVM\| pu (bus) | max \|ΔVA\| slack-rel ° (bus) | After dropping W1's excluded buses | Verdict |
| --- | --- | --- | --- | --- |
| case14 | 0.0013 (4) | 0.017 (4) | — (none excluded) | within W1 bands (2e-3 / 0.5) |
| case30 | 0.0394 (8) | 3.958 (19) | n/a | stored state is a flat start, not a solution |
| case_ieee30 | 0.0020 (2) | 0.431 (3) | 0.0020 / 0.341 | within bands (VM at the edge at bus 2, qlim off; 0.0006 with qlim on) |
| case57 | 0.0098 (46) | 0.774 (46) | **0.0009 / 0.052** | within bands only after excluding 46 |
| case118 | 0.0173 (30) | 0.303 (1) | **0.0090 (103) / 0.303** | VM at bus 103 (0.009) and 92 (0.003) exceed 2e-3 with qlim **off**; with qlim **on** the residual is 0.0010 / 0.312 — within bands |
| case300 | 0.1071 (17) | 11.34 (2040) | (W1 has no list) | not a solution of the v2 file; see §1.4 |

So: **no fixture's stored state is a 1e-8-converged solution of the shipped data** (the best, case14,
differs by 1.3e-3 pu — CDF-era convergence slop plus 3-decimal rounding); four of them are solutions of
*almost* the shipped data; case30 is flat.

### 1.3 Engine-independent cross-check: stored-state mismatch (W1's gate, recomputed densely)

probe: `gate.py` — dense Y-bus with the MATPOWER branch model (tap on from side, `b/2` per end, shunts
`(GS+jBS)/baseMVA`), `S_calc = V·conj(Y V)` at the stored V; `S_spec` = in-service gen PG/QG − PD/QD;
W1 rule: P at non-slack buses, Q additionally at PQ buses; report buses > 5 MVA; cap = ceil(5 % · n).

```
case14       maxP=  0.35 MVA maxQ(PQ)=  4.22 median_worst=0.199 buses>5MVA=0/14  cap=1
case30       maxP= 39.27 MVA maxQ(PQ)= 29.00 median_worst=7.600 buses>5MVA=17/30 cap=2  -> 2,4,7,8,10,12,13,14,15,17,19,21,...
case_ieee30  maxP=  8.21 MVA maxQ(PQ)=  3.29 median_worst=0.338 buses>5MVA=1/30  cap=2  -> 3(8.2)
case57       maxP= 45.79 MVA maxQ(PQ)= 19.76 median_worst=0.358 buses>5MVA=3/57  cap=3  -> 14(21.2) 46(45.8) 47(24.7)
case118      maxP=  7.20 MVA maxQ(PQ)=129.68 median_worst=0.636 buses>5MVA=4/118 cap=6  -> 17(45.3) 30(129.7) 38(31.3) 68(10.5)
case300      maxP=926.92 MVA maxQ(PQ)= 80.75 median_worst=0.264 buses>5MVA=9/300 cap=15 -> 137(7.7) 181(7.3) 196(926.1) 231(11.2) 235(7.2) 237(9.9) 238(8.5) 2040(926.9) 9001(5.0)
```

This reproduces W1's measured exclusions **exactly** (W1 §3.1 / PROVENANCE.md: case_ieee30 bus 3 = 8.2;
case57 14/46/47 = 21.2/45.8/24.7; case118 17/30/38/68 = 45.3/129.7/31.3/10.5; case14 none), from an
independent implementation — so the gate numbers in `m1-w1-extract.md` are confirmed, not inherited.

### 1.4 Are W1's exclusions explained by what was measured?

| W1 exclusion | What the probes show | Explained? |
| --- | --- | --- |
| case30 excluded from column parity entirely ("flat") | all 30 rows VM=1/VA=0 (§1.1); gate fails at 17/30 buses, cap 2 (§1.3); pandapower's solution is 0.039 pu / 4° away (§1.2) | **Yes** — there is no reference to compare to; self-consistency-only is the right verdict. |
| case_ieee30 bus 3 (8.2 MVA) | gate 8.21 MVA at bus 3 (§1.3); the VA error vs pandapower peaks at bus 3 (0.431°) and its neighbours 4/16/12/13 (0.30–0.34°) — still inside 0.5° but the only buses anywhere near it | **Yes**, and the neighbourhood effect is visible. |
| case57 buses 14, 46, 47 (tap 14-46 auto-adjusted in the published solution) | gate 21.2/45.8/24.7 at exactly those; pandapower differs 0.0098 pu / 0.77° at bus 46 and **< 0.001 pu / 0.06° everywhere else** (§1.2) | **Yes** — one local defect; the remaining 54 buses agree to the data precision. |
| case118 buses 17, 30, 38, 68 (bus 30 "phantom 129.7 MVAr") | gate 45.3/129.7/31.3/10.5 at those; pandapower differs 0.0173 pu at bus 30; after exclusion the residual is 0.0090 at bus 103 with qlim off but **0.0010 with qlim on** | **Yes for the listed buses; and the data show why W1 ratified qlim-ON parity** (W1-R5 option C): with limits off, buses 103/92/34/102 (0.009/0.003/0.002/0.0019) would breach the 2e-3 band — the stored point was produced with limits enforced. |
| W1 bands VM 2e-3 / VA 0.5° "set by reference precision" | 3-dec VM ⇒ ±5e-4 rounding; measured best-case agreement 1.3e-3 (case14), 0.9e-3 (case57 after exclusion), 1.0e-3 (case118, qlim on); VA 0.43° at case_ieee30 bus 3 region | **Consistent**: the bands sit 2–4× above the measured agreement of good buses; tightening below ~1.5e-3 / 0.45° would fail case14 / case_ieee30 on data, not solver, grounds. |

**Note** (interpretation, not W1's text): case118 with qlim **off** breaches the VM band at bus 103
even after W1's exclusions; M2's parity runner must keep Q-limit enforcement on for case118 (as W1 does)
or the gate list is insufficient.

---

## 2. pandapower power-flow conventions (3.3.0, `PP = .venv/Lib/site-packages/pandapower`)

| Topic | Behaviour | Evidence |
| --- | --- | --- |
| `runpp` signature defaults | `algorithm='nr'`, `calculate_voltage_angles=True`, `init="auto"`, `max_iteration="auto"`, `tolerance_mva=1e-8`, `enforce_q_lims=False`, `check_connectivity=True` | src: `PP/run.py:68-72` |
| `init="auto"` | angles: `"dc"` when `calculate_voltage_angles` (and no FACTS) else `"flat"`; magnitudes: **mean of all in-service ext_grid + gen (+ VSC-slack) setpoints** (not 1.0) | src: `PP/auxiliary.py:1769-1776`; docstring `PP/run.py:23,33` |
| `init="flat"` | `vm=1.0`, `va=0°` at PQ buses; PV buses at the gen setpoint (`ppc.bus[VM] = gen.vm_pu`, `build_gen.py:222`); slack at ext_grid `vm_pu`/`va_degree` (`build_gen.py:120-121`); `get_voltage_init_vector` returns `None` for "flat" so the ppc defaults stand | src: `PP/run.py:24-25`, `PP/build_bus.py:312-313,403-408`, `PP/build_gen.py:120-122,222` |
| `init="dc"` | `init_vm_pu="flat"`, `init_va_degree="dc"`: a DC PF runs first inside the NR driver and its angles seed NR | src: `PP/auxiliary.py:1777-1779`; `PP/pf/run_newton_raphson_pf.py:49-57` |
| Convergence test | `‖F‖∞ < tol` (strict), `F = [ΔP_pv, ΔP_pq, ΔQ_pq]` from `mis = V·conj(Ybus V) − Sbus`; **Sbus is per-unit** (`makeSbus` divides by `baseMVA`), so despite the name `tolerance_mva=1e-8` is compared against a **pu** mismatch (== MATPOWER's `pf.tol` semantics) | src: `PP/pypower/newtonpf.py:72,413,420,579,894-896,700-701`; `PP/pypower/makeSbus.py:19` |
| `max_iteration="auto"` | `{"nr": 10, "iwamoto_nr": 10, "bfsw": 100, "gs": 10000, "fdxb": 30, …}`; 30 if TDPF/FACTS | src: `PP/auxiliary.py:1742-1754` (`default_max_iteration`, `max_iteration == "auto"`) |
| Non-convergence | `runpp` **raises** `LoadflowNotConverged("Power Flow nr did not converge after N iterations!")` and cleans results; `net.converged` is only set True on success | src: `PP/powerflow.py:169-177`; probe: island with `check_connectivity=False` → `LoadflowNotConverged` |
| `enforce_q_lims=True` — PV→PQ | Outer loop: solve; `pfsoln`; gens with `QG > QMAX` / `QG < QMIN` (in service, **not `ref_gens`**) get `QG` pinned at the limit, their buses set PQ (`setdiff1d(changed_gens, ref)` — slack bus never converted), `bustypes` recomputed, the gen is temporarily switched off and its `PG/QG` folded into bus `PD/QD`; repeat until no new violations | src: `PP/pf/run_newton_raphson_pf.py:182-242` |
| `enforce_q_lims=2` | "one at a time": fix only the largest violation per round (`argmax`), same as MATPOWER's `pf.enforce_q_lims = 2` | src: `PP/pf/run_newton_raphson_pf.py:207-215` |
| PQ→PV restore? | **No.** `limited` only grows (`limited = r_[limited, mx]`); the loop exits on "no more violations"; there is no check that a pinned bus's voltage has crossed back over its setpoint. After the loop the bus types are set back to PV and gens switched on *for reporting only* (`bus[..,BUS_TYPE] = PV; gen[limited, QG] = fixedQg; GEN_STATUS = 1`) | src: `PP/pf/run_newton_raphson_pf.py:235,241-249`; probe: 3-bus net, gen `max_q=5` → `res_gen.q_mvar = 5.0`, `vm = 0.9588` (setpoint 1.06), `_ppc.bus[1,BUS_TYPE] == 2` afterwards |
| Slack-bus Q limits | never enforced (`setdiff1d(…, ref_gens)`); the commented-out multi-slack error shows the MATPOWER lineage | src: `PP/pf/run_newton_raphson_pf.py:202-203,224-227` |
| Tolerance on the limit test | none — strict `>`/`<` (MATPOWER adds `opf.violation = 5e-6`) | src: `run_newton_raphson_pf.py:199-200` vs `MP/runpf.m:367-370` |
| PV bus whose gens are all out of service | Only in-service gens (`net._is_elements["gen"]`) write `BUS_TYPE = PV`; a bus with only OOS gens keeps the default PQ type. `bustypes()` itself does **not** re-check gen status (pandapower's copy dropped MATPOWER's `bus_gen_status` test) | src: `PP/build_gen.py:207-222`; `PP/pypower/bustypes.py` (no GEN_STATUS use); probe: 3-bus net, gen `in_service=False` at bus 2 → `_ppc.bus[2,BUS_TYPE] == 1.0 (PQ)`, `vm = 0.988` |
| Multiple gens on one bus — setpoint | If the in-service voltage-controlling elements at a bus (gen/ext_grid/SSC/VSC) have different setpoints → **`UserWarning("Voltage controlling elements … at the same bus have different setpoints.")` is raised** (runpp aborts); comparison is `np.allclose` against the **first** occurrence. Equal setpoints: one PV bus, Q split first equally then in proportion to each gen's `[QMIN, QMAX]` range (MATPOWER `pfsoln` rule) | src: `PP/build_gen.py:307-352,380-394`; `PP/pypower/pfsoln.py:109-141`; probe: gens 1.05 + 1.02 → UserWarning; 1.05 + 1.05 → `vm = 1.05`, q split `[85.75, 85.75]` |
| `from_ppc` and repeated `VG` | Converter takes **the first gen row's VG per bus** (`drop_duplicates(subset=["bus"])`, default `keep="first"`; the `keep="last"` variant is commented out; the comment above it says "take VG of the last gen of each bus") — i.e. pandapower's converter silently deviates from MATPOWER's last-wins (§3) when VGs differ | src: `PP/converter/pypower/from_ppc.py:116-118` |
| `from_ppc` and isolated buses | `in_service = (BUS_TYPE != 4)` — **type-4 buses are created out of service** (W1's importer instead raised `BAD_BUS_TYPE`) | src: `PP/converter/pypower/from_ppc.py:77-82` |
| Island without ext_grid, `check_connectivity=True` (default) | BFS from a virtual node tied to all REF buses over in-service branches; unreachable buses get `BUS_TYPE = NONE` (out of service), their load is dropped (logged as unsupplied P/Q); results for them are **NaN** `vm_pu`/`va_degree`, 0 for `p_mw`/`q_mvar`; branches inside the island report 0 MW and NaN loading. A PV gen on the island does not rescue it (no REF there) | src: `PP/auxiliary.py:830-870,769-787`; `PP/results_bus.py:26-28`; probe: 4-bus net with island {2,3} → `res_bus` rows 2,3 `NaN NaN 0 0`, `converged=True` |
| Island, `check_connectivity=False` | singular/ill-conditioned Jacobian → NR does not converge → `LoadflowNotConverged` | probe (same net): `LoadflowNotConverged: Power Flow nr did not converge after 10 iterations!` |
| No REF at all | `UserWarning("No reference bus is available. Either add an ext_grid or a gen with slack=True")` | src: `PP/build_gen.py:363-368` |
| `rundcpp` | options fixed: `init='flat'`, `calculate_voltage_angles=True`, `enforce_q_lims=False`; DC solve `Va = dcpf(B, Pbus, Va0, ref, pv, pq)` with `Va0 = bus[VA]` (rad) — the **slack angle is the ext_grid's `va_degree`** (probe: `va_degree=30` → all angles shift +30°); `Pbus = makeSbus − Pbusinj − GS/baseMVA` (shunt conductance included; phase-shift injections); `PF = (Bf·Va + Pfinj)·baseMVA`, `PT = −PF`, `QF = QT = 0`; slack gens' `PG` updated to balance; `success = True` unconditionally, `iterations = 1` (so `rundcpp` never raises for non-convergence) | src: `PP/auxiliary.py:1830-1850`; `PP/pf/run_dc_pf.py:80-110`; `PP/pypower/dcpf.py:34-46` |
| `rundcpp` result tables | `res_bus.va_degree` = DC angles; `res_bus.vm_pu` = **the initial magnitudes** (ext_grid vm at slack, gen setpoints at PV, 1.0 at PQ); `res_bus.q_mvar = NaN`; `res_line.p_from_mw = −p_to_mw`, `q_* = 0.0`, `loading_percent` computed from P and those vm | probe on `pn.case14()`: `vm_pu 1.060/1.045/1.010`, `q_mvar NaN`, `p_from 147.84 / p_to −147.84`, `q_from 0.0`, `res_ext_grid q_mvar NaN` |

---

## 3. MATPOWER `runpf` conventions (source: `MP/runpf.m`, `MP/mpoption.m`, `MP/bustypes.m`, master 2026-08-20)

| Topic | Rule | Evidence |
| --- | --- | --- |
| Defaults | `pf.alg = 'NR'`, `pf.tol = 1e-8` "termination tolerance on per unit P & Q mismatch", `pf.nr.max_it = 10`, `pf.enforce_q_lims = 0` | src: `MP/mpoption.m:81-84,107-110,1554-1556` (`'tol', 1e-8`, `'max_it', 10`) |
| `pf.enforce_q_lims` values | `0` do NOT enforce; `1` enforce, **simultaneous** bus-type conversion; `2` enforce, **one-at-a-time** (largest violation per round) | src: `MP/mpoption.m:107-110`; `MP/runpf.m:391-399` |
| Violation test | `QG > QMAX + opf.violation` / `QG < QMIN − opf.violation`, in-service gens only; `opf.violation` default `5e-6` | src: `MP/runpf.m:366-370`; `MP/mpoption.m:227` |
| Conversion | `fixedQg = limit; gen(mx,QG) = fixedQg; bus(gen(mx,GEN_BUS),BUS_TYPE) = PQ; [ref,pv,pq] = bustypes(bus,gen); limited = [limited; mx]; V0 = V` (warm start next solve) | src: `MP/runpf.m:411-437` |
| Restore PQ→PV? | **No** — `limited` only accumulates; loop ends when no further violations (`repeat = 0`) | src: `MP/runpf.m:436-440` |
| Slack-bus case | The slack's generator **is** subject to the test (unlike pandapower). If the ref bus is converted to PQ, `bustypes` picks **the first remaining PV bus** as the new ref (`ref = pv(1)`), bus types are rewritten, and after the loop angles are shifted so the *original* ref keeps its original angle: `bus(:,VA) = bus(:,VA) − bus(ref0,VA) + Varef0`. Multiple slacks + a slack hitting a limit → `error('… cannot enforce Q limits for slack buses in systems with multiple slacks')`. Infeasibility: if **all** remaining PV/REF gens violate the same side, `success = 0` | src: `MP/runpf.m:44-56` (help text), `299-302`, `373-388`, `417-419`, `423-435`, `445-450`; `MP/bustypes.m:35-41` |
| Flat start | `V0 = bus(:,VM)·exp(j·VA)` (i.e. the **stored** columns are the start, not 1∠0 — the literal flat-start line is commented out), then at voltage-controlled buses the magnitude is overwritten with the gen's `VG`: `V0(gbus(k)) = gen(on(k),VG) ./ abs(V0(gbus(k))) .* V0(gbus(k))` | src: `MP/runpf.m:291-296` |
| Multi-generator setpoint rule | `V0(gbus(k)) = …` is a MATLAB indexed assignment with repeated indices → sequential assignment, **the last in-service generator row at a bus wins**. Corroborated by pandapower's converter comment "take VG of the last gen of each bus" (`PP/converter/pypower/from_ppc.py:116`). MATPOWER issues no warning when VGs differ. | src: `MP/runpf.m:296`; MATLAB language semantics of repeated-index assignment — **verified by source reading, not executed** (no MATLAB/Octave here). The manual's wording is `unverified` offline. |
| PV bus with no in-service gen | `pv = find(BUS_TYPE == PV & bus_gen_status)`, `pq = find(BUS_TYPE == PQ | ~bus_gen_status)` → treated as **PQ with zero generation**; a REF bus with no in-service gen loses ref status and the first PV becomes ref | src: `MP/bustypes.m:27-41` |
| Q split among gens at a bus | equal first, then proportional to `QMAX−QMIN` (`pfsoln`) — pandapower's copy is verbatim | src: `PP/pypower/pfsoln.py:109-141` (MATPOWER `pfsoln.m` itself not fetched — `unverified` as to line numbers, identical algorithm) |
| Isolated buses (type 4) | excluded by `ext2int` before the solve; results NaN/zero for them | `unverified` (ext2int.m not fetched; standard MATPOWER behaviour) |

---

## 4. case300

### 4.1 Upstream source (verified)

| Item | Value | Evidence |
| --- | --- | --- |
| Repository path | `MATPOWER/matpower` → `data/case300.m` (master) | GitHub contents API: `name case300.m`, `path data/case300.m`, `size 66034` |
| Raw URL | `https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case300.m` | same API (`download_url`) |
| Git blob SHA-1 | `004203b8adae83b3f21ce9ceb4a13db9b18f0132` | API `sha`; reproduced locally: `(printf "blob %d\0" $(stat -c%s case300.m); cat case300.m) \| sha1sum` → identical |
| SHA-256 of the bytes | `69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5` | `sha256sum MP/case300.m` (66034 bytes) |
| Header | "Power flow data for IEEE 300 bus test case … converted from IEEE Common Data Format (ieee300cdf.txt) on 18-Nov-2014 by cdf2matp, rev. 2393 … https://labs.ece.uw.edu/pstca/ … 13/05/91 CYME INTERNATIONAL 100.0 1991 S IEEE 300-BUS TEST SYSTEM" | `head -22 MP/case300.m` |
| Modifications | "v2 – 2025-06-14 (WGV) – Set tap parameter of branches # 71, 90, 188, 189, 190, 191, 192, 193, 208, 232, 233, 267, 279, 299, 310, 313, 315, 316, 318, 320, 324, and 325 to 1.0 to model transformers with nominal turns ratio. This configuration benefits the convert_1p_to_3p function." (same v2 wave as case_ieee30's 2025-06-14 edit) | header lines 13-18; probe: those 22 rows all carry `TAP = 1.0` |
| Format | `mpc.version = '2'`, `baseMVA 100`; **300 bus rows, 69 gen rows, 411 branch rows, 69 gencost rows**; no type-4 buses; no `BASE_KV ≤ 0`; slack = bus **7049** (`VM 1.0507, VA 0, 13.8 kV`); one negative-reactance branch (row 179: 1201–120, `x = −0.3697`); no phase shifters; cdf2matp warning block at the tail ("negative Pg at bus 8/10/20/138 treated as Pd", …) | awk counts over `MP/case300.m`; lines 23, 828, 900-906 |
| Stored precision | VM 4 decimals, VA 2 decimals | awk (§1.1) |

(WebFetch's summariser reported 161/169 bus rows — it cannot count; the awk counts over the downloaded
bytes are authoritative.)

### 4.2 Licence — what PROVENANCE.md must say

`MP/LICENSE` (sha256 `5d14c09b…`) opens with:

> The code in MATPOWER is distributed under the 3-clause BSD license below. **The MATPOWER case files
> distributed with MATPOWER are not covered by the BSD license.** In most cases, the data has either been
> included with permission or has been converted from data available from a public source.

followed by the 3-clause BSD text, "Copyright (c) 1996-2025, Power Systems Engineering Research Center
(PSERC) and individual contributors". `bustypes.m` etc. carry "Covered by the 3-clause BSD License";
`case300.m` carries **no licence line** — only "MATPOWER" and the CDF provenance.

Consequences for the record (same applies retroactively to the five existing fixtures, whose
PROVENANCE.md currently says nothing about licence):

- Do **not** write "BSD 3-clause" against the case file. Write: *MATPOWER distribution file; per MATPOWER's
  LICENSE the case files are not covered by its BSD licence; the data is the public IEEE 300-bus test case
  (1991 CYME/IEEE CDF, UW PSTCA archive) converted by cdf2matp and carried as published test data.*
- Record the raw URL, retrieval date, git blob SHA-1 `004203b8…`, SHA-256 `69a90280…`, size 66034, and the
  v2 2025-06-14 tap modification verbatim from the header, matching the existing per-fixture layout
  (Source / Upstream lineage / Reference solution / Known reference-quality findings).

### 4.3 pandapower's `case300()`

| Item | Finding | Evidence |
| --- | --- | --- |
| Function | `pandapower.networks.power_system_test_cases.case300()` → loads `networks/power_system_test_case_jsons/case300.json` (186 707 bytes) | src: `PP/networks/power_system_test_cases.py:405-421` |
| Declared origin | "data origin is PYPOWER" (+ UW and Illinois links) — i.e. a JSON snapshot of PYPOWER's `case300.py`, which is itself a port of an **older** MATPOWER `case300.m`; **not** derived from the v2 (2025-06-14) bytes | docstring lines 407-411 |
| Content | 300 buses (names = MATPOWER bus numbers), 1 ext_grid at 7049 `vm 1.0507`, 68 gen + 8 sgen, 283 lines, 128 trafos (62 with a tap position = the 62 MATPOWER branches with `TAP ∉ {0,1}`), 193 loads, 29 shunts, 69 `poly_cost`; **no stored `res_bus`** | probe |
| Reading the `.m` directly with pandapower | `pandapower.converter.matpower.from_mpc.from_mpc("case300.m")` → `NotImplementedError: matpowercaseframes is used to convert .m file. Please install that python package` — pandapower 3.3.0 has no native `.m` parser | probe |
| Bundled vs verbatim file, flat start, no Q-limits | both converge in 5 iterations to the *same* point: max \|ΔVM\| vs stored columns 0.1072 (bundled) / 0.1071 (verbatim via repo reader) — so the v2 tap edits are **not** what separates the stored columns from the solution | probe §1.2 + bundled probe |
| Q-limits enforced | **LoadflowNotConverged after 100 iterations** for `enforce_q_lims ∈ {1, 2}` × `init ∈ {flat, dc, auto}` (bundled) and after 50 (verbatim). Without limits, **23 of 68** gens violate their Q range — limit enforcement flips a third of the PV set, and pandapower's simultaneous/one-at-a-time schemes both fail to settle | probe |
| Stored-state defect | W1 gate: 9 buses > 5 MVA (cap 15 → **would pass** the cap): 137, 181, 196 (926.1), 231, 235, 237, 238, 2040 (926.9), 9001. The 927 MVA pair is branch **row 390: `196 2040 r=0.0001 x=0.02 b=0 tap=1`** — the stored angles differ by 10.4° across it (196 @ −25.32°, 2040 @ −14.94°), implying ~9 pu flow; the CDF-era solution cannot have been computed with this branch as shipped | `gate.py`; awk over rows |

**Implication for M2** (my assessment): case300 is a valid *convergence + self-consistency + DC* fixture
and an *ungated-column-parity* fixture only with Q-limits **off** (then pandapower is the oracle, not the
stored columns, which are 0.107 pu away at bus 17). Promising W1-style gated column parity against the
stored columns, or any Q-limited parity, for case300 would fail on the data.

### 4.4 How M2 should obtain the bytes

```
curl -sS -L -o fixtures/matpower/case300.m \
  https://raw.githubusercontent.com/MATPOWER/matpower/master/data/case300.m
sha256sum fixtures/matpower/case300.m   # expect 69a90280e999ef533d94656e0fbc08311f1347c962dd2753ff2005ff5e3f9ac5
git hash-object fixtures/matpower/case300.m   # expect 004203b8adae83b3f21ce9ceb4a13db9b18f0132
```

Pin the blob SHA in PROVENANCE.md and SOURCES.md (the existing table records URL + date only; adding the
blob SHA makes "verbatim" checkable). `.gitattributes` already exists at the repo root — confirm it
does not normalise line endings on `*.m` before committing (the sha256 above is for the bytes as served,
LF line endings).

---

## 5. Docs tooling (free, Python 3.12)

probe: `uv pip install --dry-run --python .venv/Scripts/python.exe mkdocs-material "mkdocstrings[python]"
mkdocs-jupyter nbmake pymdown-extensions` → "Resolved 82 packages in 507ms / Would download 66 packages /
Would install 66 packages" (nothing modified; `git status --porcelain` clean).

| Package | Resolved version | Role | Notes |
| --- | --- | --- | --- |
| `mkdocs-material` | **9.7.7** (on `mkdocs 1.6.1`, `mkdocs-material-extensions 1.3.1`) | theme | pure-Python wheel; pulls `pymdown-extensions`, `babel 2.18.0`, `backrefs 8.0`, `paginate`, `watchdog 6.0.0` |
| `mkdocstrings[python]` | **mkdocstrings 1.0.6** + **mkdocstrings-python 2.0.7** + `griffelib 2.2.0` + `mkdocs-autorefs 1.4.4` | API reference from docstrings | note the 1.x/2.x majors (post-2025 renames: `griffe` → `griffelib`); pure-Python |
| `mkdocs-jupyter` | **0.26.3** (`nbconvert 7.17.1`, `nbclient 0.11.0`, `nbformat 5.11.1`, `jupyter-client 8.9.1`, `ipykernel` chain, `pyzmq 27.2.0`, `tornado 6.5.8`, `debugpy 1.8.21`) | render/execute notebooks as pages | the only compiled wheels in the set are `pyzmq`, `tornado`, `debugpy`, `psutil 7.2.2`, `rpds-py 2026.6.3` — all resolved for cp312-win_amd64 |
| `nbmake` | **1.5.5** | pytest plugin that executes notebooks (`pytest --nbmake`) | good fit for "executed examples" as a test, independent of the site build |
| `pymdown-extensions` | **11.0.1** | `pymdownx.superfences` with the `mermaid` custom fence (mkdocs-material's documented recipe) | already a transitive dep of mkdocs-material; pin explicitly anyway |

No resolution errors or "no matching wheel" messages for Python 3.12.14. Everything above is MIT/BSD
(`unverified` — licence strings not fetched individually). Recommendation: `mkdocs-jupyter` for rendering
plus `nbmake` for CI execution of the same notebooks, so executed-example failures surface in `pytest`
rather than only in the docs build.

---

## Carry-forward list for the M2 design

1. Stored columns are 3-dec VM / 2-dec VA (4-dec for case300); no stored state converges at 1e-8; W1's
   exclusions and bands are confirmed by an independent gate computation (§1.3) and explained (§1.4).
2. case118 column parity needs Q-limits **on** (qlim-off breaches 2e-3 at bus 103 even after exclusions).
3. Our Q-limit semantics should follow MATPOWER/pandapower: no PQ→PV restore, accumulate pins, strict or
   5e-6 tolerance, slack excluded (pandapower) or re-slacked (MATPOWER) — W1's TS engine *did* restore
   (W1 §4.1 "PQ→PV restore"); that is a deliberate divergence from both oracles and must be a parameter
   or be dropped, otherwise parity runs compare different fixed points.
4. Multi-gen setpoint: MATPOWER last-wins silently; pandapower errors on disagreement, first-wins in the
   converter; W1 used first-in-service. Pick one and document; recommend *error on disagreement* (pandapower)
   with a documented override.
5. PV bus with all gens out of service → PQ in both oracles (matches W1).
6. Isolated/islanded buses: pandapower NaN-results them; `from_ppc` maps type 4 → out of service (W1 raised).
7. case300: obtain as in §4.4; licence wording per §4.2; parity scope per §4.3.
8. Docs: versions per §5; all Python-3.12 wheels present.

## Erratum (2026-08-21, after S4)

§1.2 ("case300 stored columns 0.107 pu away", "9 buses failing the gate") and §4.3
("pandapower cannot converge case300 with Q-limits") were artefacts of the oracle
construction, not of the data: pandapower `from_ppc` places each transformer tap on the
winding it picks as hv by base voltage, which for 16 case300 transformers is MATPOWER's
T_BUS, so the oracle modelled a different network (inert in DC, 164 MVA on branch 396 in
AC). With MATPOWER's exact tap-side swap applied to the oracle copy (record/m2-s4-report.md),
pandapower matches mambo-power at 3e-14 pu, converges case300 with enforce_q_lims in 2
iterations with the same 10 pins, and our case300 vs stored VM is 8.5e-3 pu worst (11/300
buses beyond 2e-3). The licence caveat and sha256 in §4 stand.
