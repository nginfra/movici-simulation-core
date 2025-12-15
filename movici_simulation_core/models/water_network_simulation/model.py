"""Water network simulation model using WNTR.

This model simulates drinking water distribution networks using the WNTR
(Water Network Tool for Resilience) library. It supports hydraulic simulation
including pressure, flow, and velocity calculations.

.. note::
   Controls (time-based or conditional) are NOT handled internally by this model.
   Use the Movici Rules Model to implement control logic externally.
"""

from __future__ import annotations

import typing as t
from pathlib import Path

import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.integrations.wntr import NetworkWrapper
from movici_simulation_core.model_connector.init_data import InitDataHandler
from movici_simulation_core.models.common.wntr_util import (
    get_junctions,
    get_pipes,
    get_pumps,
    get_reservoirs,
    get_tanks,
    get_valves,
)

from .attributes import (
    DrinkingWater_BaseDemand,
    DrinkingWater_BaseHead,
    DrinkingWater_CheckValve,
    DrinkingWater_Demand,
    DrinkingWater_DemandFactor,
    DrinkingWater_Flow,
    DrinkingWater_Head,
    DrinkingWater_HeadCurve,
    DrinkingWater_HeadFactor,
    DrinkingWater_Headloss,
    DrinkingWater_Level,
    DrinkingWater_MaxLevel,
    DrinkingWater_MinLevel,
    DrinkingWater_MinorLoss,
    DrinkingWater_MinVolume,
    DrinkingWater_Overflow,
    DrinkingWater_Power,
    DrinkingWater_Pressure,
    DrinkingWater_Roughness,
    DrinkingWater_Speed,
    DrinkingWater_ValveCurve,
    DrinkingWater_ValveFlow,
    DrinkingWater_ValveLossCoefficient,
    DrinkingWater_ValvePressure,
    DrinkingWater_Velocity,
    Geometry_Z,
    Operational_Status,
    Shape_Diameter,
    Shape_Length,
    Shape_VolumeCurve,
    Type_PumpType,
    Type_ValveType,
)
from .dataset import (
    WaterJunctionEntity,
    WaterPipeEntity,
    WaterPumpEntity,
    WaterReservoirEntity,
    WaterTankEntity,
    WaterValveEntity,
)


