"""Water network simulation model using WNTR.

This model simulates drinking water distribution networks using the WNTR
(Water Network Tool for Resilience) library. It supports hydraulic simulation
including pressure, flow, and velocity calculations.

.. note::
   Controls (time-based or conditional) are NOT handled internally by this model.
   Use the Movici Rules Model to implement control logic externally.
"""

from __future__ import annotations

import dataclasses
import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, attributes_from_dict
from movici_simulation_core.core.state import TrackedState

from . import attributes
from .dataset import (
    DrinkingWaterNetwork,
    WaterJunctionEntity,
    WaterPipeEntity,
    WaterPumpEntity,
    WaterReservoirEntity,
    WaterTankEntity,
    WaterValveEntity,
)
from .network_wrapper import NetworkWrapper


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


class Model(TrackedModel, name="drinking_water"):
    """Water network simulation model using WNTRSimulator.

    This model simulates water distribution networks including:

    - Hydraulic simulation (pressure, flow, velocity)
    - Support for pipes, pumps, valves, tanks, and reservoirs
    - CSR curve data for pump head curves and tank volume curves

    .. note::
       Controls are handled by the Movici Rules Model, not internally.
    """

    @classmethod
    def get_schema_attributes(cls):
        """Return all AttributeSpecs used by this model.

        :return: Sequence of AttributeSpec objects
        """
        return attributes_from_dict(vars(attributes))

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.network = NetworkWrapper()
        self.last_calculated: Moment | None = None
        self.dataset: DrinkingWaterNetwork | None = None
        self.dataset_name: t.Optional[str] = None

        options = self.config.get("options", {})
        self.hydraulic_timestep: int = options.get("hydraulic_timestep", 3600)
        self.report_timestep: t.Optional[int] = options.get("report_timestep")

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
        self.dataset_name = self.config.get("dataset")
        if not self.dataset_name:
            raise ValueError("dataset required in model config")

        self._register_dataset(state, self.dataset_name)

    def _register_dataset(self, state: TrackedState, dataset_name: str):
        """Register entity groups.

        Entity groups are registered as optional so that empty groups
        don't block initialization.

        :param state: Tracked state for entity registration
        :param dataset_name: Name of the dataset to register entities in
        """
        self.dataset = DrinkingWaterNetwork(
            junctions=state.register_entity_group(
                dataset_name, WaterJunctionEntity(optional=True)
            ),
            tanks=state.register_entity_group(dataset_name, WaterTankEntity(optional=True)),
            reservoirs=state.register_entity_group(
                dataset_name, WaterReservoirEntity(optional=True)
            ),
            pipes=state.register_entity_group(dataset_name, WaterPipeEntity(optional=True)),
            pumps=state.register_entity_group(dataset_name, WaterPumpEntity(optional=True)),
            valves=state.register_entity_group(dataset_name, WaterValveEntity(optional=True)),
        )

    def _ensure_pub_attributes_initialized(self):
        """Ensure all PUB attributes have their arrays allocated.

        PUB-only attributes (like link_status, flow_rate_magnitude) may not
        receive data during init loading. They must be initialized before the
        framework checks their ``.changed`` property during ``generate_update``.
        """
        from movici_simulation_core.core.attribute import PUBLISH

        for f in dataclasses.fields(self.dataset):
            entity = getattr(self.dataset, f.name)
            size = len(entity)
            for attr_name in entity.all_attributes():
                attr = getattr(entity, attr_name)
                if attr.flags & PUBLISH and not attr.has_data():
                    attr.initialize(size)

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
        """Initialize model: validate network and configure WNTR.

        :param state: Tracked state
        """
        if self.dataset is None:
            raise RuntimeError("Model.setup() must be called before model.initialize()")

        for f in dataclasses.fields(self.dataset):
            getattr(self.dataset, f.name).is_ready()

        self._ensure_pub_attributes_initialized()
        self.network.initialize(self.dataset)
        self.network.configure_options(self._get_options(state))

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """Update simulation at each timestep.

        :param state: Tracked state
        :param moment: Current simulation moment
        :return: Next update time or None
        """
        # We're a stateful, time-dependent model. That means that we should
        # update in the following way:
        # - First calculate until the current time
        # - Then process any changes to the data
        # - If we are updated multiple times in the same timestep, we only
        #   calculate once
        # The reason for this is that the world state is valid, until something
        # changes it. If we we have lastly calculated at t=x, and we now get a
        # an update (cq. change) at t=x+1, then we must first calculate with the
        # state from t=x, and then apply the changes. We then don't progress the
        # model until we're asked to update to t>x+1
        if self.last_calculated is None or self.last_calculated < moment:
            if self.last_calculated is not None:
                self.network.process_changes()

            results = self.network.run_simulation(
                duration=self.hydraulic_timestep,
                hydraulic_timestep=self.hydraulic_timestep,
                report_timestep=self.report_timestep,
            )
            self.network.write_results(results)
            self.last_calculated = moment

        return None

    def shutdown(self, state: TrackedState):
        """Clean up resources.

        :param state: Tracked state
        """
        if self.network:
            self.network.close()
