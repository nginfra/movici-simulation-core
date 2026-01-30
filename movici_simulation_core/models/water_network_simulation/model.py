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

import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, attributes_from_dict
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.integrations.wntr import NetworkWrapper
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


def _deep_merge(a: dict, b: dict) -> dict:
    """Deep-merge two dicts. Values in *b* take precedence.

    :param a: Base dictionary
    :param b: Override dictionary
    :return: New merged dictionary
    """
    result = dict(a)
    for key, value in b.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Model(TrackedModel, name="water_network_simulation"):
    """Water network simulation model using WNTRSimulator.

    This model simulates water distribution networks including:

    - Hydraulic simulation (pressure, flow, velocity)
    - Support for pipes, pumps, valves, tanks, and reservoirs
    - CSR curve data for pump head curves and tank volume curves

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
        self.dataset_name: t.Optional[str] = None

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
        **kwargs,
    ):
        """Setup the model and initialize network.

        :param state: Tracked state for entity registration
        :param schema: Attribute schema
        """
        self.network = NetworkWrapper()

        self.dataset_name = self.config.get("dataset")
        if not self.dataset_name:
            raise ValueError("dataset required in model config")

        self._register_entities(state, self.dataset_name)

    def _register_entities(self, state: TrackedState, dataset_name: str):
        """Register entity groups.

        :param state: Tracked state for entity registration
        :param dataset_name: Name of the dataset to register entities in
        """
        entity_groups = self.config.get("entity_groups", ["junctions", "pipes", "reservoirs"])

        for name in entity_groups:
            if name in _ENTITY_CLASSES:
                entity = _ENTITY_CLASSES[name]()
                setattr(self, name, entity)
                state.register_entity_group(dataset_name, entity)

    def _get_options(self, state: TrackedState) -> dict:
        """Get WNTR options from model config and dataset general section.

        Solver-tuning options (trials, accuracy, etc.) come from the model
        config ``"options"`` key.  Physical/data options (headloss, viscosity,
        etc.) come from the dataset's general section.  Both contribute
        disjoint keys to the same WNTR options structure.

        :param state: Tracked state
        :return: Dict of section_name -> {key: value} mappings
        """
        config_options = dict(self.config.get("options", {}))
        dataset_options = dict(state.general.get(self.dataset_name, {}))
        return _deep_merge(config_options, dataset_options)

    def initialize(self, state: TrackedState):
        """Initialize model and run first simulation.

        :param state: Tracked state
        """
        self._build_network_from_state(state)
        self.network.configure_options(self._get_options(state))

        # Run initial simulation
        duration = self.config.get("simulation_duration")
        hydraulic_timestep = self.config.get("hydraulic_timestep", 3600)
        report_timestep = self.config.get("report_timestep")

        results = self.network.run_simulation(
            duration=duration,
            hydraulic_timestep=hydraulic_timestep,
            report_timestep=report_timestep,
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
        self._update_dynamic_attributes(state)

        # Run simulation
        hydraulic_timestep = self.config.get("hydraulic_timestep", 3600)
        results = self.network.run_simulation(
            duration=hydraulic_timestep,
            hydraulic_timestep=hydraulic_timestep,
        )

        self._publish_results(state, results)
        return None

    def _update_dynamic_attributes(self, state: TrackedState):
        """Update dynamic network attributes from state changes.

        Called when the Rules Model or Tape Player may have modified entity
        attributes.  Handles link statuses, junction demand factors, and
        reservoir head factors.

        :param state: Tracked state
        """
        for entity in [self.pipes, self.pumps]:
            if entity and entity.status.has_data() and np.any(entity.status.changed):
                link_names = [
                    self.network.id_mapper.get_wntr_name(int(mid)) for mid in entity.index.ids
                ]
                self.network.update_link_status(link_names, entity.status.array)

        # Update junction demands when demand_factor changes
        if (
            self.junctions
            and self.junctions.demand_factor.has_data()
            and np.any(self.junctions.demand_factor.changed)
        ):
            junction_names = [
                self.network.id_mapper.get_wntr_name(int(mid)) for mid in self.junctions.index.ids
            ]
            self.network.update_junction_demands(
                junction_names,
                self.junctions.base_demand.array,
                self.junctions.demand_factor.array,
            )

        # Update reservoir heads when head_factor changes
        if (
            self.reservoirs
            and self.reservoirs.head_factor.has_data()
            and np.any(self.reservoirs.head_factor.changed)
        ):
            reservoir_names = [
                self.network.id_mapper.get_wntr_name(int(mid)) for mid in self.reservoirs.index.ids
            ]
            self.network.update_reservoir_heads(
                reservoir_names,
                self.reservoirs.base_head.array,
                self.reservoirs.head_factor.array,
            )

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
