"""pandapower JSON (``pp.to_json`` / ``pp.from_json``) importer and exporter (wave M8, W1/W2).

pandapower is imported lazily inside the functions that need it, so ``mambo_power`` itself
keeps its zero-optional-dependency import (R9). Every conversion is *best effort + report*
(design item D1): anything the other side cannot hold is dropped or repaired **and** named in
the returned :class:`~mambo_power.io.report.ImportReport` /
:class:`~mambo_power.io.report.ExportReport` with the element id and the field. An empty
report means the conversion was lossless. Nothing is logged or printed.

Tables read on import: ``bus``, ``ext_grid``, ``gen``, ``sgen``, ``load``, ``shunt``, ``line``,
``trafo``, ``poly_cost``, ``pwl_cost``. Results tables (``res_*``) are neither read nor written
(the wave's "Not doing"; M8 critic finding 10): a bus's stored ``vm_pu``/``va_deg`` does not
travel through this format except for the slack, whose state is the ``ext_grid`` setpoint; the
export names every other bus that had one (``FIELD_DROPPED``). Every other non-empty table
(``trafo3w``, ``switch``, ``impedance``, ``ward``, ``xward``, ``dcline``, ``storage``, ...) is
dropped row by row with ``ELEMENT_DROPPED``.

Unit conventions (measured on pandapower 3.3.0 against ``fixtures/matpower/case14.m``,
``record/m8-research.md`` §1; ``Zb = vn_kv(from)² / sn_mva``):

* line: ``r = r_ohm_per_km · length / parallel / Zb`` (same for ``x``);
  ``b = 2π·f_hz · c_nf_per_km·1e-9 · length · parallel · Zb``;
  ``rating_mva = max_i_ka · df · parallel · √3 · vn_kv(from)``;
* trafo: ``z = vk_percent/100 · sn_mva/sn_trafo · (vn_lv_kv/vn(lv bus))² / parallel``,
  ``r`` from ``vkr_percent`` the same way, ``x = √(z² − r²)``;
  ``tap_ratio = (vn_hv_kv/vn(hv bus)) / (vn_lv_kv/vn(lv bus))`` after the tap changer has
  scaled the tapped winding (``1 + (tap_pos − tap_neutral)·tap_step_percent/100`` for a
  ``Ratio`` tap; pandapower 3.3's full rule, ``tap_changer_type`` ``None`` = no tap, is in
  ``_Importer.tap_changer``); ``from_bus = hv_bus`` (mambo's tap side),
  ``shift_deg = shift_degree`` plus what the changer adds;
* shunt: pandapower's ``p_mw``/``q_mvar`` are *consumption*, mambo's ``b_mvar`` is *injection*:
  ``b_mvar = −q_mvar · step · (vn(bus)/vn_kv)²``, ``g_mw = p_mw · step · (vn(bus)/vn_kv)²``;
* costs: ``poly_cost`` ``cp2/cp1/cp0`` ↔ ``PolynomialCost.coefficients == [c2, c1, c0]``;
  ``pwl_cost.points == [[p0, p1, slope], ...]`` ↔ ``PiecewiseCost`` breakpoints with the cost
  at ``p0`` taken as 0 (pandapower has no offset column).

Bus roles: the first in-service ``ext_grid`` is the slack (mambo needs exactly one); any other
``ext_grid`` becomes a PV generator (``EXTRA_EXT_GRID_DEMOTED``); with no in-service ``ext_grid``
the first in-service ``gen`` with ``slack = True`` is the slack (``GEN_SLACK_PROMOTED``); a bus
with an in-service ``gen`` is ``pv``; everything else ``pq``. A file with neither leaves the
network without a slack, which ``Network`` refuses (``NO_SLACK``). On export the rule runs
backwards: the first in-service generator of the slack bus becomes ``ext_grid``, PV-bus
generators ``gen``, PQ-bus generators ``sgen``. Ids: import takes ``name`` when it is present,
else ``<table>-<index>``; export writes
the id into ``name``. ``Bus.area`` travels as an extra ``bus.area`` column (pandapower keeps
unknown columns through ``to_json``, measured).
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from os import PathLike
from pathlib import Path
from typing import Any

from mambo_power.io.report import ExportReport, ImportReport
from mambo_power.model import (
    Branch,
    Bus,
    BusType,
    Generator,
    GeneratorCost,
    Geo,
    ImportIssue,
    ImportIssueCode,
    Load,
    Network,
    PiecewiseCost,
    PolynomialCost,
    Shunt,
    Zone,
    repair_islands_entities,
)

__all__ = [
    "CODES",
    "DEFAULT_F_HZ",
    "dump",
    "dumps",
    "dumps_with_report",
    "load",
    "load_with_report",
    "loads",
    "loads_with_report",
]

CODES: tuple[str, ...] = (
    "EXTRA_EXT_GRID_DEMOTED",
    "COLUMN_DROPPED",
    "ELEMENT_DROPPED",
    "FIELD_DEFAULTED",
    "ISLAND_DEACTIVATED",
    "TAP_CHANGER_TYPE_UNSUPPORTED",
    "GEN_SLACK_PROMOTED",
    "FIELD_DROPPED",
    "COST_DROPPED",
    "BID_DROPPED",
)
"""Every report code this module emits (import: the first seven; export: the last three plus
``ELEMENT_DROPPED`` for storage and ``FIELD_DEFAULTED`` for an unrated transformer's
``sn_mva``). Registered in :data:`mambo_power.io.limitations.LIMITATIONS`."""

DEFAULT_F_HZ = 50.0
"""``net.f_hz`` written by the exporter unless given; it only enters the ``b`` ↔ ``c_nf_per_km``
conversion and the importer inverts it with the file's own ``f_hz``."""

_READ_TABLES = frozenset(
    {"bus", "ext_grid", "gen", "sgen", "load", "shunt", "line", "trafo", "poly_cost", "pwl_cost"}
)
_SQRT3 = math.sqrt(3.0)


# --- public API: import ------------------------------------------------------------------------


