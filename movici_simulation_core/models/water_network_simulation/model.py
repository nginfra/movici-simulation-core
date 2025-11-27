"""Water network simulation model using WNTR"""

from __future__ import annotations

import typing as t
from pathlib import Path

import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUB
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.integrations.wntr import NetworkWrapper
from movici_simulation_core.model_connector.init_data import InitDataHandler
from movici_simulation_core.models.common.time_series import TimeSeries
from movici_simulation_core.models.common.wntr_util import (
    get_junctions,
    get_pipes,
    get_pumps,
    get_reservoirs,
    get_tanks,
    get_valves,
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
    """Water network simulation model using WNTRSimulator

    This model simulates water distribution networks including:
    - Hydraulic simulation (pressure, flow, velocity)
    - Demand patterns (from tape files)
    - Control rules
    - Support for pipes, pumps, valves, tanks, and reservoirs

    Supports two modes:
    - inp_file: Load existing EPANET INP file
    - movici_network: Build network from Movici datasets
    """

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.network: t.Optional[NetworkWrapper] = None
        self.pattern_timeline: t.Optional[TimeSeries] = None
        self.mode = model_config.get("mode", "movici_network")

        # Entity groups
        self.junctions: t.Optional[WaterJunctionEntity] = None
        self.tanks: t.Optional[WaterTankEntity] = None
        self.reservoirs: t.Optional[WaterReservoirEntity] = None
        self.pipes: t.Optional[WaterPipeEntity] = None
        self.pumps: t.Optional[WaterPumpEntity] = None
        self.valves: t.Optional[WaterValveEntity] = None
        self.pending_control_rules: list = []

    def setup(
        self,
        state: TrackedState,
        schema: AttributeSchema,
        init_data_handler: InitDataHandler,
        **kwargs,
    ):
        """Setup the model and initialize network"""

        # Initialize network wrapper based on mode
        if self.mode == "inp_file":
            inp_file_path = self.config.get("inp_file")
            if not inp_file_path:
                raise ValueError("inp_file required when mode='inp_file'")

            # Get the INP file through init_data_handler
            # The handler looks up by stem (name without extension)
            inp_file = Path(inp_file_path)
            _, inp_path = init_data_handler.get(inp_file.stem)
            if inp_path is None:
                # Try as direct path
                inp_path = inp_file
                if not inp_path.exists():
                    raise ValueError(f"INP file not found: {inp_file_path}")

            self.network = NetworkWrapper(mode="inp_file", inp_file=inp_path)

            # Register output entities only for INP mode
            self._register_output_entities_from_inp(state)

        else:  # movici_network mode
            self.network = NetworkWrapper(mode="movici_network")

            # Register input and output entities
            dataset_name = self.config.get("dataset")
            if not dataset_name:
                raise ValueError("dataset required when mode='movici_network'")

            self._register_entities(state, dataset_name)

        # Setup demand pattern tape files if provided
        self.pattern_timeline = TimeSeries()
        demand_patterns = self.config.get("demand_patterns", [])
        if isinstance(demand_patterns, str):
            demand_patterns = [demand_patterns]

        for tape_name in demand_patterns:
            self._load_pattern_tape(tape_name, init_data_handler)

        # Store control rules to be added after network is built
        self.pending_control_rules = self.config.get("control_rules", [])

    def _register_entities(self, state: TrackedState, dataset_name: str):
        """Register entity groups for movici_network mode

        Only registers entity groups that are specified in the config or
        that are required (junctions, pipes).

        Config options:
            entity_groups: list of entity group names to register
                e.g., ["junctions", "pipes", "reservoirs", "tanks", "pumps", "valves"]
                If not specified, registers junctions, pipes, and reservoirs.
        """
        # Get list of entity groups to register from config
        entity_groups = self.config.get(
            "entity_groups", ["junctions", "pipes", "reservoirs"]
        )

        # Junctions (required)
        if "junctions" in entity_groups:
            self.junctions = WaterJunctionEntity()
            state.register_entity_group(dataset_name, self.junctions)

        # Pipes (required)
        if "pipes" in entity_groups:
            self.pipes = WaterPipeEntity()
            state.register_entity_group(dataset_name, self.pipes)

        # Reservoirs
        if "reservoirs" in entity_groups:
            self.reservoirs = WaterReservoirEntity()
            state.register_entity_group(dataset_name, self.reservoirs)

        # Tanks
        if "tanks" in entity_groups:
            self.tanks = WaterTankEntity()
            state.register_entity_group(dataset_name, self.tanks)

        # Pumps
        if "pumps" in entity_groups:
            self.pumps = WaterPumpEntity()
            state.register_entity_group(dataset_name, self.pumps)

        # Valves
        if "valves" in entity_groups:
            self.valves = WaterValveEntity()
            state.register_entity_group(dataset_name, self.valves)

    def _register_output_entities_from_inp(self, state: TrackedState):
        """Register entity groups and create entities from INP file network data

        In INP mode, we extract network data from the loaded WNTR network
        and create Movici entities with proper IDs and attributes.
        Only entity groups that have data in the network are registered.
        """
        dataset_name = self.config.get("dataset", "water_network")
        wn = self.network.wn

        # Register entity groups only for elements that exist in the network
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

        # Initialize entities with the extracted data
        state.receive_update({dataset_name: entity_data}, is_initial=True)

    def _extract_entities_from_wntr(self) -> dict:
        """Extract entity data from WNTR network in Movici format

        Returns dict in format:
        {
            "water_junction_entities": {"id": {"data": [...]}, "water.elevation": {"data": [...]}, ...},
            "water_pipe_entities": {...},
            ...
        }
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
                movici_id = i + 1  # Start IDs at 1
                # Map WNTR name to movici_id (using original INP file names)
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
                "water.elevation": {"data": np.array(elevations, dtype=np.float64)},
                "water.base_demand": {"data": np.array(base_demands, dtype=np.float64)},
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
                "water.head": {"data": np.array(heads, dtype=np.float64)},
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
                "water.elevation": {"data": np.array(elevations, dtype=np.float64)},
                "water.initial_level": {"data": np.array(init_levels, dtype=np.float64)},
                "water.min_level": {"data": np.array(min_levels, dtype=np.float64)},
                "water.max_level": {"data": np.array(max_levels, dtype=np.float64)},
                "water.tank_diameter": {"data": np.array(diameters, dtype=np.float64)},
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
                "water.diameter": {"data": np.array(diameters, dtype=np.float64)},
                "water.roughness": {"data": np.array(roughnesses, dtype=np.float64)},
                "water.minor_loss": {"data": np.array(minor_losses, dtype=np.float64)},
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
                pump_types.append(str(pump.pump_type))

            entity_data["water_pump_entities"] = {
                "id": {"data": np.array(pump_ids, dtype=np.int32)},
                "topology.from_node_id": {"data": np.array(from_node_ids, dtype=np.int32)},
                "topology.to_node_id": {"data": np.array(to_node_ids, dtype=np.int32)},
                "water.pump_type": {"data": pump_types},
            }

        # Extract valves
        valve_names = list(wn.valve_name_list)
        if valve_names:
            valve_ids = []
            from_node_ids = []
            to_node_ids = []
            valve_types = []
            diameters = []
            settings = []

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
                settings.append(valve.setting)

            entity_data["water_valve_entities"] = {
                "id": {"data": np.array(valve_ids, dtype=np.int32)},
                "topology.from_node_id": {"data": np.array(from_node_ids, dtype=np.int32)},
                "topology.to_node_id": {"data": np.array(to_node_ids, dtype=np.int32)},
                "water.valve_type": {"data": valve_types},
                "water.diameter": {"data": np.array(diameters, dtype=np.float64)},
                "water.valve_setting": {"data": np.array(settings, dtype=np.float64)},
            }

        return entity_data

    def _load_pattern_tape(self, tape_name: str, init_data_handler: InitDataHandler):
        """Load demand pattern tape file"""
        import msgpack
        import orjson as json

        from movici_simulation_core.core.data_format import load_from_json
        from movici_simulation_core.core.moment import get_timeline_info
        from movici_simulation_core.model_connector.init_data import FileType

        ftype, tapefile_path = init_data_handler.get(tape_name)
        if tapefile_path is None:
            raise ValueError(f"Tape file {tape_name} not found!")

        if ftype == FileType.JSON:
            tapefile = json.loads(tapefile_path.read_bytes())
        elif ftype == FileType.MSGPACK:
            tapefile = msgpack.unpackb(tapefile_path.read_bytes())
        else:
            raise TypeError(f"Invalid data type for tape file '{tape_name}': {ftype.name}")

        # Process tape file
        data_section = tapefile["data"]
        dataset_name = data_section["tabular_data_name"]
        timeline_info = get_timeline_info()

        schema = AttributeSchema()  # Empty schema for pattern data

        for seconds, json_data in zip(
            data_section["time_series"], data_section["data_series"]
        ):
            timestamp = timeline_info.seconds_to_timestamp(seconds)
            numpy_data = load_from_json({dataset_name: json_data}, schema)
            self.pattern_timeline.append((timestamp, numpy_data))

        self.pattern_timeline.sort()

    def _add_control_from_config(self, control_spec: dict):
        """Add a control rule from configuration"""
        control_type = control_spec.get("type", "time")
        control_name = control_spec.get("name", f"control_{id(control_spec)}")

        if control_type == "time":
            self.network.control_manager.add_time_control(
                control_name=control_name,
                target_element=control_spec["target"],
                target_attribute=control_spec.get("attribute", "status"),
                value=control_spec["value"],
                time=control_spec["time"],
                time_type=control_spec.get("time_type", "sim_time"),
            )
        elif control_type == "conditional":
            self.network.control_manager.add_conditional_control(
                control_name=control_name,
                target_element=control_spec["target"],
                target_attribute=control_spec.get("attribute", "status"),
                value=control_spec["value"],
                source_element=control_spec["source"],
                source_attribute=control_spec["source_attribute"],
                operator=control_spec["operator"],
                threshold=control_spec["threshold"],
            )

    def initialize(self, state: TrackedState):
        """Initialize model and run first simulation"""

        if self.mode == "movici_network":
            # Build network from Movici datasets
            self._build_network_from_state(state)

        # Apply pending control rules now that network is built
        for rule in self.pending_control_rules:
            self._add_control_from_config(rule)

        # Run initial simulation
        duration = self.config.get("simulation_duration")
        hydraulic_timestep = self.config.get("hydraulic_timestep", 3600)
        report_timestep = self.config.get("report_timestep")

        results = self.network.run_simulation(
            duration=duration,
            hydraulic_timestep=hydraulic_timestep,
            report_timestep=report_timestep,
        )

        # Publish initial results
        self._publish_results(state, results)

    def _build_network_from_state(self, state: TrackedState):
        """Build WNTR network from Movici entity state"""

        # Add junctions
        if self.junctions and len(self.junctions) > 0:
            junction_coll = get_junctions(self.junctions, self.network.id_mapper)
            self.network.add_junctions(junction_coll)

        # Add tanks
        if self.tanks and len(self.tanks) > 0:
            tank_coll = get_tanks(self.tanks, self.network.id_mapper)
            self.network.add_tanks(tank_coll)

        # Add reservoirs
        if self.reservoirs and len(self.reservoirs) > 0:
            reservoir_coll = get_reservoirs(self.reservoirs, self.network.id_mapper)
            self.network.add_reservoirs(reservoir_coll)

        # Add pipes
        if self.pipes and len(self.pipes) > 0:
            pipe_coll = get_pipes(self.pipes, self.network.id_mapper)
            self.network.add_pipes(pipe_coll)

        # Add pumps
        if self.pumps and len(self.pumps) > 0:
            pump_coll = get_pumps(self.pumps, self.network.id_mapper)
            self.network.add_pumps(pump_coll)

        # Add valves
        if self.valves and len(self.valves) > 0:
            valve_coll = get_valves(self.valves, self.network.id_mapper)
            self.network.add_valves(valve_coll)

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """Update simulation at each timestep"""

        # Update patterns from tape file
        if self.pattern_timeline:
            for _, pattern_data in self.pattern_timeline.pop_until(moment.timestamp):
                self._apply_pattern_data(pattern_data)

        # Update dynamic attributes (valve status, pump speed, etc.)
        if self.mode == "movici_network":
            self._update_dynamic_attributes(state)

        # Run simulation
        hydraulic_timestep = self.config.get("hydraulic_timestep", 3600)
        results = self.network.run_simulation(
            duration=hydraulic_timestep,  # Simulate one timestep
            hydraulic_timestep=hydraulic_timestep,
        )

        # Publish results
        self._publish_results(state, results)

        # Return next update time
        if self.pattern_timeline:
            return self.pattern_timeline.next_time
        return None

    def _apply_pattern_data(self, pattern_data: dict):
        """Apply demand multipliers from tape file data"""
        # pattern_data is in format: {dataset_name: {entity_group: {id: [...], attr: [...]}}}
        for dataset_name, dataset in pattern_data.items():
            for entity_group_name, entity_data in dataset.items():
                if "id" not in entity_data:
                    continue

                entity_ids = entity_data["id"]

                # Handle demand multipliers for junctions
                if "demand_multiplier" in entity_data and self.junctions:
                    multipliers = entity_data["demand_multiplier"]
                    junction_names = [
                        self.network.id_mapper.get_wntr_name(int(eid)) for eid in entity_ids
                    ]
                    # Apply multipliers by updating base demands
                    for name, mult in zip(junction_names, multipliers):
                        junction = self.network.wn.get_node(name)
                        # WNTR patterns are usually applied automatically
                        # For direct control, we could modify base_demand
                        if hasattr(junction, "base_demand"):
                            # Store original if not stored
                            if not hasattr(junction, "_original_demand"):
                                junction._original_demand = junction.base_demand
                            junction.base_demand = junction._original_demand * float(mult)

    def _update_dynamic_attributes(self, state: TrackedState):
        """Update dynamic network attributes from state changes"""

        # Update pipe statuses
        if self.pipes and self.pipes.status.has_data():
            if np.any(self.pipes.status.changed):
                movici_ids = self.pipes.index.ids
                link_names = [
                    self.network.id_mapper.get_wntr_name(int(mid)) for mid in movici_ids
                ]
                statuses = self.pipes.status.array
                self.network.update_link_status(link_names, statuses)

        # Update valve statuses
        if self.valves and self.valves.status.has_data():
            if np.any(self.valves.status.changed):
                movici_ids = self.valves.index.ids
                link_names = [
                    self.network.id_mapper.get_wntr_name(int(mid)) for mid in movici_ids
                ]
                statuses = self.valves.status.array
                self.network.update_link_status(link_names, statuses)

        # Update pump statuses and speeds
        if self.pumps:
            if self.pumps.status.has_data() and np.any(self.pumps.status.changed):
                movici_ids = self.pumps.index.ids
                link_names = [
                    self.network.id_mapper.get_wntr_name(int(mid)) for mid in movici_ids
                ]
                statuses = self.pumps.status.array
                self.network.update_link_status(link_names, statuses)

    def _publish_results(self, state: TrackedState, results):
        """Publish simulation results to state"""

        # Map WNTR node names back to Movici IDs
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
            deficits = []

            for i, (name, movici_id) in enumerate(node_id_map.items()):
                if self.network.id_mapper.get_entity_type(name) == "junction":
                    idx = self.junctions.index[movici_id]
                    if idx >= 0:
                        junction_indices.append(idx)
                        node_idx = results.node_names.index(name)
                        pressures.append(results.node_pressures[node_idx])
                        heads.append(results.node_heads[node_idx])
                        demands.append(results.node_demands[node_idx])
                        if results.node_demand_deficits is not None:
                            deficits.append(results.node_demand_deficits[node_idx])

            if junction_indices:
                self.junctions.pressure.array[junction_indices] = np.array(pressures)
                self.junctions.head.array[junction_indices] = np.array(heads)
                self.junctions.actual_demand.array[junction_indices] = np.array(demands)
                if deficits and self.junctions.demand_deficit.has_data():
                    self.junctions.demand_deficit.array[junction_indices] = np.array(deficits)

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
            powers = []

            for name, movici_id in link_id_map.items():
                if self.network.id_mapper.get_entity_type(name) == "pump":
                    idx = self.pumps.index[movici_id]
                    if idx >= 0:
                        pump_indices.append(idx)
                        link_idx = results.link_names.index(name)
                        flows.append(results.link_flows[link_idx])
                        if results.link_powers is not None:
                            powers.append(results.link_powers[link_idx])

            if pump_indices:
                self.pumps.flow.array[pump_indices] = np.array(flows)
                if powers and self.pumps.pump_power.has_data():
                    self.pumps.pump_power.array[pump_indices] = np.array(powers)

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
        """Clean up resources"""
        if self.network:
            self.network.close()
