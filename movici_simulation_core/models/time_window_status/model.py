import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import OPT, PUB
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.settings import Settings
from movici_simulation_core.validate import ensure_valid_config

from .dataset import TimeWindowEntity, TimeWindowStatusEntity
from .time_window_status import TimeWindowStatus


class Model(TrackedModel, name="time_window_status"):
    """Set boolean status attributes based on time windows.

    This model activates/deactivates target entities based on time windows
    defined in source entities. Time windows are specified using begin and
    end timestamp attributes (ISO 8601 formatted strings).

    When the simulation time enters a time window, the target status becomes
    ``True``. When the time exits, the status becomes ``False``.

    :param model_config: Configuration dictionary with the following keys:

        - ``source``: ``[dataset_name, entity_group_name]`` for source entities
        - ``time_window_begin``: Attribute name for window start time
        - ``time_window_end``: Attribute name for window end time
        - ``targets``: List of target configurations, each with:

          - ``entity_group``: ``[dataset_name, entity_group_name]``
          - ``attribute``: Boolean attribute to set on target entities

    :param time_window_status: The time window status calculator
    :param source_entity_group: Source entity group with time window definitions
    :param target_entity_groups: List of target entity groups
    """

    time_window_status: TimeWindowStatus
    source_entity_group: TimeWindowEntity
    target_entity_groups: t.List[TimeWindowStatusEntity]

    def __init__(self, model_config):
        model_config = ensure_valid_config(
            model_config,
            "2",
            {
                "1": {"schema": MODEL_CONFIG_SCHEMA_LEGACY_PATH},
                "2": {"schema": MODEL_CONFIG_SCHEMA_PATH, "convert_from": {"1": convert_v1_v2}},
            },
        )
        super().__init__(model_config)

    def setup(self, state: TrackedState, schema: AttributeSchema, settings: Settings, **_):
        source_dataset, source_entity_name = self.config["source"]
        source_entity_group = state.register_entity_group(
            source_dataset, TimeWindowEntity(source_entity_name)
        )
        source_entity_group.time_window_begin = state.register_attribute(
            source_dataset,
            source_entity_name,
            schema.get_spec(self.config["time_window_begin"], DataType(str)),
            flags=OPT,
        )
        source_entity_group.time_window_end = state.register_attribute(
            source_dataset,
            source_entity_name,
            schema.get_spec(self.config["time_window_end"], DataType(str)),
            flags=OPT,
        )
        targets = []
        for target in self.config["targets"]:
            target_dataset, target_entity_name = target["entity_group"]
            attr = target["attribute"]
            target_entity_group = state.register_entity_group(
                target_dataset, TimeWindowStatusEntity(target_entity_name)
            )
            target_entity_group.time_window_status = state.register_attribute(
                target_dataset,
                target_entity_name,
                schema.get_spec(attr, DataType(bool)),
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


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/time_window_status.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/time_window_status.json"


def convert_v1_v2(config):
    return {
        "source": config["time_window_dataset"][0],
        "time_window_begin": config["time_window_begin"][1],
        "time_window_end": config["time_window_end"][1],
        "targets": [
            {"entity_group": eg, "attribute": config["time_window_status"][1]}
            for eg in config["status_datasets"]
        ],
    }