def load(source: str | PathLike[str]) -> Network:
    """Read the pandapower JSON file at ``source``; the report is discarded."""
    return load_with_report(source)[0]


def loads(text: str) -> Network:
    """Read pandapower JSON text; the report is discarded."""
    return loads_with_report(text)[0]


def load_with_report(source: str | PathLike[str]) -> tuple[Network, ImportReport]:
    """Read the file at ``source`` and return ``(network, report)``."""
    return loads_with_report(Path(source).read_text(encoding="utf-8"))


def loads_with_report(text: str) -> tuple[Network, ImportReport]:
    """Read pandapower JSON text and return ``(network, report)``; see the module docstring."""
    import pandapower as pp

    return _from_pandapower(pp.from_json_string(text))


# --- public API: export ------------------------------------------------------------------------


def dumps(net: Network, *, f_hz: float = DEFAULT_F_HZ) -> str:
    """pandapower JSON text for ``net``; the report is discarded."""
    return dumps_with_report(net, f_hz=f_hz)[0]


def dump(net: Network, target: str | PathLike[str], *, f_hz: float = DEFAULT_F_HZ) -> None:
    """Write pandapower JSON for ``net`` to ``target``; the report is discarded."""
    Path(target).write_text(dumps(net, f_hz=f_hz), encoding="utf-8")


def dumps_with_report(net: Network, *, f_hz: float = DEFAULT_F_HZ) -> tuple[str, ExportReport]:
    """pandapower JSON text for ``net`` and the :class:`ExportReport` of what was dropped."""
    import pandapower as pp

    pn, warnings = _to_pandapower(net, f_hz=f_hz)
    return pp.to_json(pn), ExportReport(warnings=warnings)


# --- helpers ------------------------------------------------------------------------------------


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def _label(value: object) -> str:
    """A pandapower ``name``/``zone`` cell as an id: ``1.0`` -> ``"1"``, ``"x"`` -> ``"x"``
    (``inf`` -> ``"inf"``; ``int(inf)`` would raise)."""
    if isinstance(value, float) and math.isfinite(value) and value == int(value):
        return str(int(value))
    return str(value)


def _column(df: Any, name: str, index: Any, default: object = None) -> Any:
    """``df.at[index, name]`` when the column exists and the cell is not NaN/None; else default."""
    if name not in df.columns:
        return default
    value = df.at[index, name]
    return default if _is_missing(value) else value


def _issue(
    code: ImportIssueCode,
    message: str,
    *,
    bus_ids: Iterable[str] = (),
    element_ids: Iterable[str] = (),
) -> ImportIssue:
    return ImportIssue(
        code=code, message=message, bus_ids=list(bus_ids), element_ids=list(element_ids)
    )


# --- import: pandapowerNet -> Network -----------------------------------------------------------


