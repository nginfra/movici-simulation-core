"""Main wrapper for WNTR WaterNetworkModel with Movici integration.

This module provides a clean interface between Movici's entity-based
data model and WNTR's water network simulation engine.
"""

from __future__ import annotations

import logging
import typing as t

import numpy as np
import wntr

from .dataset import (
    DrinkingWaterNetwork,
    WaterJunctionEntity,
    WaterPipeEntity,
    WaterPumpEntity,
    WaterReservoirEntity,
    WaterTankEntity,
    WaterValveEntity,
)

logger = logging.getLogger(__name__)

T = t.TypeVar("T")


def _extract_csr_curve(csr_attribute, idx: int) -> t.Optional[np.ndarray]:
    """Extract a single curve from a CSR attribute.

    :param csr_attribute: CSR attribute containing curve data
    :param idx: Index of the entity
    :return: Numpy array of curve data, or None if empty
    """
    csr = csr_attribute.csr
    start = csr.row_ptr[idx]
    end = csr.row_ptr[idx + 1]
    if end > start:
        return csr.data[start:end]
    return None


def _opt_defined(attr) -> t.Optional[np.ndarray]:
    """Return a boolean mask of defined values, or None if attr has no data."""
    if not attr.has_data():
        return None
    return ~attr.is_undefined()


def _opt_val(attr, idx: int, mask: t.Optional[np.ndarray], default):
    """Get optional attribute value, returning *default* if undefined."""
    if mask is not None and mask[idx]:
        return type(default)(attr.array[idx])
    return default


class WNTRElementProcessor(t.Generic[T]):
    def __init__(self, wrapper: NetworkWrapper, entity_group: T):
        self.wrapper = wrapper
        self.entity_group = entity_group

    @property
    def wn(self) -> wntr.network.WaterNetworkModel:
        return self.wrapper.wn

    def create_elements(self):
        raise NotImplementedError

    def update_elements(self):
        pass

    def write_results(self, results: wntr.sim.SimulationResults, df_offset: int):
        """Write WNTR SimulationResults to self.entity_group.

        :param results: The simulation results
        :param df_offset: Numerical offset where this processor's data starts
            in the results dataframe
        """
        pass


class NodeProcessor(WNTRElementProcessor[T]):
    """Base for node processors that write head & pressure.

    Subclasses must define ``PREFIX`` (e.g. ``"J"`` for junctions).
    """

    PREFIX: str

    def _node_name(self, entity_id: int) -> str:
        return self.PREFIX + str(entity_id)

    def write_results(self, results: wntr.sim.SimulationResults, df_offset: int):
        eg = self.entity_group
        size = len(eg)
        if not size:
            return
        end = df_offset + size
        # the slicing assignment ([:]) is needed to maintain change tracking
        eg.head.array[:] = results.node["head"].iloc[-1].values[df_offset:end]
        eg.pressure.array[:] = results.node["pressure"].iloc[-1].values[df_offset:end]


class LinkProcessor(WNTRElementProcessor[T]):
    """Base for link processors that write flow, flow_rate_magnitude, link_status.

    Subclasses must define ``PREFIX`` (e.g. ``"P"`` for pipes).
    """

    PREFIX: str

    def _link_name(self, entity_id: int) -> str:
        return self.PREFIX + str(entity_id)

    def _from_to(self, idx: int) -> tuple[str, str]:
        eg = self.entity_group
        from_id = int(eg.from_node_id.array[idx])
        to_id = int(eg.to_node_id.array[idx])
        return (
            self.wrapper.id_mapper.get_wntr_name(from_id),
            self.wrapper.id_mapper.get_wntr_name(to_id),
        )

    def write_results(self, results: wntr.sim.SimulationResults, df_offset: int):
        eg = self.entity_group
        size = len(eg)
        if not size:
            return
        end = df_offset + size
        # the slicing assignment ([:]) is needed to maintain change tracking
        flows = results.link["flowrate"].iloc[-1].values[df_offset:end]
        eg.flow.array[:] = flows
        eg.flow_rate_magnitude.array[:] = np.abs(flows)
        if "status" in results.link:
            eg.link_status.array[:] = (
                results.link["status"].iloc[-1].values[df_offset:end].astype(int)
            )


