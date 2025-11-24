"""Main wrapper for WNTR WaterNetworkModel with Movici integration"""

from __future__ import annotations

import typing as t
from pathlib import Path

import numpy as np

from .collections import (
    JunctionCollection,
    PipeCollection,
    PumpCollection,
    ReservoirCollection,
    SimulationResults,
    TankCollection,
    ValveCollection,
)
from .control_manager import ControlManager
from .id_mapper import IdMapper
from .pattern_manager import PatternManager


class NetworkWrapper:
    """Wraps WNTR WaterNetworkModel with Movici-friendly API

    This class provides a clean interface between Movici's entity-based
    data model and WNTR's water network simulation engine.
    """

    def __init__(self, mode: str = "movici_network", inp_file: t.Optional[Path] = None):
        """Initialize network wrapper

        :param mode: Either 'inp_file' or 'movici_network'
        :param inp_file: Path to INP file (required if mode='inp_file')
        """
        try:
            import wntr
        except ImportError as e:
            raise ImportError(
                "WNTR is not installed. Install with: pip install wntr"
            ) from e

        self.mode = mode
        self.wntr = wntr

        if mode == "inp_file":
            if inp_file is None:
                raise ValueError("inp_file required when mode='inp_file'")
            self.wn = wntr.network.WaterNetworkModel(str(inp_file))
            # Build ID mapping from existing network
            self._build_id_mapping_from_inp()
        else:
            self.wn = wntr.network.WaterNetworkModel()

        self.id_mapper = IdMapper()
        self.pattern_manager = PatternManager(self.wn)
        self.control_manager = ControlManager(self.wn)

    def _build_id_mapping_from_inp(self):
        """Build ID mapping from elements loaded from INP file"""
        # For INP mode, WNTR element names are already set
        # We'll create mappings when results are requested
        pass

    def add_junctions(self, junctions: JunctionCollection):
        """Add junctions to the network

        :param junctions: Collection of junction data
        """
        for i, name in enumerate(junctions.node_names):
            coords = None
            if junctions.coordinates is not None:
                coords = (
                    float(junctions.coordinates[i, 0]),
                    float(junctions.coordinates[i, 1]),
                )

            self.wn.add_junction(
                name=name,
                base_demand=float(junctions.base_demands[i]),
                demand_pattern=junctions.demand_patterns[i]
                if junctions.demand_patterns
                else None,
                elevation=float(junctions.elevations[i]),
                coordinates=coords,
            )

    def add_tanks(self, tanks: TankCollection):
        """Add tanks to the network

        :param tanks: Collection of tank data
        """
        for i, name in enumerate(tanks.node_names):
            coords = None
            if tanks.coordinates is not None:
                coords = (
                    float(tanks.coordinates[i, 0]),
                    float(tanks.coordinates[i, 1]),
                )

            self.wn.add_tank(
                name=name,
                elevation=float(tanks.elevations[i]),
                init_level=float(tanks.init_levels[i]),
                min_level=float(tanks.min_levels[i]),
                max_level=float(tanks.max_levels[i]),
                diameter=float(tanks.diameters[i]),
                min_vol=float(tanks.min_volumes[i]) if tanks.min_volumes is not None else 0.0,
                vol_curve=tanks.volume_curves[i] if tanks.volume_curves else None,
                coordinates=coords,
            )

    def add_reservoirs(self, reservoirs: ReservoirCollection):
        """Add reservoirs to the network

        :param reservoirs: Collection of reservoir data
        """
        for i, name in enumerate(reservoirs.node_names):
            coords = None
            if reservoirs.coordinates is not None:
                coords = (
                    float(reservoirs.coordinates[i, 0]),
                    float(reservoirs.coordinates[i, 1]),
                )

            self.wn.add_reservoir(
                name=name,
                base_head=float(reservoirs.heads[i]),
                head_pattern=reservoirs.head_patterns[i]
                if reservoirs.head_patterns
                else None,
                coordinates=coords,
            )

    def add_pipes(self, pipes: PipeCollection):
        """Add pipes to the network

        :param pipes: Collection of pipe data
        """
        for i, name in enumerate(pipes.link_names):
            status_str = pipes.statuses[i] if pipes.statuses else "OPEN"

            self.wn.add_pipe(
                name=name,
                start_node_name=pipes.from_nodes[i],
                end_node_name=pipes.to_nodes[i],
                length=float(pipes.lengths[i]),
                diameter=float(pipes.diameters[i]),
                roughness=float(pipes.roughnesses[i]),
                minor_loss=float(pipes.minor_losses[i])
                if pipes.minor_losses is not None
                else 0.0,
                initial_status=status_str,
            )

    def add_pumps(self, pumps: PumpCollection):
        """Add pumps to the network

        :param pumps: Collection of pump data
        """
        for i, name in enumerate(pumps.link_names):
            pump_type = pumps.pump_types[i].upper()

            if pump_type == "POWER":
                self.wn.add_pump(
                    name=name,
                    start_node_name=pumps.from_nodes[i],
                    end_node_name=pumps.to_nodes[i],
                    pump_type=pump_type,
                    pump_parameter=float(pumps.powers[i]) if pumps.powers is not None else 1.0,
                )
            else:  # HEAD pump
                curve_name = pumps.pump_curves[i] if pumps.pump_curves else None
                self.wn.add_pump(
                    name=name,
                    start_node_name=pumps.from_nodes[i],
                    end_node_name=pumps.to_nodes[i],
                    pump_type="HEAD",
                    pump_parameter=curve_name,
                )

            # Set initial speed if provided
            if pumps.speeds is not None:
                pump = self.wn.get_link(name)
                if hasattr(pump, "speed_timeseries"):
                    pump.speed_timeseries.base_value = float(pumps.speeds[i])

    def add_valves(self, valves: ValveCollection):
        """Add valves to the network

        :param valves: Collection of valve data
        """
        for i, name in enumerate(valves.link_names):
            self.wn.add_valve(
                name=name,
                start_node_name=valves.from_nodes[i],
                end_node_name=valves.to_nodes[i],
                diameter=float(valves.diameters[i]),
                valve_type=valves.valve_types[i],
                minor_loss=float(valves.minor_losses[i])
                if valves.minor_losses is not None
                else 0.0,
                initial_setting=float(valves.settings[i]),
            )

    def run_simulation(
        self,
        duration: t.Optional[float] = None,
        hydraulic_timestep: float = 3600,
        report_timestep: t.Optional[float] = None,
    ) -> SimulationResults:
        """Run WNTR simulation

        :param duration: Simulation duration in seconds (None = use model setting)
        :param hydraulic_timestep: Hydraulic timestep in seconds
        :param report_timestep: Report timestep in seconds (None = same as hydraulic)
        :return: SimulationResults object with results mapped to Movici IDs
        """
        # Set simulation options
        if duration is not None:
            self.wn.options.time.duration = int(duration)

        self.wn.options.time.hydraulic_timestep = int(hydraulic_timestep)

        if report_timestep is not None:
            self.wn.options.time.report_timestep = int(report_timestep)
        else:
            self.wn.options.time.report_timestep = int(hydraulic_timestep)

        # Run simulation
        sim = self.wntr.sim.WNTRSimulator(self.wn)
        results = sim.run_sim()

        # Extract and package results
        return self._extract_results(results)

    def _extract_results(self, results) -> SimulationResults:
        """Extract results from WNTR simulation

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

        # Demand deficit if available
        node_demand_deficits = None
        if "demand_deficit" in results.node:
            node_demand_deficits = results.node["demand_deficit"].loc[last_time].values

        # Tank levels if available
        node_levels = None
        # Extract tank levels separately
        tank_names = [
            name for name in node_names if self.wn.get_node(name).node_type == "Tank"
        ]
        if tank_names:
            node_levels = np.zeros(len(node_names))
            for i, name in enumerate(node_names):
                if name in tank_names:
                    node_levels[i] = self.wn.get_node(name).init_level

        # Link results
        link_names = list(results.link["flowrate"].columns)
        link_flows = results.link["flowrate"].loc[last_time].values
        link_velocities = results.link["velocity"].loc[last_time].values
        link_headlosses = results.link["headloss"].loc[last_time].values
        link_statuses = results.link["status"].loc[last_time].values

        # Pump power if available
        link_powers = None
        pump_names = [
            name for name in link_names if self.wn.get_link(name).link_type == "Pump"
        ]
        if pump_names and "pump_power" in results.link:
            link_powers = np.zeros(len(link_names))
            pump_powers = results.link["pump_power"].loc[last_time]
            for i, name in enumerate(link_names):
                if name in pump_names:
                    link_powers[i] = pump_powers[name]

        return SimulationResults(
            node_names=node_names,
            node_pressures=node_pressures,
            node_heads=node_heads,
            node_demands=node_demands,
            node_demand_deficits=node_demand_deficits,
            node_levels=node_levels,
            link_names=link_names,
            link_flows=link_flows,
            link_velocities=link_velocities,
            link_headlosses=link_headlosses,
            link_statuses=link_statuses,
            link_powers=link_powers,
        )

    def update_junction_demands(self, junction_names: t.List[str], demands: np.ndarray):
        """Update base demands for junctions

        :param junction_names: List of junction names
            :param demands: Array of demand values
        """
        for name, demand in zip(junction_names, demands):
            junction = self.wn.get_node(name)
            junction.base_demand = float(demand)

    def update_link_status(self, link_names: t.List[str], statuses: np.ndarray):
        """Update link status (open/closed)

        :param link_names: List of link names
            :param statuses: Array of status values (0=closed, 1=open)
        """
        for name, status in zip(link_names, statuses):
            link = self.wn.get_link(name)
            status_str = "OPEN" if int(status) == 1 else "CLOSED"
            link.initial_status = status_str

    def get_network_summary(self) -> dict:
        """Get summary statistics of the network

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
            "num_controls": len(self.wn.control_name_list),
        }

    def close(self):
        """Clean up resources"""
        # WNTR doesn't require explicit cleanup, but included for consistency
        pass