class _Importer:
    def __init__(self, pn: Any) -> None:
        self.pn = pn
        self.warnings: list[ImportIssue] = []
        self.sn_mva = float(pn.sn_mva)
        self.f_hz = float(pn.f_hz)
        self.bus_id: dict[Any, str] = {}
        self.bus_kv: dict[Any, float] = {}
        self.bus_type: dict[Any, BusType] = {}
        self.bus_vset: dict[Any, float] = {}
        self.gen_id: dict[tuple[str, Any], str] = {}

    # -- reporting

    def dropped_column(self, element: str, table: str, index: Any, field: str, value: Any) -> None:
        if hasattr(value, "item"):  # numpy scalar -> Python scalar, so the message reads 50.0
            value = value.item()
        self.warnings.append(
            _issue(
                "COLUMN_DROPPED",
                f"{table}[{index}] ({element}): {field}={value!r} has no place in the model; "
                "dropped",
                element_ids=[element],
            )
        )

    def dropped_element(self, table: str, index: Any, why: str) -> None:
        self.warnings.append(
            _issue(
                "ELEMENT_DROPPED",
                f"{table}[{index}]: {why}; dropped",
                element_ids=[f"{table}-{index}"],
            )
        )

    def defaulted(self, element: str, field: str, value: float, why: str) -> None:
        self.warnings.append(
            _issue(
                "FIELD_DEFAULTED",
                f"{element}: {field} set to {value!r} ({why})",
                element_ids=[element],
            )
        )

    def check_columns(
        self, table: str, index: Any, element: str, expectations: dict[str, object]
    ) -> None:
        """Report every column in ``expectations`` whose cell differs from the inert value."""
        df = getattr(self.pn, table)
        for field, inert in expectations.items():
            value = _column(df, field, index)
            if value is None or value == inert:
                continue
            if isinstance(inert, (int, float)) and not isinstance(inert, bool):
                try:
                    if float(value) == float(inert):
                        continue
                except (TypeError, ValueError):
                    pass
            self.dropped_column(element, table, index, field, value)

    # -- ids

    def element_id(self, table: str, index: Any) -> str:
        name = _column(getattr(self.pn, table), "name", index)
        return _label(name) if name is not None and str(name) != "" else f"{table}-{index}"

    def rows(self, table: str) -> list[Any]:
        df = getattr(self.pn, table, None)
        return [] if df is None or len(df) == 0 else list(df.index)

    # -- tables

    def buses(self) -> tuple[list[Bus], list[Zone]]:
        pn = self.pn
        buses: list[Bus] = []
        zones: dict[str, Zone] = {}
        for idx in self.rows("bus"):
            bus_id = self.element_id("bus", idx)
            self.bus_id[idx] = bus_id
            self.bus_kv[idx] = float(pn.bus.at[idx, "vn_kv"])
            zone_raw = _column(pn.bus, "zone", idx)
            zone = None if zone_raw is None else _label(zone_raw)
            if zone is not None:
                zones.setdefault(zone, Zone(id=zone))
            geo = _parse_geo(_column(pn.bus, "geo", idx))
            area = _column(pn.bus, "area", idx)
            self.check_columns("bus", idx, bus_id, {"type": "b"})
            buses.append(
                Bus(
                    id=bus_id,
                    base_kv=self.bus_kv[idx],
                    type="pq",
                    in_service=bool(pn.bus.at[idx, "in_service"]),
                    v_min_pu=_float_or_none(_column(pn.bus, "min_vm_pu", idx)),
                    v_max_pu=_float_or_none(_column(pn.bus, "max_vm_pu", idx)),
                    area=None if area is None else str(area),
                    zone=zone,
                    geo=geo,
                )
            )
        return buses, list(zones.values())

    def limits(
        self, table: str, idx: Any, element: str, p_set: float, q_set: float
    ) -> tuple[float, float, float, float]:
        df = getattr(self.pn, table)
        out: list[float] = []
        for field, setpoint in (
            ("min_p_mw", p_set),
            ("max_p_mw", p_set),
            ("min_q_mvar", q_set),
            ("max_q_mvar", q_set),
        ):
            value = _column(df, field, idx)
            if value is None:
                self.defaulted(element, field, setpoint, f"{table}.{field} missing or NaN")
                out.append(setpoint)
            else:
                out.append(float(value))
        return out[0], out[1], out[2], out[3]

    def generators(self, buses: list[Bus]) -> list[Generator]:
        pn = self.pn
        by_id = {b.id: b for b in buses}
        gens: list[Generator] = []
        slack_taken = False
        for idx in self.rows("ext_grid"):
            gid = self.element_id("ext_grid", idx)
            self.gen_id[("ext_grid", idx)] = gid
            bus_idx = pn.ext_grid.at[idx, "bus"]
            bus = by_id[self.bus_id[bus_idx]]
            active = bool(pn.ext_grid.at[idx, "in_service"])
            vm = float(pn.ext_grid.at[idx, "vm_pu"])
            if active and not slack_taken:
                slack_taken = True
                bus.type = "slack"
                bus.vm_pu = vm
                bus.va_deg = float(_column(pn.ext_grid, "va_degree", idx, 0.0))
            elif active:
                if bus.type != "slack":
                    bus.type = "pv"
                self.warnings.append(
                    _issue(
                        "EXTRA_EXT_GRID_DEMOTED",
                        f"ext_grid[{idx}] ({gid}) at bus {bus.id!r}: a second in-service "
                        "ext_grid; imported as a PV generator (the model has one slack)",
                        bus_ids=[bus.id],
                        element_ids=[gid],
                    )
                )
            self.bus_vset[bus_idx] = vm
            p_min, p_max, q_min, q_max = self.limits("ext_grid", idx, gid, 0.0, 0.0)
            self.check_columns("ext_grid", idx, gid, {"slack_weight": 1.0})
            gens.append(
                Generator(
                    id=gid,
                    bus=bus.id,
                    p_mw=0.0,
                    q_mvar=0.0,
                    p_min_mw=p_min,
                    p_max_mw=p_max,
                    q_min_mvar=q_min,
                    q_max_mvar=q_max,
                    v_set_pu=vm,
                    in_service=active,
                )
            )
        for idx in self.rows("gen"):
            gid = self.element_id("gen", idx)
            self.gen_id[("gen", idx)] = gid
            bus_idx = pn.gen.at[idx, "bus"]
            bus = by_id[self.bus_id[bus_idx]]
            active = bool(pn.gen.at[idx, "in_service"])
            vm = float(pn.gen.at[idx, "vm_pu"])
            slack_flag = bool(_column(pn.gen, "slack", idx, False))
            expectations: dict[str, object] = {
                "slack": False,
                "slack_weight": 0.0,
                "controllable": True,
            }
            if active and slack_flag and not slack_taken:
                # pandapower's ext_grid-less slack (gen.slack = True): runpp solves it as the
                # reference bus, so the import gives it the slack role (M8 critic finding 6)
                slack_taken = True
                bus.type = "slack"
                bus.vm_pu = vm
                bus.va_deg = 0.0
                expectations.pop("slack")
                self.warnings.append(
                    _issue(
                        "GEN_SLACK_PROMOTED",
                        f"gen[{idx}] ({gid}) at bus {bus.id!r}: gen.slack is True and no "
                        "in-service ext_grid exists; imported as the slack generator "
                        "(bus type 'slack', vm_pu from gen.vm_pu, va_deg 0.0)",
                        bus_ids=[bus.id],
                        element_ids=[gid],
                    )
                )
            elif active and bus.type == "pq":
                bus.type = "pv"
            self.bus_vset.setdefault(bus_idx, vm)
            p = float(pn.gen.at[idx, "p_mw"]) * float(_column(pn.gen, "scaling", idx, 1.0))
            p_min, p_max, q_min, q_max = self.limits("gen", idx, gid, p, 0.0)
            self.check_columns("gen", idx, gid, expectations)
            gens.append(
                Generator(
                    id=gid,
                    bus=bus.id,
                    p_mw=p,
                    q_mvar=0.0,
                    p_min_mw=p_min,
                    p_max_mw=p_max,
                    q_min_mvar=q_min,
                    q_max_mvar=q_max,
                    v_set_pu=vm,
                    in_service=active,
                )
            )
        for idx in self.rows("sgen"):
            gid = self.element_id("sgen", idx)
            self.gen_id[("sgen", idx)] = gid
            bus_idx = pn.sgen.at[idx, "bus"]
            scaling = float(_column(pn.sgen, "scaling", idx, 1.0))
            p = float(pn.sgen.at[idx, "p_mw"]) * scaling
            q = float(_column(pn.sgen, "q_mvar", idx, 0.0)) * scaling
            p_min, p_max, q_min, q_max = self.limits("sgen", idx, gid, p, q)
            self.check_columns("sgen", idx, gid, {"controllable": False, "current_source": True})
            gens.append(
                Generator(
                    id=gid,
                    bus=self.bus_id[bus_idx],
                    p_mw=p,
                    q_mvar=q,
                    p_min_mw=p_min,
                    p_max_mw=p_max,
                    q_min_mvar=q_min,
                    q_max_mvar=q_max,
                    v_set_pu=self.bus_vset.get(bus_idx, 1.0),
                    in_service=bool(pn.sgen.at[idx, "in_service"]),
                )
            )
        return gens

    def loads(self) -> list[Load]:
        pn = self.pn
        out: list[Load] = []
        for idx in self.rows("load"):
            lid = self.element_id("load", idx)
            scaling = float(_column(pn.load, "scaling", idx, 1.0))
            self.check_columns(
                "load",
                idx,
                lid,
                {
                    "const_z_p_percent": 0.0,
                    "const_z_q_percent": 0.0,
                    "const_i_p_percent": 0.0,
                    "const_i_q_percent": 0.0,
                    "controllable": False,
                },
            )
            out.append(
                Load(
                    id=lid,
                    bus=self.bus_id[pn.load.at[idx, "bus"]],
                    p_mw=float(pn.load.at[idx, "p_mw"]) * scaling,
                    q_mvar=float(_column(pn.load, "q_mvar", idx, 0.0)) * scaling,
                    in_service=bool(pn.load.at[idx, "in_service"]),
                )
            )
        return out

    def shunts(self) -> list[Shunt]:
        pn = self.pn
        out: list[Shunt] = []
        for idx in self.rows("shunt"):
            sid = self.element_id("shunt", idx)
            bus_idx = pn.shunt.at[idx, "bus"]
            bus_kv = self.bus_kv[bus_idx]
            vn = float(_column(pn.shunt, "vn_kv", idx, bus_kv))
            factor = float(_column(pn.shunt, "step", idx, 1)) * (bus_kv / vn) ** 2
            self.check_columns("shunt", idx, sid, {"step_dependency_table": False})
            out.append(
                Shunt(
                    id=sid,
                    bus=self.bus_id[bus_idx],
                    g_mw=float(_column(pn.shunt, "p_mw", idx, 0.0)) * factor,
                    b_mvar=-float(pn.shunt.at[idx, "q_mvar"]) * factor,
                    in_service=bool(pn.shunt.at[idx, "in_service"]),
                )
            )
        return out

    def branches(self) -> list[Branch]:
        pn = self.pn
        out: list[Branch] = []
        for idx in self.rows("line"):
            bid = self.element_id("line", idx)
            f_idx, t_idx = pn.line.at[idx, "from_bus"], pn.line.at[idx, "to_bus"]
            vn = self.bus_kv[f_idx]
            zb = vn * vn / self.sn_mva
            length = float(pn.line.at[idx, "length_km"])
            parallel = float(_column(pn.line, "parallel", idx, 1))
            df = float(_column(pn.line, "df", idx, 1.0))
            max_i = _column(pn.line, "max_i_ka", idx)
            self.check_columns("line", idx, bid, {"g_us_per_km": 0.0, "max_loading_percent": 100.0})
            out.append(
                Branch(
                    id=bid,
                    from_bus=self.bus_id[f_idx],
                    to_bus=self.bus_id[t_idx],
                    r=float(pn.line.at[idx, "r_ohm_per_km"]) * length / parallel / zb,
                    x=float(pn.line.at[idx, "x_ohm_per_km"]) * length / parallel / zb,
                    b=2.0
                    * math.pi
                    * self.f_hz
                    * float(pn.line.at[idx, "c_nf_per_km"])
                    * 1e-9
                    * length
                    * parallel
                    * zb,
                    rating_mva=None
                    if max_i is None or float(max_i) <= 0
                    else float(max_i) * df * parallel * _SQRT3 * vn,
                    in_service=bool(pn.line.at[idx, "in_service"]),
                    kind="line",
                )
            )
        for idx in self.rows("trafo"):
            bid = self.element_id("trafo", idx)
            hv_idx, lv_idx = pn.trafo.at[idx, "hv_bus"], pn.trafo.at[idx, "lv_bus"]
            vnh = float(pn.trafo.at[idx, "vn_hv_kv"])
            vnl = float(pn.trafo.at[idx, "vn_lv_kv"])
            vnh, vnl, tap_shift = self.tap_changer(idx, bid, vnh, vnl)
            tap = (vnh / self.bus_kv[hv_idx]) / (vnl / self.bus_kv[lv_idx])
            parallel = float(_column(pn.trafo, "parallel", idx, 1))
            sn_trafo = float(pn.trafo.at[idx, "sn_mva"])
            scale = self.sn_mva / sn_trafo * (vnl / self.bus_kv[lv_idx]) ** 2 / parallel
            z = float(pn.trafo.at[idx, "vk_percent"]) / 100.0 * scale
            r = float(pn.trafo.at[idx, "vkr_percent"]) / 100.0 * scale
            x = math.sqrt(max(z * z - r * r, 0.0))
            shift = float(_column(pn.trafo, "shift_degree", idx, 0.0)) + tap_shift
            self.check_columns(
                "trafo",
                idx,
                bid,
                {
                    "pfe_kw": 0.0,
                    "i0_percent": 0.0,
                    "max_loading_percent": 100.0,
                    "tap_dependency_table": False,
                },
            )
            out.append(
                Branch(
                    id=bid,
                    from_bus=self.bus_id[hv_idx],
                    to_bus=self.bus_id[lv_idx],
                    r=r,
                    x=x,
                    b=0.0,
                    rating_mva=sn_trafo * parallel * float(_column(pn.trafo, "df", idx, 1.0)),
                    tap_ratio=None if tap == 1.0 else tap,
                    shift_deg=None if shift == 0.0 else shift,
                    in_service=bool(pn.trafo.at[idx, "in_service"]),
                    kind="transformer",
                )
            )
        return out

    def tap_changer(
        self, idx: Any, element: str, vnh: float, vnl: float
    ) -> tuple[float, float, float]:
        """``(vn_hv_kv, vn_lv_kv, extra shift_deg)`` after the tap changer, pandapower 3.3's
        ``build_branch._calc_tap_from_dataframe`` rule (M8 critic finding 2):

        * ``tap_changer_type`` ``None`` (``create_transformer_from_parameters``'s default): the
          tap columns are inert -- pandapower solves the nominal tap, so does the import; a
          non-neutral ``tap_pos`` is reported ``COLUMN_DROPPED`` because the file holds a value
          that has no effect on either side;
        * ``"Ratio"`` / ``"Symmetrical"``: the tapped winding's voltage becomes
          ``|vn + du*e^(j*theta)|`` with ``du = vn * (tap_pos - tap_neutral) * tap_step_percent
          / 100`` and ``theta = tap_step_degree`` (0 when absent -- the plain ratio tap), and the
          shift grows by ``atan(+-du*sin(theta) / (vn + du*cos(theta)))``, ``+`` for
          ``tap_side = "hv"``, ``-`` for ``"lv"``;
        * ``"Ideal"``: a phase shift of ``+-(tap_pos - tap_neutral) * tap_step_degree`` when
          ``tap_step_degree`` is set, else ``+-2*asin((tap_pos - tap_neutral) * tap_step_percent
          / 200)``; both set is what ``runpp`` itself refuses;
        * anything else (an unknown type, the refused ``Ideal`` case, or a ``tap_side`` that is
          neither ``"hv"`` nor ``"lv"``): nominal tap with ``TAP_CHANGER_TYPE_UNSUPPORTED``.
        """
        df = self.pn.trafo
        pos = float(_column(df, "tap_pos", idx, 0.0))
        neutral = float(_column(df, "tap_neutral", idx, 0.0))
        step = float(_column(df, "tap_step_percent", idx, 0.0))
        degree = float(_column(df, "tap_step_degree", idx, 0.0))
        side = _column(df, "tap_side", idx)
        changer = _column(df, "tap_changer_type", idx)
        diff = pos - neutral
        if changer is None:
            if diff != 0.0 and (step != 0.0 or degree != 0.0):
                self.warnings.append(
                    _issue(
                        "COLUMN_DROPPED",
                        f"trafo[{idx}] ({element}): tap_pos={pos:g} (tap_neutral={neutral:g}, "
                        f"tap_step_percent={step:g}, tap_step_degree={degree:g}) with "
                        "tap_changer_type=None: pandapower applies no tap without a changer "
                        "type; imported at the nominal tap",
                        element_ids=[element],
                    )
                )
            return vnh, vnl, 0.0
        direction = {"hv": 1.0, "lv": -1.0}.get(str(side))
        if direction is None or changer not in ("Ratio", "Symmetrical", "Ideal"):
            why = f"tap_side={side!r}" if direction is None else f"tap_changer_type={changer!r}"
            return self.tap_unsupported(idx, element, vnh, vnl, why)
        if changer == "Ideal":
            if degree != 0.0 and step != 0.0:
                why = (
                    "tap_changer_type='Ideal' with both tap_step_percent and tap_step_degree "
                    "set (pandapower's runpp refuses it too)"
                )
                return self.tap_unsupported(idx, element, vnh, vnl, why)
            if degree != 0.0:
                return vnh, vnl, direction * diff * degree
            return vnh, vnl, direction * 2.0 * math.degrees(math.asin(diff * step / 200.0))
        vn = vnh if side == "hv" else vnl
        du = vn * step * diff / 100.0
        theta = math.radians(degree)
        vn_tapped = math.hypot(vn + du * math.cos(theta), du * math.sin(theta))
        extra = math.degrees(
            math.atan(direction * du * math.sin(theta) / (vn + du * math.cos(theta)))
        )
        return (vn_tapped, vnl, extra) if side == "hv" else (vnh, vn_tapped, extra)

    def tap_unsupported(
        self, idx: Any, element: str, vnh: float, vnl: float, why: str
    ) -> tuple[float, float, float]:
        self.warnings.append(
            _issue(
                "TAP_CHANGER_TYPE_UNSUPPORTED",
                f"trafo[{idx}] ({element}): {why} cannot be expressed as a tap ratio and phase "
                "shift; imported at the nominal tap with no shift from the changer",
                element_ids=[element],
            )
        )
        return vnh, vnl, 0.0

    def costs(self, gens: list[Generator]) -> None:
        pn = self.pn
        by_id = {g.id: g for g in gens}
        for idx in self.rows("poly_cost"):
            et, element = str(pn.poly_cost.at[idx, "et"]), pn.poly_cost.at[idx, "element"]
            gid = self.gen_id.get((et, element))
            if gid is None:
                self.dropped_element("poly_cost", idx, f"cost of {et}[{element}], not a generator")
                continue
            self.check_columns(
                "poly_cost",
                idx,
                gid,
                {"cq0_eur": 0.0, "cq1_eur_per_mvar": 0.0, "cq2_eur_per_mvar2": 0.0},
            )
            by_id[gid].cost = PolynomialCost(
                coefficients=[
                    float(_column(pn.poly_cost, "cp2_eur_per_mw2", idx, 0.0)),
                    float(_column(pn.poly_cost, "cp1_eur_per_mw", idx, 0.0)),
                    float(_column(pn.poly_cost, "cp0_eur", idx, 0.0)),
                ]
            )
        for idx in self.rows("pwl_cost"):
            et, element = str(pn.pwl_cost.at[idx, "et"]), pn.pwl_cost.at[idx, "element"]
            gid = self.gen_id.get((et, element))
            if gid is None:
                self.dropped_element("pwl_cost", idx, f"cost of {et}[{element}], not a generator")
                continue
            if _column(pn.pwl_cost, "power_type", idx, "p") != "p":
                self.dropped_element("pwl_cost", idx, f"reactive (power_type != 'p') cost of {gid}")
                continue
            segments = pn.pwl_cost.at[idx, "points"]
            points: list[tuple[float, float]] = []
            cost = 0.0
            for k, (p0, p1, slope) in enumerate(segments):
                if k == 0:
                    points.append((float(p0), cost))
                cost += float(slope) * (float(p1) - float(p0))
                points.append((float(p1), cost))
            by_id[gid].cost = PiecewiseCost(points=points)

    def other_tables(self) -> None:
        import pandas as pd  # type: ignore[import-untyped]

        for name in self.pn.keys():
            df = self.pn[name]
            if not isinstance(df, pd.DataFrame) or name in _READ_TABLES or name.startswith("res_"):
                continue
            if name.endswith("_geodata") or name.endswith("_table") or name.endswith("_std_types"):
                continue
            if len(df) == 0:
                continue
            for idx in df.index:
                self.dropped_element(name, idx, f"{name} rows have no counterpart in the model")