# ---------------------------------------------------------------------------
# Node processors
# ---------------------------------------------------------------------------


class JunctionProcessor(NodeProcessor[WaterJunctionEntity]):
    PREFIX = "J"

    def create_elements(self):
        eg = self.entity_group
        if not len(eg):
            return

        # Pre-compute effective demands (base_demand * demand_factor where defined)
        demand = eg.base_demand.array.copy()
        df_defined = _opt_defined(eg.demand_factor)
        if df_defined is not None:
            demand[df_defined] *= eg.demand_factor.array[df_defined]

        # Pre-compute PDD masks
        min_p_defined = _opt_defined(eg.minimum_pressure)
        req_p_defined = _opt_defined(eg.required_pressure)
        exp_defined = _opt_defined(eg.pressure_exponent)

        for idx, entity_id in enumerate(eg.index.ids):
            name = self._node_name(entity_id)
            self.wrapper.id_mapper.register_nodes(
                np.array([entity_id]), prefix=self.PREFIX
            )

            self.wn.add_junction(
                name=name,
                base_demand=float(demand[idx]),
                elevation=float(eg.elevation.array[idx]),
            )

            junction = t.cast(wntr.network.Junction, self.wn.get_node(name))
            if min_p_defined is not None and min_p_defined[idx]:
                junction.minimum_pressure = float(eg.minimum_pressure.array[idx])
            if req_p_defined is not None and req_p_defined[idx]:
                junction.required_pressure = float(eg.required_pressure.array[idx])
            if exp_defined is not None and exp_defined[idx]:
                junction.pressure_exponent = float(eg.pressure_exponent.array[idx])

    def update_elements(self):
        eg = self.entity_group
        if not len(eg):
            return
        bd_changed = eg.base_demand.changed
        df_changed = eg.demand_factor.changed if eg.demand_factor.has_data() else bd_changed
        any_changed = bd_changed | df_changed

        df_defined = _opt_defined(eg.demand_factor)

        for idx in np.flatnonzero(any_changed):
            junction = t.cast(
                wntr.network.Junction,
                self.wn.get_node(self._node_name(eg.index.ids[idx])),
            )
            demand = float(eg.base_demand.array[idx])
            if df_defined is not None and df_defined[idx]:
                demand *= float(eg.demand_factor.array[idx])
            junction.demand_timeseries_list[0].base_value = demand

    def write_results(self, results: wntr.sim.SimulationResults, df_offset: int):
        eg = self.entity_group
        size = len(eg)
        if not size:
            return
        end = df_offset + size
        eg.head.array[:] = results.node["head"].iloc[-1].values[df_offset:end]
        eg.pressure.array[:] = results.node["pressure"].iloc[-1].values[df_offset:end]
        eg.demand.array[:] = results.node["demand"].iloc[-1].values[df_offset:end]


