"""Wrapper around a live pyswmm :class:`~pyswmm.Simulation` for Movici.

This module bridges Movici's entity-based, ``update(moment)``-driven model with
SWMM's *live, forward-only* simulation engine:

- the Movici dataset is synthesised into a transient ``.inp`` file
  (see :mod:`.inp_writer`) and a single :class:`~pyswmm.Simulation` is opened
  and kept alive for the whole run;
- each Movici update advances that simulation to the requested moment with
  ``step_advance`` + iteration (SWMM cannot rewind, so we never step backwards);
- control inputs (rainfall, node inflow, regulator settings) are applied to the
  live objects *before* advancing, so they govern the step about to be taken;
- per-step results are read directly off the live ``Node`` / ``Link`` /
  ``Subcatchment`` objects (there is no results DataFrame as in WNTR).

Per-entity-group :class:`SwmmProcessor`\\ s know how to (a) contribute rows to
the synthesised ``.inp``, (b) apply control inputs and (c) read results back.
"""

from __future__ import annotations

import datetime as _datetime
import logging
import os
import tempfile
import typing as t

import numpy as np
from pyswmm import Links, Nodes, RainGages, Simulation, Subcatchments

from movici_simulation_core.core.entity_group import EntityGroup

from .dataset import (
    ConduitEntity,
    DrainageLinkEntity,
    DrainageNodeEntity,
    JunctionEntity,
    OrificeEntity,
    OutfallEntity,
    OutletEntity,
    PumpEntity,
    RainGageEntity,
    StorageEntity,
    SubcatchmentEntity,
    UrbanDrainageNetwork,
    WeirEntity,
)
from .inp_writer import InpBuilder, fmt_hms, fmt_num

T = t.TypeVar("T", bound=EntityGroup)
N = t.TypeVar("N", bound=DrainageNodeEntity)
L = t.TypeVar("L", bound=DrainageLinkEntity)

# The synthesised model starts at this (arbitrary) epoch. Movici moments, which
# are seconds elapsed since the simulation start, map directly onto SWMM time as
# ``start + moment``. The end date is set far in the future so SWMM never
# terminates before the Movici scenario does.
START_DATE = "01/01/2020"
START_TIME = "00:00:00"
END_DATE = "12/31/2099"
END_TIME = "00:00:00"

# SWMM requires a weir's opening cross-section shape to match its type. Types not
# listed here use a rectangular opening (RECT_OPEN).
_WEIR_XSECTION_SHAPE = {"V-NOTCH": "TRIANGULAR", "TRAPEZOIDAL": "TRAPEZOIDAL"}


def _extract_csr_curve(csr_attribute, idx: int) -> t.Optional[np.ndarray]:
    """Extract a single ``(n, 2)`` curve from a CSR attribute, or ``None``."""
    csr = csr_attribute.csr
    start = csr.row_ptr[idx]
    end = csr.row_ptr[idx + 1]
    if end <= start:
        return None
    data = csr.data[start:end]
    if np.any(np.isnan(data)):
        return None
    if data.ndim == 1:
        data = data.reshape(-1, 2)
    return data


def _defined_mask(attr) -> t.Optional[np.ndarray]:
    """Boolean mask of defined values, or ``None`` if the attr has no data."""
    if not attr.has_data():
        return None
    return ~attr.is_undefined()


def _opt_val(attr, idx: int, mask: t.Optional[np.ndarray], default):
    """Optional scalar value at *idx*, returning *default* when undefined."""
    if mask is not None and mask[idx]:
        return type(default)(attr.array[idx])
    return default


def _enum_kw(attr, idx: int) -> str:
    """Return the (upper-cased) SWMM keyword for an enum attribute at *idx*."""
    return attr.options.enum_values[int(attr.array[idx])].upper()


class IdMapper:
    """Maps Movici integer ids to SWMM string names (unique across all types).

    Each processor uses a type-specific prefix (``"J"`` for junctions, ``"C"``
    for conduits, ...) so names are unique across entity groups and link
    endpoints / subcatchment outlets resolve unambiguously.
    """

    def __init__(self) -> None:
        self.names_by_id: t.Dict[int, str] = {}

    def register(self, entity_id: int, swmm_name: str) -> None:
        entity_id = int(entity_id)
        if entity_id in self.names_by_id:
            raise ValueError(f"Duplicate entity id {entity_id}")
        self.names_by_id[entity_id] = swmm_name

    def get_swmm_name(self, entity_id: int) -> str:
        return self.names_by_id[int(entity_id)]


# ---------------------------------------------------------------------------
# Processor base classes
# ---------------------------------------------------------------------------


