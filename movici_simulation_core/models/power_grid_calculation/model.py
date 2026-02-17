"""Power grid calculation model.

This model performs electrical network analysis using the power-grid-model library.
It supports power flow, state estimation, and short circuit calculations.
"""

from __future__ import annotations

import dataclasses
import logging
import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUBLISH, SUBSCRIBE
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.integrations.pgm.network_wrapper import (
    CalculationMethod,
    CalculationType,
    PowerGridWrapper,
)
from movici_simulation_core.json_schemas import SCHEMA_PATH

from . import dataset as ds
from .dataset import PowerGridNetwork

MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/power_grid_calculation.json"

_CALC_TYPE_MAP = {
    "power_flow": CalculationType.POWER_FLOW,
    "state_estimation": CalculationType.STATE_ESTIMATION,
    "short_circuit": CalculationType.SHORT_CIRCUIT,
}

_CALC_METHOD_MAP = {
    "newton_raphson": CalculationMethod.NEWTON_RAPHSON,
    "linear": CalculationMethod.LINEAR,
    "linear_current": CalculationMethod.LINEAR_CURRENT,
    "iterative_current": CalculationMethod.ITERATIVE_CURRENT,
}


class Model(TrackedModel, name="power_grid_calculation"):
    """Power grid calculation model using power-grid-model library.

    This model performs electrical network calculations including:

    * Power flow analysis
    * State estimation (with sensor measurements)
    * Short circuit analysis

    The model subscribes to dynamic load/generation values and publishes
    calculated voltages, currents, and power flows.
    """

    __model_config_schema__ = MODEL_CONFIG_SCHEMA_PATH
    auto_reset = PUBLISH

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.wrapper: t.Optional[PowerGridWrapper] = None
        self.dataset: t.Optional[PowerGridNetwork] = None
        self.logger: t.Optional[logging.Logger] = None

        # Cache config-derived values
        self.calc_type = _CALC_TYPE_MAP.get(
            self.config.get("calculation_type", "power_flow"),
            CalculationType.POWER_FLOW,
        )
        self.calc_method = _CALC_METHOD_MAP.get(
            self.config.get("algorithm", "newton_raphson"),
            CalculationMethod.NEWTON_RAPHSON,
        )
        self.symmetric = self.config.get("symmetric", True)

    def setup(self, state: TrackedState, logger: logging.Logger, **_):
        self.logger = logger
        name = self.config["dataset"]

        self.dataset = PowerGridNetwork(
            nodes=state.register_entity_group(
                name, ds.ElectricalNodeEntity(name="electrical_node_entities")
            ),
            virtual_nodes=state.register_entity_group(
                name,
                ds.ElectricalVirtualNodeEntity(
                    name="electrical_virtual_node_entities", optional=True
                ),
            ),
            lines=state.register_entity_group(
                name, ds.ElectricalLineEntity(name="electrical_line_entities", optional=True)
            ),
            cables=state.register_entity_group(
                name, ds.ElectricalCableEntity(name="electrical_cable_entities", optional=True)
            ),
            links=state.register_entity_group(
                name, ds.ElectricalLinkEntity(name="electrical_link_entities", optional=True)
            ),
            transformers=state.register_entity_group(
                name,
                ds.ElectricalTransformerEntity(
                    name="electrical_transformer_entities", optional=True
                ),
            ),
            three_winding_transformers=state.register_entity_group(
                name,
                ds.ElectricalThreeWindingTransformerEntity(
                    name="electrical_three_winding_transformer_entities", optional=True
                ),
            ),
            loads=state.register_entity_group(
                name, ds.ElectricalLoadEntity(name="electrical_load_entities", optional=True)
            ),
            generators=state.register_entity_group(
                name,
                ds.ElectricalGeneratorEntity(name="electrical_generator_entities", optional=True),
            ),
            sources=state.register_entity_group(
                name, ds.ElectricalSourceEntity(name="electrical_source_entities", optional=True)
            ),
            shunts=state.register_entity_group(
                name, ds.ElectricalShuntEntity(name="electrical_shunt_entities", optional=True)
            ),
            voltage_sensors=state.register_entity_group(
                name,
                ds.ElectricalVoltageSensorEntity(
                    name="electrical_voltage_sensor_entities", optional=True
                ),
            ),
            power_sensors=state.register_entity_group(
                name,
                ds.ElectricalPowerSensorEntity(
                    name="electrical_power_sensor_entities", optional=True
                ),
            ),
            current_sensors=state.register_entity_group(
                name,
                ds.ElectricalCurrentSensorEntity(
                    name="electrical_current_sensor_entities", optional=True
                ),
            ),
            faults=state.register_entity_group(
                name, ds.ElectricalFaultEntity(name="electrical_fault_entities", optional=True)
            ),
            tap_regulators=state.register_entity_group(
                name,
                ds.ElectricalTapRegulatorEntity(
                    name="electrical_tap_regulator_entities", optional=True
                ),
            ),
        )
        self.wrapper = PowerGridWrapper()

    def initialize(self, state: TrackedState):
        self._ensure_pub_attributes_initialized()
        self.wrapper.initialize(self.dataset)
        self.logger.info(f"Power grid network built with {len(self.dataset.nodes)} nodes")

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        # Run calculation with current (old) state
        result = self._calculate()

        # Apply incoming changes for next calculation
        self.wrapper.process_changes()

        # Reset SUBSCRIBE changes after process_changes consumed them
        state.reset_tracked_changes(SUBSCRIBE)

        # Publish results
        self.wrapper.write_results(result)
        return None

    def _calculate(self) -> dict:
        if self.calc_type == CalculationType.POWER_FLOW:
            return self.wrapper.calculate_power_flow(
                method=self.calc_method, symmetric=self.symmetric
            )
        elif self.calc_type == CalculationType.STATE_ESTIMATION:
            return self.wrapper.calculate_state_estimation(symmetric=self.symmetric)
        else:
            return self.wrapper.calculate_short_circuit()

    def _ensure_pub_attributes_initialized(self):
        """Ensure all PUB attributes have their arrays allocated.

        PUB-only attributes may not receive data during init loading.
        They must be initialized before the framework checks their
        ``.changed`` property during ``generate_update``.
        """
        for f in dataclasses.fields(self.dataset):
            entity = getattr(self.dataset, f.name)
            size = len(entity)
            for attr_field in entity.all_attributes().values():
                attr = attr_field.get_for(entity)
                if attr.flags & PUBLISH and not attr.has_data():
                    attr.initialize(size)

    def shutdown(self, state: TrackedState):
        if self.wrapper is not None:
            self.wrapper.close()
            self.wrapper = None