class TankProcessor(NodeProcessor[WaterTankEntity]):
    PREFIX = "T"

    def create_elements(self):
        eg = self.entity_group
        size = len(eg)
        if not size:
            return

        # Pre-compute all optional masks
        min_lvl_defined = _opt_defined(eg.min_level)
        max_lvl_defined = _opt_defined(eg.max_level)
        dia_defined = _opt_defined(eg.diameter)
        min_vol_defined = _opt_defined(eg.min_volume)
        has_vol_curve = eg.volume_curve.has_data()
        overflow_defined = _opt_defined(eg.overflow)

        # Pre-compute default arrays
        init_levels = eg.level.array
        elevations = eg.elevation.array

        for idx, entity_id in enumerate(eg.index.ids):
            name = self._node_name(entity_id)
            self.wrapper.id_mapper.register_nodes(
                np.array([entity_id]), prefix=self.PREFIX
            )

            init_level = float(init_levels[idx])
            min_level = _opt_val(eg.min_level, idx, min_lvl_defined, 0.0)
            max_level = _opt_val(
                eg.max_level, idx, max_lvl_defined, init_level * 2
            )
            diameter = _opt_val(eg.diameter, idx, dia_defined, 0.0)
            min_vol = _opt_val(eg.min_volume, idx, min_vol_defined, 0.0)

            vol_curve_name = None
            if has_vol_curve:
                curve_data = _extract_csr_curve(eg.volume_curve, idx)
                if curve_data is not None:
                    vol_curve_name = self.wrapper.add_curve(curve_data, "VOLUME")

            self.wn.add_tank(
                name=name,
                elevation=float(elevations[idx]),
                init_level=init_level,
                min_level=min_level,
                max_level=max_level,
                diameter=diameter,
                min_vol=min_vol,
                vol_curve=vol_curve_name,
            )

            if overflow_defined is not None and overflow_defined[idx]:
                self.wn.get_node(name).overflow = bool(eg.overflow.array[idx])

    def write_results(self, results: wntr.sim.SimulationResults, df_offset: int):
        eg = self.entity_group
        size = len(eg)
        if not size:
            return
        end = df_offset + size
        heads = results.node["head"].iloc[-1].values[df_offset:end]
        eg.head.array[:] = heads
        eg.pressure.array[:] = results.node["pressure"].iloc[-1].values[df_offset:end]
        eg.demand.array[:] = results.node["demand"].iloc[-1].values[df_offset:end]
        eg.level.array[:] = heads - eg.elevation.array


class ReservoirProcessor(WNTRElementProcessor[WaterReservoirEntity]):
    PREFIX = "R"

    def _node_name(self, entity_id: int) -> str:
        return self.PREFIX + str(entity_id)

    def create_elements(self):
        eg = self.entity_group
        if not len(eg):
            return

        # Pre-compute effective heads
        heads = eg.base_head.array.copy()
        hf_defined = _opt_defined(eg.head_factor)
        if hf_defined is not None:
            heads[hf_defined] *= eg.head_factor.array[hf_defined]

        for idx, entity_id in enumerate(eg.index.ids):
            name = self._node_name(entity_id)
            self.wrapper.id_mapper.register_nodes(
                np.array([entity_id]), prefix=self.PREFIX
            )
            self.wn.add_reservoir(
                name=name,
                base_head=float(heads[idx]),
                head_pattern=None,
            )

    def update_elements(self):
        eg = self.entity_group
        if not len(eg) or not eg.head_factor.has_data():
            return
        if not np.any(eg.head_factor.changed | eg.base_head.changed):
            return

        hf_defined = _opt_defined(eg.head_factor)

        for idx, entity_id in enumerate(eg.index.ids):
            reservoir = self.wn.get_node(self._node_name(entity_id))
            head = float(eg.base_head.array[idx])
            if hf_defined is not None and hf_defined[idx]:
                head *= float(eg.head_factor.array[idx])
            reservoir.base_head = head

    def write_results(self, results: wntr.sim.SimulationResults, df_offset: int):
        eg = self.entity_group
        size = len(eg)
        if not size:
            return
        end = df_offset + size
        eg.head.array[:] = results.node["head"].iloc[-1].values[df_offset:end]
        demands = results.node["demand"].iloc[-1].values[df_offset:end]
        eg.demand.array[:] = demands
        eg.flow.array[:] = -demands
        eg.flow_rate_magnitude.array[:] = np.abs(demands)


# ---------------------------------------------------------------------------
# Link processors
# ---------------------------------------------------------------------------