def _float_or_none(value: object) -> float | None:
    return None if value is None else float(value)  # type: ignore[arg-type]


def _parse_geo(value: object) -> Geo | None:
    if value is None:
        return None
    try:
        obj = json.loads(value) if isinstance(value, str) else value
        x, y = obj["coordinates"]  # type: ignore[index]
        return Geo(lon=float(x), lat=float(y))
    except (TypeError, ValueError, KeyError):
        return None


def _from_pandapower(pn: Any) -> tuple[Network, ImportReport]:
    imp = _Importer(pn)
    buses, zones = imp.buses()
    gens = imp.generators(buses)
    loads = imp.loads()
    shunts = imp.shunts()
    branches = imp.branches()
    imp.costs(gens)
    imp.other_tables()
    buses, branches, gens, loads, shunts, storage, island_warnings = repair_islands_entities(
        buses, branches, gens, loads, shunts, []
    )
    imp.warnings.extend(island_warnings)
    net = Network(
        base_mva=imp.sn_mva,
        buses=buses,
        branches=branches,
        generators=gens,
        loads=loads,
        shunts=shunts,
        storage=storage,
        zones=zones,
    )
    return net, ImportReport(warnings=imp.warnings)


# --- export: Network -> pandapowerNet -----------------------------------------------------------


