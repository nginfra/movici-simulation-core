"""Power grid calculation model.

This model performs electrical network analysis using the power-grid-model library.
It supports power flow, state estimation, and short circuit calculations.
"""

from __future__ import annotations

import logging
import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core import TrackedState
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.integrations.pgm.network_wrapper import (
    CalculationMethod,
    CalculationType,
    PowerGridWrapper,
)
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.models.common import pgm_util
from movici_simulation_core.settings import Settings
from movici_simulation_core.validate import ensure_valid_config

from . import dataset as ds

MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/power_grid_calculation.json"


class Model(TrackedModel, name="power_grid_calculation"):
    """Power grid calculation model using power-grid-model library.

    This model performs electrical network calculations including:

    * Power flow analysis
    * State estimation (with sensor measurements)
    * Short circuit analysis

    The model subscribes to dynamic load/generation values and publishes
    calculated voltages, currents, and power flows.
    """

    def __init__(self, model_config: dict):
        model_config = ensure_valid_config(
            model_config,
            "1",
            {"1": {"schema": MODEL_CONFIG_SCHEMA_PATH}},
        )
        super().__init__(model_config)
        self.wrapper: t.Optional[PowerGridWrapper] = None
        self.logger: t.Optional[logging.Logger] = None

        # Entity groups (initialized in setup)
        self.nodes: t.Optional[ds.ElectricalNodeEntity] = None
        self.lines: t.Optional[ds.ElectricalLineEntity] = None
        self.transformers: t.Optional[ds.ElectricalTransformerEntity] = None
        self.loads: t.Optional[ds.ElectricalLoadEntity] = None
        self.generators: t.Optional[ds.ElectricalGeneratorEntity] = None
        self.sources: t.Optional[ds.ElectricalSourceEntity] = None
        self.shunts: t.Optional[ds.ElectricalShuntEntity] = None
        self.voltage_sensors: t.Optional[ds.ElectricalVoltageSensorEntity] = None
        self.power_sensors: t.Optional[ds.ElectricalPowerSensorEntity] = None
        self.faults: t.Optional[ds.ElectricalFaultEntity] = None

    def setup(
        self,
        state: TrackedState,
        settings: Settings,
        logger: logging.Logger,
        **_,
    ):
        """Set up the model by registering entity groups.

        :param state: TrackedState for entity registration.
        :param settings: Global simulation settings.
        :param logger: Logger instance.
        """
        self.logger = logger
        dataset_name = self.config["dataset"]
        calc_type = self._get_calculation_type()

        # Register required entity groups
        self.nodes = state.register_entity_group(
            dataset_name,
            ds.ElectricalNodeEntity(name="electrical_node_entities"),
        )
        self.sources = state.register_entity_group(
            dataset_name,
            ds.ElectricalSourceEntity(name="electrical_source_entities"),
        )

        # Register optional entity groups
        self.lines = state.register_entity_group(
            dataset_name,
            ds.ElectricalLineEntity(name="electrical_line_entities"),
        )
        self.transformers = state.register_entity_group(
            dataset_name,
            ds.ElectricalTransformerEntity(name="electrical_transformer_entities"),
        )
        self.loads = state.register_entity_group(
            dataset_name,
            ds.ElectricalLoadEntity(name="electrical_load_entities"),
        )
        self.generators = state.register_entity_group(
            dataset_name,
            ds.ElectricalGeneratorEntity(name="electrical_generator_entities"),
        )
        self.shunts = state.register_entity_group(
            dataset_name,
            ds.ElectricalShuntEntity(name="electrical_shunt_entities"),
        )

        # Register sensor entity groups for state estimation
        if calc_type == CalculationType.STATE_ESTIMATION:
            self.voltage_sensors = state.register_entity_group(
                dataset_name,
                ds.ElectricalVoltageSensorEntity(name="electrical_voltage_sensor_entities"),
            )
            self.power_sensors = state.register_entity_group(
                dataset_name,
                ds.ElectricalPowerSensorEntity(name="electrical_power_sensor_entities"),
            )

        # Register fault entity group for short circuit
        if calc_type == CalculationType.SHORT_CIRCUIT:
            self.faults = state.register_entity_group(
                dataset_name,
                ds.ElectricalFaultEntity(name="electrical_fault_entities"),
            )

        # Create the wrapper
        self.wrapper = PowerGridWrapper()

    def initialize(self, state: TrackedState):
        """Initialize the model by building the network.

        :param state: TrackedState with loaded entity data.
        """
        # Ensure required entities are ready
        self.nodes.ensure_ready()

        # Build the network
        self._build_network()
        self.logger.info(f"Power grid network built with {len(self.nodes)} nodes")

    def _build_network(self):
        """Build the power grid model from entity data."""
        nodes = pgm_util.get_nodes(self.nodes)

        lines = None
        if self._has_entities(self.lines):
            lines = pgm_util.get_lines(self.lines)

        transformers = None
        if self._has_entities(self.transformers):
            transformers = pgm_util.get_transformers(self.transformers)

        loads = None
        if self._has_entities(self.loads):
            loads = pgm_util.get_loads(self.loads)

        generators = None
        if self._has_entities(self.generators):
            generators = pgm_util.get_generators(self.generators)

        sources = None
        if self._has_entities(self.sources):
            sources = pgm_util.get_sources(self.sources)

        shunts = None
        if self._has_entities(self.shunts):
            shunts = pgm_util.get_shunts(self.shunts)

        # Sensors for state estimation
        voltage_sensors = None
        if self._has_entities(self.voltage_sensors):
            voltage_sensors = pgm_util.get_voltage_sensors(self.voltage_sensors)

        power_sensors = None
        if self._has_entities(self.power_sensors):
            power_sensors = pgm_util.get_power_sensors(self.power_sensors)

        # Faults for short circuit
        faults = None
        if self._has_entities(self.faults):
            faults = pgm_util.get_faults(self.faults)

        self.wrapper.build_network(
            nodes=nodes,
            lines=lines,
            transformers=transformers,
            loads=loads,
            generators=generators,
            sources=sources,
            shunts=shunts,
            voltage_sensors=voltage_sensors,
            power_sensors=power_sensors,
            faults=faults,
        )

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """Perform calculation and publish results.

        :param state: TrackedState with current entity data.
        :param moment: Current simulation moment.
        :returns: None (no next time scheduling).
        """
        # Check for dynamic load updates
        if self._has_load_changes():
            loads = pgm_util.get_loads(self.loads)
            self.wrapper.update_loads(loads)

        # Check for dynamic generator updates
        if self._has_generator_changes():
            generators = pgm_util.get_generators(self.generators)
            self.wrapper.update_generators(generators)

        # Run calculation based on type
        calc_type = self._get_calculation_type()

        if calc_type == CalculationType.POWER_FLOW:
            result = self._run_power_flow()
        elif calc_type == CalculationType.STATE_ESTIMATION:
            result = self._run_state_estimation()
        elif calc_type == CalculationType.SHORT_CIRCUIT:
            result = self._run_short_circuit()
            # Short circuit has different result structure
            return None

        # Publish results
        self._publish_node_results(result)
        self._publish_line_results(result)
        self._publish_transformer_results(result)

        return None

    def _run_power_flow(self):
        """Run power flow calculation.

        :returns: PowerFlowResult.
        """
        method = self._get_calculation_method()
        symmetric = self.config.get("symmetric", True)
        return self.wrapper.calculate_power_flow(method=method, symmetric=symmetric)

    def _run_state_estimation(self):
        """Run state estimation calculation.

        Sensors must be defined in the dataset and are provided during network build.

        :returns: PowerFlowResult (estimated state).
        """
        symmetric = self.config.get("symmetric", True)
        return self.wrapper.calculate_state_estimation(symmetric=symmetric)

    def _run_short_circuit(self):
        """Run short circuit calculation.

        Faults must be defined in the dataset and are provided during network build.

        :returns: ShortCircuitResult.
        """
        return self.wrapper.calculate_short_circuit()

    def _publish_node_results(self, result):
        """Publish node results to entity group.

        :param result: PowerFlowResult with node data.
        """
        node_result = result.nodes
        # Result IDs are already Movici IDs, use entity index to get array indices
        indices = self.nodes.get_indices(node_result.ids)

        self.nodes.voltage_pu[indices] = node_result.u_pu
        self.nodes.voltage_angle[indices] = node_result.u_angle
        self.nodes.voltage[indices] = node_result.u
        self.nodes.active_power[indices] = node_result.p
        self.nodes.reactive_power[indices] = node_result.q

    def _publish_line_results(self, result):
        """Publish line results to entity group.

        :param result: PowerFlowResult with line data.
        """
        if result.lines is None or self.lines is None:
            return

        line_result = result.lines
        # Result IDs are already Movici IDs, use entity index to get array indices
        indices = self.lines.get_indices(line_result.ids)

        self.lines.current_from[indices] = line_result.i_from
        self.lines.current_to[indices] = line_result.i_to
        self.lines.power_from[indices] = line_result.p_from
        self.lines.power_to[indices] = line_result.p_to
        self.lines.reactive_power_from[indices] = line_result.q_from
        self.lines.reactive_power_to[indices] = line_result.q_to
        self.lines.loading[indices] = line_result.loading

    def _publish_transformer_results(self, result):
        """Publish transformer results to entity group.

        :param result: PowerFlowResult with transformer data.
        """
        if result.transformers is None or self.transformers is None:
            return

        trafo_result = result.transformers
        # Result IDs are already Movici IDs, use entity index to get array indices
        indices = self.transformers.get_indices(trafo_result.ids)

        self.transformers.current_from[indices] = trafo_result.i_from
        self.transformers.current_to[indices] = trafo_result.i_to
        self.transformers.power_from[indices] = trafo_result.p_from
        self.transformers.power_to[indices] = trafo_result.p_to
        self.transformers.loading[indices] = trafo_result.loading

    def _has_load_changes(self) -> bool:
        """Check if load values have changed.

        :returns: True if loads have changed.
        """
        if self.loads is None:
            return False
        return self.loads.p_specified.has_changes() or self.loads.q_specified.has_changes()

    def _has_generator_changes(self) -> bool:
        """Check if generator values have changed.

        :returns: True if generators have changed.
        """
        if self.generators is None:
            return False
        return (
            self.generators.p_specified.has_changes() or self.generators.q_specified.has_changes()
        )

    def _has_entities(self, entity_group) -> bool:
        """Check if an entity group has any entities.

        :param entity_group: Entity group to check.
        :returns: True if entity group exists and has entities.
        """
        if entity_group is None:
            return False
        try:
            return len(entity_group) > 0
        except Exception:
            return False

    def _get_calculation_type(self) -> CalculationType:
        """Get calculation type from config.

        :returns: CalculationType enum value.
        """
        type_str = self.config.get("calculation_type", "power_flow")
        type_map = {
            "power_flow": CalculationType.POWER_FLOW,
            "state_estimation": CalculationType.STATE_ESTIMATION,
            "short_circuit": CalculationType.SHORT_CIRCUIT,
        }
        return type_map.get(type_str, CalculationType.POWER_FLOW)

    def _get_calculation_method(self) -> CalculationMethod:
        """Get calculation method from config.

        :returns: CalculationMethod enum value.
        """
        method_str = self.config.get("algorithm", "newton_raphson")
        method_map = {
            "newton_raphson": CalculationMethod.NEWTON_RAPHSON,
            "linear": CalculationMethod.LINEAR,
            "linear_current": CalculationMethod.LINEAR_CURRENT,
            "iterative_current": CalculationMethod.ITERATIVE_CURRENT,
        }
        return method_map.get(method_str, CalculationMethod.NEWTON_RAPHSON)

    def shutdown(self, state: TrackedState):
        """Clean up resources.

        :param state: TrackedState (unused).
        """
        if self.wrapper is not None:
            self.wrapper.close()
            self.wrapper = None