class PipeProcessor(LinkProcessor[WaterPipeEntity]):
    PREFIX = "P"

    def create_elements(self):
        eg = self.entity_group
        if not len(eg):
            return

        # Pre-compute optional masks
        status_defined = _opt_defined(eg.status)
        cv_defined = _opt_defined(eg.check_valve)
        length_defined = _opt_defined(eg.length)
        ml_defined = _opt_defined(eg.minor_loss)

        for idx, entity_id in enumerate(eg.index.ids):
            name = self._link_name(entity_id)
            self.wrapper.id_mapper.register_links(
                np.array([entity_id]), prefix=self.PREFIX
            )
            from_node, to_node = self._from_to(idx)

            status_str = "OPEN"
            if status_defined is not None and status_defined[idx]:
                status_str = "OPEN" if eg.status.array[idx] else "CLOSED"

            check_valve = False
            if cv_defined is not None and cv_defined[idx]:
                check_valve = bool(eg.check_valve.array[idx])

            length = _opt_val(eg.length, idx, length_defined, 100.0)
            minor_loss = _opt_val(eg.minor_loss, idx, ml_defined, 0.0)

            self.wn.add_pipe(
                name=name,
                start_node_name=from_node,
                end_node_name=to_node,
                length=length,
                diameter=float(eg.diameter.array[idx]),
                roughness=float(eg.roughness.array[idx]),
                minor_loss=minor_loss,
                initial_status=status_str,
                check_valve=check_valve,
            )

    def update_elements(self):
        eg = self.entity_group
        if not len(eg) or not eg.status.has_data():
            return
        if not np.any(eg.status.changed):
            return
        for idx in np.flatnonzero(eg.status.changed):
            link = self.wn.get_link(self._link_name(eg.index.ids[idx]))
            link.initial_status = (
                wntr.network.LinkStatus.Open
                if eg.status.array[idx]
                else wntr.network.LinkStatus.Closed
            )

    def write_results(self, results: wntr.sim.SimulationResults, df_offset: int):
        super().write_results(results, df_offset)
        eg = self.entity_group
        size = len(eg)
        if not size:
            return
        end = df_offset + size
        if "velocity" in results.link:
            eg.velocity.array[:] = results.link["velocity"].iloc[-1].values[df_offset:end]
        if "headloss" in results.link:
            eg.headloss.array[:] = results.link["headloss"].iloc[-1].values[df_offset:end]


class PumpProcessor(LinkProcessor[WaterPumpEntity]):
    PREFIX = "PU"

    def create_elements(self):
        eg = self.entity_group
        if not len(eg):
            return

        # Pre-compute enum strings and optional masks
        enum_values = eg.pump_type.options.enum_values
        pump_types = [enum_values[int(v)].upper() for v in eg.pump_type.array]
        has_head_curve = eg.head_curve.has_data()
        speed_defined = _opt_defined(eg.speed)
        status_defined = _opt_defined(eg.status)

        for idx, entity_id in enumerate(eg.index.ids):
            name = self._link_name(entity_id)
            self.wrapper.id_mapper.register_links(
                np.array([entity_id]), prefix=self.PREFIX
            )
            from_node, to_node = self._from_to(idx)
            pump_type = pump_types[idx]

            if pump_type == "POWER":
                power = 1.0
                if eg.power.has_data() and not eg.power.is_undefined()[idx]:
                    power = float(eg.power.array[idx])
                self.wn.add_pump(
                    name=name,
                    start_node_name=from_node,
                    end_node_name=to_node,
                    pump_type="POWER",
                    pump_parameter=power,
                )
            else:  # HEAD
                curve_data = None
                if has_head_curve:
                    curve_data = _extract_csr_curve(eg.head_curve, idx)
                if curve_data is None:
                    raise ValueError(f"Head pump '{name}' requires a head_curve")
                curve_name = self.wrapper.add_curve(curve_data, "HEAD")
                self.wn.add_pump(
                    name=name,
                    start_node_name=from_node,
                    end_node_name=to_node,
                    pump_type="HEAD",
                    pump_parameter=curve_name,
                )

            if pump_type == "HEAD" and speed_defined is not None and speed_defined[idx]:
                pump = self.wn.get_link(name)
                if hasattr(pump, "speed_timeseries"):
                    pump.speed_timeseries.base_value = float(eg.speed.array[idx])

            if status_defined is not None and status_defined[idx]:
                pump = self.wn.get_link(name)
                pump.initial_status = (
                    wntr.network.LinkStatus.Open
                    if eg.status.array[idx]
                    else wntr.network.LinkStatus.Closed
                )

    def update_elements(self):
        eg = self.entity_group
        if not len(eg) or not eg.status.has_data():
            return
        if not np.any(eg.status.changed):
            return
        for idx in np.flatnonzero(eg.status.changed):
            link = self.wn.get_link(self._link_name(eg.index.ids[idx]))
            link.initial_status = (
                wntr.network.LinkStatus.Open
                if eg.status.array[idx]
                else wntr.network.LinkStatus.Closed
            )


