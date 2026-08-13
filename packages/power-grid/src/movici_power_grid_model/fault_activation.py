"""Fault activation model: turn hazard exposure into active electrical faults.

This model monitors a scalar attribute on the node entity group of an
electrical network (by default ``flooding.water_depth``, as published by the
``operational_status`` model) and activates the fault entity attached to a
node once the monitored value exceeds a threshold, by publishing
``electrical.status = 1`` on ``electrical_fault_entities``.

Activation is latching: a short circuit persists until repaired, so a fault
stays active even if the monitored value later drops below the threshold.

The model is hazard-agnostic: any model that publishes a per-node scalar
(flood depth, earthquake intensity, ...) can drive it.
"""

from __future__ import annotations

import logging
import pathlib
import typing as t

import numpy as np

from movici_simulation_core.attributes import Connection_ToId
from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import INIT, PUB, PUBLISH, SUB, SUBSCRIBE, field
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState

from .attributes import Electrical_Status

_PACKAGE_DIR = pathlib.Path(__file__).parent

DEFAULT_MONITOR_ENTITY_GROUP = "electrical_node_entities"
DEFAULT_MONITOR_ATTRIBUTE = "flooding.water_depth"


class ActivatableFaultEntity(EntityGroup):
    """Fault locations whose status is switched on by this model."""

    __entity_name__ = "electrical_fault_entities"

    fault_object_id = field(Connection_ToId, flags=INIT)
    status = field(Electrical_Status, flags=PUB)


class Model(TrackedModel, name="power_grid_fault_activation"):
    """Activate electrical faults when a monitored node attribute crosses a
    threshold.

    Configuration:

    .. code-block:: json

        {
            "name": "flood_faults",
            "type": "power_grid_fault_activation",
            "dataset": "power_grid_the_hague",
            "monitor_attribute": "flooding.water_depth",
            "threshold": 0.3
        }
    """

    __model_config_schema__ = _PACKAGE_DIR / "power_grid_fault_activation.json"
    auto_reset = PUBLISH

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.threshold = self.config["threshold"]
        self.nodes: t.Optional[EntityGroup] = None
        self.monitored = None
        self.faults: t.Optional[ActivatableFaultEntity] = None
        self.node_indices: t.Optional[np.ndarray] = None
        self.latched: t.Optional[np.ndarray] = None
        self.logger: t.Optional[logging.Logger] = None

    @classmethod
    def get_schema_attributes(cls):
        return [Electrical_Status]

    def setup(self, state: TrackedState, schema: AttributeSchema, logger: logging.Logger, **_):
        self.logger = logger
        dataset = self.config["dataset"]
        eg_name = self.config.get("monitor_entity_group", DEFAULT_MONITOR_ENTITY_GROUP)
        attr_name = self.config.get("monitor_attribute", DEFAULT_MONITOR_ATTRIBUTE)

        self.nodes = state.register_entity_group(dataset, EntityGroup(eg_name))
        self.monitored = self.nodes.register_attribute(
            schema.get_spec(attr_name, default_data_type=DataType(float)), flags=SUB
        )
        self.faults = state.register_entity_group(
            dataset, ActivatableFaultEntity(name="electrical_fault_entities")
        )

    def initialize(self, state: TrackedState):
        self.node_indices = self.nodes.get_indices(self.faults.fault_object_id.array)
        self.latched = np.zeros(len(self.faults), dtype=bool)
        if not self.faults.status.has_data():
            self.faults.status.initialize(len(self.faults))

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        exposure = self.monitored.array[self.node_indices]
        state.reset_tracked_changes(SUBSCRIBE)

        newly = (exposure > self.threshold) & ~self.latched
        if np.any(newly):
            indices = np.flatnonzero(newly)
            self.faults.status[indices] = 1
            self.latched |= newly
            self.logger.info(
                f"t={moment.timestamp}: activated {len(indices)} fault(s) at nodes "
                f"{self.faults.fault_object_id.array[indices].tolist()}"
            )
        return None