def _to_pandapower(net: Network, *, f_hz: float) -> tuple[Any, list[ImportIssue]]:
    """Build the ``pandapowerNet`` with one bulk creator call per table (``create_buses``,
    ``create_lines_from_parameters``, ...): pandapower's single-row creators cost a full-table
    dtype pass each, which made the export quadratic (33 s on case300, M8 critic finding 4).
    The tables and values are the ones the per-row creators produced; the test
    ``test_bulk_export_is_byte_identical_to_pandapowers_per_row_creators`` pins that."""
    import pandapower as pp

    warnings: list[ImportIssue] = []

    def dropped(element: str, field: str, value: object, why: str = "no pandapower column") -> None:
        warnings.append(
            _issue(
                "FIELD_DROPPED",
                f"{element}: {field}={value!r} dropped ({why})",
                element_ids=[element],
            )
        )

    pn = pp.create_empty_network(sn_mva=net.base_mva, f_hz=f_hz)
    bus_by_id = {b.id: b for b in net.buses}
    for zone in net.zones:
        if zone.name is not None:
            dropped(zone.id, "zone.name", zone.name)
    buses = net.buses
    indices = pp.create_buses(
        pn,
        len(buses),
        vn_kv=[b.base_kv for b in buses],
        name=[b.id for b in buses],
        zone=[b.zone for b in buses],
        in_service=[b.in_service for b in buses],
        min_vm_pu=[math.nan if b.v_min_pu is None else b.v_min_pu for b in buses],
        max_vm_pu=[math.nan if b.v_max_pu is None else b.v_max_pu for b in buses],
    )
    bus_index: dict[str, int] = {b.id: int(i) for b, i in zip(buses, indices, strict=True)}
    for b in buses:
        if b.geo is not None:  # what create_bus(geodata=(x, y)) writes
            pn.bus.at[bus_index[b.id], "geo"] = (
                f'{{"coordinates": [{b.geo.lon}, {b.geo.lat}], "type": "Point"}}'
            )
    if any(b.area is not None for b in buses):
        pn.bus["area"] = [b.area for b in buses]

    slack_gen = next(
        (g for g in net.generators if bus_by_id[g.bus].type == "slack" and g.in_service), None
    )
    _drop_bus_state(net, slack_gen, warnings)
    _export_generators(pp, pn, net, bus_by_id, bus_index, slack_gen, warnings, dropped)

    if net.loads:
        pp.create_loads(
            pn,
            [bus_index[ld.bus] for ld in net.loads],
            p_mw=[ld.p_mw for ld in net.loads],
            q_mvar=[ld.q_mvar for ld in net.loads],
            name=[ld.id for ld in net.loads],
            in_service=[ld.in_service for ld in net.loads],
        )
    for load in net.loads:
        if load.bid is not None:
            warnings.append(
                _issue(
                    "BID_DROPPED",
                    f"{load.id}: bid ({load.bid.kind}) dropped (pandapower has no demand bid)",
                    element_ids=[load.id],
                )
            )
    if net.shunts:
        pp.create_shunts(
            pn,
            [bus_index[sh.bus] for sh in net.shunts],
            q_mvar=[-sh.b_mvar for sh in net.shunts],
            p_mw=[sh.g_mw for sh in net.shunts],
            vn_kv=[bus_by_id[sh.bus].base_kv for sh in net.shunts],
            step=1,
            name=[sh.id for sh in net.shunts],
            in_service=[sh.in_service for sh in net.shunts],
        )
    for unit in net.storage:
        warnings.append(
            _issue(
                "ELEMENT_DROPPED",
                f"{unit.id}: storage dropped (pandapower storage has no efficiency columns)",
                element_ids=[unit.id],
            )
        )
    _export_branches(pp, pn, net, bus_by_id, bus_index, f_hz, warnings, dropped)
    return pn, warnings