class ValveProcessor(LinkProcessor[WaterValveEntity]):
    PREFIX = "V"

    _VALVE_SETTING_ATTRS: t.ClassVar[dict[str, str]] = {
        "PRV": "valve_pressure",
        "PSV": "valve_pressure",
        "FCV": "valve_flow",
        "TCV": "valve_loss_coefficient",
    }

    def _get_setting(self, idx: int, valve_type: str, masks: dict) -> float:
        attr_name = self._VALVE_SETTING_ATTRS.get(valve_type)
        if attr_name:
            defined = masks.get(attr_name)
            if defined is not None and defined[idx]:
                return float(getattr(self.entity_group, attr_name).array[idx])
        raise ValueError(f"No setting available for valve type {valve_type} at index {idx}")

    def create_elements(self):
        eg = self.entity_group
        if not len(eg):
            return

        # Pre-compute enum strings and optional masks
        enum_values = eg.valve_type.options.enum_values
        valve_types = [enum_values[int(v)].upper() for v in eg.valve_type.array]
        ml_defined = _opt_defined(eg.minor_loss)

        # Pre-compute setting masks for all valve setting attributes
        setting_masks = {
            attr_name: _opt_defined(getattr(eg, attr_name))
            for attr_name in set(self._VALVE_SETTING_ATTRS.values())
        }

        for idx, entity_id in enumerate(eg.index.ids):
            name = self._link_name(entity_id)
            self.wrapper.id_mapper.register_links(
                np.array([entity_id]), prefix=self.PREFIX
            )
            from_node, to_node = self._from_to(idx)
            valve_type = valve_types[idx]
            setting = self._get_setting(idx, valve_type, setting_masks)
            minor_loss = _opt_val(eg.minor_loss, idx, ml_defined, 0.0)

            self.wn.add_valve(
                name=name,
                start_node_name=from_node,
                end_node_name=to_node,
                diameter=float(eg.diameter.array[idx]),
                valve_type=valve_type,
                minor_loss=minor_loss,
                initial_setting=setting,
            )


