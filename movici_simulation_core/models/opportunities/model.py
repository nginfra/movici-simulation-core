import typing as t

import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core import DataType
from movici_simulation_core.core.attribute import OPT, PUB, UniformAttribute
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, AttributeSpec, attributes_from_dict
from movici_simulation_core.core.state import TrackedState

from . import dataset
from .dataset import LineEntity, OverlapEntity


class Model(TrackedModel, name="opportunity"):
    """
    Implementation of the opportunities model
    Takes in a line entity and a overlap status dataset
    If input attribute A is on at the same time as the overlap is active,
    the opportunity was taken.
    If only the overlap was active, the opportunity was missed.
    """

    overlap_entity: t.Optional[OverlapEntity]
    opportunity_entity: t.Optional[LineEntity]
    opportunity_taken_attribute: t.Optional[UniformAttribute]
    total_length_attribute: t.Optional[UniformAttribute]
    cost_per_meter: t.Optional[float]

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.overlap_entity = None
        self.opportunity_entity = None
        self.opportunity_taken_attribute = None
        self.cost_per_meter = None

    def setup(self, state: TrackedState, schema: AttributeSchema, **_):
        self.parse_config(state, schema)

    def initialize(self, state: TrackedState):
        self.opportunity_entity.opportunity[:] = 0
        self.opportunity_entity.missed_opportunity[:] = 0
        self.total_length_attribute[:] = 0

    def update(self, state: TrackedState, moment: Moment):
        self.update_opportunities()

    def parse_config(self, state: TrackedState, schema: AttributeSchema) -> None:
        config = self.config
        self.overlap_entity = state.register_entity_group(
            config["overlap_dataset"][0], OverlapEntity()
        )
        dataset_name, entity_name = config["opportunity_entity"][0]
        self.opportunity_entity = state.register_entity_group(
            dataset_name=dataset_name, entity=LineEntity(name=entity_name)
        )
        attr = config["opportunity_taken_property"][0]
        self.opportunity_taken_attribute = state.register_attribute(
            dataset_name=dataset_name,
            entity_name=entity_name,
            spec=schema.get_spec(attr, default_data_type=DataType(bool)),
            flags=OPT,
        )
        attr = config["total_length_property"][0]
        self.total_length_attribute = state.register_attribute(
            dataset_name=dataset_name,
            entity_name=entity_name,
            spec=schema.get_spec(attr, default_data_type=DataType(float)),
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

        # missed = once opportunity & never self.opportunity_taken_attribute
        # can be temporarily set, will be unset as overlap actives come in
        self.opportunity_entity.missed_opportunity[active] = 0

        defined = ~self.opportunity_taken_attribute.is_undefined()
        taken = defined & self.opportunity_taken_attribute.array > 0
        self.opportunity_entity.missed_opportunity[active] = (
            self.opportunity_entity.length[active] * self.cost_per_meter
        )
        self.opportunity_entity.missed_opportunity[taken & active] = 0

        self.total_length_attribute[taken] = self.opportunity_entity.length[taken]

    @classmethod
    def get_schema_attributes(cls) -> t.Iterable[AttributeSpec]:
        return attributes_from_dict(vars(dataset))