def _export_generators(
    pp: Any,
    pn: Any,
    net: Network,
    bus_by_id: dict[str, Bus],
    bus_index: dict[str, int],
    slack_gen: Generator | None,
    warnings: list[ImportIssue],
    dropped: Any,
) -> None:
    """The slack bus's first in-service generator → ``ext_grid``; PV/slack-bus generators →
    ``gen``; PQ-bus generators → ``sgen``; then every cost, in generator order."""
    gens: list[Generator] = []
    sgens: list[Generator] = []
    gen_ref: dict[str, tuple[str, int]] = {}
    for gen in net.generators:
        bus = bus_by_id[gen.bus]
        if gen.ramp_up_mw is not None:
            dropped(gen.id, "ramp_up_mw", gen.ramp_up_mw)
        if gen.ramp_down_mw is not None:
            dropped(gen.id, "ramp_down_mw", gen.ramp_down_mw)
        if gen is slack_gen:
            idx = pp.create_ext_grid(
                pn,
                bus_index[gen.bus],
                vm_pu=gen.v_set_pu,
                va_degree=0.0 if bus.va_deg is None else bus.va_deg,
                name=gen.id,
                in_service=gen.in_service,
                max_p_mw=gen.p_max_mw,
                min_p_mw=gen.p_min_mw,
                max_q_mvar=gen.q_max_mvar,
                min_q_mvar=gen.q_min_mvar,
            )
            gen_ref[gen.id] = ("ext_grid", int(idx))
            if gen.p_mw != 0.0:
                dropped(gen.id, "p_mw", gen.p_mw, "ext_grid has no setpoint")
            if gen.q_mvar != 0.0:
                dropped(gen.id, "q_mvar", gen.q_mvar, "ext_grid has no setpoint")
        elif bus.type in ("slack", "pv"):
            gens.append(gen)
            if gen.q_mvar != 0.0:
                dropped(gen.id, "q_mvar", gen.q_mvar, "gen is PV: no Q setpoint")
        else:
            sgens.append(gen)
            if gen.v_set_pu != 1.0:
                dropped(gen.id, "v_set_pu", gen.v_set_pu, "sgen on a PQ bus holds no setpoint")
    if gens:
        idx_gens = pp.create_gens(
            pn,
            [bus_index[g.bus] for g in gens],
            p_mw=[g.p_mw for g in gens],
            vm_pu=[g.v_set_pu for g in gens],
            name=[g.id for g in gens],
            in_service=[g.in_service for g in gens],
            max_p_mw=[g.p_max_mw for g in gens],
            min_p_mw=[g.p_min_mw for g in gens],
            max_q_mvar=[g.q_max_mvar for g in gens],
            min_q_mvar=[g.q_min_mvar for g in gens],
        )
        gen_ref.update({g.id: ("gen", int(i)) for g, i in zip(gens, idx_gens, strict=True)})
        _null_text_columns(pn.gen, idx_gens, ("type", "curve_style"))
    if sgens:
        idx_sgens = pp.create_sgens(
            pn,
            [bus_index[g.bus] for g in sgens],
            p_mw=[g.p_mw for g in sgens],
            q_mvar=[g.q_mvar for g in sgens],
            name=[g.id for g in sgens],
            in_service=[g.in_service for g in sgens],
            max_p_mw=[g.p_max_mw for g in sgens],
            min_p_mw=[g.p_min_mw for g in sgens],
            max_q_mvar=[g.q_max_mvar for g in sgens],
            min_q_mvar=[g.q_min_mvar for g in sgens],
        )
        gen_ref.update({g.id: ("sgen", int(i)) for g, i in zip(sgens, idx_sgens, strict=True)})
        _null_text_columns(pn.sgen, idx_sgens, ("curve_style",))
        # create_sgens adds a generator_type column create_sgen does not; the file stays the one
        # the per-row export wrote (the importer reads current_source, not this)
        pn.sgen.drop(columns=["generator_type"], inplace=True, errors="ignore")
    poly: list[tuple[int, str, float, float, float]] = []
    pwl: list[tuple[int, str, list[list[float]]]] = []
    for gen in net.generators:
        _collect_cost(gen.id, gen_ref[gen.id], gen.cost, poly, pwl, warnings, dropped)
    if poly:
        pp.create_poly_costs(
            pn,
            [element for element, _et, _c2, _c1, _c0 in poly],
            [et for _element, et, _c2, _c1, _c0 in poly],
            cp1_eur_per_mw=[c1 for _element, _et, _c2, c1, _c0 in poly],
            cp0_eur=[c0 for _element, _et, _c2, _c1, c0 in poly],
            cp2_eur_per_mw2=[c2 for _element, _et, c2, _c1, _c0 in poly],
        )
    if pwl:
        pp.create_pwl_costs(
            pn,
            [element for element, _, _ in pwl],
            [et for _, et, _ in pwl],
            points=[points for _, _, points in pwl],
        )


