"""``NetworkArrays``: the positional, per-unit view of a :class:`~mambo_power.model.Network`.

This is the *only* place in the package that holds positional indices and the *single* site
where physical units (MW, MVAr, MVA) are divided by ``base_mva`` (wave M1 design items 1
and 7). Every matrix builder in :mod:`mambo_power.numerics` consumes this view; nothing else
in the package divides by ``base_mva``.

Scope: the **in-service subset**. Out-of-service buses are dropped, and so is every branch,
generator, load or shunt that is itself out of service *or* attached to a dropped bus. The
network's own validation guarantees the surviving buses form one connected component with
exactly one slack.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from mambo_power.model import Network

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

BUS_TYPE_CODE = {"pq": 1, "pv": 2, "slack": 3}
"""MATPOWER bus type codes used in :attr:`NetworkArrays.bus_type`."""


@dataclass(frozen=True)
class NetworkArrays:
    """Frozen positional arrays over the in-service subset of a network, in per unit.

    Positions are 0-based. ``bus_ids[i]`` is the id at bus position ``i``; ``branch_ids[k]``
    and ``gen_ids[g]`` likewise. Order follows the network's collection order with the
    excluded elements removed.
    """

    base_mva: float

    bus_ids: list[str]
    bus_index: dict[str, int]
    n_bus: int
    slack: int
    bus_type: IntArray
    """1 = pq, 2 = pv, 3 = slack, as declared on the bus."""

    branch_ids: list[str]
    branch_index: dict[str, int]
    n_branch: int
    f: IntArray
    t: IntArray
    r: FloatArray
    x: FloatArray
    b: FloatArray
    """Total line charging susceptance per branch (pu); builders apply ``b / 2`` per end."""
    tap: FloatArray
    """Tap ratio magnitude on the from side; 1.0 where the branch has none."""
    shift_rad: FloatArray
    rating_pu: FloatArray
    """Thermal rating in pu of ``base_mva``; ``inf`` where the branch has none."""

    p_load_pu: FloatArray
    q_load_pu: FloatArray
    g_shunt_pu: FloatArray
    """Shunt conductance per bus in pu (MATPOWER GS sign: positive consumes)."""
    b_shunt_pu: FloatArray
    """Shunt susceptance per bus in pu (MATPOWER BS sign: positive injects)."""

    p_gen_pu: FloatArray
    q_gen_pu: FloatArray
    p_min_pu: FloatArray
    p_max_pu: FloatArray
    q_min_pu: FloatArray
    q_max_pu: FloatArray
    v_set: FloatArray
    """First in-service generator's ``v_set_pu`` at each bus; 1.0 where there is none."""

    gen_ids: list[str] = field(default_factory=list)
    gen_bus: IntArray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    gen_p_pu: FloatArray = field(default_factory=lambda: np.zeros(0))
    gen_q_pu: FloatArray = field(default_factory=lambda: np.zeros(0))
    gen_p_min_pu: FloatArray = field(default_factory=lambda: np.zeros(0))
    gen_p_max_pu: FloatArray = field(default_factory=lambda: np.zeros(0))
    gen_q_min_pu: FloatArray = field(default_factory=lambda: np.zeros(0))
    gen_q_max_pu: FloatArray = field(default_factory=lambda: np.zeros(0))
    gen_v_set: FloatArray = field(default_factory=lambda: np.zeros(0))

    load_ids: list[str] = field(default_factory=list)
    load_bus: IntArray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    load_p_min_pu: FloatArray = field(default_factory=lambda: np.zeros(0))
    load_p_max_pu: FloatArray = field(default_factory=lambda: np.zeros(0))
    """Per-load ``[0, p_mw]`` bound in pu: the natural bound for a bid-load's demand
    dispatch is zero up to its own fixed historical ``p_mw``. Built uniformly for every
    in-service load regardless of ``Load.bid`` — ``Load`` carries no
    ``p_min_mw``/``p_max_mw`` fields to mirror the generator-side source data, and this bound
    formula does not depend on bid presence; whether/how a given load's bound is actually used
    by ``opf.dc_opf`` is decided per-load elsewhere, not here. ``p_load_pu``/``q_load_pu`` (the
    bus aggregate) are untouched by this addition."""

    @classmethod
    def from_network(cls, net: Network) -> NetworkArrays:
        """Build the in-service positional view; the one pu-conversion site."""
        base = float(net.base_mva)

        live_buses = [bus for bus in net.buses if bus.in_service]
        bus_ids = [bus.id for bus in live_buses]
        bus_index = {bus_id: i for i, bus_id in enumerate(bus_ids)}
        n_bus = len(bus_ids)
        slack_positions = [i for i, bus in enumerate(live_buses) if bus.type == "slack"]
        if len(slack_positions) != 1:
            raise ValueError(
                f"expected exactly one in-service slack bus, found {len(slack_positions)}"
            )
        bus_type = np.fromiter(
            (BUS_TYPE_CODE[bus.type] for bus in live_buses), dtype=np.int64, count=n_bus
        )

        branches = [
            br
            for br in net.branches
            if br.in_service and br.from_bus in bus_index and br.to_bus in bus_index
        ]
        n_branch = len(branches)
        branch_ids = [br.id for br in branches]
        branch_index = {br_id: k for k, br_id in enumerate(branch_ids)}
        f = np.fromiter((bus_index[br.from_bus] for br in branches), np.int64, n_branch)
        t = np.fromiter((bus_index[br.to_bus] for br in branches), np.int64, n_branch)
        r = np.fromiter((br.r for br in branches), np.float64, n_branch)
        x = np.fromiter((br.x for br in branches), np.float64, n_branch)
        b = np.fromiter((br.b for br in branches), np.float64, n_branch)
        tap = np.fromiter(
            (1.0 if br.tap_ratio is None else br.tap_ratio for br in branches),
            np.float64,
            n_branch,
        )
        shift_rad = np.fromiter(
            (0.0 if br.shift_deg is None else math.radians(br.shift_deg) for br in branches),
            np.float64,
            n_branch,
        )
        rating_pu = np.fromiter(
            (math.inf if br.rating_mva is None else br.rating_mva / base for br in branches),
            np.float64,
            n_branch,
        )

        def per_bus(pairs: list[tuple[int, float]]) -> FloatArray:
            positions = np.fromiter((p for p, _ in pairs), np.int64, len(pairs))
            values = np.fromiter((v for _, v in pairs), np.float64, len(pairs))
            summed = np.asarray(
                np.bincount(positions, weights=values, minlength=n_bus), dtype=np.float64
            )
            return summed / base

        loads = [ld for ld in net.loads if ld.in_service and ld.bus in bus_index]
        p_load_pu = per_bus([(bus_index[ld.bus], ld.p_mw) for ld in loads])
        q_load_pu = per_bus([(bus_index[ld.bus], ld.q_mvar) for ld in loads])

        n_load = len(loads)
        load_bus = np.fromiter((bus_index[ld.bus] for ld in loads), np.int64, n_load)

        def per_load(values: list[float]) -> FloatArray:
            return np.fromiter(values, np.float64, n_load) / base

        shunts = [sh for sh in net.shunts if sh.in_service and sh.bus in bus_index]
        g_shunt_pu = per_bus([(bus_index[sh.bus], sh.g_mw) for sh in shunts])
        b_shunt_pu = per_bus([(bus_index[sh.bus], sh.b_mvar) for sh in shunts])

        gens = [g for g in net.generators if g.in_service and g.bus in bus_index]
        n_gen = len(gens)
        gen_bus = np.fromiter((bus_index[g.bus] for g in gens), np.int64, n_gen)
        p_gen_pu = per_bus([(bus_index[g.bus], g.p_mw) for g in gens])
        q_gen_pu = per_bus([(bus_index[g.bus], g.q_mvar) for g in gens])
        p_min_pu = per_bus([(bus_index[g.bus], g.p_min_mw) for g in gens])
        p_max_pu = per_bus([(bus_index[g.bus], g.p_max_mw) for g in gens])
        q_min_pu = per_bus([(bus_index[g.bus], g.q_min_mvar) for g in gens])
        q_max_pu = per_bus([(bus_index[g.bus], g.q_max_mvar) for g in gens])
        v_set = np.ones(n_bus)
        seen: set[int] = set()
        for g in gens:
            position = bus_index[g.bus]
            if position not in seen:
                seen.add(position)
                v_set[position] = g.v_set_pu

        def per_gen(values: list[float]) -> FloatArray:
            return np.fromiter(values, np.float64, n_gen) / base

        return cls(
            base_mva=base,
            bus_ids=bus_ids,
            bus_index=bus_index,
            n_bus=n_bus,
            slack=slack_positions[0],
            bus_type=bus_type,
            branch_ids=branch_ids,
            branch_index=branch_index,
            n_branch=n_branch,
            f=f,
            t=t,
            r=r,
            x=x,
            b=b,
            tap=tap,
            shift_rad=shift_rad,
            rating_pu=rating_pu,
            p_load_pu=p_load_pu,
            q_load_pu=q_load_pu,
            g_shunt_pu=g_shunt_pu,
            b_shunt_pu=b_shunt_pu,
            p_gen_pu=p_gen_pu,
            q_gen_pu=q_gen_pu,
            p_min_pu=p_min_pu,
            p_max_pu=p_max_pu,
            q_min_pu=q_min_pu,
            q_max_pu=q_max_pu,
            v_set=v_set,
            gen_ids=[g.id for g in gens],
            gen_bus=gen_bus,
            gen_p_pu=per_gen([g.p_mw for g in gens]),
            gen_q_pu=per_gen([g.q_mvar for g in gens]),
            gen_p_min_pu=per_gen([g.p_min_mw for g in gens]),
            gen_p_max_pu=per_gen([g.p_max_mw for g in gens]),
            gen_q_min_pu=per_gen([g.q_min_mvar for g in gens]),
            gen_q_max_pu=per_gen([g.q_max_mvar for g in gens]),
            gen_v_set=np.fromiter((g.v_set_pu for g in gens), np.float64, n_gen),
            load_ids=[ld.id for ld in loads],
            load_bus=load_bus,
            load_p_min_pu=np.zeros(n_load),
            load_p_max_pu=per_load([ld.p_mw for ld in loads]),
        )
