"""Phase-shifter flow-fix fixture (M7 F1 / M8 A19; task-shifter-flow-fix.plan.md T4).

No bundled MATPOWER case carries a phase shifter (M8 research), so this hand-built three-bus
loop is the sole fixture exercising ``numerics.bbus.flow_from_ptdf``'s ``- p_shift`` correction.
Bus ``b1`` (slack) hosts the cheap generator ``g1``; bus ``b3`` hosts the dear generator ``g3``;
bus ``b2`` carries a 100 MW fixed load and is the phase shifter branch ``t12``'s "to" end. Two
parallel paths carry power from ``b1`` to the load at ``b2`` -- directly via ``t12``, and the
long way via ``l13`` then ``l23`` through ``b3`` -- so even a single generator's dispatch splits
across the loop according to impedance and shift angle exactly as physics (and ``pf.solve_dc`` /
PyPSA's ``lpf()``) predicts. That loop-flow split is exactly what ``opf.dc_opf``,
``opf.solve_dc_opf`` and ``market._clearing`` got wrong whenever ``shift_deg != 0`` (measured a
~87 MW KCL violation at ``b2`` pre-fix on a generously-rated ±5° shifter, M8 finding F1 / A19).

:func:`shifter_loop_network` is generously rated by default (every branch's ``rating_mva`` is
``None`` -- unlimited, ``Branch.rating_mva``'s own field description) so no flow-limit row binds
and most tests built on it isolate the shift-formula bug from the rating logic entirely; pass
``t12_rating_mva`` to bind the shifter branch specifically (used by the test that confirms
``dc_opf``'s own flow-limit row keeps the LP's dispatch within the *true* physical limit).
"""

from __future__ import annotations

from mambo_power.model import Branch, Bus, Generator, Load, Network, PolynomialCost

LOAD_P_MW = 100.0
"""The fixed load at b2 every test in this module dispatches against."""

G1_C1 = 10.0
"""g1's linear cost, $/MWh -- cheap, at the slack bus b1."""

G3_C1 = 30.0
"""g3's linear cost, $/MWh -- dear, at b3, three times g1's -- the merit order that makes which
generator serves the load (and hence the loop flow split) sensitive to the shift angle."""

GEN_P_MAX_MW = 300.0
"""Wide enough above LOAD_P_MW that neither generator's own bound ever binds -- only the
shifter's rating (when set) or the merit order decides the dispatch."""


def shifter_loop_network(shift_deg: float, *, t12_rating_mva: float | None = None) -> Network:
    """Three-bus loop, one phase shifter (``t12``, ``b1`` -> ``b2``): cheap gen ``g1`` at the
    slack bus ``b1``, dear gen ``g3`` at ``b3``, a 100 MW fixed load at ``b2``. Every branch is
    unrated except optionally ``t12``; every generator is bounded ``[0, 300]`` MW, wide enough
    that the load is always servable without either generator's own bound binding.
    """

    def gen(gid: str, bus: str, c1: float) -> Generator:
        return Generator(
            id=gid,
            bus=bus,
            p_mw=0.0,
            q_mvar=0.0,
            p_min_mw=0.0,
            p_max_mw=GEN_P_MAX_MW,
            q_min_mvar=0.0,
            q_max_mvar=0.0,
            v_set_pu=1.0,
            cost=PolynomialCost(coefficients=[c1, 0.0]),
        )

    return Network(
        base_mva=100.0,
        buses=[
            Bus(id="b1", base_kv=138.0, type="slack"),
            Bus(id="b2", base_kv=138.0, type="pq"),
            Bus(id="b3", base_kv=138.0, type="pv"),
        ],
        branches=[
            Branch(
                id="t12",
                from_bus="b1",
                to_bus="b2",
                r=0.0,
                x=0.1,
                b=0.0,
                shift_deg=shift_deg,
                rating_mva=t12_rating_mva,
            ),
            Branch(id="l23", from_bus="b2", to_bus="b3", r=0.0, x=0.1, b=0.0),
            Branch(id="l13", from_bus="b1", to_bus="b3", r=0.0, x=0.1, b=0.0),
        ],
        generators=[gen("g1", "b1", G1_C1), gen("g3", "b3", G3_C1)],
        loads=[Load(id="d2", bus="b2", p_mw=LOAD_P_MW, q_mvar=0.0)],
    )


def dispatched_network(net: Network, dispatch: dict[str, float]) -> Network:
    """Deep copy of ``net`` with each generator's ``p_mw`` overwritten from ``dispatch``
    (id-keyed) -- the same construction ``opf.solve_dc_opf``'s own ``ac_check`` builds (its
    module docstring), used here to get an independent ``pf.solve_dc`` readback of an OPF/market
    dispatch on the shifter loop.
    """
    copy = net.model_copy(deep=True)
    for gen in copy.generators:
        gen.p_mw = dispatch[gen.id]
    return copy