def _export_branches(
    pp: Any,
    pn: Any,
    net: Network,
    bus_by_id: dict[str, Bus],
    bus_index: dict[str, int],
    f_hz: float,
    warnings: list[ImportIssue],
    dropped: Any,
) -> None:
    lines = [br for br in net.branches if not br.is_transformer]  # kind, or a later-assigned tap
    trafos = [br for br in net.branches if br.is_transformer]
    if lines:
        zb = [bus_by_id[br.from_bus].base_kv ** 2 / net.base_mva for br in lines]
        pp.create_lines_from_parameters(
            pn,
            [bus_index[br.from_bus] for br in lines],
            [bus_index[br.to_bus] for br in lines],
            length_km=1.0,
            r_ohm_per_km=[br.r * z for br, z in zip(lines, zb, strict=True)],
            x_ohm_per_km=[br.x * z for br, z in zip(lines, zb, strict=True)],
            c_nf_per_km=[
                br.b / z / (2.0 * math.pi * f_hz) * 1e9 for br, z in zip(lines, zb, strict=True)
            ],
            max_i_ka=[
                math.nan
                if br.rating_mva is None
                else br.rating_mva / (_SQRT3 * bus_by_id[br.from_bus].base_kv)
                for br in lines
            ],
            name=[br.id for br in lines],
            in_service=[br.in_service for br in lines],
        )
        _null_text_columns(pn.line, pn.line.index[-len(lines) :], ("std_type", "type"))
    if not trafos:
        return
    sn: list[float] = []
    for br in trafos:
        sn_trafo = net.base_mva if br.rating_mva is None else br.rating_mva
        sn.append(sn_trafo)
        if br.rating_mva is None:
            warnings.append(
                _issue(
                    "FIELD_DEFAULTED",
                    f"{br.id}: rating_mva is None; trafo sn_mva set to base_mva {sn_trafo!r} "
                    "(pandapower needs a rated power) and re-imports as the rating",
                    element_ids=[br.id],
                )
            )
    scale = [100.0 * s / net.base_mva for s in sn]
    taps = [1.0 if br.tap_ratio is None else br.tap_ratio for br in trafos]
    tapped = [tap != 1.0 for tap in taps]
    pp.create_transformers_from_parameters(
        pn,
        [bus_index[br.from_bus] for br in trafos],
        [bus_index[br.to_bus] for br in trafos],
        sn_mva=sn,
        vn_hv_kv=[bus_by_id[br.from_bus].base_kv for br in trafos],
        vn_lv_kv=[bus_by_id[br.to_bus].base_kv for br in trafos],
        vkr_percent=[br.r * k for br, k in zip(trafos, scale, strict=True)],
        vk_percent=[math.hypot(br.r, br.x) * k for br, k in zip(trafos, scale, strict=True)],
        pfe_kw=0.0,
        i0_percent=0.0,
        shift_degree=[0.0 if br.shift_deg is None else br.shift_deg for br in trafos],
        name=[br.id for br in trafos],
        in_service=[br.in_service for br in trafos],
        # a nominal tap is written as pandapower's own "no tap changer" (tap_side None, the tap
        # columns NaN, M8 walk surprise 1); an off-nominal one as a ±1 position of |tap − 1|·100 %
        tap_side=[("hv" if t else None) for t in tapped],
        tap_neutral=[(0 if t else math.nan) for t in tapped],
        tap_pos=[
            ((1 if tap > 1.0 else -1) if t else math.nan)
            for tap, t in zip(taps, tapped, strict=True)
        ],
        tap_step_percent=[
            (abs(tap - 1.0) * 100.0 if t else math.nan) for tap, t in zip(taps, tapped, strict=True)
        ],
        tap_changer_type=[("Ratio" if t else None) for t in tapped],
    )
    new_rows = pn.trafo.index[-len(trafos) :]
    _null_text_columns(pn.trafo, new_rows, ("std_type",))
    untapped = [row for row, t in zip(new_rows, tapped, strict=True) if not t]
    _null_text_columns(pn.trafo, untapped, ("tap_side", "tap_changer_type"))
    for br in trafos:
        if br.b != 0.0:
            dropped(br.id, "b", br.b, "a pandapower trafo carries no line charging")


