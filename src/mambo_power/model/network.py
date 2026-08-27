"""The :class:`Network` root model and its cross-entity invariants."""

from collections import deque
from collections.abc import Callable, Sequence
from typing import Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mambo_power.model.entities import (
    Branch,
    Bus,
    Generator,
    Load,
    Shunt,
    Storage,
    Zone,
)
from mambo_power.model.errors import NetworkValidationError, ValidationCode, ValidationIssue


class Network(BaseModel):
    """A complete power network. Construction validates every invariant in one pass.

    Any violation raises :class:`NetworkValidationError` listing every issue found. Mutating
    a constructed network does not re-validate; call :func:`validate_network` to re-check.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, allow_inf_nan=False)

    schema_version: Literal[1] = 1
    base_mva: float = Field(description="System MVA base for all per-unit quantities. Must be > 0.")
    buses: list[Bus] = Field(default_factory=list)
    branches: list[Branch] = Field(default_factory=list)
    generators: list[Generator] = Field(default_factory=list)
    loads: list[Load] = Field(default_factory=list)
    shunts: list[Shunt] = Field(default_factory=list)
    storage: list[Storage] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        issues = validate_network(self)
        if issues:
            raise NetworkValidationError(issues)
        return self

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """The JSON schema of the native file format (snapshot-tested)."""
        return cls.model_json_schema()


class _HasId(Protocol):
    id: str


class _AtBus(Protocol):
    id: str
    bus: str


_AddIssue = Callable[[ValidationCode, str, str], None]


def validate_network(net: Network) -> list[ValidationIssue]:
    """Run every cross-entity invariant and return all issues found (empty = valid)."""
    issues: list[ValidationIssue] = []

    def add(code: ValidationCode, path: str, message: str) -> None:
        issues.append(ValidationIssue(code=code, path=path, message=message))

    collections: list[tuple[str, Sequence[_HasId]]] = [
        ("buses", net.buses),
        ("branches", net.branches),
        ("generators", net.generators),
        ("loads", net.loads),
        ("shunts", net.shunts),
        ("storage", net.storage),
        ("zones", net.zones),
    ]
    for name, items in collections:
        seen: set[str] = set()
        for index, item in enumerate(items):
            if item.id in seen:
                add("DUPLICATE_ID", f"{name}[{index}].id", f'duplicate id "{item.id}" in {name}')
            seen.add(item.id)

    if not net.base_mva > 0:
        add("BAD_BASE", "base_mva", f"base_mva must be > 0, got {net.base_mva}")
    for index, bus in enumerate(net.buses):
        if not bus.base_kv > 0:
            add(
                "BAD_BASE",
                f"buses[{index}].base_kv",
                f'bus "{bus.id}": base_kv must be > 0, got {bus.base_kv}',
            )

    bus_ids = {bus.id for bus in net.buses}
    zone_ids = {zone.id for zone in net.zones}
    for index, bus in enumerate(net.buses):
        if bus.zone is not None and bus.zone not in zone_ids:
            add(
                "DANGLING_REF",
                f"buses[{index}].zone",
                f'bus "{bus.id}": zone references missing zone "{bus.zone}"',
            )
    for index, branch in enumerate(net.branches):
        for field in ("from_bus", "to_bus"):
            ref: str = getattr(branch, field)
            if ref not in bus_ids:
                add(
                    "DANGLING_REF",
                    f"branches[{index}].{field}",
                    f'branch "{branch.id}": {field} references missing bus "{ref}"',
                )
    at_bus: list[tuple[str, Sequence[_AtBus]]] = [
        ("generators", net.generators),
        ("loads", net.loads),
        ("shunts", net.shunts),
        ("storage", net.storage),
    ]
    for name, elements in at_bus:
        for index, element in enumerate(elements):
            if element.bus not in bus_ids:
                add(
                    "DANGLING_REF",
                    f"{name}[{index}].bus",
                    f'{name} "{element.id}": bus references missing bus "{element.bus}"',
                )

    for index, bus in enumerate(net.buses):
        if bus.v_min_pu is not None and bus.v_max_pu is not None and bus.v_min_pu > bus.v_max_pu:
            add(
                "BAD_RANGE",
                f"buses[{index}].v_min_pu",
                f'bus "{bus.id}": v_min_pu {bus.v_min_pu} > v_max_pu {bus.v_max_pu}',
            )
    for index, branch in enumerate(net.branches):
        if branch.from_bus == branch.to_bus:
            add(
                "BAD_RANGE",
                f"branches[{index}].to_bus",
                f'branch "{branch.id}": from_bus and to_bus are both "{branch.from_bus}"',
            )
        if branch.tap_ratio is not None and not branch.tap_ratio > 0:
            add(
                "BAD_RANGE",
                f"branches[{index}].tap_ratio",
                f'branch "{branch.id}": tap_ratio must be > 0, got {branch.tap_ratio}',
            )
        if branch.r == 0 and branch.x == 0:
            add(
                "BAD_RANGE",
                f"branches[{index}].x",
                f'branch "{branch.id}": r and x are both 0 (no series impedance)',
            )
        if branch.rating_mva is not None and not branch.rating_mva > 0:
            add(
                "BAD_RANGE",
                f"branches[{index}].rating_mva",
                f'branch "{branch.id}": rating_mva must be > 0 when given, got {branch.rating_mva}',
            )
    for index, gen in enumerate(net.generators):
        if gen.p_min_mw > gen.p_max_mw:
            add(
                "BAD_RANGE",
                f"generators[{index}].p_min_mw",
                f'generator "{gen.id}": p_min_mw {gen.p_min_mw} > p_max_mw {gen.p_max_mw}',
            )
        if gen.q_min_mvar > gen.q_max_mvar:
            add(
                "BAD_RANGE",
                f"generators[{index}].q_min_mvar",
                f'generator "{gen.id}": q_min_mvar {gen.q_min_mvar} > q_max_mvar {gen.q_max_mvar}',
            )
        for field in ("ramp_up_mw", "ramp_down_mw"):
            ramp: float | None = getattr(gen, field)
            if ramp is not None and not ramp > 0:
                add(
                    "BAD_RANGE",
                    f"generators[{index}].{field}",
                    f'generator "{gen.id}": {field} must be > 0 when given, got {ramp}',
                )
        if gen.cost is not None and gen.cost.kind == "polynomial" and not gen.cost.coefficients:
            add(
                "BAD_RANGE",
                f"generators[{index}].cost.coefficients",
                f'generator "{gen.id}": polynomial cost needs at least one coefficient',
            )
        if gen.cost is not None and gen.cost.kind == "piecewise":
            p_values = [p for p, _ in gen.cost.points]
            if len(p_values) < 2:
                add(
                    "BAD_RANGE",
                    f"generators[{index}].cost.points",
                    f'generator "{gen.id}": piecewise cost needs at least two points',
                )
            elif any(
                later <= earlier for earlier, later in zip(p_values, p_values[1:], strict=False)
            ):
                add(
                    "BAD_RANGE",
                    f"generators[{index}].cost.points",
                    f'generator "{gen.id}": piecewise cost p_mw values must be strictly increasing',
                )
    for index, load in enumerate(net.loads):
        if load.bid is not None and load.bid.kind == "polynomial" and not load.bid.coefficients:
            add(
                "BAD_RANGE",
                f"loads[{index}].bid.coefficients",
                f'load "{load.id}": polynomial bid needs at least one coefficient',
            )
        if load.bid is not None and load.bid.kind == "piecewise":
            p_values = [p for p, _ in load.bid.points]
            if len(p_values) < 2:
                add(
                    "BAD_RANGE",
                    f"loads[{index}].bid.points",
                    f'load "{load.id}": piecewise bid needs at least two points',
                )
            elif any(
                later <= earlier for earlier, later in zip(p_values, p_values[1:], strict=False)
            ):
                add(
                    "BAD_RANGE",
                    f"loads[{index}].bid.points",
                    f'load "{load.id}": piecewise bid p_mw values must be strictly increasing',
                )
    for index, unit in enumerate(net.storage):
        if not 0.0 <= unit.soc_initial <= 1.0:
            add(
                "BAD_RANGE",
                f"storage[{index}].soc_initial",
                f'storage "{unit.id}": soc_initial must be in [0, 1], got {unit.soc_initial}',
            )
        for field in ("efficiency_charge", "efficiency_discharge"):
            value: float = getattr(unit, field)
            if not 0.0 < value <= 1.0:
                add(
                    "BAD_RANGE",
                    f"storage[{index}].{field}",
                    f'storage "{unit.id}": {field} must be in (0, 1], got {value}',
                )
        # Sizing, checked here for the same reason ramp_up_mw/ramp_down_mw are: a solver reads
        # these now. Zero is the dangerous half -- an unsized unit clears "Optimal" with every
        # storage row trivially satisfied and the unit silently inert, a confidently wrong-shaped
        # answer; a negative one merely reaches HiGHS as an empty [0, negative] bound and comes
        # back "Infeasible" with nothing naming the cause. Both are caught here instead.
        for field in ("p_max_mw", "energy_mwh"):
            size: float = getattr(unit, field)
            if not size > 0:
                add(
                    "BAD_RANGE",
                    f"storage[{index}].{field}",
                    f'storage "{unit.id}": {field} must be > 0, got {size}',
                )

    slack_buses = [bus for bus in net.buses if bus.type == "slack" and bus.in_service]
    if not slack_buses:
        add("NO_SLACK", "buses", "no in-service slack bus defined")
    elif len(slack_buses) > 1:
        listed = ", ".join(f'"{bus.id}"' for bus in slack_buses)
        add(
            "MULTIPLE_SLACK",
            "buses",
            f"expected exactly one in-service slack bus, found {len(slack_buses)}: {listed}",
        )

    _check_connectivity(net, slack_buses, add)
    return issues


def _check_connectivity(
    net: Network,
    slack_buses: Sequence[Bus],
    add: _AddIssue,
) -> None:
    """DISCONNECTED_BUS: every in-service bus must reach the slack over live branches."""
    live = {bus.id for bus in net.buses if bus.in_service}
    if not live:
        return
    if slack_buses:
        start = slack_buses[0].id
    else:
        start = next(bus.id for bus in net.buses if bus.in_service)

    adjacency: dict[str, list[str]] = {bus_id: [] for bus_id in live}
    for branch in net.branches:
        if branch.in_service and branch.from_bus in live and branch.to_bus in live:
            adjacency[branch.from_bus].append(branch.to_bus)
            adjacency[branch.to_bus].append(branch.from_bus)

    reached = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in adjacency[current]:
            if neighbour not in reached:
                reached.add(neighbour)
                queue.append(neighbour)

    for index, bus in enumerate(net.buses):
        if bus.in_service and bus.id not in reached:
            add(
                "DISCONNECTED_BUS",
                f"buses[{index}]",
                f'bus "{bus.id}" is not connected to bus "{start}" over in-service branches',
            )
