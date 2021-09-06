import typing as t

from model_engine import TimeStamp
from movici_simulation_core.legacy_base_model.base import LegacyTrackedBaseModel
from movici_simulation_core.legacy_base_model.config_helpers import property_mapping
from movici_simulation_core.data_tracker.property import PropertySpec, SUB
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from .dataset import OverlapEntity
from .overlap_status import OverlapStatus
from ..common.model_util import try_get_geometry_type


class Model(LegacyTrackedBaseModel):
    """
    Implementation of the overlap status model
    """

    overlap_status: t.Union[OverlapStatus, None] = None

    def setup(self, state: TrackedState, config: dict, **_):
        self.check_input_lengths(config)
        self.parse_config(state, config)

    @staticmethod
    def check_input_lengths(config):
        keys = [
            "to_entity_groups",
            "to_geometry_types",
        ]
        if "to_check_status_properties" in config:
            keys.append("to_check_status_properties")
        if any(len(config[key]) != len(config[keys[0]]) for key in keys[1:]):
            raise IndexError(f"Arrays {[key for key in keys]} must have the same lengths")

    def initialize(self, state: TrackedState) -> None:
        if not self.overlap_status.is_ready():
            raise NotReady
        self.overlap_status.resolve_connections()

    def update(self, state: TrackedState, time_stamp: TimeStamp):
        self.overlap_status.update()

    def parse_config(
        self,
        state: TrackedState,
        config: dict,
    ) -> None:

        overlap_entity = state.register_entity_group(config["output_dataset"][0], OverlapEntity())
        to_entities = []
        to_check_properties = []
        for (ds_name, entity_name), prop, geometry in zip(
            config["to_entity_groups"],
            config.get("to_check_status_properties", [None] * len(config["to_entity_groups"])),
            config["to_geometry_types"],
        ):
            to_entities.append(
                state.register_entity_group(
                    dataset_name=ds_name, entity=try_get_geometry_type(geometry)(name=entity_name)
                )
            )
            if prop is None or prop == (None, None):
                to_check_properties.append(None)
            else:
                to_spec = property_mapping[tuple(prop)]
                self.ensure_uniform_property(ds_name, entity_name, to_spec)
                to_check_properties.append(
                    state.register_property(
                        dataset_name=ds_name, entity_name=entity_name, spec=to_spec, flags=SUB
                    )
                )

        from_ds_name, from_entity_name = config["from_entity_group"][0]
        from_geometry = try_get_geometry_type(config["from_geometry_type"])
        from_prop = config.get("from_check_status_property")
        from_entity = state.register_entity_group(
            dataset_name=from_ds_name, entity=from_geometry(name=from_entity_name)
        )
        if from_prop is None:
            from_check_property = None
        else:
            from_spec = property_mapping[tuple(from_prop)]
            self.ensure_uniform_property(from_ds_name, from_entity_name, from_spec)
            from_check_property = state.register_property(
                dataset_name=from_ds_name, entity_name=from_entity_name, spec=from_spec, flags=SUB
            )

        self.overlap_status = OverlapStatus(
            from_entity=from_entity,
            from_check_property=from_check_property,
            to_entities=to_entities,
            to_check_properties=to_check_properties,
            overlap_entity=overlap_entity,
            distance_threshold=config.get("distance_threshold"),
            display_name_template=config.get("display_name_template"),
        )

    @staticmethod
    def ensure_uniform_property(ds, entity, spec: PropertySpec):
        if spec.data_type.py_type == str:
            raise ValueError(f"Property {ds}/{entity}/{spec.full_name} can't have string type")
        if spec.data_type.csr is True:
            raise ValueError(
                f"property {ds}/{entity}/{spec.full_name} should be of uniform data type"
            )
        if len(spec.data_type.unit_shape):
            raise ValueError(f"property {ds}/{entity}/{spec.full_name} should be one-dimensional")
