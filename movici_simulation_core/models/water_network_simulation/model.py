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
from movici_simulation_core.core.schema import AttributeSchema, attributes_from_dict
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

from . import attributes
from .dataset import (
    WaterJunctionEntity,
    WaterPipeEntity,
    WaterPumpEntity,
    WaterReservoirEntity,
    WaterTankEntity,
    WaterValveEntity,
)

# Mapping of entity group names to their classes
_ENTITY_CLASSES = {
    "junctions": WaterJunctionEntity,
    "pipes": WaterPipeEntity,
    "reservoirs": WaterReservoirEntity,
    "tanks": WaterTankEntity,
    "pumps": WaterPumpEntity,
    "valves": WaterValveEntity,
}

# Mapping for building network from state
_ENTITY_CONVERTERS = [
    ("junctions", get_junctions, "add_junctions"),
    ("tanks", get_tanks, "add_tanks"),
    ("reservoirs", get_reservoirs, "add_reservoirs"),
    ("pipes", get_pipes, "add_pipes"),
    ("pumps", get_pumps, "add_pumps"),
    ("valves", get_valves, "add_valves"),
]


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
        return attributes_from_dict(vars(attributes))

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

        for name in entity_groups:
            if name in _ENTITY_CLASSES:
                entity = _ENTITY_CLASSES[name]()
                setattr(self, name, entity)
                state.register_entity_group(dataset_name, entity)

    def _register_output_entities_from_inp(self, state: TrackedState):
        """Register entity groups from INP file network data.

        :param state: Tracked state for entity registration
        """
        dataset_name = self.config.get("dataset", "water_network")
        wn = self.network.wn

        # Map entity names to WNTR name list attributes
        name_list_attrs = {
            "junctions": "junction_name_list",
            "pipes": "pipe_name_list",
            "reservoirs": "reservoir_name_list",
            "tanks": "tank_name_list",
            "pumps": "pump_name_list",
            "valves": "valve_name_list",
        }

        for name, name_list_attr in name_list_attrs.items():
            if getattr(wn, name_list_attr):
                entity = _ENTITY_CLASSES[name]()
                setattr(self, name, entity)
                state.register_entity_group(dataset_name, entity)

        # Build entity data from WNTR network
        entity_data = self._extract_entities_from_wntr()
        state.receive_update({dataset_name: entity_data}, is_initial=True)

    def _register_id(self, name: str, movici_id: int, entity_type: str):
        """Register a single ID mapping."""
        self.network.id_mapper.wntr_to_movici[name] = movici_id
        self.network.id_mapper.movici_to_wntr[movici_id] = name
        self.network.id_mapper.entity_types[name] = entity_type

    def _extract_node_entities(
        self,
        wn,
        names: t.List[str],
        entity_type: str,
        entity_key: str,
        id_offset: int,
        property_extractors: t.Dict[str, t.Callable],
    ) -> t.Tuple[dict, int]:
        """Extract node entities with given property extractors.

        :param wn: WNTR network
        :param names: List of node names
        :param entity_type: Type name for ID registration
        :param entity_key: Key for entity data dict
        :param id_offset: Starting ID offset
        :param property_extractors: Dict mapping attr name to extractor function
        :return: Tuple of (entity_data dict or empty, new id_offset)
        """
        if not names:
            return {}, id_offset

        ids, x_coords, y_coords = [], [], []
        prop_values = {key: [] for key in property_extractors}

        for i, name in enumerate(names):
            node = wn.get_node(name)
            movici_id = id_offset + i
            self._register_id(name, movici_id, entity_type)

            ids.append(movici_id)
            x, y = node.coordinates if node.coordinates else (0.0, 0.0)
            x_coords.append(x)
            y_coords.append(y)

            for key, extractor in property_extractors.items():
                prop_values[key].append(extractor(node))

        entity_data = {
            "id": {"data": np.array(ids, dtype=np.int32)},
            "geometry.x": {"data": np.array(x_coords, dtype=np.float64)},
            "geometry.y": {"data": np.array(y_coords, dtype=np.float64)},
        }
        for key, values in prop_values.items():
            dtype = np.float64 if isinstance(values[0], (int, float)) else None
            entity_data[key] = {"data": np.array(values, dtype=dtype)}

        return {entity_key: entity_data}, id_offset + len(names)

    def _extract_link_entities(
        self,
        wn,
        names: t.List[str],
        entity_type: str,
        entity_key: str,
        id_offset: int,
        property_extractors: t.Dict[str, t.Callable],
    ) -> t.Tuple[dict, int]:
        """Extract link entities with given property extractors.

        :param wn: WNTR network
        :param names: List of link names
        :param entity_type: Type name for ID registration
        :param entity_key: Key for entity data dict
        :param id_offset: Starting ID offset
        :param property_extractors: Dict mapping attr name to extractor function
        :return: Tuple of (entity_data dict or empty, new id_offset)
        """
        if not names:
            return {}, id_offset

        ids, from_node_ids, to_node_ids = [], [], []
        prop_values = {key: [] for key in property_extractors}

        for i, name in enumerate(names):
            link = wn.get_link(name)
            movici_id = id_offset + i
            self._register_id(name, movici_id, entity_type)

            ids.append(movici_id)
            from_node_ids.append(self.network.id_mapper.wntr_to_movici[link.start_node_name])
            to_node_ids.append(self.network.id_mapper.wntr_to_movici[link.end_node_name])

            for key, extractor in property_extractors.items():
                prop_values[key].append(extractor(link))

        entity_data = {
            "id": {"data": np.array(ids, dtype=np.int32)},
            "topology.from_node_id": {"data": np.array(from_node_ids, dtype=np.int32)},
            "topology.to_node_id": {"data": np.array(to_node_ids, dtype=np.int32)},
        }
        for key, values in prop_values.items():
            if values and isinstance(values[0], str):
                entity_data[key] = {"data": values}
            else:
                entity_data[key] = {"data": np.array(values, dtype=np.float64)}

        return {entity_key: entity_data}, id_offset + len(names)

    def _extract_entities_from_wntr(self) -> dict:
        """Extract entity data from WNTR network in Movici format.

        :return: Dictionary of entity data for state initialization
        """
        wn = self.network.wn
        entity_data = {}
        id_offset = 1

        # Node extraction specs: (name_list_attr, entity_type, entity_key, property_extractors)
        node_specs = [
            (
                "junction_name_list",
                "junction",
                "water_junction_entities",
                {
                    "geometry.z": lambda n: n.elevation,
                    "drinking_water.base_demand": lambda n: n.base_demand,
                },
            ),
            (
                "reservoir_name_list",
                "reservoir",
                "water_reservoir_entities",
                {"drinking_water.base_head": lambda n: n.base_head},
            ),
            (
                "tank_name_list",
                "tank",
                "water_tank_entities",
                {
                    "geometry.z": lambda n: n.elevation,
                    "drinking_water.level": lambda n: n.init_level,
                    "drinking_water.min_level": lambda n: n.min_level,
                    "drinking_water.max_level": lambda n: n.max_level,
                    "shape.diameter": lambda n: n.diameter,
                },
            ),
        ]

        for name_list_attr, entity_type, entity_key, extractors in node_specs:
            names = list(getattr(wn, name_list_attr))
            data, id_offset = self._extract_node_entities(
                wn, names, entity_type, entity_key, id_offset, extractors
            )
            entity_data.update(data)

        # Link extraction specs
        link_specs = [
            (
                "pipe_name_list",
                "pipe",
                "water_pipe_entities",
                {
                    "shape.diameter": lambda lnk: lnk.diameter,
                    "drinking_water.roughness": lambda lnk: lnk.roughness,
                    "drinking_water.minor_loss": lambda lnk: lnk.minor_loss,
                },
            ),
            (
                "pump_name_list",
                "pump",
                "water_pump_entities",
                {"type": lambda lnk: str(lnk.pump_type).lower()},
            ),
            (
                "valve_name_list",
                "valve",
                "water_valve_entities",
                {
                    "type": lambda lnk: lnk.valve_type,
                    "shape.diameter": lambda lnk: lnk.diameter,
                },
            ),
        ]

        for name_list_attr, entity_type, entity_key, extractors in link_specs:
            names = list(getattr(wn, name_list_attr))
            data, id_offset = self._extract_link_entities(
                wn, names, entity_type, entity_key, id_offset, extractors
            )
            entity_data.update(data)

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
        for attr_name, converter, adder in _ENTITY_CONVERTERS:
            entity = getattr(self, attr_name)
            if entity and len(entity) > 0:
                collection = converter(entity, self.network.id_mapper)
                getattr(self.network, adder)(collection)

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
        for entity in [self.pipes, self.pumps]:
            if entity and entity.status.has_data() and np.any(entity.status.changed):
                link_names = [
                    self.network.id_mapper.get_wntr_name(int(mid)) for mid in entity.index.ids
                ]
                self.network.update_link_status(link_names, entity.status.array)

    def _publish_node_results(
        self,
        entity_group,
        entity_type: str,
        id_map: t.Dict[str, int],
        results,
        name_to_idx: t.Dict[str, int],
        attr_mappings: t.Dict[str, str],
    ):
        """Publish node results for an entity group.

        :param entity_group: Entity group to publish to
        :param entity_type: Entity type to filter by
        :param id_map: Map of WNTR name to Movici ID
        :param results: Simulation results
        :param name_to_idx: Pre-computed name to index map
        :param attr_mappings: Dict mapping entity attr to results attr
        """
        if not entity_group:
            return

        indices = []
        values = {attr: [] for attr in attr_mappings}

        for name, movici_id in id_map.items():
            if self.network.id_mapper.get_entity_type(name) != entity_type:
                continue
            idx = entity_group.index[movici_id]
            if idx < 0:
                continue

            indices.append(idx)
            result_idx = name_to_idx[name]
            for attr, result_attr in attr_mappings.items():
                values[attr].append(getattr(results, result_attr)[result_idx])

        if indices:
            for attr, vals in values.items():
                getattr(entity_group, attr).array[indices] = np.array(vals)

    def _publish_link_results(
        self,
        entity_group,
        entity_type: str,
        id_map: t.Dict[str, int],
        results,
        name_to_idx: t.Dict[str, int],
        extra_attrs: t.Optional[t.Dict[str, str]] = None,
    ):
        """Publish link results for an entity group.

        :param entity_group: Entity group to publish to
        :param entity_type: Entity type to filter by
        :param id_map: Map of WNTR name to Movici ID
        :param results: Simulation results
        :param name_to_idx: Pre-computed name to index map
        :param extra_attrs: Additional attrs beyond flow (e.g., velocity, headloss)
        """
        if not entity_group:
            return

        indices = []
        flows = []
        extra_values = {attr: [] for attr in (extra_attrs or {})}

        for name, movici_id in id_map.items():
            if self.network.id_mapper.get_entity_type(name) != entity_type:
                continue
            idx = entity_group.index[movici_id]
            if idx < 0:
                continue

            indices.append(idx)
            result_idx = name_to_idx[name]
            flows.append(results.link_flows[result_idx])
            for attr, result_attr in (extra_attrs or {}).items():
                extra_values[attr].append(getattr(results, result_attr)[result_idx])

        if indices:
            flows_array = np.array(flows)
            entity_group.flow.array[indices] = flows_array
            entity_group.flow_rate_magnitude.array[indices] = np.abs(flows_array)
            for attr, vals in extra_values.items():
                getattr(entity_group, attr).array[indices] = np.array(vals)

    def _publish_results(self, state: TrackedState, results):
        """Publish simulation results to state.

        :param state: Tracked state
        :param results: SimulationResults from WNTR
        """
        # Pre-compute name to index maps for O(1) lookup
        node_name_to_idx = {name: i for i, name in enumerate(results.node_names)}
        link_name_to_idx = {name: i for i, name in enumerate(results.link_names)}

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

        # Publish node results
        self._publish_node_results(
            self.junctions,
            "junction",
            node_id_map,
            results,
            node_name_to_idx,
            {"pressure": "node_pressures", "head": "node_heads", "demand": "node_demands"},
        )
        self._publish_node_results(
            self.tanks,
            "tank",
            node_id_map,
            results,
            node_name_to_idx,
            {
                "pressure": "node_pressures",
                "head": "node_heads",
                "demand": "node_demands",
                "level": "node_levels",
            },
        )

        # Reservoirs need special handling for flow calculation
        if self.reservoirs:
            self._publish_node_results(
                self.reservoirs,
                "reservoir",
                node_id_map,
                results,
                node_name_to_idx,
                {"head": "node_heads", "demand": "node_demands"},
            )
            # Calculate flow from demand (flow = -demand, outflow is positive)
            indices = []
            demands = []
            for name, movici_id in node_id_map.items():
                if self.network.id_mapper.get_entity_type(name) != "reservoir":
                    continue
                idx = self.reservoirs.index[movici_id]
                if idx >= 0:
                    indices.append(idx)
                    demands.append(results.node_demands[node_name_to_idx[name]])
            if indices:
                demands_array = np.array(demands)
                self.reservoirs.flow.array[indices] = -demands_array
                self.reservoirs.flow_rate_magnitude.array[indices] = np.abs(demands_array)

        # Publish link results
        self._publish_link_results(
            self.pipes,
            "pipe",
            link_id_map,
            results,
            link_name_to_idx,
            {"velocity": "link_velocities", "headloss": "link_headlosses"},
        )
        self._publish_link_results(self.pumps, "pump", link_id_map, results, link_name_to_idx)
        self._publish_link_results(self.valves, "valve", link_id_map, results, link_name_to_idx)

    def shutdown(self, state: TrackedState):
        """Clean up resources.

        :param state: Tracked state
        """
        if self.network:
            self.network.close()
