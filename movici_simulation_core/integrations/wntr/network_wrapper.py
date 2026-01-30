"""Main wrapper for WNTR WaterNetworkModel with Movici integration.

This module provides a clean interface between Movici's entity-based
data model and WNTR's water network simulation engine.
"""

from __future__ import annotations

import logging
import typing as t

import numpy as np
import wntr

from .collections import (
    JunctionCollection,
    PipeCollection,
    PumpCollection,
    ReservoirCollection,
    SimulationResults,
    TankCollection,
    ValveCollection,
)
from .id_mapper import IdMapper

logger = logging.getLogger(__name__)


class NetworkWrapper:
    """Wraps WNTR WaterNetworkModel with Movici-friendly API.

    This class provides a clean interface between Movici's entity-based
    data model and WNTR's water network simulation engine.
    """

    def __init__(self):
        self.wntr = wntr
        self._curve_counter = 0
        self.wn = wntr.network.WaterNetworkModel()
        self.id_mapper = IdMapper()

    @staticmethod
    def _get_coords(
        coordinates: t.Optional[np.ndarray], index: int
    ) -> t.Optional[t.Tuple[float, float]]:
        """Extract coordinates for a single element.

        :param coordinates: Optional (N, 2) array of x, y coordinates
        :param index: Index of the element
        :return: Tuple of (x, y) or None if coordinates not provided
        """
        if coordinates is None:
            return None
        return (float(coordinates[index, 0]), float(coordinates[index, 1]))

    @staticmethod
    def _set_optional_junction_attr(
        junction, attr_name: str, values: t.Optional[np.ndarray], index: int
    ):
        """Set an optional per-junction attribute if the value is defined.

        Skips setting if *values* is ``None`` or the value at *index* is NaN
        (the Movici undefined sentinel for floats), leaving the WNTR default
        (``None`` = use global option) in place.

        :param junction: WNTR junction node object
        :param attr_name: Name of the junction attribute to set
        :param values: Optional numpy array of values
        :param index: Index of the junction in the array
        """
        if values is not None and not np.isnan(values[index]):
            setattr(junction, attr_name, float(values[index]))

    def add_junctions(self, junctions: JunctionCollection):
        """Add junctions to the network.

        :param junctions: Collection of junction data
        """
        for i, name in enumerate(junctions.node_names):
            base_demand = float(junctions.base_demands[i])
            if junctions.demand_factors is not None:
                base_demand *= float(junctions.demand_factors[i])

            self.wn.add_junction(
                name=name,
                base_demand=base_demand,
                demand_pattern=None,
                elevation=float(junctions.elevations[i]),
                coordinates=self._get_coords(junctions.coordinates, i),
            )

            # Set per-junction PDD attributes (only for defined values).
            # WNTR junction attributes default to None (= use global option).
            junction = self.wn.get_node(name)
            self._set_optional_junction_attr(
                junction, "minimum_pressure", junctions.minimum_pressures, i
            )
            self._set_optional_junction_attr(
                junction, "required_pressure", junctions.required_pressures, i
            )
            self._set_optional_junction_attr(
                junction, "pressure_exponent", junctions.pressure_exponents, i
            )

    def add_tanks(self, tanks: TankCollection):
        """Add tanks to the network.

        Supports both cylindrical tanks (diameter-based) and non-cylindrical
        tanks (volume curve-based).

        :param tanks: Collection of tank data
        """
        for i, name in enumerate(tanks.node_names):
            min_level = float(tanks.min_levels[i]) if tanks.min_levels is not None else 0.0
            max_level = (
                float(tanks.max_levels[i])
                if tanks.max_levels is not None
                else float(tanks.init_levels[i]) * 2
            )
            diameter = float(tanks.diameters[i]) if tanks.diameters is not None else 0.0
            min_vol = float(tanks.min_volumes[i]) if tanks.min_volumes is not None else 0.0

            vol_curve_name = None
            if tanks.volume_curves is not None and tanks.volume_curves[i] is not None:
                vol_curve_name = self._add_curve(tanks.volume_curves[i], "VOLUME")

            self.wn.add_tank(
                name=name,
                elevation=float(tanks.elevations[i]),
                init_level=float(tanks.init_levels[i]),
                min_level=min_level,
                max_level=max_level,
                diameter=diameter,
                min_vol=min_vol,
                vol_curve=vol_curve_name,
                coordinates=self._get_coords(tanks.coordinates, i),
            )

            if tanks.overflows is not None:
                tank = self.wn.get_node(name)
                tank.overflow = bool(tanks.overflows[i])

    def add_reservoirs(self, reservoirs: ReservoirCollection):
        """Add reservoirs to the network.

        :param reservoirs: Collection of reservoir data
        """
        for i, name in enumerate(reservoirs.node_names):
            base_head = float(reservoirs.base_heads[i])
            if reservoirs.head_factors is not None:
                base_head *= float(reservoirs.head_factors[i])

            self.wn.add_reservoir(
                name=name,
                base_head=base_head,
                head_pattern=None,
                coordinates=self._get_coords(reservoirs.coordinates, i),
            )

    def add_pipes(self, pipes: PipeCollection):
        """Add pipes to the network.

        :param pipes: Collection of pipe data
        """
        for i, name in enumerate(pipes.link_names):
            # Determine initial status
            status_str = "OPEN"
            if pipes.statuses is not None:
                status_str = "OPEN" if pipes.statuses[i] else "CLOSED"

            # Get check valve flag
            check_valve = False
            if pipes.check_valves is not None:
                check_valve = bool(pipes.check_valves[i])

            self.wn.add_pipe(
                name=name,
                start_node_name=pipes.from_nodes[i],
                end_node_name=pipes.to_nodes[i],
                length=float(pipes.lengths[i]),
                diameter=float(pipes.diameters[i]),
                roughness=float(pipes.roughnesses[i]),
                minor_loss=float(pipes.minor_losses[i]) if pipes.minor_losses is not None else 0.0,
                initial_status=status_str,
                check_valve=check_valve,
            )

    def add_pumps(self, pumps: PumpCollection):
        """Add pumps to the network.

        Supports both power pumps and head pumps with CSR curve data.

        :param pumps: Collection of pump data
        """
        for i, name in enumerate(pumps.link_names):
            pump_type = pumps.pump_types[i].upper()

            if pump_type == "POWER":
                power = 1.0
                if pumps.powers is not None:
                    power = float(pumps.powers[i])

                self.wn.add_pump(
                    name=name,
                    start_node_name=pumps.from_nodes[i],
                    end_node_name=pumps.to_nodes[i],
                    pump_type="POWER",
                    pump_parameter=power,
                )
            else:  # HEAD pump
                # Create curve from CSR data
                curve_name = None
                if pumps.head_curves is not None and pumps.head_curves[i] is not None:
                    curve_name = self._add_curve(pumps.head_curves[i], "HEAD")

                if curve_name is None:
                    raise ValueError(f"Head pump '{name}' requires a head_curve")

                self.wn.add_pump(
                    name=name,
                    start_node_name=pumps.from_nodes[i],
                    end_node_name=pumps.to_nodes[i],
                    pump_type="HEAD",
                    pump_parameter=curve_name,
                )

            # Set initial speed if provided (only affects head pumps)
            if pumps.speeds is not None and pump_type == "HEAD":
                pump = self.wn.get_link(name)
                if hasattr(pump, "speed_timeseries"):
                    pump.speed_timeseries.base_value = float(pumps.speeds[i])

            # Set initial status if provided
            if pumps.statuses is not None:
                pump = self.wn.get_link(name)
                pump.initial_status = (
                    wntr.network.LinkStatus.Open
                    if pumps.statuses[i]
                    else wntr.network.LinkStatus.Closed
                )

    def add_valves(self, valves: ValveCollection):
        """Add valves to the network.

        Supports all valve types with type-specific settings.

        :param valves: Collection of valve data
        """
        for i, name in enumerate(valves.link_names):
            valve_type = valves.valve_types[i].upper()

            # Get the appropriate setting based on valve type
            if valve_type == "GPV":
                # GPV needs a curve
                curve_name = None
                if valves.valve_curves is not None and valves.valve_curves[i] is not None:
                    curve_name = self._add_curve(valves.valve_curves[i], "HEADLOSS")

                if curve_name is None:
                    raise ValueError(f"GPV valve '{name}' requires a valve_curve")

                setting = curve_name
            else:
                # Get scalar setting from collection
                setting = valves.get_setting(i)

            self.wn.add_valve(
                name=name,
                start_node_name=valves.from_nodes[i],
                end_node_name=valves.to_nodes[i],
                diameter=float(valves.diameters[i]),
                valve_type=valve_type,
                minor_loss=float(valves.minor_losses[i])
                if valves.minor_losses is not None
                else 0.0,
                initial_setting=setting,
            )

    def _add_curve(self, curve_data: np.ndarray, curve_type: str) -> str:
        """Add a curve to the WNTR network from CSR data.

        :param curve_data: Numpy array of shape (N, 2) with x, y points
        :param curve_type: Type of curve (``"HEAD"``, ``"VOLUME"``, ``"HEADLOSS"``, etc.)
        :return: Name of the created curve
        """
        self._curve_counter += 1
        curve_name = f"curve_{self._curve_counter}"

        # Convert numpy array to list of tuples
        if curve_data.ndim == 1:
            # Single point, reshape to (1, 2)
            curve_data = curve_data.reshape(-1, 2)

        curve_points = [(float(row[0]), float(row[1])) for row in curve_data]

        self.wn.add_curve(curve_name, curve_type, curve_points)
        return curve_name

    def configure_options(self, options: dict):
        """Configure WNTR options from a dict of section_name -> {key: value} mappings.

        Section names correspond to attributes on ``wn.options`` (e.g. ``"hydraulic"``,
        ``"time"``, ``"quality"``). Unknown sections or keys are logged as warnings
        and skipped.

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
    ) -> SimulationResults:
        """Run WNTR simulation.

        :param duration: Simulation duration in seconds (None uses model setting)
        :param hydraulic_timestep: Hydraulic timestep in seconds
        :param report_timestep: Report timestep in seconds (None = same as hydraulic)
        :return: SimulationResults object with results
        """
        # Set simulation options
        if duration is not None:
            self.wn.options.time.duration = int(duration)

        self.wn.options.time.hydraulic_timestep = int(hydraulic_timestep)

        if report_timestep is not None:
            self.wn.options.time.report_timestep = int(report_timestep)
        else:
            self.wn.options.time.report_timestep = int(hydraulic_timestep)

        # Reset network to apply initial_status changes from update_link_status
        self.wn.reset_initial_values()

        # Run simulation
        sim = self.wntr.sim.WNTRSimulator(self.wn)
        results = sim.run_sim()

        # Extract and package results
        return self._extract_results(results)

    def _extract_results(self, results) -> SimulationResults:
        """Extract results from WNTR simulation.

        :param results: WNTR SimulationResults object
        :return: SimulationResults collection
        """
        # Get last timestep results (steady state)
        last_time = results.node["pressure"].index[-1]

        # Node results
        node_names = list(results.node["pressure"].columns)
        node_pressures = results.node["pressure"].loc[last_time].values
        node_heads = results.node["head"].loc[last_time].values
        node_demands = results.node["demand"].loc[last_time].values

        # Tank levels
        node_levels = np.zeros(len(node_names))
        for i, name in enumerate(node_names):
            node = self.wn.get_node(name)
            if node.node_type == "Tank":
                # Get level from head - elevation
                node_levels[i] = node_heads[i] - node.elevation

        # Link results
        link_names = list(results.link["flowrate"].columns)
        link_flows = results.link["flowrate"].loc[last_time].values
        link_velocities = results.link["velocity"].loc[last_time].values

        # Headloss may not be available in all WNTR versions
        if "headloss" in results.link:
            link_headlosses = results.link["headloss"].loc[last_time].values
        else:
            link_headlosses = np.zeros(len(link_names))

        link_statuses = results.link["status"].loc[last_time].values

        return SimulationResults(
            node_names=node_names,
            node_pressures=node_pressures,
            node_heads=node_heads,
            node_demands=node_demands,
            node_levels=node_levels,
            link_names=link_names,
            link_flows=link_flows,
            link_velocities=link_velocities,
            link_headlosses=link_headlosses,
            link_statuses=link_statuses,
        )

    def update_junction_demands(
        self,
        junction_names: t.List[str],
        base_demands: np.ndarray,
        demand_factors: t.Optional[np.ndarray] = None,
    ):
        """Update junction base demands (and optional demand factors).

        Called when demand_factor changes during simulation. Sets the
        effective demand (base_demand * demand_factor) on each WNTR junction.

        :param junction_names: List of WNTR junction names
        :param base_demands: Array of base demand values
        :param demand_factors: Optional array of demand factor multipliers
        """
        for i, name in enumerate(junction_names):
            demand = float(base_demands[i])
            if demand_factors is not None:
                demand *= float(demand_factors[i])
            junction = self.wn.get_node(name)
            junction.demand_timeseries_list[0].base_value = demand

    def update_reservoir_heads(
        self,
        reservoir_names: t.List[str],
        base_heads: np.ndarray,
        head_factors: t.Optional[np.ndarray] = None,
    ):
        """Update reservoir base heads (and optional head factors).

        Called when head_factor changes during simulation. Sets the
        effective head (base_head * head_factor) on each WNTR reservoir.

        :param reservoir_names: List of WNTR reservoir names
        :param base_heads: Array of base head values
        :param head_factors: Optional array of head factor multipliers
        """
        for i, name in enumerate(reservoir_names):
            head = float(base_heads[i])
            if head_factors is not None:
                head *= float(head_factors[i])
            reservoir = self.wn.get_node(name)
            reservoir.base_head = head

    def update_link_status(self, link_names: t.List[str], statuses: np.ndarray):
        """Update link status (open/closed).

        :param link_names: List of link names
        :param statuses: Array of status values (True=open, False=closed)
        """
        for name, status in zip(link_names, statuses):
            link = self.wn.get_link(name)
            link.initial_status = (
                wntr.network.LinkStatus.Open if status else wntr.network.LinkStatus.Closed
            )

    def get_network_summary(self) -> dict:
        """Get summary statistics of the network.

        :return: Dictionary with network statistics
        """
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
        # WNTR doesn't require explicit cleanup, but included for consistency
        pass
