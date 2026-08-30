# Numerics

`mambo_power.numerics` turns a `Network` into the matrices solvers need: the positional
per-unit view `NetworkArrays`, the bus admittance matrix `Ybus`, the DC susceptance matrices
`Bbus` / `Bf`, and the sensitivity matrices `PTDF` and `LODF`. It is the **only** module in
the package that holds positional indices and the **single** site where physical units are
divided by `base_mva`. Every builder takes a `NetworkArrays`, never a `Network`.

## `NetworkArrays`

`NetworkArrays.from_network(net)` builds a frozen dataclass of numpy arrays over the
**in-service subset** of the network, in per unit, with 0-based positions.

### In-service filtering

| Dropped | Rule |
| --- | --- |
| Buses | `in_service=False` |
| Branches | `in_service=False`, **or** either end bus dropped |
| Generators, loads, shunts | `in_service=False`, **or** the bus dropped |

Positions follow the network's collection order with the dropped elements removed. The
network's own validation guarantees the surviving buses form one connected component with
exactly one slack; `from_network` re-checks only the slack count and raises `ValueError`
otherwise.

### What it holds

| Group | Attributes | Notes |
| --- | --- | --- |
| Bus index | `bus_ids: list[str]`, `bus_index: dict[str, int]`, `n_bus`, `slack: int` | `bus_ids[i]` is the id at position `i`; `bus_index` is the inverse. |
| Bus roles | `bus_type: int[n_bus]` | MATPOWER codes from `BUS_TYPE_CODE`: 1 = pq, 2 = pv, 3 = slack — the **declared** role. |
| Branch index | `branch_ids`, `branch_index`, `n_branch`, `f: int[n_branch]`, `t: int[n_branch]` | From/to bus positions. |
| Branch parameters | `r`, `x`, `b`, `tap`, `shift_rad`, `rating_pu` | `b` is the total charging; `tap` is 1.0 where absent; `shift_rad` converted from degrees; `rating_pu = rating_mva / base_mva`, `inf` where unrated. |
| Bus injections | `p_load_pu`, `q_load_pu`, `g_shunt_pu`, `b_shunt_pu` | Summed per bus, divided by `base_mva`. Shunt signs as in the model (G positive consumes, B positive injects). |
| Bus-level generation | `p_gen_pu`, `q_gen_pu`, `p_min_pu`, `p_max_pu`, `q_min_pu`, `q_max_pu`, `v_set` | Summed per bus. `v_set` is the **first** in-service generator's setpoint at each bus, 1.0 where none — the effective setpoint rule is applied by `effective_roles` (see [Power flow](power-flow.md#effective-bus-roles)). |
| Per-generator | `gen_ids`, `gen_bus: int[n_gen]`, `gen_p_pu`, `gen_q_pu`, `gen_p_min_pu`, `gen_p_max_pu`, `gen_q_min_pu`, `gen_q_max_pu`, `gen_v_set` | One entry per surviving generator, in collection order. |
| Scalar | `base_mva` | The base everything was divided by. |

### Per-unit conversion — the single site

Every MW, MVAr and MVA quantity in the model is divided by `base_mva` exactly once, here.
Nothing else in the package divides by the base; `results.from_arrays` multiplies by it on the
way out. The agreement test that guards this is the Ybus parity against pandapower's
`makeYbus` on the IEEE fixtures, which fails if the conversion drifts.

```python
from mambo_power.io import matpower
from mambo_power.numerics import NetworkArrays

net = matpower.load("fixtures/matpower/case14.m")
arr = NetworkArrays.from_network(net)
print(arr.n_bus, arr.n_branch, arr.slack, arr.bus_ids[:3], arr.bus_index["bus-5"])
```

```text
14 20 0 ['bus-1', 'bus-2', 'bus-3'] 4
```

## Bus admittance matrix — `ybus`

MATPOWER `makeYbus` conventions. For each branch with series admittance
\(y = 1/(r + jx)\), total charging \(b\), and from-side complex tap
\(a = \tau\,e^{j\phi}\) (`tap` and `shift_rad`):

\[
Y_{ff} = \frac{y + j\,b/2}{|a|^2}, \qquad
Y_{ft} = -\frac{y}{a^*}, \qquad
Y_{tf} = -\frac{y}{a}, \qquad
Y_{tt} = y + j\,b/2 .
\]

With \(C_f\), \(C_t\) the branch-to-bus incidence matrices and the per-bus shunt admittance
already in pu:

\[
Y_\text{bus} = C_f^\top Y_f + C_t^\top Y_t + \operatorname{diag}(g_\text{shunt} + j\,b_\text{shunt}),
\qquad
Y_f = [Y_{ff}\;Y_{ft}],\; Y_t = [Y_{tf}\;Y_{tt}] .
\]

| Function | Returns |
| --- | --- |
| `ybus(arr)` | `n_bus × n_bus` complex CSC matrix. |
| `yf_yt(arr)` | `(Yf, Yt)`, each `n_branch × n_bus` complex CSC; `Yf @ V` is the current into each branch at its from bus, `Yt @ V` at its to bus. |
| `ybus.branch_admittances(arr)` | The four per-branch vectors `(Yff, Yft, Ytf, Ytt)`. |

A branch with `r == x == 0` has no series admittance and raises `ValueError` naming the
branch (the model already rejects it as `BAD_RANGE`; the guard covers hand-built arrays).

```python
from mambo_power.numerics import ybus

Y = ybus(arr)
print(Y.shape, Y.nnz, Y.dtype)
print(Y[0, 0])
```

```text
(14, 14) 54 complex128
(6.025029055768224-19.447070205514382j)
```

## DC susceptance matrices — `bbus`, `bf`, `p_shift`