class SwmmProcessor(t.Generic[T]):
    """Base class translating one entity group to/from SWMM."""

    PREFIX: str = ""

    def __init__(self, wrapper: "SimulationWrapper", entity_group: T) -> None:
        self.wrapper = wrapper
        self.entity_group = entity_group

    def swmm_name(self, entity_id: int) -> str:
        return self.PREFIX + str(int(entity_id))

    def register(self) -> None:
        """Register all of this group's ids in the shared :class:`IdMapper`."""
        for entity_id in self.entity_group.index.ids:
            self.wrapper.id_mapper.register(entity_id, self.swmm_name(entity_id))

    def build_inp(self, builder: InpBuilder) -> None:
        raise NotImplementedError

    def process_changes(self) -> None:
        pass

    def write_results(self) -> None:
        pass


class NodeProcessor(SwmmProcessor[N]):
    """Base for node processors: writes coordinates, reads shared node outputs."""

    def _add_coordinates(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        xs, ys = eg.x.array, eg.y.array
        for idx, entity_id in enumerate(eg.index.ids):
            builder.add(
                "COORDINATES", self.swmm_name(entity_id), fmt_num(xs[idx]), fmt_num(ys[idx])
            )

    def process_changes(self) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        inflow_mask = _defined_mask(eg.generated_inflow)
        if inflow_mask is None:
            return
        for idx, entity_id in enumerate(eg.index.ids):
            if inflow_mask[idx]:
                node = self.wrapper.nodes[self.swmm_name(entity_id)]
                node.generated_inflow(float(eg.generated_inflow.array[idx]))

    def write_results(self) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        for idx, entity_id in enumerate(eg.index.ids):
            node = self.wrapper.nodes[self.swmm_name(entity_id)]
            eg.water_depth.array[idx] = node.depth
            eg.hydraulic_head.array[idx] = node.head
            eg.flooding.array[idx] = node.flooding
            eg.total_inflow.array[idx] = node.total_inflow
            eg.total_outflow.array[idx] = node.total_outflow
            eg.lateral_inflow.array[idx] = node.lateral_inflow
            eg.stored_volume.array[idx] = node.volume


class LinkProcessor(SwmmProcessor[L]):
    """Base for link processors: resolves endpoints, reads shared link outputs."""

    def _from_to(self, idx: int, entity_id: int) -> t.Tuple[str, str]:
        eg = self.entity_group
        try:
            from_name = self.wrapper.id_mapper.get_swmm_name(eg.from_node_id.array[idx])
        except KeyError:
            raise ValueError(
                f"Invalid from_node_id {eg.from_node_id.array[idx]} for link #{entity_id}"
            ) from None
        try:
            to_name = self.wrapper.id_mapper.get_swmm_name(eg.to_node_id.array[idx])
        except KeyError:
            raise ValueError(
                f"Invalid to_node_id {eg.to_node_id.array[idx]} for link #{entity_id}"
            ) from None
        return from_name, to_name

    def process_changes(self) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        setting_mask = _defined_mask(eg.target_setting)
        if setting_mask is None:
            return
        for idx, entity_id in enumerate(eg.index.ids):
            if setting_mask[idx]:
                link = self.wrapper.links[self.swmm_name(entity_id)]
                link.target_setting = float(eg.target_setting.array[idx])

    def write_results(self) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        for idx, entity_id in enumerate(eg.index.ids):
            link = self.wrapper.links[self.swmm_name(entity_id)]
            eg.flow.array[idx] = link.flow
            eg.flow_depth.array[idx] = link.depth
            eg.flow_volume.array[idx] = link.volume
            eg.froude_number.array[idx] = link.froude
            eg.current_setting.array[idx] = link.current_setting


# ---------------------------------------------------------------------------
# Node processors
# ---------------------------------------------------------------------------


class JunctionProcessor(NodeProcessor[JunctionEntity]):
    PREFIX = "J"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        max_depth_mask = _defined_mask(eg.max_depth)
        init_depth_mask = _defined_mask(eg.initial_depth)
        sur_mask = _defined_mask(eg.surcharge_depth)
        pond_mask = _defined_mask(eg.ponded_area)
        for idx, entity_id in enumerate(eg.index.ids):
            builder.add(
                "JUNCTIONS",
                self.swmm_name(entity_id),
                fmt_num(eg.invert_elevation.array[idx]),
                fmt_num(_opt_val(eg.max_depth, idx, max_depth_mask, 0.0)),
                fmt_num(_opt_val(eg.initial_depth, idx, init_depth_mask, 0.0)),
                fmt_num(_opt_val(eg.surcharge_depth, idx, sur_mask, 0.0)),
                fmt_num(_opt_val(eg.ponded_area, idx, pond_mask, 0.0)),
            )
        self._add_coordinates(builder)


class OutfallProcessor(NodeProcessor[OutfallEntity]):
    PREFIX = "OF"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        stage_mask = _defined_mask(eg.fixed_stage)
        gate_mask = _defined_mask(eg.flap_gate)
        for idx, entity_id in enumerate(eg.index.ids):
            outfall_type = _enum_kw(eg.outfall_type, idx)
            gated = "YES" if _opt_val(eg.flap_gate, idx, gate_mask, False) else "NO"
            if outfall_type == "FIXED":
                stage = fmt_num(_opt_val(eg.fixed_stage, idx, stage_mask, 0.0))
                builder.add(
                    "OUTFALLS",
                    self.swmm_name(entity_id),
                    fmt_num(eg.invert_elevation.array[idx]),
                    "FIXED",
                    stage,
                    gated,
                )
            elif outfall_type in ("FREE", "NORMAL"):
                # FREE / NORMAL take no stage data
                builder.add(
                    "OUTFALLS",
                    self.swmm_name(entity_id),
                    fmt_num(eg.invert_elevation.array[idx]),
                    outfall_type,
                    gated,
                )
            else:
                # TIDAL / TIMESERIES need a referenced curve/timeseries that this
                # model does not synthesise; fail fast rather than emit a row SWMM
                # rejects.
                raise ValueError(
                    f"Outfall '{self.swmm_name(entity_id)}' has unsupported outfall_type "
                    f"'{outfall_type}'; only FREE, NORMAL and FIXED are supported"
                )
        self._add_coordinates(builder)


class StorageProcessor(NodeProcessor[StorageEntity]):
    PREFIX = "ST"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        const_mask = _defined_mask(eg.storage_constant)
        coeff_mask = _defined_mask(eg.storage_coefficient)
        exp_mask = _defined_mask(eg.storage_exponent)
        init_depth_mask = _defined_mask(eg.initial_depth)
        has_curve = eg.storage_curve.has_data()
        for idx, entity_id in enumerate(eg.index.ids):
            name = self.swmm_name(entity_id)
            elev = fmt_num(eg.invert_elevation.array[idx])
            ymax = fmt_num(eg.max_depth.array[idx])
            y0 = fmt_num(_opt_val(eg.initial_depth, idx, init_depth_mask, 0.0))

            # Infer the storage shape from which attributes are set: a
            # (depth, area) storage_curve -> TABULAR, otherwise FUNCTIONAL.
            curve = _extract_csr_curve(eg.storage_curve, idx) if has_curve else None
            if curve is not None:
                if any(m is not None and m[idx] for m in (const_mask, coeff_mask, exp_mask)):
                    self.wrapper.logger.warning(
                        f"Storage '{name}' has both a storage_curve and functional "
                        "coefficients; using the curve (TABULAR)."
                    )
                curve_name = self.wrapper.add_curve(curve, "Storage")
                builder.add("STORAGE", name, elev, ymax, y0, "TABULAR", curve_name)
            else:
                coeff = _opt_val(eg.storage_coefficient, idx, coeff_mask, 0.0)
                expon = _opt_val(eg.storage_exponent, idx, exp_mask, 0.0)
                const = _opt_val(eg.storage_constant, idx, const_mask, 0.0)
                if coeff == 0.0 and const == 0.0:
                    # A storage unit needs a non-zero surface area; fall back to a
                    # sensible constant area and warn rather than producing an
                    # invalid (zero-area) node.
                    const = 1000.0
                    self.wrapper.logger.warning(
                        f"Storage '{name}' has no surface-area definition; "
                        f"defaulting to a constant {const} area"
                    )
                builder.add(
                    "STORAGE",
                    name,
                    elev,
                    ymax,
                    y0,
                    "FUNCTIONAL",
                    fmt_num(coeff),
                    fmt_num(expon),
                    fmt_num(const),
                )
        self._add_coordinates(builder)


# ---------------------------------------------------------------------------
# Link processors
# ---------------------------------------------------------------------------


class ConduitProcessor(LinkProcessor[ConduitEntity]):
    PREFIX = "C"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        in_off_mask = _defined_mask(eg.inlet_offset)
        out_off_mask = _defined_mask(eg.outlet_offset)
        init_flow_mask = _defined_mask(eg.initial_flow)
        barrels_mask = _defined_mask(eg.barrels)
        for idx, entity_id in enumerate(eg.index.ids):
            name = self.swmm_name(entity_id)
            from_name, to_name = self._from_to(idx, entity_id)
            builder.add(
                "CONDUITS",
                name,
                from_name,
                to_name,
                fmt_num(eg.length.array[idx]),
                fmt_num(eg.roughness.array[idx]),
                fmt_num(_opt_val(eg.inlet_offset, idx, in_off_mask, 0.0)),
                fmt_num(_opt_val(eg.outlet_offset, idx, out_off_mask, 0.0)),
                fmt_num(_opt_val(eg.initial_flow, idx, init_flow_mask, 0.0)),
                0,
            )
            geom = eg.cross_section_geometry.array[idx]
            barrels = _opt_val(eg.barrels, idx, barrels_mask, 1)
            builder.add(
                "XSECTIONS",
                name,
                _enum_kw(eg.cross_section_shape, idx),
                fmt_num(geom[0]),
                fmt_num(geom[1]),
                fmt_num(geom[2]),
                fmt_num(geom[3]),
                max(barrels, 1),
            )


class PumpProcessor(LinkProcessor[PumpEntity]):
    PREFIX = "PU"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        has_curve = eg.pump_curve.has_data()
        curve_type_mask = _defined_mask(eg.pump_curve_type)
        startup_mask = _defined_mask(eg.startup_depth)
        shutoff_mask = _defined_mask(eg.shutoff_depth)
        for idx, entity_id in enumerate(eg.index.ids):
            name = self.swmm_name(entity_id)
            from_name, to_name = self._from_to(idx, entity_id)

            curve_type = "IDEAL"
            if curve_type_mask is not None and curve_type_mask[idx]:
                curve_type = _enum_kw(eg.pump_curve_type, idx)

            curve = _extract_csr_curve(eg.pump_curve, idx) if has_curve else None
            if curve is not None and curve_type == "IDEAL":
                # A curve was supplied but no pump_curve_type to interpret it;
                # don't silently drop the curve and run as an ideal pump.
                raise ValueError(
                    f"Pump '{name}' has a pump_curve but no pump_curve_type to interpret it"
                )

            curve_name = "*"
            if curve is not None:
                curve_name = self.wrapper.add_curve(curve, curve_type)

            builder.add(
                "PUMPS",
                name,
                from_name,
                to_name,
                curve_name,
                "ON",
                fmt_num(_opt_val(eg.startup_depth, idx, startup_mask, 0.0)),
                fmt_num(_opt_val(eg.shutoff_depth, idx, shutoff_mask, 0.0)),
            )


class OrificeProcessor(LinkProcessor[OrificeEntity]):
    PREFIX = "OR"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        offset_mask = _defined_mask(eg.crest_height)
        gate_mask = _defined_mask(eg.flap_gate)
        for idx, entity_id in enumerate(eg.index.ids):
            name = self.swmm_name(entity_id)
            from_name, to_name = self._from_to(idx, entity_id)
            gated = "YES" if _opt_val(eg.flap_gate, idx, gate_mask, False) else "NO"
            builder.add(
                "ORIFICES",
                name,
                from_name,
                to_name,
                _enum_kw(eg.orifice_type, idx),
                fmt_num(_opt_val(eg.crest_height, idx, offset_mask, 0.0)),
                fmt_num(eg.discharge_coefficient.array[idx]),
                gated,
                0,
            )
            geom = eg.cross_section_geometry.array[idx]
            builder.add(
                "XSECTIONS",
                name,
                _enum_kw(eg.orifice_shape, idx),
                fmt_num(geom[0]),
                fmt_num(geom[1]),
                fmt_num(geom[2]),
                fmt_num(geom[3]),
                1,
            )


class WeirProcessor(LinkProcessor[WeirEntity]):
    PREFIX = "W"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        offset_mask = _defined_mask(eg.crest_height)
        gate_mask = _defined_mask(eg.flap_gate)
        for idx, entity_id in enumerate(eg.index.ids):
            name = self.swmm_name(entity_id)
            from_name, to_name = self._from_to(idx, entity_id)
            gated = "YES" if _opt_val(eg.flap_gate, idx, gate_mask, False) else "NO"
            geom = eg.cross_section_geometry.array[idx]
            weir_type = _enum_kw(eg.weir_type, idx)
            # SWMM requires the opening cross-section shape to match the weir type
            xsection_shape = _WEIR_XSECTION_SHAPE.get(weir_type, "RECT_OPEN")
            # [WEIRS]: Name From To Type CrestHt Cd Gated EC Cd2 Sur
            builder.add(
                "WEIRS",
                name,
                from_name,
                to_name,
                weir_type,
                fmt_num(_opt_val(eg.crest_height, idx, offset_mask, 0.0)),
                fmt_num(eg.discharge_coefficient.array[idx]),
                gated,
                0,
                0,
                "YES",
            )
            # Weir opening geometry: Geom1=height, Geom2=length, Geom3=side slope
            builder.add(
                "XSECTIONS",
                name,
                xsection_shape,
                fmt_num(geom[0]),
                fmt_num(geom[1]),
                fmt_num(geom[2]),
                fmt_num(geom[3]),
                1,
            )


class OutletProcessor(LinkProcessor[OutletEntity]):
    PREFIX = "OU"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        offset_mask = _defined_mask(eg.crest_height)
        gate_mask = _defined_mask(eg.flap_gate)
        coeff_mask = _defined_mask(eg.rating_coefficient)
        exp_mask = _defined_mask(eg.rating_exponent)
        for idx, entity_id in enumerate(eg.index.ids):
            name = self.swmm_name(entity_id)
            from_name, to_name = self._from_to(idx, entity_id)
            rating_type = _enum_kw(eg.outlet_rating_type, idx)
            gated = "YES" if _opt_val(eg.flap_gate, idx, gate_mask, False) else "NO"
            offset = fmt_num(_opt_val(eg.crest_height, idx, offset_mask, 0.0))
            if "TABULAR" in rating_type:
                curve = _extract_csr_curve(eg.rating_curve, idx)
                if curve is None:
                    raise ValueError(f"Tabular outlet '{name}' requires a rating_curve")
                curve_name = self.wrapper.add_curve(curve, "Rating")
                builder.add(
                    "OUTLETS", name, from_name, to_name, offset, rating_type, curve_name, gated
                )
            else:
                coeff = fmt_num(_opt_val(eg.rating_coefficient, idx, coeff_mask, 1.0))
                expon = fmt_num(_opt_val(eg.rating_exponent, idx, exp_mask, 0.5))
                builder.add(
                    "OUTLETS", name, from_name, to_name, offset, rating_type, coeff, expon, gated
                )


# ---------------------------------------------------------------------------
# Hydrology processors
# ---------------------------------------------------------------------------


class SubcatchmentProcessor(SwmmProcessor[SubcatchmentEntity]):
    PREFIX = "S"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        n_imperv_mask = _defined_mask(eg.n_imperv)
        n_perv_mask = _defined_mask(eg.n_perv)
        s_imperv_mask = _defined_mask(eg.s_imperv)
        s_perv_mask = _defined_mask(eg.s_perv)
        pct_zero_mask = _defined_mask(eg.pct_zero)
        max_inf_mask = _defined_mask(eg.max_infiltration_rate)
        min_inf_mask = _defined_mask(eg.min_infiltration_rate)
        decay_mask = _defined_mask(eg.decay_constant)
        dry_mask = _defined_mask(eg.dry_time)
        suction_mask = _defined_mask(eg.suction_head)
        ksat_mask = _defined_mask(eg.conductivity)
        imd_mask = _defined_mask(eg.initial_deficit)
        cn_mask = _defined_mask(eg.curve_number)
        model = self.wrapper.infiltration_model
        for idx, entity_id in enumerate(eg.index.ids):
            name = self.swmm_name(entity_id)
            try:
                outlet_name = self.wrapper.id_mapper.get_swmm_name(eg.outlet_node_id.array[idx])
            except KeyError:
                raise ValueError(
                    f"Invalid outlet_node_id {eg.outlet_node_id.array[idx]} "
                    f"for subcatchment #{entity_id}"
                ) from None
            try:
                gage_name = self.wrapper.id_mapper.get_swmm_name(eg.raingage_id.array[idx])
            except KeyError:
                raise ValueError(
                    f"Invalid raingage_id {eg.raingage_id.array[idx]} "
                    f"for subcatchment #{entity_id}"
                ) from None

            builder.add(
                "SUBCATCHMENTS",
                name,
                gage_name,
                outlet_name,
                fmt_num(eg.area.array[idx]),
                fmt_num(eg.percent_impervious.array[idx]),
                fmt_num(eg.width.array[idx]),
                fmt_num(eg.slope.array[idx]),
                0,
            )
            builder.add(
                "SUBAREAS",
                name,
                fmt_num(_opt_val(eg.n_imperv, idx, n_imperv_mask, 0.01)),
                fmt_num(_opt_val(eg.n_perv, idx, n_perv_mask, 0.1)),
                fmt_num(_opt_val(eg.s_imperv, idx, s_imperv_mask, 0.05)),
                fmt_num(_opt_val(eg.s_perv, idx, s_perv_mask, 0.05)),
                fmt_num(_opt_val(eg.pct_zero, idx, pct_zero_mask, 25.0)),
                "OUTLET",
            )
            # The [INFILTRATION] row format depends on the configured model.
            if model in ("HORTON", "MODIFIED_HORTON"):
                builder.add(
                    "INFILTRATION",
                    name,
                    fmt_num(_opt_val(eg.max_infiltration_rate, idx, max_inf_mask, 76.2)),
                    fmt_num(_opt_val(eg.min_infiltration_rate, idx, min_inf_mask, 3.81)),
                    fmt_num(_opt_val(eg.decay_constant, idx, decay_mask, 4.0)),
                    fmt_num(_opt_val(eg.dry_time, idx, dry_mask, 7.0)),
                    0,
                )
            elif model in ("GREEN_AMPT", "MODIFIED_GREEN_AMPT"):
                builder.add(
                    "INFILTRATION",
                    name,
                    fmt_num(_opt_val(eg.suction_head, idx, suction_mask, 100.0)),
                    fmt_num(_opt_val(eg.conductivity, idx, ksat_mask, 5.0)),
                    fmt_num(_opt_val(eg.initial_deficit, idx, imd_mask, 0.3)),
                )
            elif model == "CURVE_NUMBER":
                builder.add(
                    "INFILTRATION",
                    name,
                    fmt_num(_opt_val(eg.curve_number, idx, cn_mask, 80.0)),
                    fmt_num(_opt_val(eg.conductivity, idx, ksat_mask, 5.0)),
                    fmt_num(_opt_val(eg.dry_time, idx, dry_mask, 7.0)),
                )
            else:
                raise ValueError(
                    f"Unsupported infiltration model '{model}'; expected one of "
                    "HORTON, MODIFIED_HORTON, GREEN_AMPT, MODIFIED_GREEN_AMPT, CURVE_NUMBER"
                )

    def write_results(self) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        for idx, entity_id in enumerate(eg.index.ids):
            sub = self.wrapper.subcatchments[self.swmm_name(entity_id)]
            eg.rainfall.array[idx] = sub.rainfall
            eg.runoff.array[idx] = sub.runoff
            eg.runon.array[idx] = sub.runon
            eg.infiltration_loss.array[idx] = sub.infiltration_loss
            eg.evaporation_loss.array[idx] = sub.evaporation_loss
            eg.snow_depth.array[idx] = sub.snow_depth


class RainGageProcessor(SwmmProcessor[RainGageEntity]):
    PREFIX = "RG"

    def build_inp(self, builder: InpBuilder) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        fmt_mask = _defined_mask(eg.rainfall_format)
        interval_mask = _defined_mask(eg.rainfall_interval)
        has_xy = eg.x.has_data() and eg.y.has_data()
        for idx, entity_id in enumerate(eg.index.ids):
            name = self.swmm_name(entity_id)
            rain_format = "INTENSITY"
            if fmt_mask is not None and fmt_mask[idx]:
                rain_format = _enum_kw(eg.rainfall_format, idx)
            # Rain gage interval is an "H:MM" value at minute resolution; clamp to
            # at least one minute so sub-minute intervals don't round to "0:00".
            interval_seconds = _opt_val(eg.rainfall_interval, idx, interval_mask, 3600.0)
            interval_minutes = max(1, int(round(interval_seconds / 60)))
            interval = f"{interval_minutes // 60:d}:{interval_minutes % 60:02d}"
            ts_name = f"{name}_ts"
            builder.add("RAINGAGES", name, rain_format, interval, 1.0, "TIMESERIES", ts_name)
            # Placeholder timeseries (single zero sample); rainfall is driven at
            # runtime via RainGage.total_precip (see process_changes).
            builder.add(
                "TIMESERIES", ts_name, self.wrapper.start_date, self.wrapper.start_time[:5], 0
            )
            if has_xy:
                builder.add("SYMBOLS", name, fmt_num(eg.x.array[idx]), fmt_num(eg.y.array[idx]))

    def process_changes(self) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        intensity_mask = _defined_mask(eg.rainfall_intensity)
        if intensity_mask is None:
            return
        for idx, entity_id in enumerate(eg.index.ids):
            if intensity_mask[idx]:
                gage = self.wrapper.raingages[self.swmm_name(entity_id)]
                gage.total_precip = float(eg.rainfall_intensity.array[idx])

    def write_results(self) -> None:
        eg = self.entity_group
        if not len(eg):
            return
        for idx, entity_id in enumerate(eg.index.ids):
            eg.rainfall.array[idx] = self.wrapper.raingages[self.swmm_name(entity_id)].rainfall


# Processor registry: (attribute on UrbanDrainageNetwork, processor class).
# Order matters: nodes and rain gages must be registered before links and
# subcatchments, which reference them by id.
_PROCESSOR_SPECS: t.Tuple[t.Tuple[str, t.Type[SwmmProcessor]], ...] = (
    ("junctions", JunctionProcessor),
    ("outfalls", OutfallProcessor),
    ("storage", StorageProcessor),
    ("raingages", RainGageProcessor),
    ("subcatchments", SubcatchmentProcessor),
    ("conduits", ConduitProcessor),
    ("pumps", PumpProcessor),
    ("orifices", OrificeProcessor),
    ("weirs", WeirProcessor),
    ("outlets", OutletProcessor),
)


class SimulationWrapper:
    """Owns the live pyswmm :class:`~pyswmm.Simulation` and its processors."""

    # EPA-SWMM permits only one open simulation per process. This tracks the
    # wrapper that currently holds it, so a second concurrent open fails with a
    # clear message instead of pyswmm's cryptic MultiSimulationError.
    _active: t.ClassVar[t.Optional["SimulationWrapper"]] = None

    def __init__(self, logger: t.Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.processors: t.Dict[str, SwmmProcessor] = {}
        self.id_mapper = IdMapper()
        self.sim: t.Optional[Simulation] = None
        self.nodes: t.Optional[Nodes] = None
        self.links: t.Optional[Links] = None
        self.subcatchments: t.Optional[Subcatchments] = None
        self.raingages: t.Optional[RainGages] = None
        self._inp_path: t.Optional[str] = None
        self._curve_counter = 0
        self._curve_lines: t.List[str] = []
        self._options: t.Dict[str, t.Any] = {}
        # Offset (seconds) added to the raw SWMM clock so a simulation rolled back
        # to a hotstart keeps reporting the same Movici time. Temp hotstart files
        # created by checkpoint() are tracked for cleanup in close(); their capture
        # times are recorded so rollback_to() restores state and clock together.
        self._time_offset: float = 0.0
        self._hotstart_files: t.List[str] = []
        self._checkpoint_seconds: t.Dict[str, float] = {}
        # Calendar start for the synthesised model; None falls back to the module
        # constants. Set from the Movici timeline so SWMM timestamps line up with
        # the scenario's world time.
        self._start_datetime: t.Optional[_datetime.datetime] = None

    # -- construction -------------------------------------------------------

    def add_curve(self, points: np.ndarray, curve_type: str) -> str:
        """Register a SWMM curve and return its generated name."""
        self._curve_counter += 1
        name = f"curve_{self._curve_counter}"
        first = points[0]
        rows = [f"{name}  {curve_type}  {fmt_num(first[0])}  {fmt_num(first[1])}"]
        rows += [f"{name}  {fmt_num(p[0])}  {fmt_num(p[1])}" for p in points[1:]]
        self._curve_lines.extend(rows)
        return name

    def configure_options(
        self, options: dict, start_datetime: t.Optional[_datetime.datetime] = None
    ) -> None:
        """Store options (and optional calendar start) for synthesising ``[OPTIONS]``."""
        self._options = dict(options or {})
        self._start_datetime = start_datetime

    @property
    def start_date(self) -> str:
        """SWMM ``MM/DD/YYYY`` start date (from the Movici timeline, else default)."""
        if self._start_datetime is not None:
            return self._start_datetime.strftime("%m/%d/%Y")
        return START_DATE

    @property
    def start_time(self) -> str:
        """SWMM ``HH:MM:SS`` start time (from the Movici timeline, else default)."""
        if self._start_datetime is not None:
            return self._start_datetime.strftime("%H:%M:%S")
        return START_TIME

    @property
    def infiltration_model(self) -> str:
        """The configured SWMM infiltration model keyword (upper-cased)."""
        return str(self._options.get("infiltration", "HORTON")).upper()

    def initialize(self, dataset: UrbanDrainageNetwork) -> None:
        """Build the processors, synthesise the ``.inp`` and open the simulation."""
        self.processors = {
            attr: cls(self, getattr(dataset, attr)) for attr, cls in _PROCESSOR_SPECS
        }
        inp_text = self._build_inp()
        fd, self._inp_path = tempfile.mkstemp(suffix=".inp", prefix="movici_swmm_")
        with os.fdopen(fd, "w") as fh:
            fh.write(inp_text)
        self._open_simulation()

    def _open_simulation(
        self, hotstart_file: t.Optional[str] = None, start_offset: float = 0.0
    ) -> None:
        """Open a pyswmm ``Simulation`` on the synthesised ``.inp`` and build the
        object collections. The ``.inp`` and processors are reused, so this also
        serves :meth:`rollback_to`. ``hotstart_file`` seeds the engine state and
        ``start_offset`` keeps the reported Movici time aligned to that snapshot.
        """
        if SimulationWrapper._active is not None and SimulationWrapper._active is not self:
            raise RuntimeError(
                "Another urban_drainage SWMM simulation is already open in this "
                "process. EPA-SWMM permits only one open simulation at a time; "
                "close it first, or run the models in separate processes "
                "(e.g. a distributed simulation)."
            )
        self.sim = Simulation(self._inp_path)
        if hotstart_file is not None:
            # must precede start(): seeds the engine state from the snapshot
            self.sim.use_hotstart(hotstart_file)
        self.sim.start()
        SimulationWrapper._active = self
        self._time_offset = float(start_offset)
        self.nodes = Nodes(self.sim)
        self.links = Links(self.sim)
        self.subcatchments = Subcatchments(self.sim)
        self.raingages = RainGages(self.sim)

    # -- state save / restore ----------------------------------------------
    #
    # ``checkpoint`` and ``rollback_to`` are low-level engine capabilities: SWMM
    # is forward-only, so the only way to re-run an interval (e.g. a predictor-
    # corrector / implicit-coupling iteration) is to snapshot the engine state to
    # a hotstart file and reopen from it. They are deliberately NOT wired into the
    # model's ``update()`` loop - there is no Movici orchestrator protocol to drive
    # a timestep re-run yet (see the REMAP work, issue #127). They exist so that
    # protocol, once it lands, has a proven primitive to call.

    def checkpoint(self, path: t.Optional[str] = None) -> str:
        """Snapshot the current simulation state to a hotstart file.

        Pass the returned path to :meth:`rollback_to` to restore this exact state
        (and reported time) later. May be called at any point during the run.

        :param path: target ``.hsf`` path; a temporary file (cleaned up in
            :meth:`close`) is created when omitted.
        :return: the hotstart file path.
        """
        if self.sim is None:
            raise RuntimeError("Cannot checkpoint before initialize()")
        if path is None:
            fd, path = tempfile.mkstemp(suffix=".hsf", prefix="movici_swmm_ckpt_")
            os.close(fd)
            self._hotstart_files.append(path)
        self._checkpoint_seconds[path] = self.elapsed_seconds()
        self.sim.save_hotstart(path)
        return path

    def rollback_to(self, checkpoint: str) -> None:
        """Restore the simulation to a state captured by :meth:`checkpoint`.

        Closes the current engine (keeping the synthesised ``.inp``, processors and
        id-map) and reopens it from the checkpoint, restoring both the engine state
        and the reported Movici time. The interval after the checkpoint can then be
        re-run - e.g. with corrected control inputs.
        """
        if self.sim is None:
            raise RuntimeError("Cannot rollback before initialize()")
        # close only the engine; keep the .inp, processors and hotstart files
        self.sim.close()
        self.sim = None
        self.nodes = self.links = self.subcatchments = self.raingages = None
        self._open_simulation(
            hotstart_file=checkpoint, start_offset=self._checkpoint_seconds.get(checkpoint, 0.0)
        )

    def _build_inp(self) -> str:
        builder = InpBuilder()
        self._write_options(builder)
        # Pass 1: register all ids so links/subcatchments can resolve references.
        for processor in self.processors.values():
            processor.register()
        # Pass 2: emit the .inp rows.
        self._curve_lines = []
        for processor in self.processors.values():
            processor.build_inp(builder)
        for line in self._curve_lines:
            builder.add("CURVES", line)
        return builder.render()

    def _write_options(self, builder: InpBuilder) -> None:
        opt = self._options
        hydraulic_timestep = float(opt.get("hydraulic_timestep", 60))
        report_timestep = float(opt.get("report_timestep", 300))
        builder.add("TITLE", "Movici urban drainage model")
        builder.add("OPTIONS", "FLOW_UNITS", opt.get("flow_units", "CMS"))
        builder.add("OPTIONS", "INFILTRATION", self.infiltration_model)
        builder.add("OPTIONS", "FLOW_ROUTING", opt.get("flow_routing", "DYNWAVE"))
        builder.add("OPTIONS", "LINK_OFFSETS", "DEPTH")
        builder.add("OPTIONS", "MIN_SLOPE", 0)
        builder.add("OPTIONS", "START_DATE", self.start_date)
        builder.add("OPTIONS", "START_TIME", self.start_time)
        builder.add("OPTIONS", "REPORT_START_DATE", self.start_date)
        builder.add("OPTIONS", "REPORT_START_TIME", self.start_time)
        builder.add("OPTIONS", "END_DATE", END_DATE)
        builder.add("OPTIONS", "END_TIME", END_TIME)
        builder.add("OPTIONS", "REPORT_STEP", fmt_hms(report_timestep))
        builder.add("OPTIONS", "WET_STEP", fmt_hms(report_timestep))
        builder.add("OPTIONS", "DRY_STEP", fmt_hms(report_timestep))
        builder.add("OPTIONS", "ROUTING_STEP", fmt_num(hydraulic_timestep))
        builder.add("EVAPORATION", "CONSTANT", 0.0)

    # -- stepping -----------------------------------------------------------

    def elapsed_seconds(self) -> float:
        assert self.sim is not None
        raw = (self.sim.current_time - self.sim.start_time).total_seconds()
        return self._time_offset + raw

    def process_changes(self) -> None:
        """Apply all runtime control inputs to the live simulation objects."""
        for processor in self.processors.values():
            processor.process_changes()

    def advance_to(self, target_seconds: int) -> None:
        """Step the live simulation forward until at least *target_seconds*.

        SWMM marches forward only, so this never steps backwards. Control inputs
        must already have been applied (see :meth:`process_changes`).
        """
        assert self.sim is not None
        # SWMM advances in whole seconds; a sub-second remainder is left for the
        # next update. Movici moments are integer seconds, so this loses nothing.
        while target_seconds - self.elapsed_seconds() >= 1:
            before = self.elapsed_seconds()
            self.sim.step_advance(int(target_seconds - before))
            try:
                next(self.sim)
            except StopIteration:
                self.logger.warning(
                    "SWMM simulation reached its end time before "
                    f"t={target_seconds}s; results frozen at t={before:.0f}s"
                )
                break
            if self.elapsed_seconds() <= before:  # defensive: no progress, don't spin
                break

    def write_results(self) -> None:
        """Read the current simulation state into the PUBLISH attribute arrays."""
        for processor in self.processors.values():
            processor.write_results()

    def close(self) -> None:
        """Finalise and close the simulation, removing the transient ``.inp``.

        EPA-SWMM only permits one open simulation per process, so releasing the
        simulation (and the object collections that reference it) here is what
        lets a subsequent model run open its own simulation.
        """
        if self.sim is not None:
            try:
                self.sim.report()
            finally:
                self.sim.close()
            self.sim = None
        if SimulationWrapper._active is self:
            SimulationWrapper._active = None
        self.nodes = None
        self.links = None
        self.subcatchments = None
        self.raingages = None
        if self._inp_path and os.path.exists(self._inp_path):
            try:
                os.remove(self._inp_path)
            except OSError:
                pass
            self._inp_path = None
        for hsf in self._hotstart_files:
            if os.path.exists(hsf):
                try:
                    os.remove(hsf)
                except OSError:
                    pass
        self._hotstart_files = []
        self._checkpoint_seconds = {}
