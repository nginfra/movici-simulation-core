import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.data_tracker.property import PUB, OPT
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.utils.moment import Moment
from movici_simulation_core.utils.settings import Settings
from .dataset import TimeWindowEntity, TimeWindowStatusEntity
from .time_window_status import TimeWindowStatus


class Model(TrackedModel, name="time_window_status"):
    """
    Implementation of the time window status model
    """

    time_window_status: TimeWindowStatus
    source_entity_group: TimeWindowEntity
    target_entity_groups: t.List[TimeWindowStatusEntity]

    def setup(self, state: TrackedState, schema: AttributeSchema, settings: Settings, **_):
        source_dataset, source_entity_name = self.config["time_window_dataset"][0]
        source_entity_group = state.register_entity_group(
            source_dataset, TimeWindowEntity(source_entity_name)
        )
        source_entity_group.time_window_begin = state.register_property(
            source_dataset,
            source_entity_name,
            schema.get_spec(self.config["time_window_begin"], DataType(str)),
            flags=OPT,
        )
        source_entity_group.time_window_end = state.register_property(
            source_dataset,
            source_entity_name,
            schema.get_spec(self.config["time_window_end"], DataType(str)),
            flags=OPT,
        )
        targets = []
        for target_dataset, target_entity_name in self.config["status_datasets"]:
            target_entity_group = state.register_entity_group(
                target_dataset, TimeWindowStatusEntity(target_entity_name)
            )
            target_entity_group.time_window_status = state.register_property(
                target_dataset,
                target_entity_name,
                schema.get_spec(self.config["time_window_status"], DataType(bool)),
                flags=PUB,
            )
            targets.append(target_entity_group)

        self.time_window_status = TimeWindowStatus(
            source_entity_group, targets, settings.timeline_info
        )

    def initialize(self, state: TrackedState):
        if not self.time_window_status.can_initialize():
            raise NotReady()
        self.time_window_status.initialize()

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        return self.time_window_status.update(moment)