MATPOWER `makeBdc` conventions: resistance and line charging are ignored, only the tap
magnitude enters. Per branch \(b_k = 1 / (x_k\,\tau_k)\). With \(C_{ft}\) the
`n_branch × n_bus` from-minus-to incidence matrix (+1 at the from bus, −1 at the to bus):

\[
B_f = \operatorname{diag}(b)\,C_{ft}, \qquad
B_\text{bus} = C_{ft}^\top B_f, \qquad
P_{f,\text{shift}} = -\,b \odot \phi, \qquad
P_\text{shift} = C_{ft}^\top P_{f,\text{shift}} .
\]

so that the from-side flows and bus injections are

\[
P_f = B_f\,\theta + P_{f,\text{shift}}, \qquad
P = B_\text{bus}\,\theta + P_\text{shift} .
\]

| Function | Returns |
| --- | --- |
| `bbus(arr)` | `n_bus × n_bus` real CSC \(B_\text{bus}\). |
| `bf(arr)` | `n_branch × n_bus` real CSC \(B_f\). |
| `p_shift(arr)` | Per-bus phase-shifter injection \(P_\text{shift}\) (pu). |
| `bbus.pf_shift(arr)` | Per-branch phase-shifter flow injection (pu). |
| `bbus.branch_susceptance(arr)` | Per-branch \(b_k\). |
| `bbus.incidence(arr)` | \(C_{ft}\). |

The first three rows are reachable as `numerics.bbus`/`bf`/`p_shift`; a `bbus.`-prefixed name is
not a runtime path — it names the function and the module (`numerics/bbus.py`) that implements it,
internal to this page's derivation and not part of the public surface (`numerics.bbus` is itself
the `bbus(arr)` function, not the submodule, so `numerics.bbus.pf_shift` raises `AttributeError`).

A branch with `x == 0` has undefined DC susceptance and raises
[`UnsolvableNetworkError`](../api/numerics.md) — a valid network the DC numerics cannot solve,
distinct from the malformed-input `ValueError`s elsewhere on this page.

## Power transfer distribution factors — `ptdf`

\[
\text{PTDF} = B_f\,B_\text{bus}^{-1}
\]

with the slack row and column removed before the inverse and the slack column of the result
set to zero. Then `flows = PTDF @ P` for any injection vector `P`, the slack absorbing the
imbalance. The reduced \(B_\text{bus}\) is factorised once with a sparse LU
(`scipy.sparse.linalg.splu`) and solved against the dense transposed \(B_f\); the full matrix
is never inverted densely. The result is a dense `n_branch × n_bus` array.

`ptdf(arr, slack=None)` uses the network's slack by default; pass a position to re-reference.

```python
from mambo_power.numerics import ptdf

H = ptdf(arr)
print(H.shape, abs(H[:, arr.slack]).max())  # slack column is zero
print(H[0, arr.bus_index["bus-2"]])  # 1 MW at bus-2 -> -0.838 MW on branch-1
```

```text
(20, 14) 0.0
-0.83801864961743
```

## Line outage distribution factors — `lodf` and `bridges`

`LODF[l, k]` is the fraction of branch `k`'s pre-outage flow that appears on branch `l` after
`k` is removed. With \(h_k = \text{PTDF}\,(e_{f(k)} - e_{t(k)})\) the flows caused by a unit
transfer across `k`:

\[
\text{LODF}_{lk} = \frac{h_k[l]}{1 - h_k[k]} \quad (l \ne k), \qquad \text{LODF}_{kk} = -1 .
\]

### Bridges and NaN columns

A branch whose removal disconnects the network — a **bridge** — has \(h_k[k] = 1\) and no
finite LODF. Its whole column is `NaN`: there is no post-outage flow to redistribute, because
the outage islands the network. Two independent detections must agree, and the test suite
checks that they do:

- `lodf` marks a column as a bridge numerically when \(|1 - h_k[k]| < 10^{-10}\)
  (`BRIDGE_TOL`);
- `bridges(arr)` finds them graph-theoretically with an iterative Tarjan lowpoint search over
  the multigraph. Parallel branches between the same pair of buses are never bridges.

| Function | Returns |
| --- | --- |
| `lodf(arr, ptdf_matrix=None)` | Dense `n_branch × n_branch`; diagonal −1; bridge columns `NaN`. Pass a precomputed PTDF to avoid recomputing it. |
| `bridges(arr)` | Sorted list of bridge branch **positions**. |

```python
import numpy as np
from mambo_power.numerics import bridges, lodf

L = lodf(arr, H)
print(L.shape, bridges(arr), np.flatnonzero(np.isnan(L).any(axis=0)))
print(arr.branch_ids[13])
```

```text
(20, 20) [13] [13]
branch-14
```

In case14, `branch-14` (bus-7 to bus-8) is the only bridge: bus-8 hangs off it radially.

## Putting it together

```python
from mambo_power.io import matpower
from mambo_power.numerics import NetworkArrays, bbus, bf, lodf, ptdf, ybus

net = matpower.load("fixtures/matpower/case118.m")
arr = NetworkArrays.from_network(net)

Y = ybus(arr)  # complex sparse, AC
B, Bf = bbus(arr), bf(arr)  # real sparse, DC
H = ptdf(arr)  # dense sensitivities
L = lodf(arr, H)  # outage redistribution

# Flow on every branch for 100 MW injected at one bus and withdrawn at the slack:
p = np.zeros(arr.n_bus)
p[arr.bus_index["bus-10"]] = 100 / arr.base_mva
flows_mw = H @ p * arr.base_mva
```

Positions are the only currency inside this module. To go back to ids use `arr.bus_ids[i]`
and `arr.branch_ids[k]`; the [`results`](results.md) builders do exactly that.