def _drop_bus_state(net: Network, slack_gen: Generator | None, warnings: list[ImportIssue]) -> None:
    """One ``FIELD_DROPPED`` naming every bus whose stored ``vm_pu``/``va_deg`` the file will not
    hold: results tables are not written (module docstring). The slack's state is the exception --
    ``ext_grid.vm_pu`` is its generator's ``v_set_pu`` and ``va_degree`` its ``va_deg`` -- so it
    is named only when its ``vm_pu`` differs from that setpoint."""
    lost: list[str] = []
    for bus in net.buses:
        if bus.vm_pu is None and bus.va_deg is None:
            continue
        if bus.type == "slack" and slack_gen is not None and slack_gen.bus == bus.id:
            if bus.vm_pu is None or bus.vm_pu == slack_gen.v_set_pu:
                continue
        lost.append(bus.id)
    if lost:
        warnings.append(
            _issue(
                "FIELD_DROPPED",
                f"vm_pu/va_deg dropped on {len(lost)} bus(es) {lost[:5]}"
                f"{'...' if len(lost) > 5 else ''}: pandapower results tables (res_bus) are not "
                "written; only the slack's state travels, as the ext_grid setpoint",
                bus_ids=lost,
            )
        )


def _null_text_columns(df: Any, index: Any, columns: tuple[str, ...]) -> None:
    """The bulk creators write ``""`` where the single-row creators write ``None`` in these
    free-text columns; ``None`` is what the per-row export produced and what ``from_json`` of a
    pandapower-authored file holds, so the file stays comparable (``pp.nets_equal``)."""
    for column in columns:
        if column in df.columns:
            df.loc[index, column] = None


def _collect_cost(
    gen_id: str,
    ref: tuple[str, int],
    cost: GeneratorCost | None,
    poly: list[tuple[int, str, float, float, float]],
    pwl: list[tuple[int, str, list[list[float]]]],
    warnings: list[ImportIssue],
    dropped: Any,
) -> None:
    """Append the generator's cost to ``poly`` (``(element, et, c2, c1, c0)``) or ``pwl``
    (``(element, et, segments)``), or report what pandapower cannot hold."""
    if cost is None:
        return
    if cost.startup != 0.0:
        dropped(gen_id, "cost.startup", cost.startup)
    if cost.shutdown != 0.0:
        dropped(gen_id, "cost.shutdown", cost.shutdown)
    et, element = ref
    if cost.kind == "polynomial":
        coefficients = cost.coefficients
        if len(coefficients) > 3:
            warnings.append(
                _issue(
                    "COST_DROPPED",
                    f"{gen_id}: polynomial cost of degree {len(coefficients) - 1} dropped "
                    "(poly_cost holds degree <= 2; never approximated)",
                    element_ids=[gen_id],
                )
            )
            return
        c2, c1, c0 = ([0.0] * (3 - len(coefficients)) + list(coefficients))[-3:]
        poly.append((element, et, c2, c1, c0))
        return
    points = cost.points
    if points[0][1] != 0.0:
        dropped(gen_id, "cost.points[0][1]", points[0][1], "pwl_cost has no cost offset")
    segments = [
        [p0, p1, (c1 - c0) / (p1 - p0)]
        for (p0, c0), (p1, c1) in zip(points, points[1:], strict=False)
    ]
    pwl.append((element, et, segments))