class NetworkWrapper:
    """Wraps WNTR WaterNetworkModel with Movici-friendly API.

    This class provides a clean interface between Movici's entity-based
    data model and WNTR's water network simulation engine.
    """

    def __init__(self):
        self.wntr = wntr
        self._curve_counter = 0
        self.wn = wntr.network.WaterNetworkModel()
        self.id_mapper = None
        self.processors: dict[str, WNTRElementProcessor] = {}

    def initialize(self, dataset: DrinkingWaterNetwork):
        """Build the WNTR WaterNetworkModel from a DrinkingWaterNetwork.

        :param dataset: A valid DrinkingWaterNetwork whose entity groups
            have been loaded with init data.
        """
        from .id_mapper import IdMapper

        self.id_mapper = IdMapper()
        self.processors["junctions"] = JunctionProcessor(self, dataset.junctions)
        self.processors["tanks"] = TankProcessor(self, dataset.tanks)
        self.processors["reservoirs"] = ReservoirProcessor(self, dataset.reservoirs)
        self.processors["pipes"] = PipeProcessor(self, dataset.pipes)
        self.processors["pumps"] = PumpProcessor(self, dataset.pumps)
        self.processors["valves"] = ValveProcessor(self, dataset.valves)

        for processor in self.processors.values():
            processor.create_elements()

    def process_changes(self):
        """Process any changes to the DrinkingWaterNetwork that may have happened
        and update the WNTR WaterNetworkModel."""
        for processor in self.processors.values():
            processor.update_elements()

    def add_curve(self, curve_data: np.ndarray, curve_type: str) -> str:
        """Add a curve to the WNTR network.

        :param curve_data: Numpy array of shape (N, 2) with x, y points
        :param curve_type: Type of curve (``"HEAD"``, ``"VOLUME"``, etc.)
        :return: Name of the created curve
        """
        self._curve_counter += 1
        curve_name = f"curve_{self._curve_counter}"

        if curve_data.ndim == 1:
            curve_data = curve_data.reshape(-1, 2)

        curve_points = [(float(row[0]), float(row[1])) for row in curve_data]
        self.wn.add_curve(curve_name, curve_type, curve_points)
        return curve_name

    def configure_options(self, options: dict):
        """Configure WNTR options from a dict of section_name -> {key: value} mappings.

        :param options: Dict mapping section names to dicts of option key/value pairs
        """
        for section_name, section_options in options.items():
            if not isinstance(section_options, dict):
                continue
            section = getattr(self.wn.options, section_name, None)
            if section is None:
                logger.warning(f"Unknown WNTR options section '{section_name}', ignoring")
                continue
            for key, value in section_options.items():
                if value is None:
                    continue
                if not hasattr(section, key):
                    logger.warning(f"Unknown option '{key}' in section '{section_name}', ignoring")
                    continue
                setattr(section, key, value)

    def run_simulation(
        self,
        duration: t.Optional[float] = None,
        hydraulic_timestep: float = 3600,
        report_timestep: t.Optional[float] = None,
    ) -> wntr.sim.SimulationResults:
        """Run WNTR simulation and return the raw results.

        :param duration: Simulation duration in seconds (None uses model setting)
        :param hydraulic_timestep: Hydraulic timestep in seconds
        :param report_timestep: Report timestep in seconds (None = same as hydraulic)
        :return: WNTR SimulationResults object
        """
        if duration is not None:
            self.wn.options.time.duration = int(duration)

        self.wn.options.time.hydraulic_timestep = int(hydraulic_timestep)

        if report_timestep is not None:
            self.wn.options.time.report_timestep = int(report_timestep)
        else:
            self.wn.options.time.report_timestep = int(hydraulic_timestep)

        self.wn.reset_initial_values()

        sim = self.wntr.sim.WNTRSimulator(self.wn)
        return sim.run_sim()

    def write_results(self, results: wntr.sim.SimulationResults):
        """Write WNTR results back into entity group arrays.

        The results dataframe columns are ordered by category then insertion
        order.  Nodes: Junction, Tank, Reservoir.  Links: Pipe, Pump, Valve.

        When adding new element types, the correct order in the result
        dataframe must be determined to calculate the right offset for
        each element's data.
        """
        df_offset = 0
        for kind in ["junctions", "tanks", "reservoirs"]:
            processor = self.processors[kind]
            processor.write_results(results, df_offset=df_offset)
            df_offset += len(processor.entity_group)

        df_offset = 0
        for kind in ["pipes", "pumps", "valves"]:
            processor = self.processors[kind]
            processor.write_results(results, df_offset=df_offset)
            df_offset += len(processor.entity_group)

    def get_network_summary(self) -> dict:
        """Get summary statistics of the network."""
        return {
            "num_junctions": self.wn.num_junctions,
            "num_tanks": self.wn.num_tanks,
            "num_reservoirs": self.wn.num_reservoirs,
            "num_pipes": self.wn.num_pipes,
            "num_pumps": self.wn.num_pumps,
            "num_valves": self.wn.num_valves,
            "num_patterns": len(self.wn.pattern_name_list),
            "num_curves": len(self.wn.curve_name_list),
        }

    def close(self):
        """Clean up resources."""
        pass
