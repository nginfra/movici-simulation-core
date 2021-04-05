import typing as t

import numpy as np
from model_engine import TimeStamp
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.base_model.config_helpers import property_mapping
from movici_simulation_core.data_tracker.property import UniformProperty, SUB, PUB
from movici_simulation_core.data_tracker.state import TrackedState

from .dataset import OverlapEntity, LineEntity


class Model(TrackedBaseModel):
    """
    Implementation of the opportunities model
    Takes in a line entity and a overlap status dataset
    If input property A is on at the same time as the overlap is active,
    the opportunity was taken.
    If only the overlap was active, the opportunity was missed.
    """

    overlap_entity: t.Optional[OverlapEntity]
    opportunity_entity: t.Optional[LineEntity]
    opportunity_taken_property: t.Optional[UniformProperty]
    total_length_property: t.Optional[UniformProperty]
    cost_per_meter: t.Optional[float]

    def __init__(self):
        self.overlap_entity = None
        self.opportunity_entity = None
        self.opportunity_taken_property = None
        self.cost_per_meter = None

    def setup(self, state: TrackedState, config: dict, **_):
        self.parse_config(state, config)

    def initialize(self, state: TrackedState):
        self.opportunity_entity.opportunity[:] = 0
        self.opportunity_entity.missed_opportunity[:] = 0
        self.total_length_property[:] = 0

    def update(self, state: TrackedState, time_stamp: TimeStamp):
        self.update_opportunities()

    def parse_config(
        self,
        state: TrackedState,
        config: dict,
    ) -> None:
        self.overlap_entity = state.register_entity_group(
            config["overlap_dataset"][0], OverlapEntity()
        )
        dataset_name, entity_name = config["opportunity_entity"][0]
        self.opportunity_entity = state.register_entity_group(
            dataset_name=dataset_name, entity=LineEntity(name=entity_name)
        )
        prop = config["opportunity_taken_property"][0]
        self.opportunity_taken_property = state.register_property(
            dataset_name=dataset_name,
            entity_name=entity_name,
            spec=property_mapping[tuple(prop)],
            flags=SUB,
        )
        prop = config["total_length_property"][0]
        self.total_length_property = state.register_property(
            dataset_name=dataset_name,
            entity_name=entity_name,
            spec=property_mapping[tuple(prop)],
            flags=PUB,
        )
        self.cost_per_meter = config["cost_per_meter"]

    def update_opportunities(self):
        changed = self.overlap_entity.overlap_active.changed
        changed_active = changed & (self.overlap_entity.overlap_active.array == 1)
        to_ids_active = self.overlap_entity.connection_to_id[
            changed_active
            & (
                self.overlap_entity.connection_to_dataset.array
                == self.opportunity_entity.state.dataset_name
            )
        ]
        to_index_active = self.overlap_entity.index[to_ids_active]
        to_boolean_active = np.zeros(len(self.opportunity_entity), dtype=bool)
        to_boolean_active[to_index_active] = 1
        from_ids_active = self.overlap_entity.connection_from_id[
            changed_active
            & (
                self.overlap_entity.connection_from_dataset.array
                == self.opportunity_entity.state.dataset_name
            )
        ]
        from_index_active = self.overlap_entity.index[from_ids_active]
        from_boolean_active = np.zeros(len(self.opportunity_entity), dtype=bool)
        from_boolean_active[from_index_active] = 1
        active = from_boolean_active | to_boolean_active
        self.opportunity_entity.opportunity[active] = (
            self.opportunity_entity.length[active] * self.cost_per_meter
        )

        # missed = once opportunity & never self.opportunity_taken_property
        # can be temporarily set, will be unset as overlap actives come in
        self.opportunity_entity.missed_opportunity[active] = 0
        taken = self.opportunity_taken_property.array > 0
        self.opportunity_entity.missed_opportunity[active] = (
            self.opportunity_entity.length[active] * self.cost_per_meter
        )
        self.opportunity_entity.missed_opportunity[taken & active] = 0

        self.total_length_property[taken] = self.opportunity_entity.length[taken]
