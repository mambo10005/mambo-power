# Changelog

All notable changes to mambo-power are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/). Nothing has been released yet; the first release
will be 0.1.0 on PyPI (wave M9).

## [Unreleased]

One section per wave, newest first. Nothing on this page has been released. Which waves have
merged to `epic/01-foundation` and which are still on their own branch is tracked in [the home
page's roadmap table](index.md), not restated here, so this page cannot go stale about it.

### Added — wave M8 (interop)

- `io.pandapower_json`: `load` / `loads` / `load_with_report` read a `pp.to_json` document
  (`bus`, `ext_grid`, `gen`, `sgen`, `load`, `shunt`, `line`, two-winding `trafo`, `poly_cost`,
  `pwl_cost`, `res_bus`) with the measured per-unit conversions — line `r/x/b` on
  `vn_kv²/sn_mva`, trafo impedance from `vk_percent` on the system base, the tap changer folded
  into `tap_ratio`, the shunt sign flipped from consumption to injection; the first in-service
  `ext_grid` is the slack and any further one is demoted to a PV generator with a warning.
  `dumps` / `dump` / `dumps_with_report` write a document `pp.from_json` loads and on which
  pandapower's own `rundcpp` / `runpp` agree with `pf.solve_dc` / `pf.solve_ac` to 1e-13° and
  1e-15 pu. Strict `nets_equal` on the round trip holds for the cost tables only; every carried
  value survives at 1e-12 and the set is pinned in the test rather than papered over (F2).
- `io.pypsa`: `to_network` / `to_network_with_report` build a `pypsa.Network` — lines in
  ohm/siemens, transformers as `model="pi"` on their own `s_nom` with `tap_ratio` and
  `phase_shift`, generators with `p_nom`, `p_min_pu`, `marginal_cost` (+ `marginal_cost_quadratic`),
  the constant term in a `marginal_cost_constant` column, unrated branches at `s_nom = 1e5`,
  and **never** a generator `p_set` (it pins dispatch). PyPSA `optimize()` reproduces
  `opf.solve_dc_opf`'s objective to 1e-8 on case14 / case30 / case118; the one 1.87e-3 MW
  dispatch residual on case118 is HiGHS's, measured and pinned (F3). Piecewise costs,
  degree > 2, load bids, zones and generator Q limits are dropped and reported, never
  approximated. PyPSA 1.2.4's `optimize()` ignores `phase_shift`, so DC-OPF parity is for
  shift-free networks.
- `io.psse_raw`: `load` / `loads` / `load_with_report` read PSS/E RAW **v33** — case
  identification, bus, load, fixed shunt, generator, branch, two-winding transformer (four-line
  records; `CZ` / `CW` / `CM` converted as MATPOWER's `psse_convert_xfmr` does), area, zone;
  ZIP loads, branch end shunts and magnetising admittances are folded and reported; three-winding
  transformers, switched shunts, owners and every later section are skipped with one report
  entry per record. RAW carries no costs, and the importer says so (`RAW_NO_COSTS`) rather
  than inventing any. Fixtures `case14_v33.raw` and `synthetic_quirks_v33.raw` with provenance.
- `io.csv_bundle`: `dump(net, dir)` / `load(dir)` — `manifest.json` plus one CSV per entity
  table headed by the model's field names, costs and bids as long-format side tables, empty cell
  = `None`, ids as text, floats via `repr`. `load(dump(net)) == net` **bit-exactly** on every
  bundled fixture; a bundle that is not exact is refused with every problem listed
  (`CSV_*` codes), and an optional string field holding `""` is refused on write because the
  bundle could not read it back.
- `model.Branch.kind: "line" | "transformer"`, defaulted at construction — `"transformer"` iff
  the tap is off-nominal or the shift non-zero — so no existing file changes; importers set it
  from the source table (a neutral-tap transformer stays one), exporters route on
  `Branch.is_transformer` (`kind` or an off-nominal tap/shift, so a tap assigned after
  construction is still exported), and an explicit `"line"` with a tap is promoted to
  `"transformer"`. The JSON schema snapshot moved once.
- `io.report.ExportReport`, mirroring `ImportReport` (same issue record, `warnings` / `errors`,
  `codes`, `as_strings`, `raise_on_error`), returned by every exporter under one rule: an empty
  report means the conversion was lossless, and anything dropped, approximated or repaired is an
  issue naming the element id and the field. `io.report.LIMITATIONS` registers every code the
  four modules can emit; `tests/unit/test_io_limitations.py` fails on a code the manual does
  not name.
- Docs: [File formats](manual/formats.md) gains a section per format (sections read, derived
  ids, column / record maps, warnings, errors, limitations, example); API pages for the four
  modules; [`examples/13_interop.py`](examples/index.md#13-interop) runs every format on
  case14 with its report.
- Known limitation carried out of the wave (F1 / A19): `opf.dc_opf`'s flow rows omit the
  phase shifter's PTDF term, so a network with a non-zero `shift_deg` — from any format — gets
  wrong `opf` / `market` branch flows until the standalone fix lands; `pf.solve_dc` is right
  and agrees with pandapower's `rundcpp` and PyPSA's `lpf()`. Stated under every importer's
  limitations in the manual.

### Added — wave M7 (agent-based bidding)

- `market.solve_agents(scenario, options=None, *, strategies=None) -> MarketAgentsResult`: the
  fourth market mode and the first whose input is the output of a decision. Each round every
  generator's `Strategy` sees an `Observation` (its own true cost, bounds, and its own last two
  rounds — price at its bus, cleared MW, the offer it made) and returns the cost curve it
  offers (any `GeneratorCost`); the market clears the **offered** curves with the ordinary nodal DC-OPF, and the loop
  repeats until the offers settle. Updates are simultaneous. The observation is an own-node view
  on purpose: no rival's offer, cost or dispatch ever reaches a strategy.
- `market.strategy`: the `Strategy` protocol, `PriceTakerStrategy` (offers the true cost
  verbatim — the same object, not a reconstruction) and `MarkupStrategy` (a two-point hill climb
  on its own profit with a fixed `step`, never offering below its true cost). `StrategyConfig`
  is the JSON-facing discriminated union and `build_strategy` turns it into an instance, so a
  strategy crosses `jobs` as data and never as a callable.
- `results.MarketAgentsResult`: the final round's nodal result plus per-agent `AgentOfferResult`
  (true cost, final offer, profit) and a `termination_reason` that is one of three words —
  `converged`, `iteration_cap`, `cycle` — rather than a flag that could be read as settled when
  the loop merely stopped. Convergence is decided on the amplitude of the last cycle of offers
  against `offer_tol`, with a tie rule so that a comparison exact in arithmetic is not decided
  by float noise (found on both sides of the same boundary during the wave). The derived floor
  on `offer_tol` is `3 * step`, not `2 * step`: a profit peak halfway between two grid points
  ties the two straddling offers, and the settled orbit is then three steps wide (critic
  finding, M7 S11; `MarkupStrategy.min_offer_tol` is the one place the constant lives).
- `jobs`: `kind="market.agents"`, the eighth kind; `MarketAgentsOptions` and its strategies
  cross as JSON. Caller mistakes (an unknown generator id, `offer_tol` below `3 * step`, a
  markup strategy on a non-linear cost, a bad iteration cap) map to `VALIDATION`, not
  `INTERNAL`.
- `opf.dc_opf` now raises when a generator appears in `pwl_costs` **and** has a nonzero
  `cost_coeffs` row — the generator-side mirror of the load-side guard that has always existed.
  Without it the unit's cost is charged twice (polynomial term plus epigraph rows) and the LP
  solves happily: on case14 the doubly-charged form drove one generator from 223 MW to zero and
  raised the objective by $2,409.70 with status still `Optimal`. Five waves never hit it because
  `gen_cost_coeffs` zeroes the row by construction; M7 is the first to assemble coefficients per
  round from strategy output. Disclosed as a behaviour change.
- `MarketNodalResult.branches`: per-branch flows on the nodal result, derived from the PTDF
  matrix and the phase-shift term, so the agents result can report congestion without a second
  solve.
- A manual page ([Agent-based bidding](manual/agents.md)) and
  [`examples/12_agent_market.py`](examples/index.md#12-strategic-bidding). [Design › Decisions](design/decisions.md) gains ADR-010: offers as an overlay
  the loop supplies, the own-node two-round observation, and what "settled" means.

### Added — wave M6 (zonal market and redispatch)

- `market.solve_zonal(scenario, options=None) -> MarketZonalResult`: a market cleared at **zonal**
  granularity, then redispatched onto the real network, then measured against the nodal optimum —
  three chained solves whose content is their relationship. Because the redispatch objective is
  the true cost and bid curves over the nodal problem's own feasible set, the redispatched point
  *is* the nodal optimum, so what the comparison measures is the cost of the market design alone
  and not the quality of a redispatch heuristic. `MarketZonalResult` carries both dispatch layers
  (what the market sold, what the network delivers), the deltas between them per participant and
  per direction, zone prices, per-bus LMPs and per-branch flows and duals.
- `model.Zone` and `Bus.zone` are read by a solver for the first time, having been in the schema
  and populated by every MATPOWER import since M1. The partition is read, never derived: an
  in-service bus with no zone is a `ValueError` rather than a default, because that bus's load has
  to enter *some* zone's balance row.
- `market.CorridorLimit` and `market.MarketZonalOptions`: transfer capacity per tied zone pair,
  supplied per solve rather than stored on the network. A negotiated transfer capacity is not
  determined by any branch rating and no bundled fixture carries one, so a model entity would be
  inventing committed data. The row-model shape (rather than a `{(z1, z2): cap}` mapping) is what
  makes the options object survive a JSON round trip, which every `jobs` request form must.
- `opf.zonal.zonal_dc_opf(arr, cost_coeffs, zone_of_bus, corridors, ...) -> ZonalSolution`: one
  balance row per zone, one bounded exchange column per tied zone pair, and **no** branch flow
  rows at all — each zone a copper plate internally, no PTDF matrix ever built. A zone's price is
  its own balance row's dual; a corridor's capacity price is its column's reduced cost as a
  magnitude, non-negative in both flow directions.
- `opf.redispatch.redispatch_dc_opf(arr, cost_coeffs, p0, d0, ...) -> RedispatchSolution`: the
  minimum-cost move from a zonal operating point to a network-feasible one, with Δ⁺/Δ⁻ columns on
  **both** sides of the market (demand can be restored, not only curtailed) and bounds shifted by
  the starting point so the final point ranges over exactly the box the nodal problem has.
  Reported deltas are netted to the canonical representative, so `final == p0 + up - down` and
  `up * down == 0` hold exactly whatever vertex the solver returns. The two sides are named for
  what happens to the participant: `delta_up_mw` / `delta_down_mw` on a generator row,
  `delta_restore_mw` / `delta_curtail_mw` on a `MarketZonalResult` load row.
- `results.zonal`: `MarketZonalResult` with `ZonePriceResult`, `GenRedispatchResult` and
  `LoadRedispatchResult`. Three deliberately separate figures — `redispatch_payment` (a
  settlement figure), `welfare_gap` (an exactness row, `0` by the theorem above) and
  `generation_cost_gap` (a diagnostic that is **not** sign-constrained: a zonal clearing can burn
  less fuel than the nodal optimum while being welfare-worse). It is also the first market result
  type carrying per-branch flows and their shadow prices, which makes both sides of the settlement
  identity computable from the result object alone, with no second solve.
- `jobs`: `market.zonal` registered as a seventh kind.
- Oracle: **PyPSA** with one bus per zone joined by `Link`s carrying the corridor capacities —
  column-for-column the engine's own corridor variable, where a `Line` would not be (three
  corridors close a loop and Kirchhoff's voltage law would pin the split by reactance). The
  partition and capacities are handed to the oracle independently of the engine. The `Link` form
  is an exact LP equivalence, so the pinned residuals are four orders tighter than this package's
  usual parity bands: objective 1.67e-15 relative, 1.59e-12 MW, 7.11e-15 \$/MWh.
- Fixtures, derived at test time and committing no new files: `tests/_zones.py` promotes case30's
  three MATPOWER `AREA` groups to real `Zone` entities and derives each corridor's capacity as the
  sum of `rating_mva` over its cut-set; case300's four real `ZONE` groups are used directly.
- [Manual › Zonal market](manual/zonal.md) and a new [runnable
  example](examples/index.md#11-zonal-redispatch). [Manual › Results](manual/results.md) gains a
  section per market result type, [Design › Decisions](design/decisions.md) gains ADR-006 through
  ADR-009, and the zonal page names the two things its own worked variations make true and its
  prose did not say: when `redispatch_payment` is negative, and that
  `redispatch_payment + generation_cost_gap` is exactly the curtailment compensation.

### Added — wave M5 (multiperiod market)

- `market.solve_multiperiod(scenario, options=None) -> MarketMultiperiodResult`: a whole horizon
  cleared as **one** coupled LP/QP, not `T` stacked single-period clearings. Three row families a
  single instant cannot have — a ramp row tying period `t` to `t-1`, a state-of-charge row tying
  the horizon into one energy budget, and a cyclic row closing it at
  `soc[T-1] == soc_initial * energy_mwh`. `MarketPeriodResult` carries that period's own dispatch,
  its per-bus LMPs split by `opf.lmp_decomposition`, and five settlement figures;
  `MarketMultiperiodResult` carries their plain sum as horizon totals. A `Scenario` with
  `periods=None` degenerates to `market.solve_nodal` bit-for-bit on every bundled fixture,
  case300 included.
- `model.Period(load_p_mw)` and `Scenario.periods: list[Period] | None`: an id-keyed **override**
  of each `Load.p_mw` for that period, not a scale factor — a load absent from the dict keeps its
  own `p_mw`. Keys are checked against the scenario's network by `Scenario`'s own validator, since
  a bare `Period` has no network to check against. On a load carrying a `bid` the override moves
  the upper bound of its elastic column too, `Load.p_mw` being that load's maximum served
  quantity. `market.solve_nodal` ignores `periods` entirely and stays a single-period entry point.
- `Generator.ramp_up_mw` / `ramp_down_mw`, both `float | None`, in MW per period — physical, like
  every other `Generator` field, rather than PyPSA's per-unit-of-`p_nom` convention. `None` means
  unconstrained and builds no row at all; a limit of exactly `0` is rejected by `Network` itself
  with a `BAD_RANGE` validation issue. `GenPeriodDispatchResult.ramp_dual` reports the row's
  shadow price under HiGHS's own sign convention — negative when the ramp-up side binds, positive
  when the ramp-down side does.
- `model.Storage` is read by a solver for the first time, having been in the schema and
  solver-ignored since M1. Two nonnegative power columns per unit per period plus an explicit
  `soc` column, because the charge and discharge efficiencies enter the SoC row with *different*
  coefficients (`+eta_c` against `-1/eta_d`) — an asymmetry one signed column cannot express in a
  linear row. `StorageDispatchResult` reports `charge_mw`, `discharge_mw`, end-of-period `soc_mwh`
  and `soc_dual`. A unit settles on both sides of the market, and the settlement identity does not
  close if a dispatched one is left out.
- `opf.multiperiod_dc_opf(arr, cost_coeffs, n_periods, ...) -> MultiperiodSolution`, with
  `MultiperiodDuals`: the array-level builder, on `dc_opf`'s own row-family helpers rather than a
  second solver. The variable vector is two tiers, not `T` self-contained blocks —
  `T * (n_gen + n_demand + 3*n_storage)` period-major columns the quadratic Hessian covers
  exactly, then the free PWL variables — because `dc_opf` passes its Hessian over a prefix of the
  columns.
- `jobs`: `market.multiperiod` registered as a sixth kind, and `SolveRequest` now takes either a
  `network` **or** a `scenario`, resolved through the new `SolveRequest.resolved_scenario`. A
  horizon needs `Scenario.periods`, which a bare `Network` cannot supply.
- Oracle: **PyPSA** multi-period `optimize` with `StorageUnit` and
  `ramp_limit_up` / `ramp_limit_down`, on a 24-period rated case14 with a lossy unit and an
  asymmetric generator ramp limit both genuinely engaged. Measured worst-case residuals:
  objective 4.35e-13 relative, per-generator per-period dispatch 3.01e-4 MW, net storage power
  1.10e-4 MW, state of charge 1.25e-4 MWh, per-bus per-period LMP 4.24e-5 \$/MWh. Two limits of
  that oracle — PyPSA's transformer ratings, and the fixture's inability to tell the two
  efficiencies apart — are disclosed on the manual page rather than tolerated silently.
- Fixtures, derived at test time and committing no new files: `tests/_periods.py` (a 24-hour
  raised-cosine profile, 0.7x at hour 4 up to 1.2x twelve hours later, applied as a single
  system-wide curve — the two-archetype design it started from was measured infeasible against
  the derived ratings) and `tests/_storage.py` (one unit at 15% of the network's own total
  base-case load with a 4-hour duration, `soc_initial = 0.5`, deliberately asymmetric
  efficiencies).
- Documentation: the multiperiod manual and API page, `examples/10_multiperiod_market.py`, and
  `tests/unit/test_docs_registry_listing.py`, which pins the three places the jobs manual states
  the registry's contents against the registry itself — that hand-pasted list had gone two waves
  stale before anything checked it.

### Added — wave M4 (nodal market)

- `market.solve_nodal(scenario, options=None) -> MarketNodalResult`: a day-ahead nodal energy
  market cleared as a welfare LP/QP — generation cost minimised, demand value maximised —
  subject to the same linearised network `opf.dc_opf` solves, with per-bus LMPs and settlement.
  Built directly on `opf.dc_opf` and `opf.dc_opf.lmp_decomposition`, called verbatim rather
  than reimplemented.
- `model.Scenario(network)`: the self-contained clearing input, embedding the `Network` directly,
  mirroring `jobs.SolveRequest`'s own pattern rather than an id/path cross-reference — no such
  resolution mechanism exists anywhere else in this codebase.
- `Load.bid`: a `PolynomialBid | PiecewiseBid` discriminated union mirroring `GeneratorCost`
  field-for-field with one difference — direction. `bid is None` stays fixed demand, so every
  M1–M3 network behaves exactly as it did.
- Elastic demand inside `opf.dc_opf`, through two optional parameters (`demand_bid_coeffs`,
  `demand_pwl_bids`) that leave every M2/M3 caller unaffected: one new LP column per bid load,
  bounded `[load_p_min_mw, load_p_max_mw]` with no sign flip (the column is the load's own served
  demand, not a negative-bound pseudo-generator), a matching `-1`-signed term in the balance and
  PTDF flow-limit rows, and a **hypograph** encoding for a piecewise bid — the concave mirror of
  the convex epigraph already used for PWL generator costs. `OpfSolution.demand_dispatch_mw` and
  `demand_bound` are explicit new fields, never overloading the generator-side ones. `dc_opf`
  resolves the double-counting itself, removing each bid load's own historical contribution from
  the fixed RHS, so the caller passes `NetworkArrays` completely unmodified.
- `market.NonConcaveBidError`, raised before any HiGHS object is created for a bid whose marginal
  value is not non-increasing (a non-concave PWL sequence, or a polynomial bid with `v2 > 0`).
- `results`: `MarketNodalResult`, `LoadDispatchResult`. `MarketNodalResult.loads` carries one row
  for **every** load in the network, bid or not — a bid load's `p_mw` is its solved elastic
  dispatch, a fixed load keeps its own `Load.p_mw` with `bound_dual == 0.0` — matching the
  settlement identity's own derivation, which sums `LMP · p_d` over every load.
- Settlement: `total_load_payment`, `total_generator_receipts` and `congestion_rent`, each
  computed directly from prices and quantities rather than asserted equal to the others by
  construction, and proved against `-Σ_k μ_k · flow_k` on a hand-KKT-verified 2-bus case and
  independently on real multi-bus fixtures with derived bids.
- The price-taker reduction, proved rather than assumed: where every load's bid value exceeds
  every achievable price up to its own fixed historical demand, `solve_nodal`'s dispatch, duals
  and LMPs are identical to plain `opf.solve_dc_opf` on that same demand as fixed load.
- `NetworkArrays`: per-load identity (`load_ids`, `load_bus`, `load_p_min_pu` / `load_p_max_pu`),
  the same per-entity treatment generators already had.
- `jobs`: `market.nodal` registered as a fifth kind, with the non-`"Optimal"` status translation
  factored into a helper shared with `opf.dc`.
- Oracle: pandapower `rundcopp` via the **`sgen` framing** — each bid load dropped as a `load` row
  and rebuilt as a sign-flipped, negative-bound `sgen` (`min_p_mw = -p_mw, max_p_mw = 0`) whose
  poly-cost coefficients are the bid's own sign-flipped, proved exact against a hand KKT solve
  before any test was written. The more natural-looking `load`-row framing reproducibly fails to
  converge in `rundcopp`; the parity module's docstring records that precisely so a future reader
  does not have to rediscover it. Measured on case14 with every load bid: dispatch within 1e-6 MW,
  LMP within 1e-3 \$/MWh.
- `tests/_bids.py`: bid curves derived at test time from a fixture's own already-committed
  `Load.p_mw` and `Generator.cost` — marginal value descending linearly from
  `VOLL_PER_MWH = 10,000` \$/MWh at `p = 0` to that fixture's own generation-fleet max marginal
  cost at `p = load.p_mw` — the same no-new-fixture-data discipline `tests/_rated.py`
  established.
- Documentation: the nodal-market manual and API page, and `examples/09_nodal_market.py`.

### Added — wave M3 (DC optimal power flow, N-1 screening)

- `opf.solve_dc_opf(net, options=OpfDcOptions()) -> OpfDcResult`: cost-minimising DC optimal power
  flow over [HiGHS](https://highs.dev) — one column per generator bounded by its own declared
  `[p_min_mw, p_max_mw]`, one system-wide nodal-balance equality row whose dual is the energy
  component of every LMP, and one PTDF-based flow-limit row per branch, reusing the
  `numerics.ptdf` already parity-tested on its own. `opf.dc_opf.dc_opf` is the array-level solver.
  A pure LP with no Hessian at all when every generator's `c2` is exactly 0, transparently a
  convex QP via `Highs.passHessian` when one is not — every bundled OPF fixture carries genuine
  nonzero quadratic coefficients, so matching real fixture data needs the quadratic term, not just
  the linear one.
- Convex **piecewise-linear generator costs** through `dc_opf`'s `pwl_costs`: the standard
  segment/epigraph encoding — one free `cost_g` variable with objective coefficient 1, plus one
  inequality row per segment. It composes unchanged with the QP path, so one network may mix
  quadratic and PWL generators in the same solve. A non-convex breakpoint sequence raises
  `opf.NonConvexCostError` before any HiGHS object is created, rather than a
  wrong-but-optimal-looking answer; a degree-3-or-higher `PolynomialCost` raises
  `NotImplementedError` at cost extraction.
- `opf.dc_opf.lmp_decomposition(duals, ptdf) -> LmpBreakdown`: standalone and independent of
  `dc_opf` / `solve_dc_opf`, callable with any hand-built duals/PTDF pair, splitting every bus's
  price into a system-wide-uniform energy component and a congestion component (that bus's
  exposure to every binding flow-limit row). `solve_dc_opf` calls it to populate `OpfDcResult.lmp`.
- `OpfDcOptions.ac_check`: re-runs `pf.solve_ac` on the dispatched network — a deep copy with each
  in-service generator's `p_mw` overwritten, id-keyed, from the DC-OPF dispatch — and attaches a
  `FeasibilityReport` of thermal (`loading_pct > 100%`) and voltage violations. It reports; it
  does not re-dispatch. case14's own DC-OPF-optimal dispatch lands 3 buses outside their declared
  1.06 pu upper bound once AC-solved.
- `contingency.n1(net, options=None) -> N1Result`: N-1 branch-contingency screening as
  screen-then-confirm. `screen_n1` DC-solves the base case once, then estimates every other
  branch's post-outage flow from `numerics.lodf`, skipping bridge outages entirely since LODF is
  undefined where the outage disconnects the network; `confirm_n1` re-solves only what the screen
  flagged, against one deep copy whose `in_service` flag is flipped and restored per outage rather
  than a fresh copy each time (measured ~20x slower the naive way on case300). `N1Result` carries
  `outages` — per flagged branch: rating, LODF estimate, DC-re-solved flow, and whether the
  re-solve confirms a violation — and `bridge_branch_ids`. Branch outages only; generator
  outages, N-2+ and any redispatch on a violation are explicit carry-overs.
- The agreement guarantee: on all five bundled OPF fixtures with derived ratings, the
  screen-then-confirm pipeline's confirmed-violating outage set is **exactly** the set a
  brute-force sweep finds with no LODF pre-filter at all (case14 18, case_ieee30 34, case57 75,
  case118 166, case300 293) — it misses no confirmed violation the brute force catches, and
  confirms nothing the brute force would not.
- `results`: `OpfDcResult`, `GenDispatchResult`, `OpfBranchFlowResult`, `BusLmpResult`,
  `FeasibilityReport` with `ThermalViolation` and `VoltageViolation`, `N1Result`,
  `N1OutageResult`, `N1BranchFlag`.
- `jobs`: `opf.dc` and `n1` registered as kinds, plus two new failure codes, `INFEASIBLE_LP` and
  `UNBOUNDED_LP`, so a non-`"Optimal"` LP/QP comes back as a structured failure rather than a
  "successful" result carrying a meaningless dispatch. `solve_dc_opf` itself still never raises
  for one — it is reported through `OpfDcResult.status` / `message`, mirroring `pf.solve_ac`'s
  never-raise-on-non-convergence convention.
- `tests/_rated.py`: `rating_mva = max(1.2 * |base_case_p_from_mw|, 1.0)`, derived at test time
  from each fixture's own unmodified base-case DC dispatch. No bundled fixture carries a real
  `RATE_A` (every branch reads 0, MATPOWER's "unlimited" convention), so nothing had anything for
  a flow-limit row or a contingency screen to bind against. The first of this repository's
  derived-fixture helpers, and the discipline `tests/_bids.py`, `tests/_periods.py` and
  `tests/_storage.py` each followed after it.
- Fixture: `fixtures/matpower/derived/case14_pwl.m`, two of case14's five generators converted to
  convex piecewise-linear cost with the other three keeping their real quadratic coefficients.
  pandapower's `rundcopp` refuses to mix quadratic and piecewise costs anywhere in one network, so
  this fixture cannot be oracled by it at all; verification fell back to an independent
  lambda-iteration economic dispatch, which also surfaced a genuine LP degeneracy — two
  breakpoints tie in marginal cost, so how the two affected generators split their combined output
  has multiple optima. Asserted as an interval, not a false-precise split, with the other three
  generators and the total system cost uniquely pinned.
- Named as a real formulation difference rather than rounded into a looser tolerance:
  `opf.dc_opf`'s PTDF-based dispatch and pandapower's theta-based `rundcopp` are genuinely
  different formulations that happen to agree on every bundled fixture. `rundcopp` marks the
  slack-bus generator `controllable=False`, making its dispatch the network's balance residual;
  `dc_opf` makes every generator, that one included, a bounded decision variable. The two
  conditions under which they must agree are asserted directly in the parity suite, not assumed.
- Documentation: the DC-OPF and N-1 manual pages and their API pages, and
  `examples/08_opf_and_n1.py`.

### Added — wave M2 (power flow)

- `pf.solve_dc(net) -> DcPowerFlowResult`: DC power flow \(B'\theta = P - P_\text{shift}\)
  with phase-shifter injections, flows via \(B_f\), slack balance to the first in-service
  slack-bus generator (MATPOWER `rundcpf` semantics). `pf.dc.solve(arr) -> DcSolution` is the
  positional solver. Parity with pandapower `rundcpp` within 1e-9 on every fixture including
  case300.
- `results`: typed, id-keyed result models — `BusResult`, `BranchResult`, `GenResult`,
  `ResultProvenance` (engine, version, kind, solver, started_at, elapsed_s, options),
  `DcPowerFlowResult`, `AcPowerFlowResult` — with exact JSON round-trip and a positional
  `to_arrays()` view; `dc_result_from_arrays` builder.
- Fixtures: `case300.m` verbatim from MATPOWER with recorded sha256 and a licence note
  (public IEEE test data as distributed by MATPOWER); derived case14 variants under
  `fixtures/matpower/derived/` exercising effective bus roles, a slack without a generator and
  an island.
- Documentation site (this site): mkdocs-material with mkdocstrings API reference, manual
  pages for the model, file formats, numerics, power flow, results and the jobs API, mermaid
  architecture and data-model diagrams, condensed design decisions, CI job `docs`
  (`mkdocs build --strict`) and a GitHub Pages deploy workflow.
- `tests/unit/test_docstrings.py`: every public module, class, function and method in
  `mambo_power` must carry a docstring.
- `jobs`: the stateless, JSON-serialisable job surface (ADR-004) — `SolveRequest(kind,
  network, options, job_id)`, `SolveResult(kind, job_id, status, result, error, provenance,
  warnings)`, `StructuredError(code, message, issues, details)`, the `KINDS` registry
  (`KindSpec`, `register`, `kinds`) with `pf.ac` and `pf.dc`, and `run` / `run_json`. Every
  failure is a `status="failed"` result with a stable code (`UNKNOWN_KIND`, `BAD_OPTIONS`,
  `VALIDATION` with every issue, `NO_SLACK_GENERATOR`, `BAD_REQUEST`, `INTERNAL`); a
  non-converged power flow is `status="ok"` with `converged=False`; warnings emitted by the
  solve are attached as strings. Manual page with executed examples and API reference page.
- `pf.solve_ac(net, *, options=AcOptions()) -> AcPowerFlowResult`: sparse polar
  Newton-Raphson AC power flow (MATPOWER `newtonpf` formulation, `scipy.sparse.linalg.splu`),
  tolerance 1e-8 pu on the mismatch ∞-norm, flat or warm start (`init="auto"|"flat"`),
  reactive-limit enforcement with pandapower semantics (pin PV→PQ at the limit, never
  restore, slack never limited, ≤ `max_q_rounds` rounds); non-convergence is
  `converged=False`, never an exception. `pf.ac_newton.newton` is the positional solver;
  `results.ac_result_from_arrays` builds the typed result. Parity with pandapower `runpp` at
  machine precision on case14, case_ieee30, case57, case118 (Q-limits on) and case300
  (Q-limits off and on), identical pinned sets; MATPOWER stored columns within 2e-3 pu /
  0.5 deg outside the documented exclusions; case300 cold solve measured and echoed in CI.
- Effective bus roles (`numerics.effective_roles`, `EffectiveRoles`): a PV bus without an
  in-service generator solves as PQ, a slack without one raises `NoSlackGeneratorError`, the
  last in-service generator's setpoint wins with a `SetpointConflictWarning` when setpoints
  differ. Both solvers and `BusResult.role_effective` use the effective roles.
- Island repair in importers (`model.repair_islands`, `model.repair_islands_entities`):
  buses unreachable from the slack and their elements are deactivated before validation,
  reported as typed `ImportIssue(code="ISLAND_DEACTIVATED", bus_ids, element_ids)`; the
  model itself still rejects islands (`DISCONNECTED_BUS`). `io.matpower.load_with_report` /
  `loads_with_report` return an `ImportReport` of typed issues; the `load_with_warnings`
  strings are the same entries rendered `CODE: message`.
- `examples/`: seven runnable scripts (load and validate, AC power flow, DC power flow, jobs
  API, roles and islands, network matrices, results and export), each run by
  `tests/unit/test_examples_run.py` and by the `examples` CI job, and embedded byte-for-byte
  in the documentation's Examples gallery.
- Documentation: the power-flow manual covers the AC solver as shipped (options, formulation,
  Q-limit loop diagram, warm start, parity and timing tables); the model and formats manuals
  document `ImportIssue`, `ImportReport` and `repair_islands`; getting started runs an AC
  power flow.

### Added — wave M1 (substrate)

- uv-managed `src/` layout with hatchling; ruff, mypy `--strict`, pytest tiers `unit` /
  `parity` / `property`; GitHub Actions CI on Ubuntu, macOS and Windows (Python 3.12) plus
  Ubuntu 3.11 and 3.13; pandapower and PyPSA installed as development-only oracles.
- `model`: pydantic v2 `Network` with `Bus`, `Branch`, `Generator` (optional
  `PolynomialCost` / `PiecewiseCost`), `Load`, `Shunt`, `Storage`, `Zone`, `Geo`. Physical
  units (MW, MVAr, kV, MWh, degrees), branch impedances in pu on `base_mva`, stable string
  ids, `in_service` booleans, `schema_version = 1`.
- All-issues validation: `NetworkValidationError` carrying every `ValidationIssue(code,
  path, message)` with codes `NO_SLACK`, `MULTIPLE_SLACK`, `DISCONNECTED_BUS`,
  `DUPLICATE_ID`, `DANGLING_REF`, `BAD_BASE`, `BAD_RANGE`; `validate_network` as the public
  re-check; non-finite floats rejected; unknown fields rejected.
- `Network.json_schema()` with a committed snapshot test; native JSON round-trip is identity
  on every fixture (`io.native`: `load`, `loads`, `save`, `dumps`).
- `io.matpower`: `load`, `loads`, `load_with_warnings`, `loads_with_warnings` for MATPOWER
  caseformat v2 files including `gencost` (MODEL 1 and 2, `2 * ngen` rows tolerated);
  `BASE_KV <= 0` repaired to 1.0 with a warning; bus type 4 mapped to an out-of-service bus;
  BOM and CRLF tolerated; `MatpowerImportError` with codes `MISSING_BASE_MVA`,
  `MISSING_SECTION`, `UNTERMINATED_MATRIX`, `BAD_NUMBER`, `BAD_ROW`. Parity with pandapower
  `from_mpc` on case14, case30, case_ieee30, case57, case118.
- `numerics`: `NetworkArrays` (in-service positional view, the single per-unit conversion
  site), `ybus` / `yf_yt` (MATPOWER `makeYbus`), `bbus` / `bf` / `p_shift` (`makeBdc`),
  `ptdf` (sparse LU, zero slack column), `lodf` with `NaN` bridge columns, and
  graph-theoretic `bridges`. Ybus parity with pandapower within 1e-9; PTDF/LODF checked
  against dense re-derivation and brute-force outages; hypothesis property tests over random
  radial and meshed networks.
- Packaging: `uv build` wheel ships only the package and `py.typed`; sdist carries `tests/`
  and `fixtures/`; CI installs both into clean virtual environments and loads case14.
- Fixtures: `case14`, `case30`, `case_ieee30`, `case57`, `case118` with `PROVENANCE.md` and
  `SOURCES.md`.

### Changed

- The API reference renders every pydantic model's fields. Result and options models put their
  prose in `Field(description=...)`, which is a call argument rather than a docstring, so the
  documentation generator saw undocumented attributes and dropped them: `mambo_power.results`
  published two field entries across every result type on it, and `MarketZonalResult`'s field
  names occurred nowhere on the site. They now render with their descriptions, and an attribute's
  shown default is the field's actual default rather than the whole `Field(...)` call. M6.
- `opf.dc_opf`'s cost/bid extraction and both convexity guards are one shared helper, so the
  nodal, multiperiod, zonal and redispatch builders cannot get them subtly different — they do
  not each implement them. Extracted and proved behaviour-preserving before any zonal row was
  written; no public behaviour changed. M6.
- `Scenario.periods` accepts at most 200 entries and `MarketZonalOptions.corridors` at most 500.
  An unbounded list in a network-facing model is an unbounded solve; 200 periods is more than
  eight days at hourly resolution, and 500 corridors is a complete graph on 32 zones. The corridor
  list is echoed back in `provenance.options`, so its bound holds the response down too. Both are
  listed on [Manual > Jobs API](manual/jobs.md#request-size-bounds). M6.
- `jobs.SolveRequest` now takes **exactly one** of `network` and `scenario`; neither or both is a
  `ValueError`, and `BAD_REQUEST` through `run_json`. A request carrying only a `network` — every
  M2–M4 caller, and every stored request JSON — keeps working unchanged, wrapped as a
  single-period `Scenario` by `resolved_scenario`. That wrap left the individual runners as a
  result, and every kind now runs through one uniform `Runner`. M5.
- `opf.dc_opf`'s nodal-balance, PTDF flow-limit, epigraph and hypograph row families are built by
  internal helpers rather than inline, so `opf.multiperiod_dc_opf` calls the same code once per
  period instead of carrying a second copy of it. Extracted and proved behaviour-preserving
  before any multiperiod row existed; no public behaviour changed. M5.
- `opf.gen_cost_coeffs` and `market.load_bid_coeffs` are public, so `market.nodal` and
  `market.multiperiod` share one cost extraction and one bid extraction rather than each carrying
  its own copy. M4 for the generator side, M5 for the demand side.
- A quadratic `GeneratorCost` with `c2 < 0` is now rejected as `NonConvexCostError` before any
  solve. M3 checked convexity only for piecewise costs; the quadratic gap was found while
  building the demand-side guard and closed in the same commit, rather than shipping an
  asymmetric check. M4.
- The settlement identity on [the nodal-market page](manual/market.md#settlement) is stated in
  its narrow form, `congestion_rent == -Σ_k μ_k · flow_k`, which is exact only on a network with
  no phase-shifting transformer and no bus shunt conductance — every fixture M4's own tests use,
  but not `case300`. The general form, with both correction terms, is on [the multiperiod
  page](manual/multiperiod.md#settlement). The value was always right; it is the *name* that is
  narrower than the number. M5.
- MATPOWER repair warnings are now `CODE: message` strings (`BASE_KV_REPLACED`,
  `GENCOST_REACTIVE_IGNORED`, `ISLAND_DEACTIVATED`) — M2, with island repair.
- The typed import-issue record is `model.ImportIssue` (`ImportIssueCode`); it was briefly
  named `ImportWarning` on the wave branch, which shadowed the Python built-in. Behaviour is
  unchanged.
- `fixtures/matpower/PROVENANCE.md`, case300: the reference-solution wording now carries the
  measured residual against the AC solver (8.5e-3 pu worst, 11 of 300 buses beyond 2e-3) and
  withdraws the earlier "0.107 pu" and "pandapower cannot converge with Q-limits" figures,
  which came from a tap-side defect in the research's oracle copy, not from the data.

[Unreleased]: https://github.com/mambo10005/mambo-power/commits/epic/01-foundation