class Model(TrackedModel, name="water_network_simulation"):
    """Water network simulation model using WNTRSimulator.

    This model simulates water distribution networks including:

    - Hydraulic simulation (pressure, flow, velocity)
    - Support for pipes, pumps, valves, tanks, and reservoirs
    - CSR curve data for pump head curves and tank volume curves

    Supports two modes:

    - ``inp_file``: Load existing EPANET INP file
    - ``movici_network``: Build network from Movici datasets

    .. note::
       Controls are handled by the Movici Rules Model, not internally.

    :ivar network: WNTR network wrapper
    :ivar junctions: Junction entity group
    :ivar tanks: Tank entity group
    :ivar reservoirs: Reservoir entity group
    :ivar pipes: Pipe entity group
    :ivar pumps: Pump entity group
    :ivar valves: Valve entity group
    """

    @classmethod
    def get_schema_attributes(cls):
        """Return all AttributeSpecs used by this model.

        :return: Sequence of AttributeSpec objects
        """
        return [
            # Geometry attributes
            Geometry_Z,
            # Shape attributes
            Shape_Diameter,
            Shape_Length,
            Shape_VolumeCurve,
            # Junction attributes
            DrinkingWater_BaseDemand,
            DrinkingWater_DemandFactor,
            DrinkingWater_Demand,
            # Node outputs
            DrinkingWater_Pressure,
            DrinkingWater_Head,
            # Tank attributes
            DrinkingWater_Level,
            DrinkingWater_MinLevel,
            DrinkingWater_MaxLevel,
            DrinkingWater_MinVolume,
            DrinkingWater_Overflow,
            # Reservoir attributes
            DrinkingWater_BaseHead,
            DrinkingWater_HeadFactor,
            # Pipe attributes
            DrinkingWater_Roughness,
            DrinkingWater_MinorLoss,
            DrinkingWater_CheckValve,
            # Link outputs
            DrinkingWater_Flow,
            DrinkingWater_Velocity,
            DrinkingWater_Headloss,
            # Pump attributes
            DrinkingWater_Power,
            DrinkingWater_Speed,
            DrinkingWater_HeadCurve,
            # Valve attributes
            DrinkingWater_ValvePressure,
            DrinkingWater_ValveFlow,
            DrinkingWater_ValveLossCoefficient,
            DrinkingWater_ValveCurve,
            # Operational attributes
            Operational_Status,
            # Type attributes
            Type_PumpType,
            Type_ValveType,
        ]

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.network: t.Optional[NetworkWrapper] = None
        self.mode = model_config.get("mode", "movici_network")

        # Simulation options
        self.viscosity = model_config.get("viscosity", 1.0)
        self.specific_gravity = model_config.get("specific_gravity", 1.0)

        # Entity groups
        self.junctions: t.Optional[WaterJunctionEntity] = None
        self.tanks: t.Optional[WaterTankEntity] = None
        self.reservoirs: t.Optional[WaterReservoirEntity] = None
        self.pipes: t.Optional[WaterPipeEntity] = None
        self.pumps: t.Optional[WaterPumpEntity] = None
        self.valves: t.Optional[WaterValveEntity] = None

    def setup(
        self,
        state: TrackedState,
        schema: AttributeSchema,
        init_data_handler: InitDataHandler,
        **kwargs,
    ):
        """Setup the model and initialize network.

        :param state: Tracked state for entity registration
        :param schema: Attribute schema
        :param init_data_handler: Handler for initialization data files
        """
        # Initialize network wrapper based on mode
        if self.mode == "inp_file":
            inp_file_path = self.config.get("inp_file")
            if not inp_file_path:
                raise ValueError("inp_file required when mode='inp_file'")

            # Get the INP file through init_data_handler
            inp_file = Path(inp_file_path)
            _, inp_path = init_data_handler.get(inp_file.stem)
            if inp_path is None:
                inp_path = inp_file
                if not inp_path.exists():
                    raise ValueError(f"INP file not found: {inp_file_path}")

            self.network = NetworkWrapper(mode="inp_file", inp_file=inp_path)
            self._register_output_entities_from_inp(state)

        else:  # movici_network mode
            self.network = NetworkWrapper(mode="movici_network")

            dataset_name = self.config.get("dataset")
            if not dataset_name:
                raise ValueError("dataset required when mode='movici_network'")

            self._register_entities(state, dataset_name)

    def _register_entities(self, state: TrackedState, dataset_name: str):
        """Register entity groups for movici_network mode.

        :param state: Tracked state for entity registration
        :param dataset_name: Name of the dataset to register entities in
        """
        entity_groups = self.config.get("entity_groups", ["junctions", "pipes", "reservoirs"])

        if "junctions" in entity_groups:
            self.junctions = WaterJunctionEntity()
            state.register_entity_group(dataset_name, self.junctions)

        if "pipes" in entity_groups:
            self.pipes = WaterPipeEntity()
            state.register_entity_group(dataset_name, self.pipes)

        if "reservoirs" in entity_groups:
            self.reservoirs = WaterReservoirEntity()
            state.register_entity_group(dataset_name, self.reservoirs)

        if "tanks" in entity_groups:
            self.tanks = WaterTankEntity()
            state.register_entity_group(dataset_name, self.tanks)

        if "pumps" in entity_groups:
            self.pumps = WaterPumpEntity()
            state.register_entity_group(dataset_name, self.pumps)

        if "valves" in entity_groups:
            self.valves = WaterValveEntity()
            state.register_entity_group(dataset_name, self.valves)

    def _register_output_entities_from_inp(self, state: TrackedState):
        """Register entity groups from INP file network data.

        :param state: Tracked state for entity registration
        """
        dataset_name = self.config.get("dataset", "water_network")
        wn = self.network.wn

        if wn.junction_name_list:
            self.junctions = WaterJunctionEntity()
            state.register_entity_group(dataset_name, self.junctions)

        if wn.pipe_name_list:
            self.pipes = WaterPipeEntity()
            state.register_entity_group(dataset_name, self.pipes)

        if wn.reservoir_name_list:
            self.reservoirs = WaterReservoirEntity()
            state.register_entity_group(dataset_name, self.reservoirs)

        if wn.tank_name_list:
            self.tanks = WaterTankEntity()
            state.register_entity_group(dataset_name, self.tanks)

        if wn.pump_name_list:
            self.pumps = WaterPumpEntity()
            state.register_entity_group(dataset_name, self.pumps)

        if wn.valve_name_list:
            self.valves = WaterValveEntity()
            state.register_entity_group(dataset_name, self.valves)

        # Build entity data from WNTR network
        entity_data = self._extract_entities_from_wntr()
        state.receive_update({dataset_name: entity_data}, is_initial=True)

    def _extract_entities_from_wntr(self) -> dict:
        """Extract entity data from WNTR network in Movici format.

        :return: Dictionary of entity data for state initialization
        """
        wn = self.network.wn
        entity_data = {}

        # Extract junctions
        junction_names = list(wn.junction_name_list)
        if junction_names:
            junction_ids = []
            elevations = []
            base_demands = []
            x_coords = []
            y_coords = []

            for i, name in enumerate(junction_names):
                junction = wn.get_node(name)
                movici_id = i + 1
                self.network.id_mapper.wntr_to_movici[name] = movici_id
                self.network.id_mapper.movici_to_wntr[movici_id] = name
                self.network.id_mapper.entity_types[name] = "junction"

                junction_ids.append(movici_id)
                elevations.append(junction.elevation)
                base_demands.append(junction.base_demand)
                if junction.coordinates:
                    x_coords.append(junction.coordinates[0])
                    y_coords.append(junction.coordinates[1])
                else:
                    x_coords.append(0.0)
                    y_coords.append(0.0)

            entity_data["water_junction_entities"] = {
                "id": {"data": np.array(junction_ids, dtype=np.int32)},
                "geometry.x": {"data": np.array(x_coords, dtype=np.float64)},
                "geometry.y": {"data": np.array(y_coords, dtype=np.float64)},
                "geometry.z": {"data": np.array(elevations, dtype=np.float64)},
                "drinking_water.base_demand": {"data": np.array(base_demands, dtype=np.float64)},
            }

        # Extract reservoirs
        reservoir_names = list(wn.reservoir_name_list)
        if reservoir_names:
            reservoir_ids = []
            heads = []
            x_coords = []
            y_coords = []

            id_offset = len(junction_names) + 1
            for i, name in enumerate(reservoir_names):
                reservoir = wn.get_node(name)
                movici_id = id_offset + i
                self.network.id_mapper.wntr_to_movici[name] = movici_id
                self.network.id_mapper.movici_to_wntr[movici_id] = name
                self.network.id_mapper.entity_types[name] = "reservoir"

                reservoir_ids.append(movici_id)
                heads.append(reservoir.base_head)
                if reservoir.coordinates:
                    x_coords.append(reservoir.coordinates[0])
                    y_coords.append(reservoir.coordinates[1])
                else:
                    x_coords.append(0.0)
                    y_coords.append(0.0)

            entity_data["water_reservoir_entities"] = {
                "id": {"data": np.array(reservoir_ids, dtype=np.int32)},
                "geometry.x": {"data": np.array(x_coords, dtype=np.float64)},
                "geometry.y": {"data": np.array(y_coords, dtype=np.float64)},
                "drinking_water.base_head": {"data": np.array(heads, dtype=np.float64)},
            }

        # Extract tanks
        tank_names = list(wn.tank_name_list)
        if tank_names:
            tank_ids = []
            elevations = []
            init_levels = []
            min_levels = []
            max_levels = []
            diameters = []
            x_coords = []
            y_coords = []

            id_offset = len(junction_names) + len(reservoir_names) + 1
            for i, name in enumerate(tank_names):
                tank = wn.get_node(name)
                movici_id = id_offset + i
                self.network.id_mapper.wntr_to_movici[name] = movici_id
                self.network.id_mapper.movici_to_wntr[movici_id] = name
                self.network.id_mapper.entity_types[name] = "tank"

                tank_ids.append(movici_id)
                elevations.append(tank.elevation)
                init_levels.append(tank.init_level)
                min_levels.append(tank.min_level)
                max_levels.append(tank.max_level)
                diameters.append(tank.diameter)
                if tank.coordinates:
                    x_coords.append(tank.coordinates[0])
                    y_coords.append(tank.coordinates[1])
                else:
                    x_coords.append(0.0)
                    y_coords.append(0.0)

            entity_data["water_tank_entities"] = {
                "id": {"data": np.array(tank_ids, dtype=np.int32)},
                "geometry.x": {"data": np.array(x_coords, dtype=np.float64)},
                "geometry.y": {"data": np.array(y_coords, dtype=np.float64)},
                "geometry.z": {"data": np.array(elevations, dtype=np.float64)},
                "drinking_water.level": {"data": np.array(init_levels, dtype=np.float64)},
                "drinking_water.min_level": {"data": np.array(min_levels, dtype=np.float64)},
                "drinking_water.max_level": {"data": np.array(max_levels, dtype=np.float64)},
                "shape.diameter": {"data": np.array(diameters, dtype=np.float64)},
            }

        # Track total node count for link ID offset
        total_nodes = len(junction_names) + len(reservoir_names) + len(tank_names)

        # Extract pipes
        pipe_names = list(wn.pipe_name_list)
        if pipe_names:
            pipe_ids = []
            from_node_ids = []
            to_node_ids = []
            diameters = []
            roughnesses = []
            minor_losses = []

            link_id_offset = total_nodes + 1
            for i, name in enumerate(pipe_names):
                pipe = wn.get_link(name)
                movici_id = link_id_offset + i
                self.network.id_mapper.wntr_to_movici[name] = movici_id
                self.network.id_mapper.movici_to_wntr[movici_id] = name
                self.network.id_mapper.entity_types[name] = "pipe"

                pipe_ids.append(movici_id)
                from_node_ids.append(self.network.id_mapper.wntr_to_movici[pipe.start_node_name])
                to_node_ids.append(self.network.id_mapper.wntr_to_movici[pipe.end_node_name])
                diameters.append(pipe.diameter)
                roughnesses.append(pipe.roughness)
                minor_losses.append(pipe.minor_loss)

            entity_data["water_pipe_entities"] = {
                "id": {"data": np.array(pipe_ids, dtype=np.int32)},
                "topology.from_node_id": {"data": np.array(from_node_ids, dtype=np.int32)},
                "topology.to_node_id": {"data": np.array(to_node_ids, dtype=np.int32)},
                "shape.diameter": {"data": np.array(diameters, dtype=np.float64)},
                "drinking_water.roughness": {"data": np.array(roughnesses, dtype=np.float64)},
                "drinking_water.minor_loss": {"data": np.array(minor_losses, dtype=np.float64)},
            }

        # Extract pumps
        pump_names = list(wn.pump_name_list)
        if pump_names:
            pump_ids = []
            from_node_ids = []
            to_node_ids = []
            pump_types = []

            link_id_offset = total_nodes + len(pipe_names) + 1
            for i, name in enumerate(pump_names):
                pump = wn.get_link(name)
                movici_id = link_id_offset + i
                self.network.id_mapper.wntr_to_movici[name] = movici_id
                self.network.id_mapper.movici_to_wntr[movici_id] = name
                self.network.id_mapper.entity_types[name] = "pump"

                pump_ids.append(movici_id)
                from_node_ids.append(self.network.id_mapper.wntr_to_movici[pump.start_node_name])
                to_node_ids.append(self.network.id_mapper.wntr_to_movici[pump.end_node_name])
                pump_types.append(str(pump.pump_type).lower())

            entity_data["water_pump_entities"] = {
                "id": {"data": np.array(pump_ids, dtype=np.int32)},
                "topology.from_node_id": {"data": np.array(from_node_ids, dtype=np.int32)},
                "topology.to_node_id": {"data": np.array(to_node_ids, dtype=np.int32)},
                "type": {"data": pump_types},
            }

        # Extract valves
        valve_names = list(wn.valve_name_list)
        if valve_names:
            valve_ids = []
            from_node_ids = []
            to_node_ids = []
            valve_types = []
            diameters = []

            link_id_offset = total_nodes + len(pipe_names) + len(pump_names) + 1
            for i, name in enumerate(valve_names):
                valve = wn.get_link(name)
                movici_id = link_id_offset + i
                self.network.id_mapper.wntr_to_movici[name] = movici_id
                self.network.id_mapper.movici_to_wntr[movici_id] = name
                self.network.id_mapper.entity_types[name] = "valve"

                valve_ids.append(movici_id)
                from_node_ids.append(self.network.id_mapper.wntr_to_movici[valve.start_node_name])
                to_node_ids.append(self.network.id_mapper.wntr_to_movici[valve.end_node_name])
                valve_types.append(valve.valve_type)
                diameters.append(valve.diameter)

            entity_data["water_valve_entities"] = {
                "id": {"data": np.array(valve_ids, dtype=np.int32)},
                "topology.from_node_id": {"data": np.array(from_node_ids, dtype=np.int32)},
                "topology.to_node_id": {"data": np.array(to_node_ids, dtype=np.int32)},
                "type": {"data": valve_types},
                "shape.diameter": {"data": np.array(diameters, dtype=np.float64)},
            }

        return entity_data

    def initialize(self, state: TrackedState):
        """Initialize model and run first simulation.

        :param state: Tracked state
        """
        if self.mode == "movici_network":
            self._build_network_from_state(state)

        # Run initial simulation
        duration = self.config.get("simulation_duration")
        hydraulic_timestep = self.config.get("hydraulic_timestep", 3600)
        report_timestep = self.config.get("report_timestep")

        results = self.network.run_simulation(
            duration=duration,
            hydraulic_timestep=hydraulic_timestep,
            report_timestep=report_timestep,
            viscosity=self.viscosity,
            specific_gravity=self.specific_gravity,
        )

        self._publish_results(state, results)

    def _build_network_from_state(self, state: TrackedState):
        """Build WNTR network from Movici entity state.

        :param state: Tracked state with entity data
        """
        if self.junctions and len(self.junctions) > 0:
            junction_coll = get_junctions(self.junctions, self.network.id_mapper)
            self.network.add_junctions(junction_coll)

        if self.tanks and len(self.tanks) > 0:
            tank_coll = get_tanks(self.tanks, self.network.id_mapper)
            self.network.add_tanks(tank_coll)

        if self.reservoirs and len(self.reservoirs) > 0:
            reservoir_coll = get_reservoirs(self.reservoirs, self.network.id_mapper)
            self.network.add_reservoirs(reservoir_coll)

        if self.pipes and len(self.pipes) > 0:
            pipe_coll = get_pipes(self.pipes, self.network.id_mapper)
            self.network.add_pipes(pipe_coll)

        if self.pumps and len(self.pumps) > 0:
            pump_coll = get_pumps(self.pumps, self.network.id_mapper)
            self.network.add_pumps(pump_coll)

        if self.valves and len(self.valves) > 0:
            valve_coll = get_valves(self.valves, self.network.id_mapper)
            self.network.add_valves(valve_coll)

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """Update simulation at each timestep.

        :param state: Tracked state
        :param moment: Current simulation moment
        :return: Next update time or None
        """
        # Update dynamic attributes (status changes from Rules Model)
        if self.mode == "movici_network":
            self._update_dynamic_attributes(state)

        # Run simulation
        hydraulic_timestep = self.config.get("hydraulic_timestep", 3600)
        results = self.network.run_simulation(
            duration=hydraulic_timestep,
            hydraulic_timestep=hydraulic_timestep,
            viscosity=self.viscosity,
            specific_gravity=self.specific_gravity,
        )

        self._publish_results(state, results)
        return None

    def _update_dynamic_attributes(self, state: TrackedState):
        """Update dynamic network attributes from state changes.

        Called when the Rules Model may have modified entity attributes.

        :param state: Tracked state
        """
        # Update pipe statuses
        if self.pipes and self.pipes.status.has_data():
            if np.any(self.pipes.status.changed):
                movici_ids = self.pipes.index.ids
                link_names = [self.network.id_mapper.get_wntr_name(int(mid)) for mid in movici_ids]
                statuses = self.pipes.status.array
                self.network.update_link_status(link_names, statuses)

        # Update pump statuses
        if self.pumps and self.pumps.status.has_data():
            if np.any(self.pumps.status.changed):
                movici_ids = self.pumps.index.ids
                link_names = [self.network.id_mapper.get_wntr_name(int(mid)) for mid in movici_ids]
                statuses = self.pumps.status.array
                self.network.update_link_status(link_names, statuses)

    def _publish_results(self, state: TrackedState, results):
        """Publish simulation results to state.

        :param state: Tracked state
        :param results: SimulationResults from WNTR
        """
        node_id_map = {
            name: self.network.id_mapper.get_movici_id(name)
            for name in results.node_names
            if self.network.id_mapper.has_wntr_name(name)
        }

        link_id_map = {
            name: self.network.id_mapper.get_movici_id(name)
            for name in results.link_names
            if self.network.id_mapper.has_wntr_name(name)
        }

        # Publish junction results
        if self.junctions:
            junction_indices = []
            pressures = []
            heads = []
            demands = []

            for name, movici_id in node_id_map.items():
                if self.network.id_mapper.get_entity_type(name) == "junction":
                    idx = self.junctions.index[movici_id]
                    if idx >= 0:
                        junction_indices.append(idx)
                        node_idx = results.node_names.index(name)
                        pressures.append(results.node_pressures[node_idx])
                        heads.append(results.node_heads[node_idx])
                        demands.append(results.node_demands[node_idx])

            if junction_indices:
                self.junctions.pressure.array[junction_indices] = np.array(pressures)
                self.junctions.head.array[junction_indices] = np.array(heads)
                self.junctions.demand.array[junction_indices] = np.array(demands)

        # Publish tank results
        if self.tanks:
            tank_indices = []
            pressures = []
            heads = []
            levels = []

            for name, movici_id in node_id_map.items():
                if self.network.id_mapper.get_entity_type(name) == "tank":
                    idx = self.tanks.index[movici_id]
                    if idx >= 0:
                        tank_indices.append(idx)
                        node_idx = results.node_names.index(name)
                        pressures.append(results.node_pressures[node_idx])
                        heads.append(results.node_heads[node_idx])
                        levels.append(results.node_levels[node_idx])

            if tank_indices:
                self.tanks.pressure.array[tank_indices] = np.array(pressures)
                self.tanks.head.array[tank_indices] = np.array(heads)
                self.tanks.level.array[tank_indices] = np.array(levels)

        # Publish reservoir results
        if self.reservoirs:
            reservoir_indices = []
            heads = []
            flows = []

            for name, movici_id in node_id_map.items():
                if self.network.id_mapper.get_entity_type(name) == "reservoir":
                    idx = self.reservoirs.index[movici_id]
                    if idx >= 0:
                        reservoir_indices.append(idx)
                        node_idx = results.node_names.index(name)
                        heads.append(results.node_heads[node_idx])
                        # Calculate total flow from connected links
                        total_flow = 0.0
                        for link_name in results.link_names:
                            link = self.network.wn.get_link(link_name)
                            if link.start_node_name == name or link.end_node_name == name:
                                link_idx = results.link_names.index(link_name)
                                if link.start_node_name == name:
                                    total_flow -= results.link_flows[link_idx]
                                else:
                                    total_flow += results.link_flows[link_idx]
                        flows.append(total_flow)

            if reservoir_indices:
                self.reservoirs.head.array[reservoir_indices] = np.array(heads)
                self.reservoirs.flow.array[reservoir_indices] = np.array(flows)

        # Publish pipe results
        if self.pipes:
            pipe_indices = []
            flows = []
            velocities = []
            headlosses = []

            for name, movici_id in link_id_map.items():
                if self.network.id_mapper.get_entity_type(name) == "pipe":
                    idx = self.pipes.index[movici_id]
                    if idx >= 0:
                        pipe_indices.append(idx)
                        link_idx = results.link_names.index(name)
                        flows.append(results.link_flows[link_idx])
                        velocities.append(results.link_velocities[link_idx])
                        headlosses.append(results.link_headlosses[link_idx])

            if pipe_indices:
                self.pipes.flow.array[pipe_indices] = np.array(flows)
                self.pipes.velocity.array[pipe_indices] = np.array(velocities)
                self.pipes.headloss.array[pipe_indices] = np.array(headlosses)

        # Publish pump results
        if self.pumps:
            pump_indices = []
            flows = []

            for name, movici_id in link_id_map.items():
                if self.network.id_mapper.get_entity_type(name) == "pump":
                    idx = self.pumps.index[movici_id]
                    if idx >= 0:
                        pump_indices.append(idx)
                        link_idx = results.link_names.index(name)
                        flows.append(results.link_flows[link_idx])

            if pump_indices:
                self.pumps.flow.array[pump_indices] = np.array(flows)

        # Publish valve results
        if self.valves:
            valve_indices = []
            flows = []

            for name, movici_id in link_id_map.items():
                if self.network.id_mapper.get_entity_type(name) == "valve":
                    idx = self.valves.index[movici_id]
                    if idx >= 0:
                        valve_indices.append(idx)
                        link_idx = results.link_names.index(name)
                        flows.append(results.link_flows[link_idx])

            if valve_indices:
                self.valves.flow.array[valve_indices] = np.array(flows)

    def shutdown(self, state: TrackedState):
        """Clean up resources.

        :param state: Tracked state
        """
        if self.network:
            self.network.close()
